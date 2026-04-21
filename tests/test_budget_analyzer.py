"""Tests for budget analyzer module."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermesoptimizer.budget.analyzer import (
    BudgetSignal,
    extract_signal,
    parse_session_directory,
    parse_session_file,
)

# Path to fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "budget"


class TestExtractSignal:
    """Tests for extract_signal function."""

    def test_extract_signal_normal(self) -> None:
        """Test extraction from a normally populated task dict."""
        task_data = {
            "task_id": "t1",
            "role": "implement",
            "turns_used": 45,
            "turns_budget": 100,
            "retries": 2,
            "loops": False,
            "status": "completed",
            "fix_cycles": 1,
            "tokens_used": 25000,
            "productive_calls": 35,
            "total_calls": 45,
            "duration_seconds": 120.5,
        }

        signal = extract_signal(task_data)

        assert signal.task_id == "t1"
        assert signal.role == "implement"
        assert signal.turn_utilization == 0.45
        assert signal.retry_count == 2
        assert signal.loop_detected is False
        assert signal.completion_status == "completed"
        assert signal.fix_cycles == 1
        assert signal.tokens_used == 25000
        assert signal.productive_call_ratio == 35 / 45
        assert signal.duration_seconds == 120.5

    def test_extract_signal_missing_fields(self) -> None:
        """Test extraction with missing fields uses defaults."""
        task_data: dict = {}

        signal = extract_signal(task_data)

        assert signal.task_id == ""
        assert signal.role == ""
        assert signal.turn_utilization == 0.0
        assert signal.retry_count == 0
        assert signal.loop_detected is False
        assert signal.completion_status == "incomplete"
        assert signal.fix_cycles == 0
        assert signal.tokens_used == 0
        assert signal.productive_call_ratio == 0.0
        assert signal.duration_seconds == 0.0

    def test_extract_signal_partial_fields(self) -> None:
        """Test extraction with only some fields present."""
        task_data = {"task_id": "t_partial", "role": "research"}

        signal = extract_signal(task_data)

        assert signal.task_id == "t_partial"
        assert signal.role == "research"
        assert signal.turn_utilization == 0.0
        assert signal.retry_count == 0
        assert signal.loop_detected is False
        assert signal.completion_status == "incomplete"
        assert signal.fix_cycles == 0
        assert signal.tokens_used == 0
        assert signal.productive_call_ratio == 0.0
        assert signal.duration_seconds == 0.0

    def test_extract_signal_zero_budget(self) -> None:
        """Test extraction when turns_budget is zero."""
        task_data = {
            "task_id": "t_zero",
            "turns_used": 0,
            "turns_budget": 0,
            "total_calls": 0,
            "productive_calls": 0,
        }

        signal = extract_signal(task_data)

        assert signal.turn_utilization == 0.0
        assert signal.productive_call_ratio == 0.0

    def test_extract_signal_zero_total_calls(self) -> None:
        """Test extraction when total_calls is zero."""
        task_data = {
            "task_id": "t_no_calls",
            "total_calls": 0,
            "productive_calls": 0,
        }

        signal = extract_signal(task_data)

        assert signal.productive_call_ratio == 0.0


class TestParseSessionFile:
    """Tests for parse_session_file function."""

    def test_parse_normal_session(self) -> None:
        """Test parsing a normal session file."""
        signals = parse_session_file(FIXTURES_DIR / "normal_session.json")

        assert len(signals) == 2

        assert signals[0].task_id == "t1"
        assert signals[0].turn_utilization == 0.45
        assert signals[0].completion_status == "completed"

        assert signals[1].task_id == "t2"
        assert signals[1].turn_utilization == 0.6
        assert signals[1].completion_status == "completed"

    def test_parse_early_exit(self) -> None:
        """Test parsing early exit pattern (util < 0.3, completed)."""
        signals = parse_session_file(FIXTURES_DIR / "early_exit.json")

        assert len(signals) == 1
        signal = signals[0]

        assert signal.turn_utilization == 0.25  # 25/100
        assert signal.completion_status == "completed"
        assert signal.loop_detected is False
        assert signal.retry_count == 0

    def test_parse_maxed_out(self) -> None:
        """Test parsing maxed out pattern (util > 0.9, completed)."""
        signals = parse_session_file(FIXTURES_DIR / "maxed_out.json")

        assert len(signals) == 1
        signal = signals[0]

        assert signal.turn_utilization == 0.95  # 95/100
        assert signal.completion_status == "completed"
        assert signal.retry_count == 1

    def test_parse_retry_exhaustion(self) -> None:
        """Test parsing retry exhaustion pattern (high retries, error)."""
        signals = parse_session_file(FIXTURES_DIR / "retry_exhaustion.json")

        assert len(signals) == 1
        signal = signals[0]

        assert signal.retry_count == 5
        assert signal.completion_status == "error"
        assert signal.turn_utilization == 1.0  # 100/100

    def test_parse_loop_detected(self) -> None:
        """Test parsing loop detected pattern."""
        signals = parse_session_file(FIXTURES_DIR / "loop_detected.json")

        assert len(signals) == 1
        signal = signals[0]

        assert signal.loop_detected is True
        assert signal.completion_status == "incomplete"
        assert signal.fix_cycles == 4

    def test_parse_missing_fields(self) -> None:
        """Test parsing session with missing/empty fields."""
        signals = parse_session_file(FIXTURES_DIR / "missing_fields.json")

        assert len(signals) == 2

        # First task has only task_id
        assert signals[0].task_id == "t_partial"
        assert signals[0].role == ""
        assert signals[0].turn_utilization == 0.0

        # Second task has empty string fields
        assert signals[1].task_id == "t_empty"
        assert signals[1].role == ""
        assert signals[1].completion_status == ""

    def test_parse_zero_edge_cases(self) -> None:
        """Test parsing with zero budget and zero calls."""
        signals = parse_session_file(FIXTURES_DIR / "zero_edge_cases.json")

        assert len(signals) == 1
        signal = signals[0]

        assert signal.turn_utilization == 0.0
        assert signal.productive_call_ratio == 0.0
        assert signal.tokens_used == 0
        assert signal.duration_seconds == 0.0


class TestParseSessionDirectory:
    """Tests for parse_session_directory function."""

    def test_parse_directory(self) -> None:
        """Test parsing all JSON files in a directory."""
        signals = parse_session_directory(FIXTURES_DIR)

        # Should get signals from all fixture files
        # early_exit (1), maxed_out (1), retry_exhaustion (1),
        # loop_detected (1), normal_session (2), missing_fields (2), zero_edge_cases (1)
        assert len(signals) == 9

        # Verify all expected task_ids are present
        task_ids = {s.task_id for s in signals}
        expected_ids = {
            "t_early",
            "t_maxed",
            "t_retry",
            "t_loop",
            "t1",
            "t2",
            "t_partial",
            "t_empty",
            "t_zero_budget",
        }
        assert task_ids == expected_ids

    def test_parse_directory_empty(self, tmp_path: Path) -> None:
        """Test parsing an empty directory returns empty list."""
        signals = parse_session_directory(tmp_path)
        assert signals == []


class TestBudgetSignal:
    """Tests for BudgetSignal dataclass."""

    def test_budget_signal_immutable(self) -> None:
        """Test that BudgetSignal is frozen (immutable)."""
        signal = BudgetSignal(
            task_id="t1",
            role="test",
            turn_utilization=0.5,
            retry_count=1,
            loop_detected=False,
            completion_status="completed",
            fix_cycles=0,
            tokens_used=1000,
            productive_call_ratio=0.8,
            duration_seconds=30.0,
        )

        with pytest.raises(Exception):  # frozen dataclass raises error on modification
            signal.task_id = "t2"

    def test_budget_signal_fields(self) -> None:
        """Test BudgetSignal has all required fields."""
        signal = BudgetSignal(
            task_id="t_test",
            role="implement",
            turn_utilization=0.75,
            retry_count=3,
            loop_detected=True,
            completion_status="error",
            fix_cycles=2,
            tokens_used=50000,
            productive_call_ratio=0.6,
            duration_seconds=90.5,
        )

        assert signal.task_id == "t_test"
        assert signal.role == "implement"
        assert signal.turn_utilization == 0.75
        assert signal.retry_count == 3
        assert signal.loop_detected is True
        assert signal.completion_status == "error"
        assert signal.fix_cycles == 2
        assert signal.tokens_used == 50000
        assert signal.productive_call_ratio == 0.6
        assert signal.duration_seconds == 90.5
