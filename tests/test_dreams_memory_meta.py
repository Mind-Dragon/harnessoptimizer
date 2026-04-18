"""Tests for the sidecar memory metadata database (Phase 0).

These tests verify the DB wrapper module that manages ~/.hermes/dreams/memory_meta.db.
All tests use temporary fixture databases to avoid touching the real ~/.hermes directory.

Schema under test:
    supermemory_id TEXT PK,
    content_hash TEXT,
    importance REAL DEFAULT 1.0,
    created_at INTEGER,
    last_recalled INTEGER,
    recall_count INTEGER DEFAULT 0,
    fidelity_tier TEXT DEFAULT 'full'
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Tests for init_db
# ---------------------------------------------------------------------------


def test_init_db_creates_table_with_correct_schema(tmp_path: Path) -> None:
    """init_db creates the memory_meta table with the correct column types."""
    from hermesoptimizer.dreams.memory_meta import init_db

    db_path = tmp_path / "memory_meta.db"
    init_db(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name, type FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    conn.close()

    table_names = [t[0] for t in tables]
    assert table_names == ["memory_meta"]

    # Verify schema
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(memory_meta)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    conn.close()

    assert columns["supermemory_id"] == "TEXT"
    assert columns["content_hash"] == "TEXT"
    assert columns["importance"] == "REAL"
    assert columns["created_at"] == "INTEGER"
    assert columns["last_recalled"] == "INTEGER"
    assert columns["recall_count"] == "INTEGER"
    assert columns["fidelity_tier"] == "TEXT"


def test_init_db_is_idempotent(tmp_path: Path) -> None:
    """Calling init_db twice on the same path does not raise."""
    from hermesoptimizer.dreams.memory_meta import init_db

    db_path = tmp_path / "memory_meta.db"
    init_db(db_path)
    init_db(db_path)  # Should not raise


# ---------------------------------------------------------------------------
# Tests for upsert
# ---------------------------------------------------------------------------


def test_upsert_inserts_new_row(tmp_path: Path) -> None:
    """upsert inserts a new row when supermemory_id is not present."""
    from hermesoptimizer.dreams.memory_meta import init_db, upsert

    db_path = tmp_path / "memory_meta.db"
    init_db(db_path)

    upsert(db_path, supermemory_id="entry-1", content_hash="abc123")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM memory_meta WHERE supermemory_id=?", ("entry-1",))
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row[0] == "entry-1"
    assert row[1] == "abc123"
    assert row[2] == 1.0  # importance default
    assert row[6] == "full"  # fidelity_tier default


def test_upsert_updates_existing_row(tmp_path: Path) -> None:
    """upsert updates an existing row when supermemory_id is already present."""
    from hermesoptimizer.dreams.memory_meta import init_db, upsert

    db_path = tmp_path / "memory_meta.db"
    init_db(db_path)

    upsert(db_path, supermemory_id="entry-1", content_hash="abc123")
    upsert(db_path, supermemory_id="entry-1", content_hash="def456")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT content_hash FROM memory_meta WHERE supermemory_id=?", ("entry-1",))
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row[0] == "def456"


def test_upsert_respects_explicit_importance(tmp_path: Path) -> None:
    """upsert uses the provided importance value when given."""
    from hermesoptimizer.dreams.memory_meta import init_db, upsert

    db_path = tmp_path / "memory_meta.db"
    init_db(db_path)

    upsert(db_path, supermemory_id="entry-1", content_hash="abc123", importance=3.5)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT importance FROM memory_meta WHERE supermemory_id=?", ("entry-1",))
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row[0] == 3.5


# ---------------------------------------------------------------------------
# Tests for query_by_score
# ---------------------------------------------------------------------------


def test_query_by_score_returns_rows_above_threshold(tmp_path: Path) -> None:
    """query_by_score returns entries with importance >= threshold."""
    from hermesoptimizer.dreams.memory_meta import init_db, query_by_score, upsert

    db_path = tmp_path / "memory_meta.db"
    init_db(db_path)

    upsert(db_path, supermemory_id="low", content_hash="h1", importance=0.5)
    upsert(db_path, supermemory_id="mid", content_hash="h2", importance=1.5)
    upsert(db_path, supermemory_id="high", content_hash="h3", importance=3.0)

    results = query_by_score(db_path, threshold=1.5)

    ids = {r["supermemory_id"] for r in results}
    assert "mid" in ids
    assert "high" in ids
    assert "low" not in ids


def test_query_by_score_returns_empty_when_none_match(tmp_path: Path) -> None:
    """query_by_score returns an empty list when nothing meets the threshold."""
    from hermesoptimizer.dreams.memory_meta import init_db, query_by_score, upsert

    db_path = tmp_path / "memory_meta.db"
    init_db(db_path)

    upsert(db_path, supermemory_id="low", content_hash="h1", importance=0.5)

    results = query_by_score(db_path, threshold=2.0)

    assert results == []


def test_query_by_score_returns_all_when_threshold_is_zero(tmp_path: Path) -> None:
    """query_by_score returns all entries when threshold is 0."""
    from hermesoptimizer.dreams.memory_meta import init_db, query_by_score, upsert

    db_path = tmp_path / "memory_meta.db"
    init_db(db_path)

    upsert(db_path, supermemory_id="e1", content_hash="h1", importance=0.5)
    upsert(db_path, supermemory_id="e2", content_hash="h2", importance=1.5)

    results = query_by_score(db_path, threshold=0.0)

    assert len(results) == 2


# ---------------------------------------------------------------------------
# Tests for update_recall
# ---------------------------------------------------------------------------


def test_update_recall_increments_recall_count(tmp_path: Path) -> None:
    """update_recall increments recall_count and updates last_recalled."""
    from hermesoptimizer.dreams.memory_meta import init_db, update_recall, upsert

    db_path = tmp_path / "memory_meta.db"
    init_db(db_path)

    upsert(db_path, supermemory_id="entry-1", content_hash="abc123")

    update_recall(db_path, "entry-1")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT recall_count, last_recalled FROM memory_meta WHERE supermemory_id=?",
        ("entry-1",),
    )
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row[0] == 1
    assert row[1] is not None


def test_update_recall_accumulates_across_calls(tmp_path: Path) -> None:
    """Multiple update_recall calls increment count each time."""
    from hermesoptimizer.dreams.memory_meta import init_db, update_recall, upsert

    db_path = tmp_path / "memory_meta.db"
    init_db(db_path)

    upsert(db_path, supermemory_id="entry-1", content_hash="abc123")

    update_recall(db_path, "entry-1")
    update_recall(db_path, "entry-1")
    update_recall(db_path, "entry-1")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT recall_count FROM memory_meta WHERE supermemory_id=?",
        ("entry-1",),
    )
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row[0] == 3


def test_update_recall_raises_for_unknown_id(tmp_path: Path) -> None:
    """update_recall raises KeyError when supermemory_id is not found."""
    from hermesoptimizer.dreams.memory_meta import init_db, update_recall

    db_path = tmp_path / "memory_meta.db"
    init_db(db_path)

    with pytest.raises(KeyError, match="entry-1"):
        update_recall(db_path, "entry-1")


# ---------------------------------------------------------------------------
# Tests for set_fidelity
# ---------------------------------------------------------------------------


def test_set_fidelity_updates_tier(tmp_path: Path) -> None:
    """set_fidelity changes the fidelity_tier column."""
    from hermesoptimizer.dreams.memory_meta import init_db, set_fidelity, upsert

    db_path = tmp_path / "memory_meta.db"
    init_db(db_path)

    upsert(db_path, supermemory_id="entry-1", content_hash="abc123")
    set_fidelity(db_path, "entry-1", "summary")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT fidelity_tier FROM memory_meta WHERE supermemory_id=?",
        ("entry-1",),
    )
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row[0] == "summary"


def test_set_fidelity_raises_for_unknown_id(tmp_path: Path) -> None:
    """set_fidelity raises KeyError when supermemory_id is not found."""
    from hermesoptimizer.dreams.memory_meta import init_db, set_fidelity

    db_path = tmp_path / "memory_meta.db"
    init_db(db_path)

    with pytest.raises(KeyError, match="entry-1"):
        set_fidelity(db_path, "entry-1", "essence")


def test_set_fidelity_raises_for_invalid_tier(tmp_path: Path) -> None:
    """set_fidelity raises ValueError when fidelity_tier is not a known tier."""
    from hermesoptimizer.dreams.memory_meta import init_db, set_fidelity, upsert

    db_path = tmp_path / "memory_meta.db"
    init_db(db_path)

    upsert(db_path, supermemory_id="entry-1", content_hash="abc123")

    with pytest.raises(ValueError, match="Invalid fidelity_tier"):
        set_fidelity(db_path, "entry-1", "invalid_tier")


# --------------------------------------------------------------------------
# Tests for bootstrap abstraction (injectable supermemory source)
# --------------------------------------------------------------------------


def test_bootstrap_from_entries_inserts_all(tmp_path: Path) -> None:
    """bootstrap_from_entries inserts all provided supermemory entries."""
    from hermesoptimizer.dreams.memory_meta import bootstrap_from_entries, init_db

    db_path = tmp_path / "memory_meta.db"
    init_db(db_path)

    entries = [
        {"supermemory_id": "sm-1", "content_hash": "hash1"},
        {"supermemory_id": "sm-2", "content_hash": "hash2"},
    ]

    bootstrap_from_entries(db_path, entries)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM memory_meta")
    count = cursor.fetchone()[0]
    conn.close()

    assert count == 2


def test_bootstrap_from_entries_uses_default_importance(tmp_path: Path) -> None:
    """Bootstrap sets default importance=1.0 when not provided."""
    from hermesoptimizer.dreams.memory_meta import bootstrap_from_entries, init_db

    db_path = tmp_path / "memory_meta.db"
    init_db(db_path)

    entries = [{"supermemory_id": "sm-1", "content_hash": "hash1"}]
    bootstrap_from_entries(db_path, entries)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT importance FROM memory_meta WHERE supermemory_id=?", ("sm-1",))
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row[0] == 1.0


def test_bootstrap_from_entries_sets_created_at(tmp_path: Path) -> None:
    """Bootstrap sets created_at to current unix timestamp."""
    from hermesoptimizer.dreams.memory_meta import bootstrap_from_entries, init_db

    db_path = tmp_path / "memory_meta.db"
    init_db(db_path)

    before = int(time.time())
    entries = [{"supermemory_id": "sm-1", "content_hash": "hash1"}]
    bootstrap_from_entries(db_path, entries)
    after = int(time.time())

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT created_at FROM memory_meta WHERE supermemory_id=?", ("sm-1",))
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert before <= row[0] <= after


def test_bootstrap_from_entries_raises_for_missing_smemory_id(tmp_path: Path) -> None:
    """bootstrap_from_entries raises ValueError with clear context when supermemory_id is missing."""
    from hermesoptimizer.dreams.memory_meta import bootstrap_from_entries, init_db

    db_path = tmp_path / "memory_meta.db"
    init_db(db_path)

    entries = [{"content_hash": "hash1"}]  # missing supermemory_id

    with pytest.raises(ValueError, match="supermemory_id"):
        bootstrap_from_entries(db_path, entries)


def test_bootstrap_from_entries_raises_for_missing_content_hash(tmp_path: Path) -> None:
    """bootstrap_from_entries raises ValueError with clear context when content_hash is missing."""
    from hermesoptimizer.dreams.memory_meta import bootstrap_from_entries, init_db

    db_path = tmp_path / "memory_meta.db"
    init_db(db_path)

    entries = [{"supermemory_id": "sm-1"}]  # missing content_hash

    with pytest.raises(ValueError, match="content_hash"):
        bootstrap_from_entries(db_path, entries)


# ---------------------------------------------------------------------------
# Tests for bootstrap probe command (integration smoke)
# ---------------------------------------------------------------------------


def test_probe_command_runs_without_error(tmp_path: Path) -> None:
    """A full init + insert + query cycle works end-to-end."""
    from hermesoptimizer.dreams.memory_meta import (
        bootstrap_from_entries,
        init_db,
        query_by_score,
        set_fidelity,
        upsert,
        update_recall,
    )

    db_path = tmp_path / "memory_meta.db"
    init_db(db_path)

    # Bootstrap with initial entries
    entries = [
        {"supermemory_id": "sm-1", "content_hash": "hash1", "importance": 2.0},
        {"supermemory_id": "sm-2", "content_hash": "hash2", "importance": 0.5},
    ]
    bootstrap_from_entries(db_path, entries)

    # Upsert an update
    upsert(db_path, supermemory_id="sm-1", content_hash="hash1-updated", importance=2.5)

    # Update recall
    update_recall(db_path, "sm-1")

    # Set fidelity
    set_fidelity(db_path, "sm-1", "summary")

    # Query
    results = query_by_score(db_path, threshold=1.0)
    assert len(results) == 1
    assert results[0]["supermemory_id"] == "sm-1"
    assert results[0]["content_hash"] == "hash1-updated"
    assert results[0]["importance"] == 2.5
    assert results[0]["fidelity_tier"] == "summary"
    assert results[0]["recall_count"] == 1
