"""Phase 1 dreaming sweep: decay scoring, tier demotion, and pruning.

This module provides the sweep logic that scores all memory entries using
the exponential decay formula, classifies them into fidelity tiers, and
produces a decision list (prune/demote/keep) plus a summary.

Sweep operates on in-memory entry dicts compatible with the sidecar DB
schema from memory_meta.py. It does NOT call supermemory directly --
the caller is responsible for reading entries and applying decisions.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from .decay import classify_tier, decay_score, get_adaptive_thresholds


# ---------------------------------------------------------------------------
# Reheat boost (from Phase 3 spec -- included here so sweep can apply it)
# ---------------------------------------------------------------------------

REHEAT_BOOST = 0.3
REHEAT_CAP = 5.0


def _reheat_importance(importance: float, recall_count: int) -> float:
    """Apply a recall reheating boost to importance.

    More recalls = higher effective importance. Each recall adds REHEAT_BOOST
    but the boost diminishes and is capped at REHEAT_CAP.

    Args:
        importance: Current importance value from the DB.
        recall_count: Number of times this entry was recalled.

    Returns:
        Reheated importance (capped at REHEAT_CAP).
    """
    if recall_count <= 0:
        return importance
    # Diminishing boost: sqrt(recall_count) * REHEAT_BOOST
    boost = (recall_count ** 0.5) * REHEAT_BOOST
    return min(importance + boost, REHEAT_CAP)


def _get_entry_value(entry: dict[str, Any] | object, key: str, default: Any = None) -> Any:
    """Get a value from an entry dict or object with attribute/key access."""
    if isinstance(entry, dict):
        return entry.get(key, default)
    return getattr(entry, key, default)


# ---------------------------------------------------------------------------
# Entry scoring
# ---------------------------------------------------------------------------


def sweep_entry_score(
    entry: dict[str, Any] | object,
    now_ts: float | None = None,
) -> float:
    """Compute the decayed score for a single entry.

    Uses the entry's importance and computes hours_since_access from
    created_at or last_recalled. A fixed now_ts can be passed for
    deterministic/replayable scoring.

    Args:
        entry: Entry dict or object with attributes: importance, created_at,
            last_recalled (may be None), recall_count.
        now_ts: Fixed Unix timestamp to use as "now". If None, uses current time.
            Passing a fixed now_ts makes scoring deterministic and testable.

    Returns:
        Decayed score (>= 0).
    """
    importance = float(_get_entry_value(entry, "importance", 1.0))

    # Phase 1: no reheating - recall_count does not affect score
    # (reheating is Phase 3 feature, not active in Phase 1 scoring)

    # Compute hours since last access
    if now_ts is None:
        now_ts = time.time()
    last_accessed = _get_entry_value(entry, "last_recalled") or _get_entry_value(entry, "created_at", now_ts)
    hours_since_access = (now_ts - last_accessed) / 3600.0

    return decay_score(importance, hours_since_access)


# ---------------------------------------------------------------------------
# Sweep logic
# ---------------------------------------------------------------------------


def run_sweep(
    entries: list[dict[str, Any]],
    injected_memory_pct: float = 0.0,
) -> dict[str, Any]:
    """Run the dreaming sweep over a list of memory entries.

    Scores every entry, classifies it into a fidelity tier, and produces
    a decision: 'prune', 'demote', or 'keep'.

    Prune: score < gone threshold (entry is forgotten).
    Demote: entry is in a higher tier than its score warrants.
    Keep: entry's tier matches its score classification.

    Args:
        entries: List of entry dicts with supermemory_id, importance,
            created_at, last_recalled, recall_count, fidelity_tier.
        injected_memory_pct: Current injected memory fill percentage (0-100).
            Used for adaptive threshold scaling.

    Returns:
        Dict with:
            - decisions: list of dicts with supermemory_id, action, previous_tier,
              tier, score
            - summary: dict with total, pruned, demoted, kept, injected_memory_pct,
              thresholds_used, sweep_timestamp
    """
    thresholds = get_adaptive_thresholds(injected_memory_pct)
    decisions: list[dict[str, Any]] = []
    now_ts = int(time.time())

    pruned_count = 0
    demoted_count = 0
    kept_count = 0

    for entry in entries:
        sm_id = _get_entry_value(entry, "supermemory_id", "unknown")
        previous_tier = _get_entry_value(entry, "fidelity_tier", "full")
        score = sweep_entry_score(entry, now_ts=now_ts)
        tier = classify_tier(score, injected_memory_pct)

        if tier == "gone":
            decisions.append({
                "supermemory_id": sm_id,
                "action": "prune",
                "previous_tier": previous_tier,
                "tier": "gone",
                "score": score,
            })
            pruned_count += 1
        elif tier == previous_tier:
            # Tier matches score classification -> keep
            decisions.append({
                "supermemory_id": sm_id,
                "action": "keep",
                "previous_tier": previous_tier,
                "tier": tier,
                "score": score,
            })
            kept_count += 1
        else:
            # Tier demotion needed
            decisions.append({
                "supermemory_id": sm_id,
                "action": "demote",
                "previous_tier": previous_tier,
                "tier": tier,
                "score": score,
            })
            demoted_count += 1

    summary = {
        "total": len(entries),
        "pruned": pruned_count,
        "demoted": demoted_count,
        "kept": kept_count,
        "injected_memory_pct": injected_memory_pct,
        "thresholds_used": thresholds,
        "sweep_timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return {"decisions": decisions, "summary": summary}
