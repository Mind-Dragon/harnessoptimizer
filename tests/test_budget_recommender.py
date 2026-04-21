from __future__ import annotations

import pytest

from hermesoptimizer.budget.analyzer import BudgetSignal
from hermesoptimizer.budget.recommender import (
    BudgetRecommendation,
    _compute_aggregate_metrics,
    _determine_step,
    recommend,
)
from hermesoptimizer.budget.profile import get_profile


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def make_signal(
    *,
    task_id: str = "task-1",
    role: str = "implement",
    turn_utilization: float = 0.5,
    retry_count: int = 1,
    loop_detected: bool = False,
    completion_status: str = "completed",
    fix_cycles: int = 1,
    tokens_used: int = 10_000,
    productive_call_ratio: float = 0.8,
    duration_seconds: float = 60.0,
) -> BudgetSignal:
    return BudgetSignal(
        task_id=task_id,
        role=role,
        turn_utilization=turn_utilization,
        retry_count=retry_count,
        loop_detected=loop_detected,
        completion_status=completion_status,
        fix_cycles=fix_cycles,
        tokens_used=tokens_used,
        productive_call_ratio=productive_call_ratio,
        duration_seconds=duration_seconds,
    )


# ----------------------------------------------------------------------
# Tests: _compute_aggregate_metrics
# ----------------------------------------------------------------------


class TestComputeAggregateMetrics:
    def test_empty_signals_returns_zeros(self):
        result = _compute_aggregate_metrics([])
        assert result["avg_utilization"] == 0.0
        assert result["completion_rate"] == 0.0
        assert result["avg_retry_count"] == 0.0
        assert result["loop_rate"] == 0.0
        assert result["avg_fix_cycles"] == 0.0
        assert result["total_signals"] == 0

    def test_single_signal(self):
        sig = make_signal(turn_utilization=0.4, retry_count=3, fix_cycles=2, loop_detected=True)
        result = _compute_aggregate_metrics([sig])
        assert result["avg_utilization"] == 0.4
        assert result["avg_retry_count"] == 3.0
        assert result["avg_fix_cycles"] == 2.0
        assert result["loop_rate"] == 1.0
        assert result["total_signals"] == 1

    def test_multiple_signals_averages(self):
        signals = [
            make_signal(turn_utilization=0.2, completion_status="completed"),
            make_signal(turn_utilization=0.4, completion_status="completed"),
            make_signal(turn_utilization=0.6, completion_status="incomplete"),
            make_signal(turn_utilization=0.8, completion_status="error"),
        ]
        result = _compute_aggregate_metrics(signals)
        assert result["avg_utilization"] == pytest.approx(0.5)
        assert result["completion_rate"] == 0.5  # 2 out of 4
        assert result["total_signals"] == 4


# ----------------------------------------------------------------------
# Tests: _determine_step
# ----------------------------------------------------------------------


class TestDetermineStep:
    def test_low_utilization_high_completion_steps_down(self):
        """turn_utilization < 0.3 AND completion_rate > 0.9 → step DOWN."""
        metrics = {"avg_utilization": 0.2, "completion_rate": 0.95, "loop_rate": 0.0, "avg_fix_cycles": 1.0, "total_signals": 5}
        current = get_profile("medium")
        level, reasoning = _determine_step(metrics, current)
        assert level == "low-medium"
        assert "low" in reasoning.lower() or "step down" in reasoning.lower()

    def test_high_utilization_steps_up(self):
        """turn_utilization > 0.7 → step UP."""
        metrics = {"avg_utilization": 0.85, "completion_rate": 0.9, "loop_rate": 0.0, "avg_fix_cycles": 1.0, "total_signals": 5}
        current = get_profile("low-medium")
        level, reasoning = _determine_step(metrics, current)
        assert level == "medium"
        assert "high" in reasoning.lower() or "step up" in reasoning.lower()

    def test_low_completion_steps_up(self):
        """completion_rate < 0.7 → step UP regardless of utilization."""
        metrics = {"avg_utilization": 0.5, "completion_rate": 0.5, "loop_rate": 0.0, "avg_fix_cycles": 1.0, "total_signals": 5}
        current = get_profile("medium")
        level, reasoning = _determine_step(metrics, current)
        assert level == "medium-high"

    def test_medium_utilization_stays(self):
        """0.3 <= utilization <= 0.7 with completion > 0.8 → stay."""
        metrics = {"avg_utilization": 0.5, "completion_rate": 0.85, "loop_rate": 0.0, "avg_fix_cycles": 1.0, "total_signals": 5}
        current = get_profile("medium")
        level, reasoning = _determine_step(metrics, current)
        assert level == "medium"

    def test_medium_utilization_approaching_boundary_steps_up(self):
        """utilization > 0.6 within medium band → step up."""
        metrics = {"avg_utilization": 0.65, "completion_rate": 0.9, "loop_rate": 0.0, "avg_fix_cycles": 1.0, "total_signals": 5}
        current = get_profile("low-medium")
        level, reasoning = _determine_step(metrics, current)
        assert level == "medium"

    def test_already_at_high_boundary(self):
        """At high profile with high utilization → stay with axis override note."""
        metrics = {"avg_utilization": 0.9, "completion_rate": 0.6, "loop_rate": 0.0, "avg_fix_cycles": 1.0, "total_signals": 5}
        current = get_profile("high")
        level, reasoning = _determine_step(metrics, current)
        assert level == "high"
        assert "axis overrides" in reasoning.lower()

    def test_already_at_low_boundary(self):
        """At low profile with low utilization → stay with axis override note."""
        metrics = {"avg_utilization": 0.1, "completion_rate": 0.95, "loop_rate": 0.0, "avg_fix_cycles": 1.0, "total_signals": 5}
        current = get_profile("low")
        level, reasoning = _determine_step(metrics, current)
        assert level == "low"
        assert "axis overrides" in reasoning.lower() or "lowest profile" in reasoning.lower()


