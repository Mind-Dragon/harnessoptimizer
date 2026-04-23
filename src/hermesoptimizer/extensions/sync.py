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
) -> SyncResult:
    """Sync one extension from repo source to target paths.

    Uses transactional sync with pre/during/post checks and rollback on failure.
    """
    actions: list[str] = []
    errors: list[str] = []

    if entry.ownership == Ownership.EXTERNAL_RUNTIME:
        return SyncResult(
            id=entry.id,
            synced=False,
            skipped=True,
            actions=["skipped: external_runtime ownership"],
        )

    source = repo_root / entry.source_path
    if not source.exists():
        return SyncResult(
            id=entry.id,
            synced=False,
            skipped=False,
            errors=[f"source_path does not exist: {source}"],
        )

    if not entry.target_paths:
        return SyncResult(
            id=entry.id,
            synced=False,
            skipped=True,
            actions=["skipped: no target_paths defined"],
        )

    # Expand target paths and check for existing targets (if not force)
    expanded_targets: list[Path] = []
    for tp in entry.target_paths:
        target = Path(tp).expanduser()
        if target.exists() and not force:
            errors.append(f"target exists (use --force to overwrite): {target}")
            continue
        expanded_targets.append(target)

    if errors and not force:
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
) -> list[SyncResult]:
    """Sync all extensions."""
    return [sync_extension(e, repo_root, dry_run, force) for e in entries]
