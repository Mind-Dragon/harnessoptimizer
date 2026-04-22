#!/usr/bin/env python3
"""Provider canary runner for the local brain scaffold.

Reads `brain/evals/provider-canaries.json`, resolves `${ENV_VAR}` placeholders,
optionally performs live HTTP probes with stdlib urllib, and prints JSON results.

Examples:
  python3 provider_probe.py --config ../evals/provider-canaries.json --list
  python3 provider_probe.py --config ../evals/provider-canaries.json --provider kimi-coding --dry-run
  python3 provider_probe.py --config ../evals/provider-canaries.json --provider minimax-chat --timeout 20
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")

DEFAULT_AUTH_PATH = Path.home() / ".hermes" / "auth.json"

# Auth JSON cache (lazily loaded, cleared between runs in tests)
_auth_json_cache: dict[str, Any] | None = None


def _load_auth_json(path: Path | None = None) -> dict[str, Any]:
    """Load auth.json from path, or DEFAULT_AUTH_PATH if not specified."""
    global _auth_json_cache
    if path is None:
        path = DEFAULT_AUTH_PATH
    cache_key = str(path)

    # Return cached if exists and file hasn't changed
    if _auth_json_cache is not None and _auth_json_cache.get("_cache_key") == cache_key:
        cached_path = Path(_auth_json_cache.get("_cache_path", ""))
        if cached_path.exists() and cached_path.stat().st_mtime == _auth_json_cache.get("_cache_mtime"):
            return _auth_json_cache

    try:
        data = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        data = {}

    # Store cache metadata
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0
    data["_cache_key"] = cache_key
    data["_cache_path"] = str(path)
    data["_cache_mtime"] = mtime
    _auth_json_cache = data
    return data


def _find_credential_by_label(label: str, auth_data: dict[str, Any]) -> str | None:
    """Find credential in credential_pool by label, return access_token or None.

    Selects the credential with the lowest priority value.
    Does not log or return secret values.
    """
    credential_pool = auth_data.get("credential_pool", {})
    matching_credentials: list[tuple[int, str]] = []

    for provider_credentials in credential_pool.values():
        if not isinstance(provider_credentials, list):
            continue
        for cred in provider_credentials:
            if not isinstance(cred, dict):
                continue
            if cred.get("label") == label:
                priority = cred.get("priority", 0)
                access_token = cred.get("access_token", "")
                # Don't use masked tokens (***)
                if access_token and access_token != "***":
                    matching_credentials.append((priority, access_token))

    if not matching_credentials:
        return None

    # Sort by priority (lower first) and return the token
    matching_credentials.sort(key=lambda x: x[0])
    return matching_credentials[0][1]


def clear_auth_cache() -> None:
    """Clear the auth JSON cache. Used for testing."""
    global _auth_json_cache
    _auth_json_cache = None


def load_config(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise ValueError("config must be a list")
    return data


def resolve_env(value: Any, missing: list[str], auth_path: Path | None = None) -> Any:
    """Resolve ${ENV_VAR} placeholders.

    Priority:
    1. Environment variable (if set)
    2. ~/.hermes/auth.json credential_pool (fallback)
    3. Leave placeholder unchanged and add to missing list
    """
    if isinstance(value, str):
        def repl(match: re.Match[str]) -> str:
            key = match.group(1)
            env = os.getenv(key)
            if env is not None:
                return env
            # Fallback: try auth.json
            auth_data = _load_auth_json(auth_path)
            token = _find_credential_by_label(key, auth_data)
            if token is not None:
                return token
            # Still missing
            missing.append(key)
            return match.group(0)
        return ENV_PATTERN.sub(repl, value)
    if isinstance(value, dict):
        return {k: resolve_env(v, missing, auth_path) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_env(v, missing, auth_path) for v in value]
    return value


def run_probe(
    entry: dict[str, Any], timeout: int, dry_run: bool, auth_path: Path | None = None
) -> dict[str, Any]:
    missing: list[str] = []
    resolved = resolve_env(entry, missing, auth_path)
    result: dict[str, Any] = {
        "name": resolved.get("name"),
        "url": resolved.get("url"),
        "missing_env": sorted(set(missing)),
        "dry_run": dry_run,
    }
    if dry_run:
        result["status"] = "dry_run"
        return result
    if missing:
        result["status"] = "skipped_missing_env"
        return result

    body = json.dumps(resolved.get("body", {})).encode("utf-8")
    req = urllib.request.Request(
        resolved["url"],
        data=body,
        method=resolved.get("method", "POST"),
        headers=resolved.get("headers", {}),
    )
    start = time.time()
    raw_text = ""
    status = None
    error = None
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.getcode()
            raw_text = resp.read(4096).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw_text = exc.read(4096).decode("utf-8", errors="replace")
        error = f"HTTPError: {exc}"
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"

    elapsed_ms = round((time.time() - start) * 1000, 1)
    result.update({
        "http_status": status,
        "elapsed_ms": elapsed_ms,
        "body_preview": raw_text[:500],
        "transport_error": error,
    })

    expect = resolved.get("expect", {})
    allowed_statuses = set(expect.get("allowed_statuses", []))
    forbid_statuses = set(expect.get("forbid_statuses", []))
    forbid_body = expect.get("forbid_body_substrings", [])
    violations: list[str] = []

    if status is None and error:
        violations.append("no_http_status")
    if allowed_statuses and status not in allowed_statuses:
        violations.append(f"status_not_allowed:{status}")
    if status in forbid_statuses:
        violations.append(f"status_forbidden:{status}")
    lower_body = raw_text.lower()
    for token in forbid_body:
        if token.lower() in lower_body:
            violations.append(f"forbidden_body:{token}")

    result["violations"] = violations
    result["status"] = "pass" if not violations and not error else ("fail" if violations else "transport_error")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="../evals/provider-canaries.json")
    parser.add_argument("--provider", help="probe one provider name")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--output", help="optional path to write JSON result")
    parser.add_argument(
        "--auth-json",
        help="path to auth.json (default: ~/.hermes/auth.json, or HERMES_AUTH_JSON_PATH env var)",
    )
    args = parser.parse_args()

    # Determine auth path: CLI arg > HERMES_AUTH_JSON_PATH env > default
    if args.auth_json:
        auth_path = Path(args.auth_json).resolve()
    elif os.getenv("HERMES_AUTH_JSON_PATH"):
        auth_path = Path(os.getenv("HERMES_AUTH_JSON_PATH", "")).resolve()
        if not auth_path.exists():
            auth_path = None
    else:
        auth_path = DEFAULT_AUTH_PATH if DEFAULT_AUTH_PATH.exists() else None

    config_path = Path(args.config).resolve()
    entries = load_config(config_path)
    if args.provider:
        entries = [e for e in entries if e.get("name") == args.provider]
        if not entries:
            print(json.dumps({"error": f"provider not found: {args.provider}"}, indent=2))
            return 2

    if args.list:
        print(json.dumps([e.get("name") for e in entries], indent=2))
        return 0

    results = [
        run_probe(entry, timeout=args.timeout, dry_run=args.dry_run, auth_path=auth_path)
        for entry in entries
    ]
    text = json.dumps(results, indent=2)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n")
    print(text)
    return 0 if all(r.get("status") in {"pass", "dry_run", "skipped_missing_env"} for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
