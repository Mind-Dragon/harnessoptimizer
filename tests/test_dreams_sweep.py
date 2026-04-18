"""Tests for Phase 1 dreaming sweep logic.

These tests verify that the dreaming sweep:
- scores all entries using decay_score
- prunes entries below the 'gone' threshold
- demotes fidelity tiers based on score

The sweep operates on in-memory data structures and produces a sweep_result
with decisions (prune/demote/keep) and a summary.
"""

from __future__ import annotations

import math
import time
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class MockEntry:
    """Minimal mock supermemory entry for sweep testing."""

    def __init__(
        self,
        supermemory_id: str,
        content_hash: str,
        importance: float,
        created_at: int,
        fidelity_tier: str = "full",
    ) -> None:
        self.supermemory_id = supermemory_id
        self.content_hash = content_hash
        self.importance = importance
        self.created_at = created_at
        self.fidelity_tier = fidelity_tier

    def to_dict(self) -> dict:
        return {
            "supermemory_id": self.supermemory_id,
            "content_hash": self.content_hash,
            "importance": self.importance,
            "created_at": self.created_at,
            "last_recalled": None,
            "recall_count": 0,
            "fidelity_tier": self.fidelity_tier,
        }


def make_entry(
    supermemory_id: str,
    importance: float,
    hours_ago: float,
    fidelity_tier: str = "full",
) -> MockEntry:
    """Helper: create a mock entry with created_at set to hours_ago hours ago."""
    created_at = int(time.time() - hours_ago * 3600)
    return MockEntry(
        supermemory_id=supermemory_id,
        content_hash=f"hash-{supermemory_id}",
        importance=importance,
        created_at=created_at,
        fidelity_tier=fidelity_tier,
    )


# ---------------------------------------------------------------------------
# Tests for sweep scoring
# ---------------------------------------------------------------------------


class TestSweepScoring:
    """Test that sweep_entry_score computes the correct decay score per entry."""

    def test_score_uses_decay_formula(self) -> None:
        """sweep_entry_score applies decay_score using hours_since_access."""
        import math

        from hermesoptimizer.dreams.sweep import sweep_entry_score

        # An entry with importance=3.0 accessed 0 hours ago should score ~3.0
        # (tiny time gap between make_entry and sweep_entry_score means we use isclose)
        entry = make_entry("e1", importance=3.0, hours_ago=0.0)
        score = sweep_entry_score(entry)
        assert math.isclose(score, 3.0, rel_tol=1e-5)

    def test_score_reflects_hours_ago(self) -> None:
        """Score decays based on hours since last access."""
        import math

        from hermesoptimizer.dreams.sweep import sweep_entry_score

        # importance=2.0, 100 hours ago -> score = 2.0 * exp(-1.0) ~= 0.736
        # Tiny time gap between make_entry and sweep_entry_score means we use rel_tol=1e-5
        entry = make_entry("e1", importance=2.0, hours_ago=100.0)
        score = sweep_entry_score(entry)
        expected = 2.0 * math.exp(-1.0)
        assert math.isclose(score, expected, rel_tol=1e-5)

    def test_score_uses_importance(self) -> None:
        """Higher importance entries score higher at the same age."""
        from hermesoptimizer.dreams.sweep import sweep_entry_score

        entry_low = make_entry("e1", importance=1.0, hours_ago=50.0)
        entry_high = make_entry("e2", importance=3.0, hours_ago=50.0)

        score_low = sweep_entry_score(entry_low)
        score_high = sweep_entry_score(entry_high)

        assert score_high > score_low
        assert math.isclose(score_high, 3.0 * score_low, rel_tol=1e-5)  # 3x importance at same age


# ---------------------------------------------------------------------------
# Tests for sweep decisions (prune/demote/keep)
# ---------------------------------------------------------------------------


