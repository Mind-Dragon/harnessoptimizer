#!/usr/bin/env python3
"""Bootstrap probe for the sidecar memory metadata database.

This script demonstrates:
1. Schema creation (init_db)
2. Initial row creation via bootstrap_from_entries (injectable abstraction)
3. Full CRUD cycle: upsert, query_by_score, update_recall, set_fidelity

Usage:
    # Run against the real ~/.hermes/dreams/memory_meta.db (one-time bootstrap):
    python scripts/probe_memory_meta.py --bootstrap

    # Run in probe mode (dry-run against a temp DB, no real ~/.hermes changes):
    python scripts/probe_memory_meta.py --probe

    # Run full demonstration (bootstrap + all operations):
    python scripts/probe_memory_meta.py

Exit codes:
    0 — all operations succeeded
    1 — any operation failed (schema mismatch, DB error, assertion error)

This script is safe to run multiple times — init_db is idempotent and
bootstrap_from_entries uses upsert semantics (insert or update).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add the src directory to the path so we can import hermesoptimizer
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hermesoptimizer.dreams.memory_meta import (
    bootstrap_from_entries,
    init_db,
    query_by_score,
    set_fidelity,
    update_recall,
    upsert,
)


def _print(msg: str) -> None:
    print(msg)


def _probe_with_temp_db() -> bool:
    """Run the full CRUD cycle against a temporary DB (no ~/.hermes touched)."""
    import tempfile

    tmp = Path(tempfile.mkdtemp())
    db_path = tmp / "memory_meta.db"

    _print("\n=== Probe mode: using temp DB at {db_path} ===".format(db_path=db_path))

    # 1. Init schema
    _print("\n[1] init_db()...")
    init_db(db_path)

    # Verify schema
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(memory_meta)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    conn.close()

    expected = {
        "supermemory_id": "TEXT",
        "content_hash": "TEXT",
        "importance": "REAL",
        "created_at": "INTEGER",
        "last_recalled": "INTEGER",
        "recall_count": "INTEGER",
        "fidelity_tier": "TEXT",
    }
    if columns != expected:
        _print("FAIL: schema mismatch")
        _print("  expected: {expected}".format(expected=expected))
        _print("  got:      {got}".format(got=columns))
        return False
    _print("  OK — schema verified")

    # 2. Bootstrap entries
    _print("\n[2] bootstrap_from_entries()...")
    now_ts = int(time.time())
    entries = [
        {
            "supermemory_id": "sm-001",
            "content_hash": "abc123",
            "importance": 2.5,
        },
        {
            "supermemory_id": "sm-002",
            "content_hash": "def456",
            "importance": 1.0,
        },
        {
            "supermemory_id": "sm-003",
            "content_hash": "ghi789",
            "importance": 0.3,
        },
    ]
    bootstrap_from_entries(db_path, entries)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM memory_meta")
    count = cursor.fetchone()[0]
    conn.close()
    if count != 3:
        _print("FAIL: expected 3 rows, got {count}".format(count=count))
        return False
    _print("  OK — 3 rows inserted")

    # 3. Upsert (update existing)
    _print("\n[3] upsert() — update existing row...")
    upsert(db_path, supermemory_id="sm-001", content_hash="abc123-updated", importance=3.0)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT content_hash, importance FROM memory_meta WHERE supermemory_id=?", ("sm-001",))
    row = cursor.fetchone()
    conn.close()
    if row is None or row[0] != "abc123-updated":
        _print("FAIL: upsert did not update content_hash")
        return False
    if row[1] != 3.0:
        _print("FAIL: upsert did not update importance")
        return False
    _print("  OK — upsert verified")

    # 4. Query by score
    _print("\n[4] query_by_score(threshold=1.5)...")
    results = query_by_score(db_path, threshold=1.5)
    ids = {r["supermemory_id"] for r in results}
    if "sm-001" not in ids or "sm-003" in ids:
        _print("FAIL: query_by_score returned wrong entries: {ids}".format(ids=ids))
        return False
    _print("  OK — returned {n} entries above threshold".format(n=len(results)))

    # 5. Update recall
    _print("\n[5] update_recall('sm-001')...")
    update_recall(db_path, "sm-001")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT recall_count, last_recalled FROM memory_meta WHERE supermemory_id=?", ("sm-001",))
    row = cursor.fetchone()
    conn.close()
    if row is None or row[0] != 1:
        _print("FAIL: recall_count != 1")
        return False
    _print("  OK — recall_count=1, last_recalled={ts}".format(ts=row[1]))

    # 6. Set fidelity
    _print("\n[6] set_fidelity('sm-001', 'summary')...")
    set_fidelity(db_path, "sm-001", "summary")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT fidelity_tier FROM memory_meta WHERE supermemory_id=?", ("sm-001",))
    row = cursor.fetchone()
    conn.close()
    if row is None or row[0] != "summary":
        _print("FAIL: fidelity_tier != 'summary'")
        return False
    _print("  OK — fidelity_tier='summary'")

    # 7. Full query dump
    _print("\n[7] Full DB dump...")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM memory_meta ORDER BY importance DESC")
    for row in cursor.fetchall():
        _print("  {d}".format(d=dict(row)))
    conn.close()

    _print("\n=== All probe checks passed ===")
    return True


def _bootstrap_mode(db_path: Path) -> bool:
    """Run bootstrap against the real ~/.hermes/dreams/memory_meta.db.

    This is the one-time bootstrap that populates initial rows from an
    injectable supermemory source (supermemory_profile + supermemory_search).

    Since we don't have network access, we simulate the supermemory entries
    as a demonstration. In production, this would be replaced with actual
    supermemory_profile + supermemory_search calls.
    """
    _print("\n=== Bootstrap mode: populating {db_path} ===".format(db_path=db_path))

    # Ensure ~/.hermes/dreams/ directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Init schema
    _print("\n[1] init_db()...")
    init_db(db_path)
    _print("  OK — schema created at {db_path}".format(db_path=db_path))

    # Simulate supermemory entries (injectable bootstrap abstraction)
    # In production, replace this with actual supermemory_profile + supermemory_search calls
    _print("\n[2] Simulating supermemory bootstrap entries...")
    entries = [
        {
            "supermemory_id": "sm-bootstrap-001",
            "content_hash": "hash_initial_001",
            "importance": 2.0,
        },
        {
            "supermemory_id": "sm-bootstrap-002",
            "content_hash": "hash_initial_002",
            "importance": 1.5,
        },
        {
            "supermemory_id": "sm-bootstrap-003",
            "content_hash": "hash_initial_003",
            "importance": 1.0,
        },
    ]
    _print("  Simulated entries (replace with real supermemory_profile + supermemory_search in production):")
    for e in entries:
        _print("    {id} importance={imp}".format(id=e["supermemory_id"], imp=e["importance"]))

    # Bootstrap
    _print("\n[3] bootstrap_from_entries()...")
    bootstrap_from_entries(db_path, entries)
    _print("  OK — {n} entries bootstrapped".format(n=len(entries)))

    # Verify
    _print("\n[4] Verifying bootstrap...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM memory_meta")
    count = cursor.fetchone()[0]
    conn.close()
    if count != len(entries):
        _print("FAIL: expected {n} rows, got {count}".format(n=len(entries), count=count))
        return False

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM memory_meta ORDER BY importance DESC")
    _print("\n  Bootstrapped entries:")
    for row in cursor.fetchall():
        _print("    {d}".format(d=dict(row)))
    conn.close()

    _print("\n=== Bootstrap complete ===")
    _print("\nNOTE: This was a simulated bootstrap. In production, replace the")
    _print("      entries list in this script with real supermemory_profile")
    _print("      + supermemory_search calls via the Hermes MCP tools.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap probe for the sidecar memory metadata database."
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Run probe mode: full CRUD cycle against a temp DB (no ~/.hermes changes).",
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Run bootstrap mode: populate the real ~/.hermes/dreams/memory_meta.db.",
    )
    args = parser.parse_args()

    if args.probe and args.bootstrap:
        print("ERROR: --probe and --bootstrap are mutually exclusive", file=sys.stderr)
        return 1

    if args.bootstrap:
        db_path = Path.home() / ".hermes" / "dreams" / "memory_meta.db"
        ok = _bootstrap_mode(db_path)
        return 0 if ok else 1

    if args.probe:
        ok = _probe_with_temp_db()
        return 0 if ok else 1

    # Default: probe mode (backwards-compatible default)
    ok = _probe_with_temp_db()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
