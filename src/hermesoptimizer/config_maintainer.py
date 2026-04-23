"""Config maintainer: backup dedup, merge semantics, force-restore, status.

Phase E.1: Config backup with dedup, previous symlink, pruning, diff logging.
Phase E.2: Config merge (not overwrite) with user-ownership tracking.

Design principles:
- User-owned = any key present in current config. No sidecar metadata.
- Deep-merge: dicts merge, scalars user-wins, lists replace.
- Force-fix emits [HERMES_FORCE_FIX] marker.
- All operations are pure or file-local I/O, testable.
"""
from __future__ import annotations

import difflib
import hashlib
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class BackupResult:
    """Result of a backup operation."""

    success: bool = False
    skipped: bool = False
    backup_path: Path | None = None
    diff: str | None = None
    error: str | None = None


@dataclass
class ForceRestoreResult:
    """Result of a force-restore operation."""

    restored: bool = False
    marker: str = ""
    error: str | None = None


@dataclass
class ConfigStatus:
    """Status of the current config."""

    model: str = ""
    provider: str = ""
    last_backup: str | None = None
    diff_since_backup: str | None = None
    user_owned_keys: list[str] = field(default_factory=list)
    error: str | None = None


# ---------------------------------------------------------------------------
# E.1: Config backup
# ---------------------------------------------------------------------------