class TestSweepDecisions:
    """Test that sweep produces correct decisions per entry."""

    def test_prune_below_gone_threshold(self) -> None:
        """Entry with score < gone threshold is marked for pruning."""
        from hermesoptimizer.dreams.sweep import run_sweep

        # importance=0.1, 500 hours ago -> score ~= 0.1 * exp(-5) ~= 0.00067 < 0.01
        entries = [make_entry("stale", importance=0.1, hours_ago=500.0)]
        result = run_sweep(entries)

        prune_ids = {d["supermemory_id"] for d in result["decisions"] if d["action"] == "prune"}
        assert "stale" in prune_ids

    def test_keep_full_tier_when_hot(self) -> None:
        """Entry with score >= hot threshold stays at 'full' tier."""
        from hermesoptimizer.dreams.sweep import run_sweep

        # importance=3.0, 0 hours ago -> score=3.0 >= 2.0 hot threshold
        entries = [make_entry("hot", importance=3.0, hours_ago=0.0)]
        result = run_sweep(entries)

        keep_full = [
            d for d in result["decisions"]
            if d["supermemory_id"] == "hot" and d["action"] == "keep" and d["tier"] == "full"
        ]
        assert len(keep_full) == 1

    def test_demote_full_to_summary(self) -> None:
        """Entry with score >= warm but < hot is demoted to 'summary'."""
        from hermesoptimizer.dreams.sweep import run_sweep

        # importance=1.5, 0 hours ago -> score=1.5 (warm >= 1.0, < 2.0)
        entries = [make_entry("warm", importance=1.5, hours_ago=0.0)]
        result = run_sweep(entries)

        demote = [
            d for d in result["decisions"]
            if d["supermemory_id"] == "warm" and d["action"] == "demote"
        ]
        assert len(demote) == 1
        assert demote[0]["tier"] == "summary"
        assert demote[0]["previous_tier"] == "full"

    def test_demote_summary_to_essence(self) -> None:
        """Entry with score >= cool but < warm is demoted to 'essence'."""
        from hermesoptimizer.dreams.sweep import run_sweep

        # importance=0.5, 0 hours ago -> score=0.5 (cool >= 0.3, < 1.0)
        entries = [make_entry("cool", importance=0.5, hours_ago=0.0)]
        result = run_sweep(entries)

        demote = [
            d for d in result["decisions"]
            if d["supermemory_id"] == "cool" and d["action"] == "demote"
        ]
        assert len(demote) == 1
        assert demote[0]["tier"] == "essence"

    def test_essence_entry_that_scores_in_essence_stays_keep(self) -> None:
        """An 'essence' tier entry that still scores in essence range stays kept."""
        from hermesoptimizer.dreams.sweep import run_sweep

        # importance=0.5, 0 hours ago -> score=0.5 (cool)
        entry = make_entry("cool", importance=0.5, hours_ago=0.0)
        # Override tier to 'essence' to reflect the entry's current state in the DB
        entry.fidelity_tier = "essence"
        entries = [entry]
        result = run_sweep(entries)

        # Essence tier + score in essence range -> keep (no reheating in Phase 1)
        keep = [d for d in result["decisions"] if d["action"] == "keep"]
        assert len(keep) == 1

    def test_empty_entries_returns_empty_decisions(self) -> None:
        """run_sweep on empty list returns empty decisions list."""
        from hermesoptimizer.dreams.sweep import run_sweep

        result = run_sweep([])
        assert result["decisions"] == []
        assert result["summary"]["total"] == 0
        assert result["summary"]["pruned"] == 0
        assert result["summary"]["demoted"] == 0
        assert result["summary"]["kept"] == 0

    def test_mixed_entries_produces_correct_counts(self) -> None:
        """A mix of prune/keep/demote entries is counted correctly."""
        from hermesoptimizer.dreams.sweep import run_sweep

        entries = [
            make_entry("hot", importance=3.0, hours_ago=0.0),      # keep full
            make_entry("warm", importance=1.5, hours_ago=0.0),    # demote summary
            make_entry("cool", importance=0.5, hours_ago=0.0),    # demote essence
            make_entry("stale", importance=0.1, hours_ago=500.0),  # prune
        ]
        result = run_sweep(entries)

        assert result["summary"]["total"] == 4
        assert result["summary"]["kept"] == 1
        assert result["summary"]["demoted"] == 2
        assert result["summary"]["pruned"] == 1


# ---------------------------------------------------------------------------
# Tests for adaptive thresholds in sweep
# ---------------------------------------------------------------------------


