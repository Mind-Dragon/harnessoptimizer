from __future__ import annotations

from pathlib import Path

from hermesoptimizer.catalog import init_db
from hermesoptimizer.paths import get_db_path


def run(db_path: str | Path | None = None) -> None:
    if db_path is None:
        db_path = get_db_path()
    init_db(db_path)
    print(f"hermes mode ready: {db_path}")
