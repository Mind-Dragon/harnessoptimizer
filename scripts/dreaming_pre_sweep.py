#!/usr/bin/env python3
"""Dreaming pre-sweep script — Phase 1 exponential decay scoring.

Reads all entries from ~/.hermes/dreams/memory_meta.db, runs the decay sweep,
and outputs a JSON summary to stdout. This script is designed to run as
the `script` field of a Hermes cron job before the dreaming skill prompt.

Phase 3 adds recall reheating: before running the sweep, the script can
scan session transcripts and/or recall_log.jsonl for recall signals, then
apply importance boosts to the sidecar DB so the sweep sees updated scores.

Usage:
    python scripts/dreaming_pre_sweep.py
    python scripts/dreaming_pre_sweep.py --db-path /path/to/memory_meta.db
    python scripts/dreaming_pre_sweep.py --injected-memory-pct 55

Phase 3 (recall reheating):
    python scripts/dreaming_pre_sweep.py --reheat --sessions-dir ~/.hermes/sessions
    python scripts/dreaming_pre_sweep.py --reheat --recall-log ~/.hermes/dreams/recall_log.jsonl
    python scripts/dreaming_pre_sweep.py --reheat --recall-ids ID-ABC ID-DEF

Output format:
    {
      "phase": "pre-sweep",
      "version": "0.7.0-phase3",
      "entry_count": N,
      "injected_memory_pct": M,
      "decisions_summary": {"total": N, "pruned": P, "demoted": D, "kept": K},
      "thresholds_used": {"hot": H, "warm": W, "cool": C, "gone": G},
      "sweep_timestamp": "ISO-8601",
      "reheat_stats": {"reheated": R, "skipped": S},  <-- Phase 3 only when --reheat
      "entries": [
        {
          "supermemory_id": "...",
          "action": "keep|demote|prune",
          "previous_tier": "full|summary|essence",
          "tier": "...",
          "score": 0.XX
        },
        ...
      ]
    }

This script is Phase 1 only by default — reheating is opt-in.
The calling agent is responsible for applying decisions (forgetting pruned entries,
updating fidelity tiers in the sidecar DB).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add src to path for imports during development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hermesoptimizer.dreams import (
    get_adaptive_thresholds,
    reheat_recalled_ids,
    run_sweep,
)
from hermesoptimizer.dreams.fidelity import best_representation, get_downgrade_target
from hermesoptimizer.dreams.recall import (
    DEFAULT_RECALL_LOG,
    DEFAULT_SESSIONS_DIR,
    read_recall_log_ids,
    scan_sessions_directory,
)


def _load_entries_from_db(db_path: Path) -> list[dict]:
    """Load all entries from the sidecar memory_meta.db."""
    if not db_path.exists():
        return []

    entries: list[dict] = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT supermemory_id, content_hash, importance, created_at,
                   last_recalled, recall_count, fidelity_tier
            FROM memory_meta
            """
        )
        for row in cursor.fetchall():
            entries.append(dict(row))
    return entries


