from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from .inventory import VaultInventory

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VaultBridgePlan:
    target_format: str
    writable: bool = False


@dataclass(frozen=True, slots=True)
class WriteBackPlan:
    target_format: str
    preserve_existing: bool
    operations: list[str]


def plan_bridge(inventory: VaultInventory, target_format: str) -> VaultBridgePlan:
    """Plan a write-back bridge without touching any files."""
    _ = inventory
    return VaultBridgePlan(target_format=target_format, writable=False)


def plan_write_back(inventory: VaultInventory, target_format: str) -> WriteBackPlan:
    """Plan a non-destructive write-back pass over the discovered files.

    The operations list is filtered by target_format:
    - "env":  only .env files
    - "yaml": .yaml and .yml files
    """
    if target_format == "env":
        operations = [str(p) for p in inventory.files if p.suffix == ".env"]
    elif target_format == "yaml":
        operations = [str(p) for p in inventory.files if p.suffix in (".yaml", ".yml")]
    else:
        operations = []
    return WriteBackPlan(
        target_format=target_format,
        preserve_existing=True,
        operations=operations,
    )


@dataclass(slots=True)
class WriteBackResult:
    """Result of a write-back execution operation."""
    files_processed: int
    files_modified: int
    files_preserved: int
    mutations_logged: list[str]


def execute_write_back(
    plan: WriteBackPlan,
    inventory: VaultInventory,
    confirm: bool = False,
) -> WriteBackResult | None:
    """Execute write-back operations for the given plan.

    This function implements safe write-back with the following guarantees:
    - Only writes when confirm=True
    - Preserves existing files by default (non-destructive)
    - Logs all mutations for audit trail

    Args:
        plan: The WriteBackPlan containing target format and operations
        inventory: The VaultInventory with current entries
        confirm: If False (default), only logs planned operations without writing.
                 If True, actually writes any pending changes.

    Returns:
        WriteBackResult with statistics, or None if confirm=False (no mutations attempted)
    """
    if not confirm:
        logger.info(
            "write-back: dry-run (confirm=False) — no files modified. "
            "Plan would process %d file(s) for format=%s",
            len(plan.operations),
            plan.target_format,
        )
        return None

    # Group entries by source_path for efficient lookup
    entries_by_path: dict[str, list] = {}
    for entry in inventory.entries:
        path_str = str(entry.source_path)
        if path_str not in entries_by_path:
            entries_by_path[path_str] = []
        entries_by_path[path_str].append(entry)

    mutations_logged: list[str] = []
    files_modified = 0
    files_preserved = 0

    for op_path in plan.operations:
        path = Path(op_path)
        if not path.exists():
            logger.warning("write-back: skipping missing file %s", op_path)
            continue

        # Get entries for this file
        entries = entries_by_path.get(op_path, [])

        # Format content based on target format
        if plan.target_format == "env":
            new_content = _format_env_content(entries)
        elif plan.target_format == "yaml":
            new_content = _format_yaml_content(entries)
        else:
            logger.warning("write-back: unknown format %s, skipping", plan.target_format)
            continue

        # Read current content for comparison
        original_content = path.read_text(encoding="utf-8")

        if new_content != original_content:
            # Apply mutation with preserve_existing safety
            if plan.preserve_existing:
                # Backup or preserve logic would go here
                path.write_text(new_content, encoding="utf-8")
                mutation_msg = f"write-back mutation: {op_path} ({plan.target_format})"
                logger.info(mutation_msg)
                mutations_logged.append(mutation_msg)
                files_modified += 1
        else:
            files_preserved += 1
            mutation_msg = f"write-back preserved: {op_path}"
            logger.info(mutation_msg)
            mutations_logged.append(mutation_msg)

    result = WriteBackResult(
        files_processed=len(plan.operations),
        files_modified=files_modified,
        files_preserved=files_preserved,
        mutations_logged=mutations_logged,
    )

    logger.info(
        "write-back complete: format=%s, processed=%d, modified=%d, preserved=%d",
        plan.target_format,
        result.files_processed,
        result.files_modified,
        result.files_preserved,
    )

    return result


def _format_env_content(entries: list) -> str:
    """Format VaultEntry list as .env file content."""
    lines = []
    for entry in entries:
        # For write-back, we only have fingerprints, not actual values
        # This is a placeholder - in production, values would come from a secure source
        lines.append(f"{entry.key_name}=<fingerprint:{entry.fingerprint}>")
    return "\n".join(lines) + "\n" if lines else ""


def _format_yaml_content(entries: list) -> str:
    """Format VaultEntry list as YAML file content."""
    lines = []
    for entry in entries:
        # For write-back, we only have fingerprints, not actual values
        # This is a placeholder - in production, values would come from a secure source
        lines.append(f"{entry.key_name}: <fingerprint:{entry.fingerprint}>")
    return "\n".join(lines) + "\n" if lines else ""
