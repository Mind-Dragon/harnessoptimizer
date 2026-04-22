#!/usr/bin/env python3
"""Brain doctor — orchestrate rail, digest, and probe checks into one report.

Single command to run all deterministic checks with optional dry-run mode.
All checks must work in dry-run without external credentials.
Provider probing inherits provider_probe.py behavior, which resolves API keys from
environment variables first and `~/.hermes/auth.json` second.

Examples:
  python3 brain_doctor.py --dry-run
  python3 brain_doctor.py --check rail_loader --check request_dump
  python3 brain_doctor.py --output brain/reports/doctor-summary.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Check runners — each calls the underlying script and returns parsed JSON
# ---------------------------------------------------------------------------

def run_rail_check(dry_run: bool = False) -> dict[str, Any]:
    """Run rail_loader_check.py and return parsed JSON report."""
    cmd = [
        "python3",
        str(Path(__file__).parent / "rail_loader_check.py"),
        "--dry-run" if dry_run else "",
    ]
    cmd = [c for c in cmd if c]
    try:
        cp = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Find the outermost JSON object/array in stdout
        text = cp.stdout.strip()
        # Try to find a balanced JSON starting point
        for start_idx in range(len(text)):
            if text[start_idx] in ("{", "["):
                try:
                    return json.loads(text[start_idx:])
                except json.JSONDecodeError:
                    continue
        return {
            "check": "rail_loader",
            "error": "no JSON output",
            "stdout": cp.stdout[:500],
            "stderr": cp.stderr[:500],
        }
    except Exception as exc:
        return {
            "check": "rail_loader",
            "error": str(exc),
        }


def run_request_digest(dry_run: bool = False, limit: int = 50) -> dict[str, Any]:
    """Run request_dump_digest.py and return parsed JSON report."""
    cmd = [
        "python3",
        str(Path(__file__).parent / "request_dump_digest.py"),
        "--limit", str(limit),
    ]
    # Note: request_dump_digest.py does not have --dry-run; it scans local
    # session files which is safe and deterministic. We still pass it for
    # future compatibility.
    try:
        cp = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        text = cp.stdout.strip()
        for start_idx in range(len(text)):
            if text[start_idx] in ("{", "["):
                try:
                    result = json.loads(text[start_idx:])
                    result["check"] = "request_dump"
                    result["limit"] = limit
                    result["dry_run"] = dry_run
                    return result
                except json.JSONDecodeError:
                    continue
        return {
            "check": "request_dump",
            "error": "no JSON output",
            "stdout": cp.stdout[:500],
            "stderr": cp.stderr[:500],
        }
    except Exception as exc:
        return {
            "check": "request_dump",
            "error": str(exc),
        }


def run_provider_probe(
    dry_run: bool = False,
    list_only: bool = False,
    provider: str | None = None,
) -> dict[str, Any]:
    """Run provider_probe.py and return parsed JSON report."""
    config_path = Path(__file__).parent.parent / "evals" / "provider-canaries.json"
    cmd = [
        "python3",
        str(Path(__file__).parent / "provider_probe.py"),
        "--config", str(config_path),
    ]
    if dry_run:
        cmd.append("--dry-run")
    if list_only:
        cmd.append("--list")
    if provider:
        cmd.extend(["--provider", provider])
    try:
        cp = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        text = cp.stdout.strip()
        for start_idx in range(len(text)):
            if text[start_idx] in ("{", "["):
                try:
                    parsed = json.loads(text[start_idx:])
                    if list_only and isinstance(parsed, list):
                        # --list returns a JSON array of provider names
                        return {
                            "check": "provider_probe",
                            "status": "dry_run_list" if dry_run else "list",
                            "providers": parsed,
                            "dry_run": dry_run,
                        }
                    if isinstance(parsed, list):
                        # Probe results: list of per-provider result dicts
                        return {
                            "check": "provider_probe",
                            "status": "fail" if any(r.get("status") == "fail" for r in parsed) else "pass",
                            "dry_run": dry_run,
                            "results": parsed,
                        }
                    result = parsed
                    result["check"] = "provider_probe"
                    return result
                except json.JSONDecodeError:
                    continue
        return {
            "check": "provider_probe",
            "status": "error",
            "stdout": cp.stdout[:500],
            "stderr": cp.stderr[:500],
        }
    except Exception as exc:
        return {
            "check": "provider_probe",
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------

def build_summary(
    results: dict[str, Any],
    dry_run: bool = False,
) -> dict[str, Any]:
    """Build a compact summary across all check results.

    Returns dict with:
      overall_status (pass|fail|error),
      checks_run (int),
      check_results (dict),
      dry_run (bool),
      timestamp (str ISO)
    """
    check_results: dict[str, Any] = {}
    critical_failures = 0

    for name, result in results.items():
        check_results[name] = result
        if name == "rail_loader":
            if result.get("overall_status") == "fail":
                critical_failures += 1
        elif name == "provider_probe":
            if result.get("status") in {"fail", "error"}:
                critical_failures += 1
        elif result.get("error"):
            critical_failures += 1

    overall = "pass"
    if critical_failures > 0:
        overall = "fail"

    return {
        "overall_status": overall,
        "checks_run": len(results),
        "check_results": check_results,
        "dry_run": dry_run,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

ALL_CHECKS = ["rail_loader", "request_dump", "provider_probe"]

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Brain doctor — orchestrate all brain checks.",
    )
    parser.add_argument(
        "--check",
        action="append",
        dest="checks",
        default=[],
        help=f"Checks to run: {' | '.join(ALL_CHECKS)}. Can be repeated. "
             "Default: all.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without live network calls or log scanning.",
    )
    parser.add_argument(
        "--request-digest-limit",
        type=int, default=50,
        help="Max request dump files to analyze (default: 50).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write JSON summary.",
    )
    args = parser.parse_args()

    checks_to_run = args.checks if args.checks else ALL_CHECKS

    results: dict[str, Any] = {}

    if "rail_loader" in checks_to_run:
        results["rail_loader"] = run_rail_check(dry_run=args.dry_run)

    if "request_dump" in checks_to_run:
        results["request_dump"] = run_request_digest(
            dry_run=args.dry_run,
            limit=args.request_digest_limit,
        )

    if "provider_probe" in checks_to_run:
        results["provider_probe"] = run_provider_probe(
            dry_run=args.dry_run,
            list_only=args.dry_run,  # dry-run = list-only (safe); non-dry-run = real probes
        )

    summary = build_summary(results, dry_run=args.dry_run)

    text = json.dumps(summary, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n")
    print(text)

    return 0 if summary["overall_status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
