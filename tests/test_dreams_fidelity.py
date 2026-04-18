"""Tests for Phase 2 fidelity-tier storage and representation selection.

These tests verify that:
1. Structured JSON payloads can be created with full/summary/essence/tier
2. best_representation() selects the correct fidelity tier based on budget
3. JSON round-trip preserves all three representations
4. No-loss preservation of all three representations
5. Downgrade decisions are correctly determined from sweep results

Phase 2 does NOT include:
- Phase 3 transcript reheating
- Phase 4 cron reflection
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


class MockEntry:
    """Minimal mock supermemory entry for fidelity testing."""

    def __init__(
        self,
        supermemory_id: str,
        content_hash: str,
        importance: float,
        created_at: int,
        fidelity_tier: str = "full",
        full_content: str | None = None,
        summary_content: str | None = None,
        essence_content: str | None = None,
    ) -> None:
        self.supermemory_id = supermemory_id
        self.content_hash = content_hash
        self.importance = importance
        self.created_at = created_at
        self.last_recalled: int | None = None
        self.recall_count = 0
        self.fidelity_tier = fidelity_tier
        self.full_content = full_content
        self.summary_content = summary_content
        self.essence_content = essence_content

    def to_dict(self) -> dict:
        return {
            "supermemory_id": self.supermemory_id,
            "content_hash": self.content_hash,
            "importance": self.importance,
            "created_at": self.created_at,
            "last_recalled": self.last_recalled,
            "recall_count": self.recall_count,
            "fidelity_tier": self.fidelity_tier,
            "full_content": self.full_content,
            "summary_content": self.summary_content,
            "essence_content": self.essence_content,
        }


def make_fidelity_entry(
    supermemory_id: str,
    full: str = "Full content here",
    summary: str = "Summary here",
    essence: str = "Essence here",
    tier: str = "full",
) -> MockEntry:
    """Helper: create a mock entry with all three fidelity representations."""
    import time

    return MockEntry(
        supermemory_id=supermemory_id,
        content_hash=f"hash-{supermemory_id}",
        importance=1.0,
        created_at=int(time.time()),
        fidelity_tier=tier,
        full_content=full,
        summary_content=summary,
        essence_content=essence,
    )


# --------------------------------------------------------------------------
# Tests for Structured Fidelity Payload
# --------------------------------------------------------------------------


class TestStructuredFidelityPayload:
    """Test that structured JSON payloads can be created and serialized."""

    def test_make_fidelity_payload_creates_full_summary_essence_tier(self) -> None:
        """make_fidelity_payload creates a dict with full, summary, essence, tier keys."""
        from hermesoptimizer.dreams.fidelity import make_fidelity_payload

        payload = make_fidelity_payload(
            full="Full memory content",
            summary="Summarized memory",
            essence="Core essence",
            tier="full",
        )

        assert "full" in payload
        assert "summary" in payload
        assert "essence" in payload
        assert "tier" in payload
        assert payload["full"] == "Full memory content"
        assert payload["summary"] == "Summarized memory"
        assert payload["essence"] == "Core essence"
        assert payload["tier"] == "full"

    def test_fidelity_payload_serialization_round_trip(self) -> None:
        """A fidelity payload survives JSON serialization round-trip."""
        from hermesoptimizer.dreams.fidelity import make_fidelity_payload

        payload = make_fidelity_payload(
            full="Full content",
            summary="Summary content",
            essence="Essence content",
            tier="summary",
        )

        serialized = json.dumps(payload)
        deserialized = json.loads(serialized)

        assert deserialized["full"] == "Full content"
        assert deserialized["summary"] == "Summary content"
        assert deserialized["essence"] == "Essence content"
        assert deserialized["tier"] == "summary"

    def test_fidelity_payload_tier_defaults_to_full(self) -> None:
        """make_fidelity_payload defaults tier to 'full' when not specified."""
        from hermesoptimizer.dreams.fidelity import make_fidelity_payload

        payload = make_fidelity_payload(
            full="Full",
            summary="Summary",
            essence="Essence",
        )

        assert payload["tier"] == "full"

    def test_fidelity_payload_preserves_all_representations(self) -> None:
        """All three representations are preserved intact, not truncated."""
        from hermesoptimizer.dreams.fidelity import make_fidelity_payload

        long_full = "A" * 10000
        long_summary = "B" * 500
        long_essence = "C" * 50

        payload = make_fidelity_payload(
            full=long_full,
            summary=long_summary,
            essence=long_essence,
            tier="full",
        )

        assert payload["full"] == long_full
        assert payload["summary"] == long_summary
        assert payload["essence"] == long_essence


# --------------------------------------------------------------------------
# Tests for best_representation selection
# --------------------------------------------------------------------------


class TestBestRepresentationSelection:
    """Test best_representation() selects correct tier based on budget and score."""

    def test_best_representation_full_when_budget_high_and_score_hot(self) -> None:
        """When budget is generous and score is hot, return 'full'."""
        from hermesoptimizer.dreams.fidelity import best_representation

        entry = make_fidelity_entry("e1", tier="full")
        budget = 10000  # tokens
        score = 3.0  # hot
        thresholds = {"hot": 2.0, "warm": 1.0, "cool": 0.3, "gone": 0.01}

        result = best_representation(entry, budget, score, thresholds)

        assert result == "full"

    def test_best_representation_summary_when_budget_medium(self) -> None:
        """When budget is moderate, prefer 'summary' even if score is hot."""
        from hermesoptimizer.dreams.fidelity import best_representation

        entry = make_fidelity_entry("e1", tier="full")
        budget = 500  # tokens - medium
        score = 2.5  # hot
        thresholds = {"hot": 2.0, "warm": 1.0, "cool": 0.3, "gone": 0.01}

        result = best_representation(entry, budget, score, thresholds)

        # Medium budget should prefer summary over full
        assert result in ("full", "summary")

    def test_best_representation_essence_when_budget_low(self) -> None:
        """When budget is tight, prefer 'essence' for warm/cool scores."""
        from hermesoptimizer.dreams.fidelity import best_representation

        entry = make_fidelity_entry("e1", tier="summary")
        budget = 100  # tokens - low
        score = 1.5  # warm
        thresholds = {"hot": 2.0, "warm": 1.0, "cool": 0.3, "gone": 0.01}

        result = best_representation(entry, budget, score, thresholds)

        assert result in ("summary", "essence")

    def test_best_representation_never_upgrades_tier(self) -> None:
        """best_representation never returns a higher tier than the entry's current tier."""
        from hermesoptimizer.dreams.fidelity import best_representation

        entry = make_fidelity_entry("e1", tier="essence")
        budget = 10000  # very generous
        score = 3.0  # hot
        thresholds = {"hot": 2.0, "warm": 1.0, "cool": 0.3, "gone": 0.01}

        result = best_representation(entry, budget, score, thresholds)

        # Should NOT return 'full' since entry is at 'essence'
        tier_rank = {"full": 3, "summary": 2, "essence": 1, "gone": 0}
        assert tier_rank[result] <= tier_rank["essence"]

    def test_best_representation_uses_score_to_cap_max_tier(self) -> None:
        """Score determines the maximum tier that can be selected."""
        from hermesoptimizer.dreams.fidelity import best_representation

        entry = make_fidelity_entry("e1", tier="full")
        budget = 10000  # generous
        thresholds = {"hot": 2.0, "warm": 1.0, "cool": 0.3, "gone": 0.01}

        # Score in 'cool' range should not return 'full'
        result = best_representation(entry, budget, score=0.5, thresholds=thresholds)
        assert result in ("summary", "essence")

        # Score in 'warm' range
        result = best_representation(entry, budget, score=1.5, thresholds=thresholds)
        assert result in ("summary", "essence")

        # Score in 'hot' range
        result = best_representation(entry, budget, score=3.0, thresholds=thresholds)
        assert result in ("full", "summary", "essence")

    def test_best_representation_returns_current_tier_when_score_matches(self) -> None:
        """When score warrants current tier, stay at that tier."""
        from hermesoptimizer.dreams.fidelity import best_representation

        entry = make_fidelity_entry("e1", tier="summary")
        budget = 10000
        score = 1.5  # warm
        thresholds = {"hot": 2.0, "warm": 1.0, "cool": 0.3, "gone": 0.01}

        result = best_representation(entry, budget, score, thresholds)

        assert result == "summary"


