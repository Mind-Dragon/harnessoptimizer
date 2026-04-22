"""Resolve the extension registry directory.

In editable installs the YAML files live at <repo_root>/extensions/.
In wheel installs they live inside the package at extensions/data/.
"""

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    """Return the repo root (works only in editable installs)."""
    return Path(__file__).resolve().parents[3]


def registry_dir() -> Path:
    """Return the extensions registry directory.

    Prefers the packaged data directory (works in wheels).
    Falls back to repo-root extensions/ (works in editable installs).
    """
    packaged = Path(__file__).resolve().parent / "data"
    if packaged.is_dir():
        return packaged
    repo = _repo_root() / "extensions"
    if repo.is_dir():
        return repo
    raise FileNotFoundError(
        "Cannot find extensions registry directory. "
        f"Checked {packaged} and {repo}."
    )
