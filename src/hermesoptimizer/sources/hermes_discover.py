"""
Phase 0 source discovery for Hermes.

Provides:
- SourceEntry: a single discovered path with type, authority, and existence flag
- SourceInventory: a loaded collection of SourceEntries organized by category
- discover_live_paths(): checks which inventory paths actually exist on the filesystem
- load_inventory(): loads a YAML source inventory file
- classify_path(): guesses the type of a path by its extension/pattern
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class SourceEntry:
    path: str
    type: str
    authoritative: bool = False
    command: str | None = None  # for gateway entries
    exists: bool = False  # set by discover_live_paths

    def expand_path(self) -> str:
        """Expand ~ and environment variables in the path."""
        return os.path.expandvars(os.path.expanduser(self.path))

    def resolve_path(self) -> Path | None:
        """Resolve to a Path, or None if it does not exist."""
        p = Path(self.expand_path())
        return p if p.exists() else None


@dataclass
class SourceInventory:
    sources: dict[str, list[SourceEntry]] = field(default_factory=dict)
    run_marker: str | None = None  # set after a run completes

    def paths_for_category(self, category: str) -> list[SourceEntry]:
        return self.sources.get(category, [])


# ---------------------------------------------------------------------------
# YAML loader
# ---------------------------------------------------------------------------

def _dict_to_entry(d: dict[str, Any]) -> SourceEntry:
    return SourceEntry(
        path=d.get("path", ""),
        type=d.get("type", "unknown"),
        authoritative=d.get("authoritative", False),
        command=d.get("command"),
    )


def load_inventory(path: str | Path) -> SourceInventory:
    """Load a YAML source inventory file."""
    p = Path(path)
    if not p.exists():
        return SourceInventory()
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    sources: dict[str, list[SourceEntry]] = {}
    for category, entries in data.items():
        if not isinstance(entries, list):
            continue
        sources[category] = [_dict_to_entry(e) for e in entries]
    return SourceInventory(sources=sources)


# ---------------------------------------------------------------------------
# Path classification
# ---------------------------------------------------------------------------

_PATH_TYPE_RULES: list[tuple[str, str]] = [
    ("config.yaml", "config"),
    ("config.yml", "config"),
    (".yaml", "config"),
    (".yml", "config"),
    (".json", "session"),   # session files are JSON
    (".log", "log"),
    (".db", "database"),
    ("cache", "cache"),
    ("runtime", "runtime"),
    ("gateway", "gateway"),
]


def classify_path(path: str) -> str:
    """Guess the source type of a path by its string pattern."""
    lowered = path.lower()
    for pattern, category in _PATH_TYPE_RULES:
        if pattern in lowered:
            return category
    return "unknown"


# ---------------------------------------------------------------------------
# Live discovery
# ---------------------------------------------------------------------------

def discover_live_paths(inventory: SourceInventory) -> dict[str, list[SourceEntry]]:
    """
    For each category in the inventory, check which paths actually exist
    on the filesystem and update the `exists` field on each entry.
    Returns a dict of category -> list[SourceEntry] with exists set.
    """
    result: dict[str, list[SourceEntry]] = {}
    for category, entries in inventory.sources.items():
        checked = []
        for entry in entries:
            # gateway entries don't have filesystem paths
            if entry.command:
                e = SourceEntry(
                    path=entry.path,
                    type=entry.type,
                    authoritative=entry.authoritative,
                    command=entry.command,
                    exists=True,  # command existence not checked here
                )
            else:
                expanded = entry.expand_path()
                e = SourceEntry(
                    path=entry.path,
                    type=entry.type,
                    authoritative=entry.authoritative,
                    command=entry.command,
                    exists=Path(expanded).exists(),
                )
            checked.append(e)
        result[category] = checked
    return result
