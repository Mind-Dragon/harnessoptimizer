"""Tests for Phase 1 exponential decay scoring and threshold classification.

These tests verify the decay_score formula, fidelity tier classification,
and adaptive threshold logic described in v0.7.0 Phase 1.

decay_score(importance, hours_since_access, lambda=0.01) = importance * exp(-lambda * hours)

Fidelity thresholds:
  - hot >= 2.0 -> 'full'
  - warm >= 1.0 -> 'summary'
  - cool >= 0.3 -> 'essence'
  - gone < 0.01 -> 'prune'

Adaptive thresholds under memory pressure: raise proportionally when injected memory > 40% full.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Tests for decay_score formula
# ---------------------------------------------------------------------------


class TestDecayScoreFormula:
    """Test the exponential decay formula: score = importance * exp(-lambda * hours)"""

    def test_decay_score_zero_hours_returns_importance(self) -> None:
        """At 0 hours since access, score equals the original importance."""
        from hermesoptimizer.dreams.decay import decay_score

        assert decay_score(importance=3.0, hours_since_access=0.0) == 3.0
        assert decay_score(importance=1.0, hours_since_access=0.0) == 1.0
        assert decay_score(importance=5.0, hours_since_access=0.0) == 5.0

    def test_decay_score_one_hour_with_default_lambda(self) -> None:
        """At 1 hour with lambda=0.01, score = importance * exp(-0.01)."""
        from hermesoptimizer.dreams.decay import decay_score

        importance = 2.0
        expected = importance * math.exp(-0.01)
        result = decay_score(importance=importance, hours_since_access=1.0)
        assert math.isclose(result, expected, rel_tol=1e-9)

    def test_decay_score_hundred_hours_with_default_lambda(self) -> None:
        """At 100 hours with lambda=0.01, score = importance * exp(-1.0)."""
        from hermesoptimizer.dreams.decay import decay_score

        importance = 2.0
        expected = importance * math.exp(-1.0)
        result = decay_score(importance=importance, hours_since_access=100.0)
        assert math.isclose(result, expected, rel_tol=1e-9)

    def test_decay_score_custom_lambda(self) -> None:
        """A custom lambda value is respected in the formula."""
        from hermesoptimizer.dreams.decay import decay_score

        importance = 1.0
        hours = 10.0
        lam = 0.05
        expected = importance * math.exp(-lam * hours)
        result = decay_score(importance=importance, hours_since_access=hours, lambda_=lam)
        assert math.isclose(result, expected, rel_tol=1e-9)

    def test_decay_score_half_life_approximation(self) -> None:
        """After ~69.3 hours with lambda=0.01, score should be ~half of importance (ln(2) ~= 0.693)."""
        from hermesoptimizer.dreams.decay import decay_score

        importance = 2.0
        half_life_hours = 69.3
        result = decay_score(importance=importance, hours_since_access=half_life_hours)
        # exp(-0.01 * 69.3) ~= 0.5, so score ~= 1.0
        assert math.isclose(result, 1.0, rel_tol=0.01)

    def test_decay_score_very_large_hours(self) -> None:
        """Score approaches zero but never goes negative."""
        from hermesoptimizer.dreams.decay import decay_score

        result = decay_score(importance=1.0, hours_since_access=10000.0)
        assert result >= 0.0
        assert result < 1e-4

    def test_decay_score_zero_importance(self) -> None:
        """Zero importance always produces zero score."""
        from hermesoptimizer.dreams.decay import decay_score

        result = decay_score(importance=0.0, hours_since_access=100.0)
        assert result == 0.0


# ---------------------------------------------------------------------------
# Tests for fidelity tier classification
# ---------------------------------------------------------------------------


class TestFidelityTierClassification:
    """Test classify_tier(score) maps to correct fidelity tier strings."""

    def test_hot_threshold_returns_full(self) -> None:
        """Score >= 2.0 classifies as 'full' (hot tier)."""
        from hermesoptimizer.dreams.decay import classify_tier

        assert classify_tier(2.0) == "full"
        assert classify_tier(3.0) == "full"
        assert classify_tier(100.0) == "full"

    def test_warm_threshold_returns_summary(self) -> None:
        """Score >= 1.0 and < 2.0 classifies as 'summary' (warm tier)."""
        from hermesoptimizer.dreams.decay import classify_tier

        assert classify_tier(1.0) == "summary"
        assert classify_tier(1.5) == "summary"
        assert classify_tier(1.99) == "summary"

    def test_cool_threshold_returns_essence(self) -> None:
        """Score >= 0.3 and < 1.0 classifies as 'essence' (cool tier)."""
        from hermesoptimizer.dreams.decay import classify_tier

        assert classify_tier(0.3) == "essence"
        assert classify_tier(0.5) == "essence"
        assert classify_tier(0.99) == "essence"

    def test_gone_threshold_returns_gone(self) -> None:
        """Score < 0.01 classifies as 'gone' (gone tier)."""
        from hermesoptimizer.dreams.decay import classify_tier

        assert classify_tier(0.0) == "gone"
        assert classify_tier(0.005) == "gone"
        assert classify_tier(0.009) == "gone"

    def test_score_between_gone_and_cool_is_gone(self) -> None:
        """Score between gone (0.01) and cool (0.3) is 'gone' -- gap between tiers."""
        from hermesoptimizer.dreams.decay import classify_tier

        # 0.1 is > gone (0.01) but < cool (0.3) -- falls in the gap, treated as gone
        assert classify_tier(0.1) == "gone"

    def test_boundary_at_exactly_one(self) -> None:
        """Score exactly at 1.0 is 'summary' (>= 1.0 warm threshold)."""
        from hermesoptimizer.dreams.decay import classify_tier

        assert classify_tier(1.0) == "summary"

    def test_boundary_at_exactly_two(self) -> None:
        """Score exactly at 2.0 is 'full' (>= 2.0 hot threshold)."""
        from hermesoptimizer.dreams.decay import classify_tier

        assert classify_tier(2.0) == "full"


# ---------------------------------------------------------------------------
# Tests for adaptive thresholds under memory pressure
# ---------------------------------------------------------------------------


class TestAdaptiveThresholds:
    """Test that thresholds scale up when injected memory > 40% full."""

    def test_no_pressure_returns_default_thresholds(self) -> None:
        """When memory is at 0-40% full, default thresholds are returned."""
        from hermesoptimizer.dreams.decay import get_adaptive_thresholds

        thresholds = get_adaptive_thresholds(injected_memory_pct=0.0)
        assert thresholds == {"hot": 2.0, "warm": 1.0, "cool": 0.3, "gone": 0.01}

        thresholds = get_adaptive_thresholds(injected_memory_pct=20.0)
        assert thresholds == {"hot": 2.0, "warm": 1.0, "cool": 0.3, "gone": 0.01}

        thresholds = get_adaptive_thresholds(injected_memory_pct=39.9)
        assert thresholds == {"hot": 2.0, "warm": 1.0, "cool": 0.3, "gone": 0.01}

    def test_at_40_percent_full_thresholds_unchanged(self) -> None:
        """At exactly 40%, thresholds are still at defaults."""
        from hermesoptimizer.dreams.decay import get_adaptive_thresholds

        thresholds = get_adaptive_thresholds(injected_memory_pct=40.0)
        assert thresholds == {"hot": 2.0, "warm": 1.0, "cool": 0.3, "gone": 0.01}

    def test_above_40_percent_scales_proportionally(self) -> None:
        """Above 40%, thresholds scale proportionally to memory pressure ratio."""
        from hermesoptimizer.dreams.decay import get_adaptive_thresholds

        # At 50% full (pressure_ratio = 1.25), thresholds scale by 1.25
        thresholds = get_adaptive_thresholds(injected_memory_pct=50.0)
        assert thresholds["hot"] == pytest.approx(2.0 * 1.25)
        assert thresholds["warm"] == pytest.approx(1.0 * 1.25)
        assert thresholds["cool"] == pytest.approx(0.3 * 1.25)
        assert thresholds["gone"] == pytest.approx(0.01 * 1.25)

    def test_above_40_percent_60_percent_full(self) -> None:
        """At 60% full (pressure_ratio = 1.5), thresholds scale by 1.5."""
        from hermesoptimizer.dreams.decay import get_adaptive_thresholds

        thresholds = get_adaptive_thresholds(injected_memory_pct=60.0)
        assert thresholds["hot"] == pytest.approx(2.0 * 1.5)
        assert thresholds["warm"] == pytest.approx(1.0 * 1.5)
        assert thresholds["cool"] == pytest.approx(0.3 * 1.5)
        assert thresholds["gone"] == pytest.approx(0.01 * 1.5)

    def test_at_100_percent_full_max_pressure(self) -> None:
        """At 100% full (pressure_ratio = 2.5), thresholds scale by 2.5."""
        from hermesoptimizer.dreams.decay import get_adaptive_thresholds

        thresholds = get_adaptive_thresholds(injected_memory_pct=100.0)
        assert thresholds["hot"] == pytest.approx(2.0 * 2.5)
        assert thresholds["warm"] == pytest.approx(1.0 * 2.5)
        assert thresholds["cool"] == pytest.approx(0.3 * 2.5)
        assert thresholds["gone"] == pytest.approx(0.01 * 2.5)

    def test_adaptive_classify_tier_uses_adapted_thresholds(self) -> None:
        """classify_tier with injected_memory_pct > 40 uses scaled thresholds."""
        from hermesoptimizer.dreams.decay import classify_tier

        # At 50% memory pressure, score of 2.0 should NOT be 'full' anymore
        # because hot threshold is now 2.0 * 1.25 = 2.5
        result = classify_tier(score=2.0, injected_memory_pct=50.0)
        # 2.0 < 2.5 hot threshold, so it should be 'summary' (warm)
        assert result == "summary"

        # Score of 3.0 (above 2.5) should still be 'full'
        result = classify_tier(score=3.0, injected_memory_pct=50.0)
        assert result == "full"
