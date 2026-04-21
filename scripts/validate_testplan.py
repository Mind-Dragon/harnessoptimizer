#!/usr/bin/env python3
"""Validate TESTPLAN.md against the live test inventory.

Checks:
1. Every test file referenced in TESTPLAN.md exists under tests/
2. Every test file under tests/ is referenced in TESTPLAN.md
3. Test counts in TESTPLAN.md are within 10% of actual collected counts

Exit codes:
  0 — all checks pass
  1 — mismatches found
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

if len(sys.argv) > 1 and sys.argv[1] in ("--help", "-h"):
    print(__doc__)
    sys.exit(0)

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTPLAN = REPO_ROOT / "TESTPLAN.md"
TESTS_DIR = REPO_ROOT / "tests"


def get_testplan_files() -> dict[str, int]:
    """Extract test file references and counts from TESTPLAN.md."""
    text = TESTPLAN.read_text(encoding="utf-8")
    # Match patterns like `tests/test_foo.py` | 42 |
    pattern = r"`(tests/test_\w+\.py)`\s*\|\s*(\d+)\s*\|"
    matches = re.findall(pattern, text)
    return {m[0]: int(m[1]) for m in matches}


def get_actual_test_files() -> set[str]:
    """List all test files under tests/."""
    return {str(p.relative_to(REPO_ROOT)) for p in TESTS_DIR.glob("test_*.py")}


def get_collected_counts() -> dict[str, int]:
    """Run pytest --collect-only and count tests per file."""
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src") + os.pathsep + os.environ.get("PYTHONPATH", "")}
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )
    counts: dict[str, int] = {}
    for line in result.stdout.splitlines():
        # Lines like: tests/test_foo.py::test_bar
        match = re.match(r"^(tests/test_\w+\.py)::", line)
        if match:
            fname = match.group(1)
            counts[fname] = counts.get(fname, 0) + 1
    return counts


def main() -> int:
    errors: list[str] = []

    plan_files = get_testplan_files()
    actual_files = get_actual_test_files()

    # Check 1: plan references that don't exist
    plan_only = set(plan_files) - actual_files
    for f in sorted(plan_only):
        errors.append(f"PLAN references non-existent file: {f}")

    # Check 2: actual files not in plan
    actual_only = actual_files - set(plan_files)
    for f in sorted(actual_only):
        errors.append(f"ACTUAL file not in TESTPLAN: {f}")

    # Check 3: count drift (optional, informational)
    try:
        collected = get_collected_counts()
        for fname, plan_count in sorted(plan_files.items()):
            actual_count = collected.get(fname, 0)
            if actual_count == 0 and fname not in actual_files:
                continue  # already reported as missing file
            drift = abs(actual_count - plan_count)
            threshold = max(3, plan_count * 0.1)
            if drift > threshold:
                errors.append(f"COUNT drift: {fname} plan={plan_count} actual={actual_count} drift={drift}")
    except Exception as e:
        print(f"WARN: could not run pytest collect: {e}")

    if errors:
        print(f"TESTPLAN validation FAILED ({len(errors)} issues):")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"TESTPLAN validation OK — {len(plan_files)} files referenced, {len(actual_files)} on disk, counts aligned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
