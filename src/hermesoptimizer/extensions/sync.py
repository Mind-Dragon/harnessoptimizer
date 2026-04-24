"""Extension sync: copy repo-managed artifacts to install targets.

This module provides transactional install semantics via install_integrity:
- Pre-install intent validation
- Atomic writes with temp-file staging
- Post-install canary proof
- Automatic rollback on failure
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from hermesoptimizer.extensions.install_integrity import (
    InstallIntent,
    InstallProof,
    InstallState,
    PreInstallIntentError,
    InstallValidationError,
    check_pre_install_intent,
    run_install_canary,
    transactional_sync,
    save_install_state,
    validate_yaml_file,
)
from hermesoptimizer.extensions.schema import ExtensionEntry, Ownership


@dataclass(frozen=True)
class SyncResult:
    """Result of syncing one extension."""

    id: str
    synced: bool
    skipped: bool
    actions: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    proof: InstallProof | None = None


def sync_extension(
    entry: ExtensionEntry,
    repo_root: Path,
    dry_run: bool = False,
    force: bool = False,
    fresh_root: Path | None = None,
) -> SyncResult:
    """Sync one extension from repo source to target paths.

    Uses transactional sync with pre/during/post checks and rollback on failure.
    """
    actions: list[str] = []
    errors: list[str] = []

    if not entry.selected:
        return SyncResult(
            id=entry.id,
            synced=False,
            skipped=True,
            actions=["skipped: not selected"],
        )

    if entry.ownership == Ownership.EXTERNAL_RUNTIME:
        return SyncResult(
            id=entry.id,
            synced=False,
            skipped=True,
            actions=["skipped: external_runtime ownership"],
        )

    source = repo_root / entry.source_path
    sync_files = entry.metadata.get("sync_files") if isinstance(entry.metadata, dict) else None
    if sync_files:
        if not isinstance(sync_files, dict):
            return SyncResult(
                id=entry.id,
                synced=False,
                skipped=False,
                errors=["metadata.sync_files must map source paths to target paths"],
            )
        expanded_pairs: list[tuple[Path, Path]] = []
        for rel_source, target_path in sync_files.items():
            src = repo_root / str(rel_source)
            if not src.exists():
                errors.append(f"source_path does not exist: {src}")
                continue
            target = _expand_target(str(target_path), fresh_root=fresh_root)
            if target.exists() and not force:
                if dry_run:
                    actions.append(f"target exists: {target}")
                    expanded_pairs.append((src, target))
                else:
                    errors.append(f"target exists (use --force to overwrite): {target}")
            else:
                expanded_pairs.append((src, target))
        if errors and not force and not dry_run:
            return SyncResult(id=entry.id, synced=False, skipped=False, actions=actions, errors=errors)
        if errors:
            return SyncResult(id=entry.id, synced=False, skipped=False, actions=actions, errors=errors)
        if dry_run:
            for src, target in expanded_pairs:
                actions.append(f"would copy {src} -> {target}")
            return SyncResult(id=entry.id, synced=False, skipped=False, actions=actions, errors=[])
        try:
            for src, target in expanded_pairs:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, target)
                actions.append(f"copied {src} -> {target}")
            return SyncResult(id=entry.id, synced=True, skipped=False, actions=actions, errors=[])
        except Exception as exc:
            return SyncResult(
                id=entry.id,
                synced=False,
                skipped=False,
                actions=actions,
                errors=[f"unexpected error during sync: {exc}"],
            )

    if not source.exists():
        return SyncResult(
            id=entry.id,
            synced=False,
            skipped=False,
            errors=[f"source_path does not exist: {source}"],
        )

    if not entry.target_paths:
        install_mode = entry.metadata.get("install_mode") if isinstance(entry.metadata, dict) else None
        no_sync_reason = entry.metadata.get("no_sync_reason") if isinstance(entry.metadata, dict) else None
        if install_mode == "repo_only_no_sync" and no_sync_reason:
            action = f"skipped: no target_paths defined (repo_only_no_sync: {no_sync_reason})"
        else:
            action = "skipped: no target_paths defined"
        return SyncResult(
            id=entry.id,
            synced=False,
            skipped=True,
            actions=[action],
        )

    # Expand target paths and check for existing targets (if not force)
    expanded_targets: list[Path] = []
    for tp in entry.target_paths:
        target = _expand_target(tp, fresh_root=fresh_root)
        if target.exists() and not force:
            if dry_run:
                actions.append(f"target exists: {target}")
                expanded_targets.append(target)
            else:
                errors.append(f"target exists (use --force to overwrite): {target}")
                continue
        else:
            expanded_targets.append(target)

    if errors and not force and not dry_run:
        return SyncResult(
            id=entry.id,
            synced=False,
            skipped=False,
            actions=actions,
            errors=errors,
        )

    # Build install intent
    intent = InstallIntent(
        id=entry.id,
        source_path=source,
        target_paths=expanded_targets,
        ownership=entry.ownership.value,
    )

    # Pre-install intent check
    intent_errors = check_pre_install_intent(intent)
    if intent_errors:
        return SyncResult(
            id=entry.id,
            synced=False,
            skipped=False,
            actions=actions,
            errors=intent_errors,
        )

    # Dry run - report what would happen
    if dry_run:
        for tp in expanded_targets:
            actions.append(f"would copy {source} -> {tp}")
        return SyncResult(
            id=entry.id,
            synced=False,
            skipped=False,
            actions=actions,
            errors=[],
        )

    # Perform transactional sync
    try:
        state = transactional_sync(intent, dry_run=False)

        # Build actions from successful sync
        for tp in expanded_targets:
            actions.append(f"copied {source} -> {tp}")

        return SyncResult(
            id=entry.id,
            synced=True,
            skipped=False,
            actions=actions,
            errors=state.errors,
            proof=state.proof,
        )

    except (PreInstallIntentError, InstallValidationError) as exc:
        return SyncResult(
            id=entry.id,
            synced=False,
            skipped=False,
            actions=actions,
            errors=[str(exc)],
        )
    except Exception as exc:
        return SyncResult(
            id=entry.id,
            synced=False,
            skipped=False,
            actions=actions,
            errors=[f"unexpected error during sync: {exc}"],
        )


def sync_all(
    entries: list[ExtensionEntry],
    repo_root: Path,
    dry_run: bool = False,
    force: bool = False,
    fresh_root: Path | None = None,
) -> list[SyncResult]:
    """Sync all extensions."""
    return [sync_extension(e, repo_root, dry_run, force, fresh_root) for e in entries]


def _expand_target(path: str, *, fresh_root: Path | None = None) -> Path:
    """Expand an extension target, optionally remapping ~/ under a fresh root."""
    if fresh_root is not None and path.startswith("~/"):
        return fresh_root / path[2:]
    return Path(path).expanduser()
