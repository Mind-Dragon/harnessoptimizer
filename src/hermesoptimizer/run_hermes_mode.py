from __future__ import annotations

from pathlib import Path

from hermesoptimizer.catalog import init_db


def run(db_path: str | Path = "catalog.db") -> None:
    init_db(db_path)
    print(f"hermes mode ready: {db_path}")