# ----------------------------------------------------------------------
# Tests: recommend (integration)
# ----------------------------------------------------------------------


class TestRecommend:
    def test_empty_signal_list_defaults_stay_low_confidence(self):
        rec = recommend([], "medium")
        assert rec.recommended_profile == "medium"
        assert rec.confidence == 0.0
        assert rec.signals_used == 0
        assert rec.main_turns == get_profile("medium").main_turns

    def test_single_signal(self):
        sig = make_signal(turn_utilization=0.8, completion_status="completed")
        rec = recommend([sig], "low-medium")
        assert rec.signals_used == 1
        assert rec.confidence == 0.4
        assert rec.recommended_profile == "medium"

    def test_low_utilization_high_completion_steps_down(self):
        signals = [
            make_signal(turn_utilization=0.1, completion_status="completed"),
            make_signal(turn_utilization=0.15, completion_status="completed"),
            make_signal(turn_utilization=0.2, completion_status="completed"),
            make_signal(turn_utilization=0.1, completion_status="completed"),
            make_signal(turn_utilization=0.15, completion_status="completed"),
        ]
        rec = recommend(signals, "medium")
        assert rec.recommended_profile == "low-medium"
        assert rec.confidence >= 0.5

    def test_high_utilization_steps_up(self):
        signals = [
            make_signal(turn_utilization=0.8, completion_status="completed"),
            make_signal(turn_utilization=0.9, completion_status="completed"),
            make_signal(turn_utilization=0.85, completion_status="completed"),
            make_signal(turn_utilization=0.75, completion_status="completed"),
            make_signal(turn_utilization=0.88, completion_status="completed"),
        ]
        rec = recommend(signals, "low-medium")
        assert rec.recommended_profile == "medium"

    def test_loop_detection_triggers_axis_override(self):
        signals = [
            make_signal(loop_detected=True),
            make_signal(loop_detected=True),
            make_signal(loop_detected=False),
            make_signal(loop_detected=True),
        ]  # 3/4 = 75% loop rate > 20%
        rec = recommend(signals, "medium")
        assert "retry_limit" in rec.axis_overrides
        assert rec.axis_overrides["retry_limit"] > get_profile("medium").retry_limit

    def test_high_fix_cycles_triggers_axis_override(self):
        signals = [
            make_signal(fix_cycles=4),
            make_signal(fix_cycles=5),
            make_signal(fix_cycles=3),
            make_signal(fix_cycles=4),
            make_signal(fix_cycles=5),
        ]  # avg = 4.2 > 3
        rec = recommend(signals, "medium")
        assert "fix_iterate_cycles" in rec.axis_overrides
        assert rec.axis_overrides["fix_iterate_cycles"] > get_profile("medium").fix_iterate_cycles

    def test_recommendation_has_reasoning(self):
        signals = [
            make_signal(turn_utilization=0.85, completion_status="completed"),
        ]
        rec = recommend(signals, "medium")
        assert len(rec.reasoning) > 10
        assert isinstance(rec.reasoning, str)

    def test_confidence_increases_with_signal_count(self):
        rec_few = recommend([make_signal()] * 3, "medium")
        rec_many = recommend([make_signal()] * 10, "medium")
        assert rec_many.confidence > rec_few.confidence

    def test_confidence_capped_at_point_nine(self):
        signals = [make_signal()] * 50
        rec = recommend(signals, "medium")
        assert rec.confidence <= 0.9

    def test_returns_correct_turns_for_recommended_profile(self):
        signals = [
            make_signal(turn_utilization=0.8, completion_status="completed"),
        ]
        rec = recommend(signals, "low-medium")
        recommended = get_profile(rec.recommended_profile)
        assert rec.main_turns == recommended.main_turns
        assert rec.subagent_turns == recommended.subagent_turns

    def test_current_profile_preserved_in_output(self):
        rec = recommend([], "high")
        assert rec.current_profile == "high"

    def test_role_overrides_default_empty(self):
        rec = recommend([], "medium")
        assert rec.role_overrides == {}