class TestSweepAdaptiveThresholds:
    """Test that sweep respects memory pressure when making decisions."""

    def test_high_memory_pressure_more_pruning(self) -> None:
        """At 60% injected memory, more entries should be pruned due to raised thresholds."""
        from hermesoptimizer.dreams.sweep import run_sweep

        # importance=2.5 at 0 hours = score ~2.5 (above hot threshold even with timing gap)
        # At 0% pressure: hot=2.0 -> keep full
        # At 60% pressure: hot=2.0*1.5=3.0 -> now warm, demotes to summary
        entries = [make_entry("border", importance=2.5, hours_ago=0.0)]
        result_lo = run_sweep(entries, injected_memory_pct=0.0)
        result_hi = run_sweep(entries, injected_memory_pct=60.0)

        # At low pressure: kept as full (score ~2.5, hot threshold = 2.0)
        lo_action = result_lo["decisions"][0]["action"]
        assert lo_action == "keep"

        # At high pressure: demoted because hot threshold is now 3.0
        hi_action = result_hi["decisions"][0]["action"]
        assert hi_action == "demote"

    def test_100_percent_memory_maximum_pruning(self) -> None:
        """At 100% injected memory, thresholds are 2.5x, making most entries prune candidates."""
        from hermesoptimizer.dreams.sweep import run_sweep

        # importance=1.0, 0 hours ago -> score=1.0
        # At 100% pressure: warm threshold = 1.0 * 2.5 = 2.5, gone = 0.01 * 2.5 = 0.025
        # score=1.0 < 2.5 warm threshold but > 0.025 gone -> demotes to essence
        entries = [make_entry("medium", importance=1.0, hours_ago=0.0)]
        result = run_sweep(entries, injected_memory_pct=100.0)

        assert result["decisions"][0]["action"] == "demote"
        assert result["decisions"][0]["tier"] == "essence"


# ---------------------------------------------------------------------------
# Tests for sweep summary
# ---------------------------------------------------------------------------


class TestSweepSummary:
    """Test that sweep produces a correct summary dict."""

    def test_summary_contains_total_pruned_demoted_kept(self) -> None:
        """Summary tracks all three categories plus total."""
        from hermesoptimizer.dreams.sweep import run_sweep

        entries = [
            make_entry("a", importance=3.0, hours_ago=0.0),
            make_entry("b", importance=0.1, hours_ago=500.0),
        ]
        result = run_sweep(entries)

        assert "total" in result["summary"]
        assert "pruned" in result["summary"]
        assert "demoted" in result["summary"]
        assert "kept" in result["summary"]
        assert "injected_memory_pct" in result["summary"]
        assert "thresholds_used" in result["summary"]

    def test_summary_includes_thresholds_used(self) -> None:
        """Summary records the thresholds that were applied."""
        from hermesoptimizer.dreams.sweep import run_sweep

        entries = [make_entry("a", importance=3.0, hours_ago=0.0)]
        result = run_sweep(entries, injected_memory_pct=60.0)

        thresh = result["summary"]["thresholds_used"]
        assert thresh["hot"] == pytest.approx(3.0)  # 2.0 * 1.5
        assert thresh["warm"] == pytest.approx(1.5)  # 1.0 * 1.5
        assert thresh["cool"] == pytest.approx(0.45)  # 0.3 * 1.5
        assert thresh["gone"] == pytest.approx(0.015)  # 0.01 * 1.5

    def test_summary_sweep_timestamp_present(self) -> None:
        """Summary includes a ISO-format sweep_timestamp."""
        from hermesoptimizer.dreams.sweep import run_sweep

        entries = []
        result = run_sweep(entries)
        assert "sweep_timestamp" in result["summary"]
        assert isinstance(result["summary"]["sweep_timestamp"], str)


# ---------------------------------------------------------------------------
# Phase 1 Review Fix Tests: Deterministic scoring
# --------------------------------------------------------------------------


class TestDeterministicScoring:
    """Test that sweep scoring is deterministic and replayable.

    Issue: sweep_entry_score captured wall-clock time inside per-entry scoring,
    making it non-deterministic and hard to test. Fix: pass now_ts explicitly.
    """

    def test_sweep_entry_score_accepts_now_ts_parameter(self) -> None:
        """sweep_entry_score should accept an optional now_ts parameter."""
        from hermesoptimizer.dreams.sweep import sweep_entry_score

        # Create an entry with known created_at
        entry = make_entry("e1", importance=2.0, hours_ago=0.0)
        # Should accept now_ts as second parameter
        now_ts = entry.created_at  # fixed timestamp
        score = sweep_entry_score(entry, now_ts=now_ts)
        # With hours_ago=0, score should equal importance
        assert score == 2.0

    def test_sweep_entry_score_with_fixed_timestamp_is_deterministic(self) -> None:
        """Score computed with fixed now_ts is reproducible."""
        from hermesoptimizer.dreams.sweep import sweep_entry_score

        entry = make_entry("e1", importance=2.0, hours_ago=100.0)
        created = entry.created_at
        # Simulate scoring at two different moments but with same now_ts
        now_ts = created + int(100 * 3600)  # exactly 100 hours after creation
        score1 = sweep_entry_score(entry, now_ts=now_ts)
        score2 = sweep_entry_score(entry, now_ts=now_ts)
        assert score1 == score2

    def test_run_sweep_is_deterministic(self) -> None:
        """run_sweep should produce identical results when entries haven't changed."""
        from hermesoptimizer.dreams.sweep import run_sweep

        entries = [
            make_entry("a", importance=3.0, hours_ago=0.0),
            make_entry("b", importance=1.5, hours_ago=50.0),
            make_entry("c", importance=0.5, hours_ago=200.0),
        ]
        # Run sweep twice
        result1 = run_sweep(entries, injected_memory_pct=0.0)
        result2 = run_sweep(entries, injected_memory_pct=0.0)
        # Scores and decisions should be identical
        for d1, d2 in zip(result1["decisions"], result2["decisions"]):
            assert d1["score"] == d2["score"]
            assert d1["action"] == d2["action"]
            assert d1["tier"] == d2["tier"]