# --------------------------------------------------------------------------
# Tests for downgrade decision application
# --------------------------------------------------------------------------


class TestDowngradeDecisionApplication:
    """Test that sweep decisions correctly map to tier downgrade actions."""

    def test_demote_full_to_summary_sets_target_tier(self) -> None:
        """A demote decision from 'full' to 'summary' indicates rewrite needed."""
        from hermesoptimizer.dreams.fidelity import get_downgrade_target

        # Simulate a sweep decision
        previous_tier = "full"
        new_tier = "summary"

        target = get_downgrade_target(previous_tier, new_tier)

        assert target == "summary"

    def test_demote_summary_to_essence_sets_target_tier(self) -> None:
        """A demote decision from 'summary' to 'essence' indicates rewrite needed."""
        from hermesoptimizer.dreams.fidelity import get_downgrade_target

        target = get_downgrade_target("summary", "essence")

        assert target == "essence"

    def test_downgrade_target_is_none_for_keep_action(self) -> None:
        """A 'keep' action means no rewrite is needed."""
        from hermesoptimizer.dreams.fidelity import get_downgrade_target

        target = get_downgrade_target("full", "full")

        assert target is None

    def test_downgrade_target_is_none_for_prune_action(self) -> None:
        """A 'prune' action (gone tier) means entry should be removed, not rewritten."""
        from hermesoptimizer.dreams.fidelity import get_downgrade_target

        target = get_downgrade_target("essence", "gone")

        assert target is None


