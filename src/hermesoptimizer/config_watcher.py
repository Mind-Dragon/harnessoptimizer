"""Config watcher: detect config file changes, classify scope, trigger repair.

Phase I.1: Polling-based file watcher for priority Hermes config files.
Phase I.3: Integration with config maintainer for auto-repair on major changes.

Design:
- Polling fallback (no inotify dependency)
- Classifies changes as minor (flag for next run) or major (auto-repair)
- Major changes trigger force_restore + [HERMES_FORCE_FIX]
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml


class ChangeScope(Enum):
    MINOR = "minor"
    MAJOR = "major"


@dataclass
class ChangeClassification:
    scope: ChangeScope
    details: str
    keys_changed: list[str] = field(default_factory=list)
    sections_removed: list[str] = field(default_factory=list)


@dataclass
class WatchedFile:
    path: Path
    last_hash: str = ""
    last_mtime: float = 0.0


@dataclass
class ConfigWatcher:
    watched_files: list[WatchedFile] = field(default_factory=list)
    poll_interval: float = 5.0
    flags: list[str] = field(default_factory=list)
    _running: bool = field(default=False, repr=False)


def _file_hash(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _load_yaml_safe(path: Path) -> dict[str, Any]:
    try:
        content = path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        return parsed if isinstance(parsed, dict) else {}
    except (yaml.YAMLError, OSError):
        return {}


def classify_change(old_config: dict, new_config: dict) -> ChangeClassification:
    """Classify a config change as minor or major.

    Major:
    - >3 top-level keys changed
    - Entire section removed
    - model or provider set to null/empty
    - Config truncated (fewer than half the keys)

    Minor:
    - Everything else
    """
    old_keys = set(old_config.keys())
    new_keys = set(new_config.keys())

    sections_removed = sorted(old_keys - new_keys)

    # Check for section removal
    if sections_removed:
        return ChangeClassification(
            scope=ChangeScope.MAJOR,
            details=f"sections removed: {sections_removed}",
            sections_removed=sections_removed,
        )

    # Check for model/provider null/empty
    old_model = old_config.get("model", {})
    new_model = new_config.get("model", {})
    if isinstance(old_model, dict) and isinstance(new_model, dict):
        if old_model.get("default") and not new_model.get("default"):
            return ChangeClassification(
                scope=ChangeScope.MAJOR,
                details="model.default set to null/empty",
            )
        if old_model.get("provider") and not new_model.get("provider"):
            return ChangeClassification(
                scope=ChangeScope.MAJOR,
                details="model.provider set to null/empty",
            )

    # Count changed keys at top level
    changed = []
    for k in old_keys | new_keys:
        if old_config.get(k) != new_config.get(k):
            changed.append(k)

    if len(changed) > 3:
        return ChangeClassification(
            scope=ChangeScope.MAJOR,
            details=f">{3} top-level keys changed: {changed[:5]}",
            keys_changed=changed,
        )

    # Truncation check
    if len(new_keys) < len(old_keys) * 0.5 and len(old_keys) > 2:
        return ChangeClassification(
            scope=ChangeScope.MAJOR,
            details=f"config truncated: {len(old_keys)} -> {len(new_keys)} keys",
        )

    return ChangeClassification(
        scope=ChangeScope.MINOR,
        details=f"minor change in keys: {changed}",
        keys_changed=changed,
    )


def create_watcher(
    config_dir: Path | None = None,
    poll_interval: float = 5.0,
) -> ConfigWatcher:
    """Create a config watcher for the standard Hermes config paths."""
    if config_dir is None:
        config_dir = Path.home() / ".hermes"

    watched = [
        WatchedFile(path=config_dir / "config.yaml"),
        WatchedFile(path=config_dir / "auth.json"),
    ]

    # Snapshot current hashes
    for wf in watched:
        wf.last_hash = _file_hash(wf.path)
        if wf.path.exists():
            wf.last_mtime = wf.path.stat().st_mtime

    return ConfigWatcher(
        watched_files=watched,
        poll_interval=poll_interval,
    )


def poll_once(watcher: ConfigWatcher) -> list[tuple[WatchedFile, ChangeClassification]]:
    """Poll all watched files once. Returns list of (file, classification) for changes."""
    changes = []

    for wf in watcher.watched_files:
        current_hash = _file_hash(wf.path)
        if current_hash and current_hash != wf.last_hash:
            # File changed — classify
            old_config = _load_yaml_safe(wf.path) if wf.path.suffix in (".yaml", ".yml") else {}
            # For classification, we'd need the old content — use hash as proxy
            # In practice, we compare against the backup
            wf.last_hash = current_hash
            if wf.path.exists():
                wf.last_mtime = wf.path.stat().st_mtime

            # Simple classification for non-YAML files
            if wf.path.suffix not in (".yaml", ".yml"):
                classification = ChangeClassification(
                    scope=ChangeScope.MINOR,
                    details=f"non-YAML file changed: {wf.path.name}",
                )
            else:
                # For YAML, we need old vs new — mark as minor by default
                # The service layer handles the full comparison
                classification = ChangeClassification(
                    scope=ChangeScope.MINOR,
                    details=f"YAML file changed: {wf.path.name}",
                )
            changes.append((wf, classification))

    return changes


def log_change(
    classification: ChangeClassification,
    file_path: Path,
    log_path: Path | None = None,
) -> None:
    """Log a config change to the watch log."""
    if log_path is None:
        log_path = Path.home() / ".hermes" / "config_watch.log"

    log_path.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "file": str(file_path),
        "scope": classification.scope.value,
        "details": classification.details,
        "keys_changed": classification.keys_changed,
        "sections_removed": classification.sections_removed,
    }

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
