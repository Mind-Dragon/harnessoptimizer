"""Hermes Optimizer Dreams package — v0.9.0 memory consolidation sidecar.

This package contains:
- memory_meta: Sidecar SQLite database wrapper for tracking per-entry metadata
- decay: Exponential decay scoring and threshold classification (Phase 1)
- sweep: Dreaming sweep logic -- scores entries, produces prune/demote/keep decisions (Phase 1)
- fidelity: Structured fidelity-tier storage and best_representation selection (Phase 2)
- recall: Transcript parsing, recall_log fallback, and DB reheating (Phase 3)

No Hermes core changes — all work happens in scripts, skills, and this
sidecar database.
"""

from __future__ import annotations

from .decay import (
    classify_tier,
    decay_score,
    get_adaptive_thresholds,
)
from .fidelity import (
    best_representation,
    get_active_content,
    get_downgrade_target,
    is_downgrade,
    make_fidelity_payload,
    parse_fidelity_payload,
)
from .memory_meta import (
    apply_recall_reheat,
    bootstrap_from_entries,
    init_db,
    query_by_score,
    set_fidelity,
    update_recall,
    upsert,
)
from .recall import (
    append_recall_log_entry,
    compute_reheated_importance,
    parse_session_transcript,
    read_recall_log,
    read_recall_log_ids,
    reheat_recalled_ids,
    scan_sessions_directory,
)
from .sweep import run_sweep, sweep_entry_score

__all__ = [
    # memory_meta (Phase 0)
    "apply_recall_reheat",
    "bootstrap_from_entries",
    "init_db",
    "query_by_score",
    "set_fidelity",
    "update_recall",
    "upsert",
    # decay (Phase 1)
    "classify_tier",
    "decay_score",
    "get_adaptive_thresholds",
    # sweep (Phase 1)
    "run_sweep",
    "sweep_entry_score",
    # fidelity (Phase 2)
    "best_representation",
    "get_active_content",
    "get_downgrade_target",
    "is_downgrade",
    "make_fidelity_payload",
    "parse_fidelity_payload",
    # recall (Phase 3)
    "append_recall_log_entry",
    "compute_reheated_importance",
    "parse_session_transcript",
    "read_recall_log",
    "read_recall_log_ids",
    "reheat_recalled_ids",
    "scan_sessions_directory",
]