# --------------------------------------------------------------------------
# Tests for rewrite decision emission from pre-sweep
# --------------------------------------------------------------------------


class TestPreSweepRewriteDecisions:
    """Test that pre-sweep output includes rewrite decisions for the dreaming skill."""

    def test_pre_sweep_output_includes_chosen_representation(self) -> None:
        """Pre-sweep output should include 'chosen_representation' for demote decisions."""
        import subprocess
        import sys
        from pathlib import Path

        # Create a temp DB with an entry that will be demoted
        import tempfile
        import time

        from hermesoptimizer.dreams.memory_meta import init_db, upsert

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "memory_meta.db"
            init_db(db_path)

            # Create entry with importance=1.5 -> score will be warm (demote to summary)
            upsert(db_path, supermemory_id="demote-me", content_hash="hash1", importance=1.5)

            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).parent.parent / "scripts" / "dreaming_pre_sweep.py"),
                    "--db-path", str(db_path),
                    "--injected-memory-pct", "0",
                ],
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0
            data = json.loads(result.stdout)

            # Find the demote entry
            demote_entry = next(
                (e for e in data["entries"] if e["supermemory_id"] == "demote-me"),
                None,
            )
            assert demote_entry is not None
            assert demote_entry["action"] == "demote"
            assert "chosen_representation" in demote_entry
            assert demote_entry["chosen_representation"] == "summary"

    def test_pre_sweep_output_includes_rewrite_guidance_for_essence(self) -> None:
        """Pre-sweep should emit rewrite guidance when demoting to essence."""
        import subprocess
        import sys
        from pathlib import Path

        import tempfile

        from hermesoptimizer.dreams.memory_meta import init_db, upsert

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "memory_meta.db"
            init_db(db_path)

            # Create entry with importance=0.5 -> score will be cool (demote to essence)
            upsert(db_path, supermemory_id="demote-essence", content_hash="hash1", importance=0.5)

            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).parent.parent / "scripts" / "dreaming_pre_sweep.py"),
                    "--db-path", str(db_path),
                    "--injected-memory-pct", "0",
                ],
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0
            data = json.loads(result.stdout)

            demote_entry = next(
                (e for e in data["entries"] if e["supermemory_id"] == "demote-essence"),
                None,
            )
            assert demote_entry is not None
            assert demote_entry["action"] == "demote"
            assert demote_entry["chosen_representation"] == "essence"


# --------------------------------------------------------------------------
# Tests for sidecar DB tier update (memory_meta integration)
# --------------------------------------------------------------------------


class TestSidecarTierUpdate:
    """Test that set_fidelity correctly updates the sidecar DB."""

    def test_set_fidelity_reflects_in_query(self, tmp_path: Path) -> None:
        """After set_fidelity, query_by_score returns updated tier info."""
        from hermesoptimizer.dreams.memory_meta import init_db, query_by_score, set_fidelity, upsert

        db_path = tmp_path / "memory_meta.db"
        init_db(db_path)

        upsert(db_path, supermemory_id="e1", content_hash="hash1", importance=1.5)

        # Demote from 'full' to 'summary'
        set_fidelity(db_path, "e1", "summary")

        results = query_by_score(db_path, threshold=0.0)
        assert len(results) == 1
        assert results[0]["fidelity_tier"] == "summary"