def _format_output(
    entries: list[dict],
    injected_memory_pct: float,
    decisions: list[dict],
    summary: dict,
    thresholds: dict[str, float],
    phase_version: str = "0.7.0-phase2",
) -> dict:
    """Format the sweep result as a JSON-serializable dict.

    For demote decisions, includes 'chosen_representation' indicating which
    fidelity tier should be written to supermemory.
    """
    formatted_entries = []
    for d in decisions:
        entry_info = {
            "supermemory_id": d["supermemory_id"],
            "action": d["action"],
            "previous_tier": d["previous_tier"],
            "tier": d["tier"],
            "score": round(d["score"], 6),
        }

        # Add rewrite guidance for demote actions
        if d["action"] == "demote":
            target = get_downgrade_target(d["previous_tier"], d["tier"])
            if target is not None:
                # Phase 2: use best_representation with a default budget
                # The dreaming skill can override this based on actual token budget
                # Default budget of 500 tokens assumes summary fits
                chosen = best_representation(
                    entry={},  # empty entry - will use default estimates
                    budget=500,
                    score=d["score"],
                    thresholds=thresholds,
                )
                # Cap at the target tier (demotion target)
                tier_rank = {"full": 3, "summary": 2, "essence": 1}
                if tier_rank.get(chosen, 0) > tier_rank.get(target, 0):
                    chosen = target
                entry_info["chosen_representation"] = chosen
                entry_info["rewrite_to_tier"] = target

        formatted_entries.append(entry_info)

    return {
        "phase": "pre-sweep",
        "version": phase_version,
        "entry_count": len(entries),
        "injected_memory_pct": injected_memory_pct,
        "decisions_summary": {
            "total": summary["total"],
            "pruned": summary["pruned"],
            "demoted": summary["demoted"],
            "kept": summary["kept"],
        },
        "thresholds_used": summary["thresholds_used"],
        "sweep_timestamp": summary["sweep_timestamp"],
        "entries": formatted_entries,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dreaming pre-sweep: decay scoring and tier classification."
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path.home() / ".hermes" / "dreams" / "memory_meta.db",
        help="Path to memory_meta.db (default: ~/.hermes/dreams/memory_meta.db)",
    )
    parser.add_argument(
        "--injected-memory-pct",
        type=float,
        default=0.0,
        help="Current injected memory fill percentage (0-100). "
             "Above 40%%, thresholds scale proportionally.",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=None,
        help="Only include entries with score >= this threshold in output.",
    )
    # Phase 3: recall reheating options
    parser.add_argument(
        "--reheat",
        action="store_true",
        help="Enable recall reheating before sweep (Phase 3).",
    )
    parser.add_argument(
        "--sessions-dir",
        type=Path,
        default=None,
        help="Path to session transcripts directory "
             "(default: ~/.hermes/sessions). Only used when --reheat is set.",
    )
    parser.add_argument(
        "--recall-log",
        type=Path,
        default=None,
        help="Path to recall_log.jsonl fallback file "
             "(default: ~/.hermes/dreams/recall_log.jsonl). Only used when --reheat is set.",
    )
    parser.add_argument(
        "--recall-ids",
        nargs="*",
        default=None,
        help="Explicit list of supermemory IDs to reheat. Only used when --reheat is set.",
    )
    args = parser.parse_args()

    # Phase 3: run recall reheating if enabled
    reheat_stats = {"reheated": 0, "skipped": 0}
    if args.reheat:
        # Collect recalled IDs from all sources (priority: explicit IDs > sessions > recall_log)
        recalled_ids: list[str] = []

        if args.recall_ids:
            # Explicit IDs take priority
            recalled_ids = args.recall_ids
        else:
            # Scan sessions directory
            sessions_dir = args.sessions_dir or DEFAULT_SESSIONS_DIR
            ids_from_sessions = scan_sessions_directory(sessions_dir)
            recalled_ids.extend(ids_from_sessions)

            # Fall back to recall_log if no IDs found from sessions
            if not recalled_ids:
                recall_log_path = args.recall_log or DEFAULT_RECALL_LOG
                ids_from_log = read_recall_log_ids(recall_log_path)
                recalled_ids.extend(ids_from_log)

        # Apply reheating to the DB
        if recalled_ids:
            reheat_stats = reheat_recalled_ids(args.db_path, recalled_ids)

    entries = _load_entries_from_db(args.db_path)

    # Determine phase version: Phase 3 reheating changes the version string
    phase_version = "0.7.0-phase3" if args.reheat else "0.7.0-phase2"

    thresholds = get_adaptive_thresholds(args.injected_memory_pct)
    if not entries:
        output = {
            "phase": "pre-sweep",
            "version": phase_version,
            "entry_count": 0,
            "injected_memory_pct": args.injected_memory_pct,
            "decisions_summary": {"total": 0, "pruned": 0, "demoted": 0, "kept": 0},
            "thresholds_used": thresholds,
            "sweep_timestamp": datetime.now(timezone.utc).isoformat(),
            "entries": [],
        }
        print(json.dumps(output, indent=2))
        return

    result = run_sweep(entries, injected_memory_pct=args.injected_memory_pct)
    output = _format_output(
        entries,
        args.injected_memory_pct,
        result["decisions"],
        result["summary"],
        thresholds,
        phase_version,
    )

    if args.min_score is not None:
        output["entries"] = [
            e for e in output["entries"] if e["score"] >= args.min_score
        ]

    # Phase 3: include reheat stats when reheating was enabled
    if args.reheat:
        output["reheat_stats"] = reheat_stats

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
