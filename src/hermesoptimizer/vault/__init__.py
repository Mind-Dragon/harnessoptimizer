from __future__ import annotations

from .bridge import (
    VaultBridgePlan,
    WriteBackPlan,
    WriteBackResult,
    execute_write_back,
    plan_bridge,
    plan_write_back,
)
from .dedup import DeduplicationResult, deduplicate_entries
from .fingerprint import fingerprint_secret
from .inventory import (
    VaultEntry,
    VaultInventory,
    build_vault_inventory,
    default_vault_roots,
    discover_vault_files,
)
from .rotation import (
    RotationAdapter,
    RotationEvent,
    RotationExecutor,
    RotationResult,
    RotationRollback,
    execute_rotation,
    track_rotation,
)
from .validator import StatusProvider, ValidationResult, validate_inventory

__all__ = [
    "DeduplicationResult",
    "RotationAdapter",
    "RotationEvent",
    "RotationExecutor",
    "RotationResult",
    "RotationRollback",
    "StatusProvider",
    "ValidationResult",
    "VaultBridgePlan",
    "VaultEntry",
    "VaultInventory",
    "WriteBackPlan",
    "WriteBackResult",
    "build_vault_inventory",
    "deduplicate_entries",
    "default_vault_roots",
    "discover_vault_files",
    "execute_rotation",
    "execute_write_back",
    "fingerprint_secret",
    "plan_bridge",
    "plan_write_back",
    "track_rotation",
    "validate_inventory",
]
