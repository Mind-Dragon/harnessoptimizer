"""Tests for active_work_lint.py — TDD for active-work snapshot validation."""

from pathlib import Path
from datetime import datetime

import pytest

import importlib.util
spec = importlib.util.spec_from_file_location(
    "active_work_lint",
    Path(__file__).parent / "active_work_lint.py",
)
lint_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lint_module)

lint_file = lint_module.lint_file
_check_heading = lint_module._check_heading
_check_size = lint_module._check_size
REQUIRED_HEADINGS = lint_module.REQUIRED_HEADINGS
MAX_SIZE_BYTES = lint_module.MAX_SIZE_BYTES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_VALID = """\
# Active Work: Phase 5 continuity task

## Objective
Implement work continuity tooling for the local brain.

## Current verified state
- Phase 1-4 complete per TODO.md
- Baseline passes: 36 passed, 2 warnings

## Blockers
None

## Files / paths in play
- brain/active-work/current.md (this file)
- brain/scripts/active_work_lint.py (being tested)

## Last successful checks
- pytest brain/scripts/test_rail_loader_check.py → 12 passed

## Next deterministic step
Write brain_doctor.py to orchestrate existing scripts.

## Notes to future session
Keep snapshots small and evidence-based.
"""

GOOD_SNAPSHOT = """\
# Active Work: Phase 5 Task 5.1

## Objective
Create active-work snapshot and lint tooling.

## Current verified state
- Phase 1 fixture fix: PASS (36 passed, 2 warnings)
- Phase 2 rail check: mismatch risk flagged
- Phase 3 provider notes: hardened
- Phase 4 evidence digestion: 100 files analyzed

## Blockers
- MINIMAX_API_KEY, KIMI_API_KEY absent (Phase 3.2 blocked)

## Files / paths in play
- brain/active-work/current.md (being created)
- brain/scripts/active_work_lint.py
- brain/scripts/brain_doctor.py

## Last successful checks
- python3 -m pytest -q brain/scripts/test_rail_loader_check.py → 12 passed
- python3 rail_loader_check.py --dry-run → overall_status=fail, mismatch_detected=true

## Next deterministic step
1. Write test_active_work_lint.py (TDD)
2. Write active_work_lint.py
3. Write brain_doctor.py
4. Create brain/active-work/current.md from verified state

## Notes to future session
- TDD first, then implementation
- Keep current.md grounded in real repo state
"""


# ---------------------------------------------------------------------------
# Tests: _check_heading
# ---------------------------------------------------------------------------

class TestCheckHeading:
    def test_all_required_present(self):
        content = MINIMAL_VALID
        errors = _check_heading(content, REQUIRED_HEADINGS)
        assert errors == []

    def test_missing_single_heading(self):
        content = MINIMAL_VALID.replace("## Objective\n", "")
        errors = _check_heading(content, REQUIRED_HEADINGS)
        assert len(errors) == 1
        assert "Objective" in errors[0]

    def test_missing_multiple_headings(self):
        content = MINIMAL_VALID.replace("## Objective\n", "").replace("## Blockers\n", "")
        errors = _check_heading(content, REQUIRED_HEADINGS)
        assert len(errors) == 2

    def test_extra_heading_allowed(self):
        """Extra headings beyond required are fine."""
        content = MINIMAL_VALID + "\n## Extra Section\nSome text.\n"
        errors = _check_heading(content, REQUIRED_HEADINGS)
        assert errors == []

    def test_heading_case_sensitive(self):
        content = MINIMAL_VALID.replace("## Objective\n", "## objective\n")
        errors = _check_heading(content, REQUIRED_HEADINGS)
        assert len(errors) == 1


# ---------------------------------------------------------------------------
# Tests: _check_size
# ---------------------------------------------------------------------------

class TestCheckSize:
    def test_under_limit(self, tmp_path):
        f = tmp_path / "small.md"
        f.write_text("Short content.\n")
        errors = _check_size(f, MAX_SIZE_BYTES)
        assert errors == []

    def test_over_limit(self, tmp_path):
        f = tmp_path / "large.md"
        f.write_text("x" * (MAX_SIZE_BYTES + 1))
        errors = _check_size(f, MAX_SIZE_BYTES)
        assert len(errors) == 1
        assert "too large" in errors[0]

    def test_exactly_at_limit(self, tmp_path):
        f = tmp_path / "exact.md"
        f.write_text("x" * MAX_SIZE_BYTES)
        errors = _check_size(f, MAX_SIZE_BYTES)
        assert errors == []


# ---------------------------------------------------------------------------
# Tests: lint_file
# ---------------------------------------------------------------------------

class TestLintFile:
    def test_valid_minimal_file(self, tmp_path):
        f = tmp_path / "valid.md"
        f.write_text(MINIMAL_VALID)
        result = lint_file(f)
        assert result["passed"] is True
        assert result["errors"] == []

    def test_valid_good_snapshot(self, tmp_path):
        f = tmp_path / "good.md"
        f.write_text(GOOD_SNAPSHOT)
        result = lint_file(f)
        assert result["passed"] is True
        assert result["errors"] == []

    def test_missing_file(self):
        result = lint_file(Path("/nonexistent/current.md"))
        assert result["passed"] is False
        assert any("not found" in e for e in result["errors"])

    def test_missing_headings(self, tmp_path):
        f = tmp_path / "incomplete.md"
        # Remove Blockers and Notes to future session
        content = MINIMAL_VALID.replace("## Blockers\n", "").replace(
            "## Notes to future session\n", ""
        )
        f.write_text(content)
        result = lint_file(f)
        assert result["passed"] is False
        assert len(result["errors"]) >= 2

    def test_over_size_limit(self, tmp_path):
        f = tmp_path / "oversized.md"
        f.write_text("x" * (MAX_SIZE_BYTES + 100))
        result = lint_file(f)
        assert result["passed"] is False
        assert any("too large" in e for e in result["errors"])

    def test_result_keys(self, tmp_path):
        f = tmp_path / "keys.md"
        f.write_text(MINIMAL_VALID)
        result = lint_file(f)
        assert set(result.keys()) == {"passed", "errors", "path", "size_bytes"}

    def test_empty_file_has_missing_headings(self, tmp_path):
        f = tmp_path / "empty.md"
        f.write_text("")
        result = lint_file(f)
        assert result["passed"] is False
        # All headings missing
        assert len(result["errors"]) >= len(REQUIRED_HEADINGS)
