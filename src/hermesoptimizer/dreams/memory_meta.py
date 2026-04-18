"""Sidecar SQLite database wrapper for memory metadata.

This module provides a minimal wrapper around ~/.hermes/dreams/memory_meta.db,
tracking per-entry metadata that supermemory doesn't expose.

Schema:
    CREATE TABLE memory_meta (
        supermemory_id TEXT PRIMARY KEY,
        content_hash TEXT NOT NULL,
        importance REAL DEFAULT 1.0,
        created_at INTEGER NOT NULL,
        last_recalled INTEGER,
        recall_count INTEGER DEFAULT 0,
        fidelity_tier TEXT DEFAULT 'full'
    );

All functions accept a db_path parameter so tests can use temp fixtures.
In production, db_path defaults to ~/.hermes/dreams/memory_meta.db.

Bootstrap:
    Use bootstrap_from_entries() to populate initial rows from an injectable
    supermemory source (supermemory_profile + supermemory_search). The
    bootstrap abstraction is intentionally decoupled from Hermes core so this
    module remains testable without network or MCP tool access.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def init_db(db_path: Path | str | None = None) -> None:
    """Initialize the memory_meta.db schema.

    Creates the database file and the memory_meta table if they don't exist.
    Safe to call multiple times (idempotent).

    Args:
        db_path: Path to the SQLite database. Defaults to
            ~/.hermes/dreams/memory_meta.db when None.
    """
    if db_path is None:
        db_path = _default_db_path()

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_meta (
                supermemory_id TEXT PRIMARY KEY,
                content_hash TEXT NOT NULL,
                importance REAL DEFAULT 1.0,
                created_at INTEGER NOT NULL,
                last_recalled INTEGER,
                recall_count INTEGER DEFAULT 0,
                fidelity_tier TEXT DEFAULT 'full'
            )
            """
        )
        conn.commit()