# ---------------------------------------------------------------------------
# Phase 1 Review Fix Tests: No Phase 3 reheating in scoring
# --------------------------------------------------------------------------


class TestNoReheatingInPhase1:
    """Test that Phase 3 reheating does NOT affect Phase 1 scoring.

    Issue: _reheat_importance was being called inside sweep_entry_score,
    applying recall-based boosting during Phase 1. Reheating should not
    be active yet.
    """

    def test_recall_count_does_not_affect_score(self) -> None:
        """Recall count should not boost the decayed score in Phase 1."""
        from hermesoptimizer.dreams.sweep import sweep_entry_score

        now_ts = int(time.time())
        # Two identical entries, different recall counts
        entry_a = type("Entry", (), {
            "importance": 2.0,
            "recall_count": 0,
            "created_at": now_ts - int(100 * 3600),
            "last_recalled": None,
        })()
        entry_b = type("Entry", (), {
            "importance": 2.0,
            "recall_count": 100,  # lots of recalls
            "created_at": now_ts - int(100 * 3600),
            "last_recalled": None,
        })()
        score_a = sweep_entry_score(entry_a, now_ts=now_ts)
        score_b = sweep_entry_score(entry_b, now_ts=now_ts)
        # Without reheating, both scores should be identical
        assert score_a == score_b


# ---------------------------------------------------------------------------
# Phase 1 Review Fix Tests: gone/prune naming alignment
# --------------------------------------------------------------------------


class TestGonePruneNaming:
    """Test that classify_tier returns 'gone' not 'prune' for the lowest tier.

    Issue: threshold class is 'gone' per DB schema and TODO wording, but
    classify_tier returned 'prune'. The action in sweep decisions should
    reflect 'gone' tier when score < gone threshold.
    """

    def test_classify_tier_returns_gone_not_prune(self) -> None:
        """Score below gone threshold should classify as 'gone', not 'prune'."""
        from hermesoptimizer.dreams.decay import classify_tier

        # Score of 0.0 is below gone threshold (0.01)
        tier = classify_tier(0.0)
        assert tier == "gone", f"Expected 'gone', got '{tier}'"

        # Score of 0.005 is below gone threshold
        tier = classify_tier(0.005)
        assert tier == "gone", f"Expected 'gone', got '{tier}'"

        # Score of 0.009 is below gone threshold
        tier = classify_tier(0.009)
        assert tier == "gone", f"Expected 'gone', got '{tier}'"

    def test_run_sweep_decision_tier_is_gone_for_prune_action(self) -> None:
        """When an entry is pruned, its tier in the decision should be 'gone'."""
        from hermesoptimizer.dreams.sweep import run_sweep

        # importance=0.1, 500 hours ago -> score ~= 0.00067 < 0.01 (gone threshold)
        entries = [make_entry("stale", importance=0.1, hours_ago=500.0)]
        result = run_sweep(entries)

        # Find the prune decision
        prune_decisions = [d for d in result["decisions"] if d["action"] == "prune"]
        assert len(prune_decisions) == 1
        # The tier field should be 'gone', not 'prune'
        assert prune_decisions[0]["tier"] == "gone", f"Expected 'gone', got '{prune_decisions[0]['tier']}'"

    def test_gone_threshold_still_used_for_prune_decisions(self) -> None:
        """Entries below gone threshold should be pruned (action='prune')."""
        from hermesoptimizer.dreams.sweep import run_sweep

        entries = [make_entry("stale", importance=0.1, hours_ago=500.0)]
        result = run_sweep(entries)

        # Action should still be 'prune' - just the tier changes to 'gone'
        prune_decisions = [d for d in result["decisions"] if d["action"] == "prune"]
        assert len(prune_decisions) == 1
        assert prune_decisions[0]["tier"] == "gone"
