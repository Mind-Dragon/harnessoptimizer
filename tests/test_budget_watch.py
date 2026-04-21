"""Tests for budget watch module."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermesoptimizer.budget.analyzer import BudgetSignal
from hermesoptimizer.budget.recommender import BudgetRecommendation, recommend
from hermesoptimizer.budget.watch import budget_watch_entry, format_watch_line

# Path to fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "budget"


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def make_recommendation(
    current_profile: str = "medium",
    recommended_profile: str = "medium",
    confidence: float = 0.6,
    reasoning: str = "Test reasoning.",
    signals_used: int = 2,
    axis_overrides: dict | None = None,
) -> BudgetRecommendation:
    """Create a BudgetRecommendation for testing."""
    return BudgetRecommendation(
        current_profile=current_profile,
        recommended_profile=recommended_profile,
        confidence=confidence,
        reasoning=reasoning,
        main_turns=500,
        subagent_turns=100,
        role_overrides={},
        axis_overrides=axis_overrides or {},
        signals_used=signals_used,
    )


# ----------------------------------------------------------------------
# Tests: format_watch_line
# ----------------------------------------------------------------------


class TestFormatWatchLine:
    """Tests for format_watch_line function."""

    def test_basic_format(self) -> None:
        """Test basic log line format."""
        rec = make_recommendation(
            current_profile="medium",
            recommended_profile="medium-high",
            reasoning="Test reasoning.",
        )
        line = format_watch_line(rec, 0.42, "abc123", "2026-04-19")

        assert "2026-04-19" in line
        assert "session=abc123" in line
        assert "profile=medium" in line
        assert "utilization=0.42" in line
        assert "recommend=medium-high" in line

    def test_default_date(self) -> None:
        """Test that date defaults to today."""
        rec = make_recommendation()
        line = format_watch_line(rec, 0.5, "test_session")

        # Should contain a valid ISO date
        assert line.startswith("2026-")
        assert "session=test_session" in line

    def test_utilization_formatting(self) -> None:
        """Test utilization is formatted to 2 decimal places."""
        rec = make_recommendation()

        line = format_watch_line(rec, 0.0, "test", "2026-04-19")
        assert "utilization=0.00" in line

        line = format_watch_line(rec, 1.0, "test", "2026-04-19")
        assert "utilization=1.00" in line

        line = format_watch_line(rec, 0.999, "test", "2026-04-19")
        assert "utilization=1.00" in line  # Rounded

        line = format_watch_line(rec, 0.555, "test", "2026-04-19")
        assert "utilization=0.56" in line  # Rounded

    def test_axis_overrides_as_notes(self) -> None:
        """Test axis overrides are included in notes."""
        rec = make_recommendation(
            recommended_profile="high",
            reasoning="High utilization detected.",
            axis_overrides={"retry_limit": 10, "fix_iterate_cycles": 7},
        )
        line = format_watch_line(rec, 0.85, "test", "2026-04-19")

        assert "implement_retry_limit_10" in line
        assert "implement_fix_iterate_cycles_7" in line

    def test_reasoning_included_when_short(self) -> None:
        """Test that short reasoning is included."""
        rec = make_recommendation(
            reasoning="Short note.",
        )
        line = format_watch_line(rec, 0.5, "test", "2026-04-19")

        assert "Short note." in line

    def test_reasoning_truncated_when_long(self) -> None:
        """Test that long reasoning is truncated to first sentence."""
        long_reasoning = (
            "This is a very long reasoning string that exceeds sixty characters. "
            "It should be truncated to the first sentence."
        )
        rec = make_recommendation(reasoning=long_reasoning)
        line = format_watch_line(rec, 0.5, "test", "2026-04-19")

        # Should end with first sentence
        assert "This is a very long reasoning string that exceeds sixty characters." in line
        # Should not contain the second sentence
        assert "truncated" not in line

    def test_no_extra_spaces_when_no_notes(self) -> None:
        """Test no extra spaces when there are no notes."""
        rec = make_recommendation(reasoning="Simple.")
        line = format_watch_line(rec, 0.5, "test", "2026-04-19")

        # Should not have trailing space before newline
        assert not line.endswith(" ")


# ----------------------------------------------------------------------
# Tests: budget_watch_entry
# ----------------------------------------------------------------------


class TestBudgetWatchEntry:
    """Tests for budget_watch_entry function."""

    def test_normal_session_dir_produces_log_line(self, tmp_path: Path) -> None:
        """Test normal session directory produces a log line."""
        # Use fixture directory
        result = budget_watch_entry(
            session_dir=FIXTURES_DIR,
            log_path=tmp_path / "test.log",
            current_profile="medium",
        )

        assert result is not None
        assert "session=" in result
        assert "profile=medium" in result

    def test_empty_session_dir_returns_log_line(self, tmp_path: Path) -> None:
        """Test empty session directory still produces a valid log entry."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = budget_watch_entry(
            session_dir=empty_dir,
            log_path=tmp_path / "test.log",
            current_profile="medium",
        )

        # Empty directory still produces a log line with 0 utilization
        assert result is not None
        assert "session=empty" in result
        assert "utilization=0.00" in result
        assert "recommend=medium" in result

    def test_log_file_created_if_not_exists(self, tmp_path: Path) -> None:
        """Test log file is created if it doesn't exist."""
        log_path = tmp_path / "new" / "budget-advice.log"

        result = budget_watch_entry(
            session_dir=FIXTURES_DIR,
            log_path=log_path,
            current_profile="medium",
        )

        assert result is not None
        assert log_path.exists()

    def test_log_file_appended_to_if_exists(self, tmp_path: Path) -> None:
        """Test log file is appended to if it already exists."""
        log_path = tmp_path / "test.log"

        # Create file with existing content
        existing_content = "2026-04-18 previous entry\n"
        log_path.write_text(existing_content)

        result1 = budget_watch_entry(
            session_dir=FIXTURES_DIR,
            log_path=log_path,
            current_profile="medium",
        )

        result2 = budget_watch_entry(
            session_dir=FIXTURES_DIR,
            log_path=log_path,
            current_profile="medium-high",
        )

        content = log_path.read_text()
        lines = content.strip().split("\n")

        assert len(lines) == 3  # 1 existing + 2 new
        assert lines[0] == "2026-04-18 previous entry"
        assert result1 is not None
        assert result2 is not None

    def test_nonexistent_session_dir_produces_log_line(self, tmp_path: Path) -> None:
        """Test nonexistent session directory produces a log line gracefully."""
        bad_dir = tmp_path / "nonexistent" / "sessions"

        result = budget_watch_entry(
            session_dir=bad_dir,
            log_path=tmp_path / "test.log",
            current_profile="medium",
        )

        # Should still produce a log line (non-existent dir is handled gracefully)
        assert result is not None
        assert "session=sessions" in result
        assert "utilization=0.00" in result
        assert "recommend=medium" in result

    def test_silent_failure_on_bad_log_path(self, tmp_path: Path) -> None:
        """Test silent failure when log_path is invalid."""
        # Use a path that would fail on write - e.g., a path in a non-existent
        # directory that cannot be created (using /dev full or similar)
        # Since we can't easily simulate this, we test with an invalid path
        invalid_path = Path("/root/budget-advice.log")  # Likely unwritable on linux

        result = budget_watch_entry(
            session_dir=FIXTURES_DIR,
            log_path=invalid_path,
            current_profile="medium",
        )

        # Should return None silently if log file cannot be written
        assert result is None

    def test_log_line_format_matches_expected_pattern(self, tmp_path: Path) -> None:
        """Test log line format matches the expected pattern."""
        log_path = tmp_path / "test.log"

        result = budget_watch_entry(
            session_dir=FIXTURES_DIR,
            log_path=log_path,
            current_profile="medium",
        )

        assert result is not None

        # Parse the line
        # Format: YYYY-MM-DD session=<id> profile=<p> utilization=<f> recommend=<p> <notes>
        parts = result.split()
        assert len(parts) >= 5  # date, session=..., profile=..., utilization=..., recommend=...
        assert parts[0].startswith("2026-")  # Date
        assert parts[1].startswith("session=")
        assert parts[2].startswith("profile=")
        assert parts[3].startswith("utilization=")
        assert parts[4].startswith("recommend=")

    def test_returns_none_on_write_exception(self, tmp_path: Path) -> None:
        """Test that write exceptions result in None being returned."""
        # Use a file path that exists but cannot be written to (directory as file)
        # This will cause the open() call to fail with IsADirectoryError
        file_as_path = tmp_path / "adir"
        file_as_path.mkdir()  # Create a directory

        result = budget_watch_entry(
            session_dir=FIXTURES_DIR,
            log_path=file_as_path,  # Try to write to a directory
            current_profile="medium",
        )

        # Should return None on exception (IsADirectoryError when trying to write)
        assert result is None

    def test_multiple_entries_increase_line_count(self, tmp_path: Path) -> None:
        """Test multiple calls append to the log file."""
        log_path = tmp_path / "test.log"

        for _ in range(3):
            result = budget_watch_entry(
                session_dir=FIXTURES_DIR,
                log_path=log_path,
                current_profile="medium",
            )
            assert result is not None

        content = log_path.read_text()
        lines = [line for line in content.strip().split("\n") if line]
        assert len(lines) == 3


class TestBudgetWatchEntryIntegration:
    """Integration tests using actual fixture data."""

    def test_with_valid_fixture_directory(self, tmp_path: Path) -> None:
        """Test with fixture directory containing session files."""
        log_path = tmp_path / "test.log"

        result = budget_watch_entry(
            session_dir=FIXTURES_DIR,
            log_path=log_path,
            current_profile="medium",
        )

        assert result is not None
        assert "profile=medium" in result

        # Verify it was actually written
        content = log_path.read_text()
        assert "profile=medium" in content
