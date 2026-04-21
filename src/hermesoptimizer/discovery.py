"""Discover Hermes session and log files from known locations."""
from __future__ import annotations

from pathlib import Path


def discover_hermes_surfaces() -> list[Path]:
    """Scan known Hermes directories for session/log files.

    Scans:
    - ~/.hermes/sessions
    - ~/.hermes/logs
    - ~/.config/hermes/sessions
    - ~/.config/hermes/logs

    Returns list of .json, .yaml, .log files found.
    """
    candidates: list[Path] = [
        Path.home() / ".hermes" / "sessions",
        Path.home() / ".hermes" / "logs",
        Path.home() / ".config" / "hermes" / "sessions",
        Path.home() / ".config" / "hermes" / "logs",
    ]

    found: list[Path] = []
    for directory in candidates:
        if not directory.is_dir():
            continue
        for ext in ("*.json", "*.yaml", "*.log"):
            found.extend(directory.rglob(ext))

    return sorted(found)