def _config_hash(path: Path) -> str:
    """SHA256 of the config file content."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _timestamp_tag() -> str:
    """UTC timestamp tag for backup filenames."""
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _diff_configs(old: str, new: str) -> str:
    """Unified diff between two config texts."""
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    return "".join(
        difflib.unified_diff(old_lines, new_lines, lineterm="")
    )


def backup_config(
    config_path: Path,
    backup_dir: Path,
    max_backups: int = 10,
) -> BackupResult:
    """Backup config.yaml with dedup, previous symlink, and pruning.

    Parameters
    ----------
    config_path : Path
        Path to the config.yaml file.
    backup_dir : Path
        Directory to store backups in.
    max_backups : int
        Maximum number of backups to keep.

    Returns
    -------
    BackupResult
        Success/failure, whether skipped (duplicate), backup path, diff.
    """
    if not config_path.exists():
        return BackupResult(success=False, error=f"config not found: {config_path}")

    backup_dir.mkdir(parents=True, exist_ok=True)

    current_content = config_path.read_text(encoding="utf-8")
    current_hash = _config_hash(config_path)

    # Check if previous backup has same hash (dedup)
    previous_link = backup_dir / "previous.yaml"
    if previous_link.exists() or previous_link.is_symlink():
        try:
            previous_target = previous_link.resolve()
            if previous_target.exists():
                previous_hash = _config_hash(previous_target)
                if previous_hash == current_hash:
                    return BackupResult(
                        success=True,
                        skipped=True,
                        backup_path=previous_target,
                    )
                # Compute diff against previous
                previous_content = previous_target.read_text(encoding="utf-8")
                diff = _diff_configs(previous_content, current_content)
            else:
                diff = None
        except OSError:
            diff = None
    else:
        diff = None

    # Write new backup
    tag = _timestamp_tag()
    backup_name = f"config.{tag}.{current_hash}.yaml"
    backup_path = backup_dir / backup_name
    backup_path.write_text(current_content, encoding="utf-8")

    # Update previous symlink
    _update_symlink(previous_link, backup_path)

    # Prune old backups
    _prune_backups(backup_dir, max_backups)

    return BackupResult(
        success=True,
        skipped=False,
        backup_path=backup_path,
        diff=diff,
    )


def _update_symlink(link_path: Path, target: Path) -> None:
    """Update a symlink, removing existing one first."""
    if link_path.is_symlink():
        link_path.unlink()
    elif link_path.exists():
        link_path.unlink()
    # Use relative path for portability
    try:
        link_path.symlink_to(target.name)
    except OSError:
        # Fallback: copy instead of symlink (Windows, restricted envs)
        import shutil
        shutil.copy2(target, link_path)


def _prune_backups(backup_dir: Path, max_backups: int) -> None:
    """Keep at most max_backups backup files, oldest first."""
    backups = sorted(backup_dir.glob("config.*.yaml"))
    # Don't prune the previous.yaml symlink target
    while len(backups) > max_backups:
        oldest = backups.pop(0)
        # Don't delete if it's what previous.yaml points to
        previous = backup_dir / "previous.yaml"
        try:
            if previous.resolve() == oldest.resolve():
                continue
        except OSError:
            pass
        oldest.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# E.2: Config merge
# ---------------------------------------------------------------------------


def get_user_owned_keys(config: dict[str, Any], prefix: str = "") -> set[str]:
    """Extract all dotted key paths present in the config.

    Any key present in the config is considered user-owned.
    """
    keys: set[str] = set()
    for k, v in config.items():
        full_key = f"{prefix}.{k}" if prefix else k
        keys.add(full_key)
        if isinstance(v, dict):
            keys.update(get_user_owned_keys(v, full_key))
    return keys


def merge_config(
    current: dict[str, Any],
    incoming: dict[str, Any],
) -> dict[str, Any]:
    """Deep-merge incoming config into current, preserving user-owned keys.

    Rules:
    - Dicts merge recursively
    - Scalars: if key exists in current (user-owned), keep user value
    - Scalars: if key does not exist in current, take incoming value
    - Lists: replaced by incoming (not concatenated)
    - None is a valid user value — if user set None, keep None
    """
    result = {}
    all_keys = set(current.keys()) | set(incoming.keys())

    for k in all_keys:
        if k in current and k in incoming:
            if isinstance(current[k], dict) and isinstance(incoming[k], dict):
                # Both dicts: recurse
                result[k] = merge_config(current[k], incoming[k])
            elif isinstance(current[k], dict) != isinstance(incoming[k], dict):
                # Type mismatch: user wins
                result[k] = current[k]
            elif isinstance(current[k], list) or isinstance(incoming[k], list):
                # Lists: incoming replaces (concatenation is unpredictable)
                result[k] = incoming[k]
            else:
                # Both scalars: user wins (key exists in current)
                result[k] = current[k]
        elif k in current:
            result[k] = current[k]
        else:
            result[k] = incoming[k]

    return result


def force_restore(
    config_path: Path,
    backup_dir: Path,
) -> ForceRestoreResult:
    """Restore config from backup after destructive change.

    Emits [HERMES_FORCE_FIX] marker.
    """
    previous = backup_dir / "previous.yaml"
    if not previous.exists() and not previous.is_symlink():
        return ForceRestoreResult(
            restored=False,
            error="no previous backup found",
        )

    try:
        backup_target = previous.resolve()
        if not backup_target.exists():
            return ForceRestoreResult(
                restored=False,
                error="previous backup target not found",
            )
    except OSError:
        return ForceRestoreResult(
            restored=False,
            error="cannot resolve previous symlink",
        )

    # Restore
    restored_content = backup_target.read_text(encoding="utf-8")
    config_path.write_text(restored_content, encoding="utf-8")

    tag = _timestamp_tag()
    marker = f"[HERMES_FORCE_FIX] {tag} restored from {backup_target.name}"

    return ForceRestoreResult(
        restored=True,
        marker=marker,
    )


# ---------------------------------------------------------------------------
# Config status
# ---------------------------------------------------------------------------


def config_status(
    config_path: Path,
    backup_dir: Path,
) -> ConfigStatus:
    """Report current config state: model, provider, last backup, diff."""
    if not config_path.exists():
        return ConfigStatus(error=f"config not found: {config_path}")

    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            return ConfigStatus(error="config is not a valid YAML dict")
    except yaml.YAMLError as exc:
        return ConfigStatus(error=f"config parse error: {exc}")

    model = ""
    provider = ""
    model_section = config.get("model", {})
    if isinstance(model_section, dict):
        model = model_section.get("default", "")
        provider = model_section.get("provider", "")

    # Find last backup
    last_backup = None
    previous = backup_dir / "previous.yaml"
    if previous.exists() or previous.is_symlink():
        try:
            target = previous.resolve()
            if target.exists():
                last_backup = time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ",
                    time.gmtime(target.stat().st_mtime),
                )
        except OSError:
            pass

    # Diff against last backup
    diff_since_backup = None
    if previous.exists() or previous.is_symlink():
        try:
            target = previous.resolve()
            if target.exists():
                backup_content = target.read_text(encoding="utf-8")
                current_content = config_path.read_text(encoding="utf-8")
                diff = _diff_configs(backup_content, current_content)
                if diff.strip():
                    diff_since_backup = diff
        except OSError:
            pass

    user_keys = sorted(get_user_owned_keys(config))

    return ConfigStatus(
        model=str(model),
        provider=str(provider),
        last_backup=last_backup,
        diff_since_backup=diff_since_backup,
        user_owned_keys=user_keys,
    )
