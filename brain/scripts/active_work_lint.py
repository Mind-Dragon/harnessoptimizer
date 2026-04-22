#!/usr/bin/env python3
"""Lint brain/active-work/current.md for required sections and compactness.

Fails or warns on:
- missing required headings
- file size over MAX_SIZE_BYTES (default 10 KB)
- file not found

Required headings (per _template.md):
  Objective, Current verified state, Blockers,
  Files / paths in play, Last successful checks,
  Next deterministic step, Notes to future session

Examples:
  python3 active_work_lint.py
  python3 active_work_lint.py --path brain/active-work/current.md
  python3 active_work_lint.py --path brain/active-work/current.md --output lint.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# Default thresholds
MAX_SIZE_BYTES = 10 * 1024  # 10 KB

# Required headings — must appear as exact markdown H2 lines
REQUIRED_HEADINGS = [
    "Objective",
    "Current verified state",
    "Blockers",
    "Files / paths in play",
    "Last successful checks",
    "Next deterministic step",
    "Notes to future session",
]

# Heading pattern: exactly "## <Name>" at start of line
HEADING_RE = re.compile(r"^(#{1,2})\s+(.+)$", re.MULTILINE)


def _check_heading(content: str, required: list[str]) -> list[str]:
    """Return list of error messages for missing headings."""
    errors: list[str] = []
    found: set[str] = set()
    for match in HEADING_RE.finditer(content):
        found.add(match.group(2).strip())
    for name in required:
        if name not in found:
            errors.append(f"missing heading: ## {name}")
    return errors


def _check_size(path: Path, max_bytes: int) -> list[str]:
    """Return error if file exceeds max_bytes."""
    try:
        size = path.stat().st_size
    except OSError:
        return []
    if size > max_bytes:
        return [f"file too large: {size} bytes (max {max_bytes})"]
    return []


def lint_file(path: Path) -> dict[str, Any]:
    """Lint a single active-work markdown file.

    Returns dict with keys:
      passed (bool),
      errors (list[str]),
      path (str),
      size_bytes (int)
    """
    result: dict[str, Any] = {
        "passed": True,
        "errors": [],
        "path": str(path),
        "size_bytes": 0,
    }

    if not path.exists():
        result["passed"] = False
        result["errors"].append(f"file not found: {path}")
        return result

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:
        result["passed"] = False
        result["errors"].append(f"read error: {exc}")
        return result

    result["size_bytes"] = len(content.encode("utf-8"))

    heading_errors = _check_heading(content, REQUIRED_HEADINGS)
    result["errors"].extend(heading_errors)

    size_errors = _check_size(path, MAX_SIZE_BYTES)
    result["errors"].extend(size_errors)

    if result["errors"]:
        result["passed"] = False

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lint brain/active-work/current.md for required sections and compactness."
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=Path("brain/active-work/current.md"),
        help="Path to active-work snapshot (default: brain/active-work/current.md)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write JSON report",
    )
    args = parser.parse_args()

    result = lint_file(args.path)
    text = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n")
    print(text)

    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
