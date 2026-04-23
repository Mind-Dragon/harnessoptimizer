"""Extension status: compare repo source vs installed/runtime target."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from hermesoptimizer.extensions.schema import ExtensionEntry, Ownership


class Status(str):
    OK = "ok"
    MISSING_SOURCE = "missing_source"
    MISSING_TARGET = "missing_target"
    DRIFTED = "drifted"
    EXTERNAL = "external"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ExtensionStatus:
    """Status report for a single extension."""

    id: str
    status: str
    source_ok: bool
    targets: list[dict] = field(default_factory=list)
    detail: str = ""


def _expand(path: str) -> Path:
    return Path(path).expanduser()


def check_extension_status(entry: ExtensionEntry, repo_root: Path, dry_run: bool = False) -> ExtensionStatus:
    """Check the status of one extension.

    In dry-run mode, REPO_EXTERNAL extensions with missing targets are
    downgraded to non-critical warnings because their artifacts are
    already tracked under a repo-only extension (e.g. ``scripts``) and
    the missing targets only indicate they have not been *installed* to
    the runtime yet.  This is expected in CI / test environments.
    """
    if entry.ownership == Ownership.EXTERNAL_RUNTIME:
        return ExtensionStatus(
            id=entry.id,
            status=Status.EXTERNAL,
            source_ok=True,
            detail="external_runtime: not managed by repo",
        )

    source_ok = entry.source_exists(repo_root)
    if not source_ok:
        return ExtensionStatus(
            id=entry.id,
            status=Status.MISSING_SOURCE,
            source_ok=False,
            detail=f"source_path missing: {entry.source_path}",
        )

    targets = []
    missing_targets = []
    for tp in entry.target_paths:
        expanded = _expand(tp)
        exists = expanded.exists()
        targets.append({"path": str(expanded), "exists": exists})
        if not exists:
            missing_targets.append(str(expanded))

    if missing_targets:
        # In dry-run, REPO_EXTERNAL missing targets are a warning, not a
        # failure, because the source-of-truth lives in the repo and the
        # runtime install is an optional deployment step.
        if dry_run and entry.ownership == Ownership.REPO_EXTERNAL:
            return ExtensionStatus(
                id=entry.id,
                status=Status.DRIFTED,
                source_ok=True,
                targets=targets,
                detail=f"not installed (dry-run): {', '.join(missing_targets)}",
            )
        return ExtensionStatus(
            id=entry.id,
            status=Status.MISSING_TARGET,
            source_ok=True,
            targets=targets,
            detail=f"missing targets: {', '.join(missing_targets)}",
        )

    return ExtensionStatus(
        id=entry.id,
        status=Status.OK,
        source_ok=True,
        targets=targets,
        detail="all checks pass",
    )


def check_all_statuses(entries: list[ExtensionEntry], repo_root: Path, dry_run: bool = False) -> list[ExtensionStatus]:
    """Check status for all extensions."""
    return [check_extension_status(e, repo_root, dry_run=dry_run) for e in entries]
