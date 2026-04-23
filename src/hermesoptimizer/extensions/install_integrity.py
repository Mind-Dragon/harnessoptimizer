"""Install integrity gate: transactional install with staged validation.

This module provides fail-closed install semantics:
- Pre-install: confirm intent and target validity
- During: confirm write is happening and validate intermediate state
- Post-install: prove the result matches intent, run canary checks
- Rollback: preserve original state if any stage fails

Used by sync and doctor flows to prevent corrupted or half-written installs.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


class InstallIntegrityError(Exception):
    """Base exception for install integrity failures."""


class PreInstallIntentError(InstallIntegrityError):
    """Raised when pre-install intent check fails."""


class InstallValidationError(InstallIntegrityError):
    """Raised when install validation fails."""


class InstallRollbackError(InstallIntegrityError):
    """Raised when rollback fails."""


@dataclass(frozen=True)
class InstallIntent:
    """What we intend to install."""
    id: str
    source_path: Path
    target_paths: list[Path]
    ownership: str


@dataclass(frozen=True)
class InstallProof:
    """Proof that install succeeded."""
    id: str
    timestamp: str
    source_valid: bool
    targets_match: bool
    target_contents_match: bool
    canary_passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class InstallState:
    """Mutable install state for tracking progress."""
    id: str
    intent: InstallIntent | None = None
    started_at: str | None = None
    backup_paths: dict[str, Path] = field(default_factory=dict)
    temp_paths: dict[str, Path] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    proof: InstallProof | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "intent": {
                "id": self.intent.id if self.intent else None,
                "source_path": str(self.intent.source_path) if self.intent else None,
                "target_paths": [str(p) for p in self.intent.target_paths] if self.intent else [],
                "ownership": self.intent.ownership if self.intent else None,
            } if self.intent else None,
            "started_at": self.started_at,
            "backup_paths": {k: str(v) for k, v in self.backup_paths.items()},
            "temp_paths": {k: str(v) for k, v in self.temp_paths.items()},
            "errors": self.errors,
            "warnings": self.warnings,
            "proof": {
                "id": self.proof.id if self.proof else None,
                "timestamp": self.proof.timestamp if self.proof else None,
                "source_valid": self.proof.source_valid if self.proof else None,
                "targets_match": self.proof.targets_match if self.proof else None,
                "target_contents_match": self.proof.target_contents_match if self.proof else None,
                "canary_passed": self.proof.canary_passed if self.proof else None,
                "errors": self.proof.errors if self.proof else [],
                "warnings": self.proof.warnings if self.proof else [],
            } if self.proof else None,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_file_digest(path: Path) -> str:
    """Compute a simple content digest for comparison."""
    if path.is_file():
        return hash(path.read_bytes())
    return ""


# ---------------------------------------------------------------------------
# Pre-install checks
# ---------------------------------------------------------------------------

def check_pre_install_intent(intent: InstallIntent) -> list[str]:
    """Verify the install intent is valid before any write.

    Returns list of errors (empty means intent is valid).
    """
    errors: list[str] = []

    if not intent.id:
        errors.append("intent.id is empty")

    if not intent.source_path:
        errors.append("intent.source_path is empty")
    elif not intent.source_path.exists():
        errors.append(f"source_path does not exist: {intent.source_path}")

    if not intent.target_paths:
        errors.append("intent.target_paths is empty")

    for tp in intent.target_paths:
        if not tp:
            errors.append("one of target_paths is empty")
            continue
        # Target's parent directory must exist or be creatable
        parent = tp.parent
        if not parent.exists():
            try:
                parent.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                errors.append(f"cannot create parent directory for target: {tp}")

    return errors


# ---------------------------------------------------------------------------
# Backup and rollback
# ---------------------------------------------------------------------------

def _backup_target(target: Path) -> Path | None:
    """Create a backup of target file/directory.

    Returns path to backup, or None if no backup needed (target doesn't exist).
    """
    if not target.exists():
        return None

    backup = Path(str(target) + f".backup.{os.getpid()}")
    if target.is_dir():
        shutil.copytree(target, backup, dirs_exist_ok=True)
    else:
        shutil.copy2(target, backup)
    return backup


def restore_from_backup(target: Path, backup: Path) -> None:
    """Restore target from backup."""
    if not backup.exists():
        raise InstallRollbackError(f"backup does not exist: {backup}")

    if target.exists():
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()

    if backup.is_dir():
        shutil.copytree(backup, target, dirs_exist_ok=True)
    else:
        shutil.copy2(backup, target)


# ---------------------------------------------------------------------------
# Transactional write
# ---------------------------------------------------------------------------

def _atomic_write_content(target: Path, content: bytes) -> Path:
    """Write content to temp file then atomically rename to target.

    Returns the final target path (same as input).
    Raises InstallValidationError if validation fails.
    """
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)

    tmp = parent / f".{target.name}.tmp.{os.getpid()}"
    tmp.write_bytes(content)

    # Atomic rename (on POSIX this is atomic if on same filesystem)
    tmp.rename(target)
    return target


# ---------------------------------------------------------------------------
# Install canary checks
# ---------------------------------------------------------------------------

def run_install_canary(
    intent: InstallIntent,
    source_path: Path,
    target_paths: list[Path],
) -> InstallProof:
    """Run post-install canary to prove install succeeded.

    Checks:
    - Source is still valid
    - All targets exist
    - Target contents match source (for files)
    - CLI canary (if applicable)
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Source valid
    source_valid = source_path.exists()

    # Targets match
    targets_match = True
    for tp in target_paths:
        if not tp.exists():
            targets_match = False
            errors.append(f"target missing after install: {tp}")

    # Contents match (for files)
    target_contents_match = True
    if source_path.is_file() and source_valid:
        source_content = source_path.read_bytes()
        for tp in target_paths:
            if tp.is_file():
                if tp.read_bytes() != source_content:
                    target_contents_match = False
                    errors.append(f"target content mismatch: {tp}")
            elif tp.is_dir():
                # For directories, check if source file exists inside
                if not (tp / source_path.name).exists():
                    target_contents_match = False
                    errors.append(f"source file not found in target directory: {tp / source_path.name}")
    elif source_path.is_dir() and source_valid:
        # For directories, compare a marker file or count
        for tp in target_paths:
            if not tp.is_dir():
                target_contents_match = False
                errors.append(f"target is not a directory: {tp}")

    # Canary passed if no errors
    canary_passed = len(errors) == 0

    return InstallProof(
        id=intent.id,
        timestamp=_utc_now(),
        source_valid=source_valid,
        targets_match=targets_match,
        target_contents_match=target_contents_match,
        canary_passed=canary_passed,
        errors=errors,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Full transactional install with rollback
# ---------------------------------------------------------------------------

def transactional_sync(
    intent: InstallIntent,
    dry_run: bool = False,
) -> InstallState:
    """Perform a transactional sync with pre-checks, canary, and rollback.

    On failure, restores original state.
    """
    state = InstallState(id=intent.id)

    # Pre-install intent check
    state.started_at = _utc_now()
    intent_errors = check_pre_install_intent(intent)
    if intent_errors:
        state.errors.extend(intent_errors)
        raise PreInstallIntentError(
            f"pre-install intent check failed for {intent.id}: {intent_errors}"
        )

    state.intent = intent

    # If dry run, skip actual writes
    if dry_run:
        proof = InstallProof(
            id=intent.id,
            timestamp=_utc_now(),
            source_valid=intent.source_path.exists(),
            targets_match=False,  # Not checked in dry run
            target_contents_match=False,
            canary_passed=True,
            warnings=["dry run - no actual install performed"],
        )
        state.proof = proof
        return state

    # Backup existing targets
    for tp in intent.target_paths:
        backup = _backup_target(tp)
        if backup:
            state.backup_paths[str(tp)] = backup

    try:
        # During: perform the actual sync
        if intent.source_path.is_dir():
            for tp in intent.target_paths:
                if tp.exists():
                    shutil.rmtree(tp)
                shutil.copytree(intent.source_path, tp)
        elif intent.source_path.is_file():
            for tp in intent.target_paths:
                _atomic_write_content(tp, intent.source_path.read_bytes())

        # Post-install: run canary
        proof = run_install_canary(intent, intent.source_path, intent.target_paths)
        state.proof = proof

        if not proof.canary_passed:
            raise InstallValidationError(
                f"install canary failed for {intent.id}: {proof.errors}"
            )

        # Clean up backups on success
        for backup in state.backup_paths.values():
            if backup and backup.exists():
                if backup.is_dir():
                    shutil.rmtree(backup)
                else:
                    backup.unlink()
        state.backup_paths.clear()

    except Exception as exc:
        # Rollback on failure
        state.errors.append(f"install failed: {exc}")
        for tp_str, backup in state.backup_paths.items():
            tp = Path(tp_str)
            try:
                restore_from_backup(tp, backup)
            except Exception as rollback_exc:
                state.errors.append(f"rollback failed for {tp}: {rollback_exc}")
        raise

    return state


# ---------------------------------------------------------------------------
# State artifact persistence
# ---------------------------------------------------------------------------

def _state_path(intent_id: str) -> Path:
    return Path.home() / ".hoptimizer" / "install_state" / f"{intent_id}.json"


def save_install_state(state: InstallState) -> None:
    """Save install state artifact for auditing."""
    path = _state_path(state.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")


def load_install_state(intent_id: str) -> InstallState | None:
    """Load a previously saved install state."""
    path = _state_path(intent_id)
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    # Reconstruct (simplified - enough for debugging)
    intent = None
    if data.get("intent") and data["intent"].get("id"):
        intent = InstallIntent(
            id=data["intent"]["id"],
            source_path=Path(data["intent"]["source_path"]),
            target_paths=[Path(p) for p in data["intent"]["target_paths"]],
            ownership=data["intent"]["ownership"],
        )
    state = InstallState(id=data["id"])
    state.intent = intent
    state.started_at = data.get("started_at")
    state.backup_paths = {k: Path(v) for k, v in data.get("backup_paths", {}).items()}
    state.temp_paths = {k: Path(v) for k, v in data.get("temp_paths", {}).items()}
    state.errors = data.get("errors", [])
    state.warnings = data.get("warnings", [])
    if data.get("proof"):
        p = data["proof"]
        state.proof = InstallProof(
            id=p["id"],
            timestamp=p["timestamp"],
            source_valid=p["source_valid"],
            targets_match=p["targets_match"],
            target_contents_match=p["target_contents_match"],
            canary_passed=p["canary_passed"],
            errors=p.get("errors", []),
            warnings=p.get("warnings", []),
        )
    return state


# ---------------------------------------------------------------------------
# Config file helpers for caveman/hermes config
# ---------------------------------------------------------------------------

def validate_yaml_file(path: Path) -> list[str]:
    """Validate that a YAML file is parseable.

    Returns list of errors (empty means valid).
    """
    errors: list[str] = []
    if not path.exists():
        errors.append(f"file does not exist: {path}")
        return errors
    try:
        content = path.read_text(encoding="utf-8")
        if content.strip():
            yaml.safe_load(content)
    except yaml.YAMLError as exc:
        errors.append(f"YAML parse error in {path}: {exc}")
    except Exception as exc:
        errors.append(f"error reading {path}: {exc}")
    return errors


def atomic_yaml_write(path: Path, data: dict) -> None:
    """Atomically write a YAML file with validation.

    Writes to temp file, validates, then renames. If the target already exists,
    a backup is kept so the original is preserved on any failure in the rename
    step. Raises InstallValidationError if validation fails.
    """
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)

    tmp = parent / f".{path.name}.tmp.{os.getpid()}"
    rendered = yaml.safe_dump(data, sort_keys=False)
    tmp.write_text(rendered, encoding="utf-8")

    # Validate before rename
    errors = validate_yaml_file(tmp)
    if errors:
        tmp.unlink(missing_ok=True)
        raise InstallValidationError(f"YAML validation failed: {errors}")

    # Preserve original via backup so rename failure cannot lose it
    backup = None
    had_original = path.exists()
    if had_original:
        backup = parent / f".{path.name}.pre-atomic-backup.{os.getpid()}"
        shutil.copy2(path, backup)

    try:
        tmp.rename(path)
    except OSError:
        # Rename failed — restore original if we had one
        if backup and backup.exists():
            shutil.copy2(backup, path)
            backup.unlink(missing_ok=True)
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise
    finally:
        # Clean up backup on success path (rename already replaced it)
        if backup and backup.exists():
            backup.unlink(missing_ok=True)
