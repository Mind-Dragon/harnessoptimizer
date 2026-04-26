"""Packaged brain-doctor fallback for wheel installs.

The full repo-local brain doctor lives under ``brain/scripts`` in editable
checkouts. Wheels cannot rely on that repo tree, so this module provides the
same dry-run/list contract needed by release gates without touching runtime
state.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ALL_CHECKS = ["rail_loader", "request_dump", "provider_probe"]


def run_brain_doctor(*, dry_run: bool = False, checks: list[str] | None = None) -> dict[str, Any]:
    selected = checks or ALL_CHECKS
    return {
        "check": "brain_doctor",
        "status": "dry_run" if dry_run else "packaged_canary",
        "dry_run": dry_run,
        "checks_requested": selected,
        "checks": {name: {"status": "dry_run" if dry_run else "not_available_in_wheel"} for name in selected},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--check", action="append", choices=ALL_CHECKS)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    report = run_brain_doctor(dry_run=args.dry_run, checks=args.check)
    text = json.dumps(report, indent=2)
    if args.output:
        out = Path(args.output).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    # Emit to both stdout (for CLI consumers) and logging
    print(text)
    logger.info(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
