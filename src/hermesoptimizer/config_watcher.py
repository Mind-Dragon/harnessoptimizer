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
from typing import Any, Callable

import yaml

from hermesoptimizer.config_maintainer import force_restore


class ChangeScope(Enum):
    MINOR = "minor"
    MAJOR = "major"


@dataclass
class ChangeClassification:
    scope: ChangeScope
    details: str
    keys_changed: list[str] = field(default_factory=list)
    sections_removed: list[str] = field(default_factory=list)
    force_fix_marker: str | None = None


@dataclass
class WatchedFile:
    path: Path
    last_hash: str = ""
    last_mtime: float = 0.0
    last_snapshot: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfigWatcher:
    watched_files: list[WatchedFile] = field(default_factory=list)
    poll_interval: float = 5.0
    flags: list[str] = field(default_factory=list)
    origin_pid: int | None = None
    allow_current_process_events: bool = False
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


def _load_snapshot(path: Path) -> dict[str, Any]:
    if path.suffix in (".yaml", ".yml"):
        return _load_yaml_safe(path)
    return {"__content__": path.read_text(encoding="utf-8") if path.exists() else ""}


def classify_change(old_config: dict, new_config: dict) -> ChangeClassification:
    """Classify a config change as minor or major."""
    old_keys = set(old_config.keys())
    new_keys = set(new_config.keys())

    sections_removed = sorted(k for k in old_keys - new_keys if isinstance(old_config.get(k), dict))
    if sections_removed:
        return ChangeClassification(
            scope=ChangeScope.MAJOR,
            details=f"sections removed: {sections_removed}",
            sections_removed=sections_removed,
        )

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

    changed = []
    for k in old_keys | new_keys:
        if old_config.get(k) != new_config.get(k):
            changed.append(k)

    if len(changed) > 3:
        return ChangeClassification(
            scope=ChangeScope.MAJOR,
            details=f">3 top-level keys changed: {changed[:5]}",
            keys_changed=changed,
        )

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
    origin_pid: int | None = None,
) -> ConfigWatcher:
    """Create a config watcher for the standard Hermes config paths."""
    if config_dir is None:
        config_dir = Path.home() / ".hermes"

    watched_paths = [
        config_dir / "config.yaml",
        config_dir / "auth.json",
    ]

    watched = []
    for path in watched_paths:
        watched.append(
            WatchedFile(
                path=path,
                last_hash=_file_hash(path),
                last_mtime=path.stat().st_mtime if path.exists() else 0.0,
                last_snapshot=_load_snapshot(path),
            )
        )

    return ConfigWatcher(
        watched_files=watched,
        poll_interval=poll_interval,
        origin_pid=origin_pid,
    )


def poll_once(
    watcher: ConfigWatcher,
    *,
    repair_callback: Callable[[Path], str | None] | None = None,
    log_path: Path | None = None,
) -> list[tuple[WatchedFile, ChangeClassification]]:
    """Poll watched files once.

    Returns a list of (file, classification) for files that changed.
    """
    changes = []
    if watcher._running and watcher.origin_pid is not None and watcher.origin_pid == os.getpid() and not watcher.allow_current_process_events:
        # Self-change exclusion for the running service process.
        return changes

    for wf in watcher.watched_files:
        current_hash = _file_hash(wf.path)
        current_snapshot = _load_snapshot(wf.path)

        if current_hash == wf.last_hash and wf.path.exists():
            continue

        if not wf.path.exists() and wf.last_hash:
            classification = ChangeClassification(
                scope=ChangeScope.MAJOR,
                details=f"file deleted: {wf.path.name}",
                force_fix_marker=None,
            )
        elif wf.path.suffix in (".yaml", ".yml"):
            classification = classify_change(wf.last_snapshot, current_snapshot)
        else:
            classification = ChangeClassification(
                scope=ChangeScope.MINOR,
                details=f"non-YAML file changed: {wf.path.name}",
            )

        wf.last_hash = current_hash
        wf.last_mtime = wf.path.stat().st_mtime if wf.path.exists() else wf.last_mtime

        if classification.scope == ChangeScope.MAJOR:
            # Auto-repair config.yaml from latest backup if available.
            if wf.path.name == "config.yaml":
                backup_dir = wf.path.parent / "config.backups"
                restore_result = force_restore(wf.path, backup_dir)
                if restore_result.restored:
                    classification.force_fix_marker = restore_result.marker
                    classification.details = f"{classification.details}; auto-repaired from backup"
                    # Refresh snapshot after restore.
                    wf.last_snapshot = _load_snapshot(wf.path)
                    wf.last_hash = _file_hash(wf.path)
                else:
                    classification.details = f"{classification.details}; repair failed: {restore_result.error}"

            if repair_callback is not None:
                repair_callback(wf.path)

        else:
            wf.last_snapshot = current_snapshot

        log_change(classification, wf.path, log_path=log_path)
        changes.append((wf, classification))

    return changes


def start_watching(
    watcher: ConfigWatcher,
    *,
    repair_callback: Callable[[Path], str | None] | None = None,
    log_path: Path | None = None,
    stop_event: Any | None = None,
) -> None:
    """Run the watcher loop until stopped."""
    watcher._running = True
    try:
        while True:
            if stop_event is not None and getattr(stop_event, "is_set", lambda: False)():
                break
            poll_once(watcher, repair_callback=repair_callback, log_path=log_path)
            time.sleep(watcher.poll_interval)
    finally:
        watcher._running = False


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
        "force_fix_marker": classification.force_fix_marker,
    }

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