def upsert(
    db_path: Path | str,
    supermemory_id: str,
    content_hash: str,
    importance: float = 1.0,
) -> None:
    """Insert or update a memory_meta entry.

    If supermemory_id already exists, updates content_hash and importance.
    Does not reset recall_count or created_at.

    Args:
        db_path: Path to the SQLite database.
        supermemory_id: Unique identifier from supermemory.
        content_hash: Hash of the entry content for change detection.
        importance: Initial or updated importance score.

    Raises:
        sqlite3.Error: If the database operation fails.
    """
    with sqlite3.connect(_to_path(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO memory_meta (supermemory_id, content_hash, importance, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(supermemory_id) DO UPDATE SET
                content_hash = excluded.content_hash,
                importance = excluded.importance
            """,
            (supermemory_id, content_hash, importance, int(time.time())),
        )
        conn.commit()


def query_by_score(
    db_path: Path | str,
    threshold: float = 0.0,
) -> list[dict[str, Any]]:
    """Query entries with importance >= threshold, ordered by importance desc.

    Args:
        db_path: Path to the SQLite database.
        threshold: Minimum importance score (inclusive). Default 0.0 returns all.

    Returns:
        List of row dictionaries with all schema fields.

    Raises:
        sqlite3.Error: If the database query fails.
    """
    with sqlite3.connect(_to_path(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT supermemory_id, content_hash, importance, created_at,
                   last_recalled, recall_count, fidelity_tier
            FROM memory_meta
            WHERE importance >= ?
            ORDER BY importance DESC
            """,
            (threshold,),
        )
        rows = [dict(row) for row in cursor.fetchall()]
    return rows


def update_recall(db_path: Path | str, supermemory_id: str) -> None:
    """Record a recall event for an entry.

    Increments recall_count and sets last_recalled to the current unix timestamp.

    Args:
        db_path: Path to the SQLite database.
        supermemory_id: The entry to mark as recalled.

    Raises:
        KeyError: If supermemory_id is not found in the database.
        sqlite3.Error: If the database operation fails.
    """
    path = _to_path(db_path)
    with sqlite3.connect(path) as conn:
        cursor = conn.cursor()
        # Check existence first to raise a clear KeyError
        cursor.execute(
            "SELECT 1 FROM memory_meta WHERE supermemory_id = ?",
            (supermemory_id,),
        )
        if cursor.fetchone() is None:
            raise KeyError(supermemory_id)
        now = int(time.time())
        cursor.execute(
            """
            UPDATE memory_meta
            SET recall_count = recall_count + 1,
                last_recalled = ?
            WHERE supermemory_id = ?
            """,
            (now, supermemory_id),
        )
        conn.commit()


def set_fidelity(
    db_path: Path | str,
    supermemory_id: str,
    fidelity_tier: str,
) -> None:
    """Update the fidelity_tier for an entry.

    Valid tiers: 'full', 'summary', 'essence', 'gone'.

    Args:
        db_path: Path to the SQLite database.
        supermemory_id: The entry to update.
        fidelity_tier: New fidelity tier.

    Raises:
        KeyError: If supermemory_id is not found in the database.
        ValueError: If fidelity_tier is not a known tier.
        sqlite3.Error: If the database operation fails.
    """
    valid_tiers = {"full", "summary", "essence", "gone"}
    if fidelity_tier not in valid_tiers:
        raise ValueError(
            f"Invalid fidelity_tier '{fidelity_tier}'. Must be one of: {valid_tiers}"
        )

    path = _to_path(db_path)
    with sqlite3.connect(path) as conn:
        cursor = conn.cursor()
        # Check existence first
        cursor.execute(
            "SELECT 1 FROM memory_meta WHERE supermemory_id = ?",
            (supermemory_id,),
        )
        if cursor.fetchone() is None:
            raise KeyError(supermemory_id)
        cursor.execute(
            """
            UPDATE memory_meta
            SET fidelity_tier = ?
            WHERE supermemory_id = ?
            """,
            (fidelity_tier, supermemory_id),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Phase 3: recall reheating
# ---------------------------------------------------------------------------

REHEAT_BOOST = 0.3
REHEAT_CAP = 5.0


def apply_recall_reheat(
    db_path: Path | str,
    supermemory_id: str,
    boost: float = REHEAT_BOOST,
) -> None:
    """Apply a recall reheating event to an entry.

    For the given supermemory_id:
    - Increment recall_count by 1
    - Set last_recalled to current unix timestamp
    - Boost importance by `boost`, capped at REHEAT_CAP (5.0)

    This function is atomic (single UPDATE statement).

    Args:
        db_path: Path to the SQLite database.
        supermemory_id: The entry to reheat.
        boost: Importance boost amount (default 0.3).

    Raises:
        KeyError: If supermemory_id is not found in the database.
        sqlite3.Error: If the database operation fails.
    """
    path = _to_path(db_path)
    now = int(time.time())
    cap = REHEAT_CAP

    with sqlite3.connect(path) as conn:
        cursor = conn.cursor()
        # Check existence first to raise a clear KeyError
        cursor.execute(
            "SELECT 1 FROM memory_meta WHERE supermemory_id = ?",
            (supermemory_id,),
        )
        if cursor.fetchone() is None:
            raise KeyError(supermemory_id)

        # Atomic update: increment recall_count, set last_recalled,
        # and boost importance with capping
        cursor.execute(
            """
            UPDATE memory_meta
            SET recall_count = recall_count + 1,
                last_recalled = ?,
                importance = MIN(importance + ?, ?)
            WHERE supermemory_id = ?
            """,
            (now, boost, cap, supermemory_id),
        )
        conn.commit()


def bootstrap_from_entries(
    db_path: Path | str,
    entries: list[dict[str, Any]],
) -> None:
    """Insert multiple entries as a one-time bootstrap from supermemory.

    This function is the injectable/bootstrap abstraction described in the
    Phase 0 spec. It accepts a list of entry dictionaries (e.g., from
    supermemory_profile + supermemory_search) and upserts them all.

    Each entry dict should contain:
        - supermemory_id: str (required)
        - content_hash: str (required)
        - importance: float (optional, defaults to 1.0)

    Args:
        db_path: Path to the SQLite database.
        entries: List of supermemory entry dicts to bootstrap.

    Raises:
        sqlite3.Error: If any database operation fails.
    """
    for entry in entries:
        if "supermemory_id" not in entry:
            raise ValueError(
                f"Entry missing required key 'supermemory_id': {entry!r}"
            )
        if "content_hash" not in entry:
            raise ValueError(
                f"Entry missing required key 'content_hash': {entry!r}"
            )
        upsert(
            db_path,
            supermemory_id=entry["supermemory_id"],
            content_hash=entry["content_hash"],
            importance=entry.get("importance", 1.0),
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _default_db_path() -> Path:
    """Return the default database path ~/.hermes/dreams/memory_meta.db."""
    return Path.home() / ".hermes" / "dreams" / "memory_meta.db"


def _to_path(db_path: Path | str) -> Path:
    """Normalise db_path to a Path object."""
    return Path(db_path) if isinstance(db_path, str) else db_path
