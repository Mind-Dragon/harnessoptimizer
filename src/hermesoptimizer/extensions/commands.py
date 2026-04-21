"""CLI handlers for extension management commands."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hermesoptimizer.extensions import build_registry
from hermesoptimizer.extensions.schema import Ownership


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def handle_ext_list(args: argparse.Namespace) -> int:
    """List all registered extensions."""
    registry_dir = _repo_root() / "extensions"
    if not registry_dir.exists():
        print("No extensions directory found.", file=sys.stderr)
        return 1

    entries = build_registry(registry_dir)
    for entry in entries:
        status = "ok"
        if entry.ownership != Ownership.EXTERNAL_RUNTIME:
            if not entry.source_exists(_repo_root()):
                status = "missing_source"
        print(f"{entry.id:20} {entry.type.value:18} {entry.ownership.value:18} {status}")
    return 0
