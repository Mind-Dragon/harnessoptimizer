"""Central path resolution for hoptimizer runtime files.

Production defaults to ~/.hoptimizer/.
Override with HOPTIMIZER_HOME env var.
Tests should pass explicit paths.
"""
from __future__ import annotations

import os
from pathlib import Path


_ENV_KEY = "HOPTIMIZER_HOME"


def _base() -> Path:
    raw = os.environ.get(_ENV_KEY)
    if raw:
        return Path(raw).expanduser().resolve()
    return Path.home() / ".hoptimizer"


def get_base_dir() -> Path:
    """Return the hoptimizer base directory."""
    return _base()


def get_db_path(name: str = "catalog.db") -> Path:
    """Return path to a database file under ~/.hoptimizer/db/."""
    return _base() / "db" / name


def get_log_dir() -> Path:
    """Return path to the logs directory."""
    return _base() / "logs"


def get_report_dir() -> Path:
    """Return path to the reports directory."""
    return _base() / "reports"


def get_data_dir() -> Path:
    """Return path to the data directory (for packaged resources)."""
    return _base() / "data"


def ensure_dirs() -> None:
    """Create all hoptimizer runtime directories if they don't exist."""
    base = _base()
    (base / "db").mkdir(parents=True, exist_ok=True)
    (base / "logs").mkdir(parents=True, exist_ok=True)
    (base / "reports").mkdir(parents=True, exist_ok=True)
    (base / "data").mkdir(parents=True, exist_ok=True)