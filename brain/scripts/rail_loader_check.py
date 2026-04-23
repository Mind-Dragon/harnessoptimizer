#!/usr/bin/env python3
"""Rail loader check — verifies SOUL/HEARTBEAT rails are readable.

Inspects:
- File existence and format shape for rail documents
- Recent Hermes logs for the known prefill error signature

SOUL/HEARTBEAT are governance rails, not JSON prefill payloads. The JSON
contract belongs to Hermes `prefill_messages_file` only.

Examples:
  python3 rail_loader_check.py --dry-run
  python3 rail_loader_check.py --soul-path /custom/SOUL.md
  python3 rail_loader_check.py --logs-dir ~/.hermes/logs
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Known rail locations
DEFAULT_SOUL_PATH = Path("/home/agent/clawd/SOUL.md")
DEFAULT_HEARTBEAT_PATH = Path("/home/agent/clawd/HEARTBEAT.md")
DEFAULT_LOG_GLOB = "agent*.log"

# Error signature from incident: mismatch between loader JSON expectation
# and markdown/plaintext file content
PREFILL_ERROR_RE = re.compile(
    r"Failed to load prefill messages from (?P<file>[^\s:]+):\s*"
    r"Expecting value: line (?P<line>\d+) column (?P<col>\d+) \(char (?P<char>\d+)\)"
)


def classify_format(path: Path) -> dict[str, Any]:
    """Classify file format as markdown/plaintext or json.

    Returns dict with keys: format (str), valid_json (bool).
    """
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return {"format": "unknown", "valid_json": False, "error": "not_found"}
    except Exception as exc:
        return {"format": "unknown", "valid_json": False, "error": str(exc)}

    text = raw.strip()
    if not text:
        return {"format": "markdown/plaintext", "valid_json": False}

    try:
        json.loads(text)
        return {"format": "json", "valid_json": True}
    except (json.JSONDecodeError, ValueError):
        return {"format": "markdown/plaintext", "valid_json": False}


def check_rail_file(path: Path) -> dict[str, Any]:
    """Check a single rail file for existence and format.

    Returns dict with keys: exists, format, valid_json, loader_expects, status.
    Status is one of: ok | mismatch_risk | missing | error
    """
    result: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "format": None,
        "valid_json": None,
        "loader_expects": "markdown/plaintext",
    }

    if not result["exists"]:
        result["status"] = "missing"
        return result

    fmt = classify_format(path)
    result["format"] = fmt["format"]
    result["valid_json"] = fmt["valid_json"]

    # SOUL/HEARTBEAT rails are expected to be markdown/plaintext. JSON is also
    # accepted for compatibility with older prefill-message experiments.
    if fmt["format"] == "markdown/plaintext":
        result["status"] = "ok"
    elif fmt["format"] == "json":
        result["status"] = "ok"
    else:
        result["status"] = "error"

    return result


def scan_log_for_prefill_errors(log_paths: list[Path]) -> list[dict[str, Any]]:
    """Scan log files for the known prefill error signature.

    Returns a list of error records with keys: timestamp, file, error, line.
    """
    errors: list[dict[str, Any]] = []

    # Log line pattern: 2026-04-22 20:11:38,456 WARNING gateway.run: ...
    log_line_re = re.compile(
        r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s+"
        r"(?P<level>\w+)\s+"
        r"(?P<logger>[^:]+):\s*"
        r"(?P<message>.*)$"
    )

    for log_path in log_paths:
        if not log_path.exists():
            continue
        try:
            content = log_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        for line_no, line in enumerate(content.splitlines(), start=1):
            match = PREFILL_ERROR_RE.search(line)
            if match:
                log_match = log_line_re.match(line)
                timestamp = log_match.group("timestamp") if log_match else None
                errors.append({
                    "timestamp": timestamp,
                    "file": match.group("file"),
                    "error": "Expecting value (JSON parse failure)",
                    "line": line_no,
                    "log_path": str(log_path),
                })

    return errors


def build_report(
    rail_paths: dict[str, Path],
    log_paths: list[Path],
    dry_run: bool = False,
) -> dict[str, Any]:
    """Build a full report across all rails and logs.

    Returns a machine-readable dict with overall_status, rails list,
    log_errors_found, and mismatch_detected flag.
    """
    rail_results = []
    for name, path in rail_paths.items():
        result = check_rail_file(path)
        result["rail"] = name
        rail_results.append(result)

    log_errors = scan_log_for_prefill_errors(log_paths)

    # Determine overall status
    mismatch_detected = any(
        r["status"] == "mismatch_risk" for r in rail_results
    ) or len(log_errors) > 0

    statuses = {r["status"] for r in rail_results}
    if "error" in statuses or "missing" in statuses:
        overall = "fail"
    elif mismatch_detected:
        overall = "fail"
    else:
        overall = "pass"

    report: dict[str, Any] = {
        "check": "rail_loader",
        "dry_run": dry_run,
        "overall_status": overall,
        "mismatch_detected": mismatch_detected,
        "rails": rail_results,
        "log_errors_found": len(log_errors),
        "log_errors": log_errors[-10:] if log_errors else [],  # last 10
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return report


def find_log_files(logs_dir: Path, pattern: str = DEFAULT_LOG_GLOB) -> list[Path]:
    """Find recent log files in logs_dir matching pattern."""
    if not logs_dir.exists():
        return []
    # Sort by mtime descending, take 3 most recent
    files = sorted(logs_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:3]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check SOUL/HEARTBEAT rail loader for prefill mismatch risk."
    )
    parser.add_argument(
        "--soul-path", type=Path, default=DEFAULT_SOUL_PATH,
        help="Path to SOUL.md (default: /home/agent/clawd/SOUL.md)"
    )
    parser.add_argument(
        "--heartbeat-path", type=Path, default=DEFAULT_HEARTBEAT_PATH,
        help="Path to HEARTBEAT.md (default: /home/agent/clawd/HEARTBEAT.md)"
    )
    parser.add_argument(
        "--logs-dir", type=Path, default=Path.home() / ".hermes/logs",
        help="Path to Hermes logs directory"
    )
    parser.add_argument(
        "--log-pattern", default=DEFAULT_LOG_GLOB,
        help="Glob pattern for log files (default: agent*.log)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Run without log scanning or external dependencies"
    )
    parser.add_argument(
        "--output", type=Path,
        help="Optional path to write JSON report"
    )
    args = parser.parse_args()

    rail_paths = {
        "SOUL": args.soul_path,
        "HEARTBEAT": args.heartbeat_path,
    }

    log_paths: list[Path] = []
    if not args.dry_run:
        log_paths = find_log_files(args.logs_dir, args.log_pattern)

    report = build_report(
        rail_paths=rail_paths,
        log_paths=log_paths,
        dry_run=args.dry_run,
    )

    text = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n")
    print(text)

    return 0 if report["overall_status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
