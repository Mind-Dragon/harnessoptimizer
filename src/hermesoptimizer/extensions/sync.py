"""Extension sync: copy repo-managed artifacts to install targets."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from hermesoptimizer.extensions.schema import ExtensionEntry, Ownership


@dataclass(frozen=True)
class SyncResult:
    """Result of syncing one extension."""

    id: str
    synced: bool
    skipped: bool
    actions: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def sync_extension(
    entry: ExtensionEntry,
    repo_root: Path,
    dry_run: bool = False,
    force: bool = False,
) -> SyncResult:
    """Sync one extension from repo source to target paths."""
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

    for tp in entry.target_paths:
        target = Path(tp).expanduser()
        if target.exists() and not force:
            errors.append(f"target exists (use --force to overwrite): {target}")
            continue

        if dry_run:
            actions.append(f"would copy {source} -> {target}")
            continue

        try:
            if source.is_dir():
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(source, target)
            elif source.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            else:
                errors.append(f"source is neither file nor directory: {source}")
                continue
            actions.append(f"copied {source} -> {target}")
        except Exception as exc:
            errors.append(f"copy failed for {target}: {exc}")

    synced = bool(actions) and not errors and not dry_run
    return SyncResult(
        id=entry.id,
        synced=synced,
        skipped=False,
        actions=actions,
        errors=errors,
    )


def sync_all(
    entries: list[ExtensionEntry],
    repo_root: Path,
    dry_run: bool = False,
    force: bool = False,
) -> list[SyncResult]:
    """Sync all extensions."""
    return [sync_extension(e, repo_root, dry_run, force) for e in entries]
