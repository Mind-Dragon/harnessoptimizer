"""Database lifecycle CLI handlers."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from hermesoptimizer.paths import get_db_path


HANDLERS: dict[str, Callable[[argparse.Namespace], int]] = {}


def add_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Register db subcommands under the given subparsers action."""
    # db-vacuum
    vacuum = subparsers.add_parser("db-vacuum", help="Reclaim SQLite DB space")
    vacuum.add_argument("--db", default=str(get_db_path()))
    vacuum.set_defaults(handler=handle_db_vacuum)
    HANDLERS["db-vacuum"] = handle_db_vacuum

    # db-retention
    retention = subparsers.add_parser("db-retention", help="Prune old catalog data")
    retention.add_argument("--db", default=str(get_db_path()))
    retention.add_argument(
        "--days", type=int, default=30, help="Keep data newer than N days"
    )
    retention.set_defaults(handler=handle_db_retention)
    HANDLERS["db-retention"] = handle_db_retention

    # db-stats
    stats = subparsers.add_parser("db-stats", help="Show catalog DB statistics")
    stats.add_argument("--db", default=str(get_db_path()))
    stats.set_defaults(handler=handle_db_stats)
    HANDLERS["db-stats"] = handle_db_stats


def handle_db_vacuum(args: argparse.Namespace) -> int:
    """Reclaim SQLite DB space by running VACUUM."""
    db_path = args.db
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("VACUUM;")
        conn.close()
        print(f"Vacuumed {db_path}")
        return 0
    except Exception as e:
        print(f"Error vacuuming {db_path}: {e}", file=sys.stderr)
        return 1


def handle_db_retention(args: argparse.Namespace) -> int:
    """Prune old catalog data based on retention policy."""
    db_path = args.db
    days = args.days

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Delete old findings
        cursor.execute(
            "DELETE FROM findings WHERE created_at < datetime('now', '-{} days')".format(
                days
            )
        )
        findings_deleted = cursor.rowcount

        # Delete old runs
        cursor.execute(
            "DELETE FROM runs WHERE started_at < datetime('now', '-{} days')".format(
                days
            )
        )
        runs_deleted = cursor.rowcount

        conn.commit()
        conn.close()

        print(f"Pruned {days} days of data from {db_path}")
        print(f"  Findings deleted: {findings_deleted}")
        print(f"  Runs deleted: {runs_deleted}")
        return 0
    except Exception as e:
        print(f"Error pruning {db_path}: {e}", file=sys.stderr)
        return 1


def handle_db_stats(args: argparse.Namespace) -> int:
    """Show catalog DB statistics."""
    db_path = args.db

    try:
        db_file = Path(db_path)
        if not db_file.exists():
            print(f"Database not found: {db_path}")
            return 1

        db_size = db_file.stat().st_size

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        print(f"Database: {db_path}")
        print(f"Size: {db_size:,} bytes")
        print()
        print(f"{'Table':<20} {'Rows':>10}")
        print("-" * 31)

        for table in tables:
            try:
                cursor.execute(f"SELECT count(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"{table:<20} {count:>10,}")
            except Exception:
                print(f"{table:<20} {'N/A':>10}")

        conn.close()
        return 0
    except Exception as e:
        print(f"Error reading stats from {db_path}: {e}", file=sys.stderr)
        return 1
