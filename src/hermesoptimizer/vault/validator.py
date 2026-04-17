from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import time

from .inventory import VaultEntry, VaultInventory


@dataclass(frozen=True, slots=True)
class ValidationResult:
    source_path: str | None
    ok: bool
    status: str
    message: str


# Hook type: given an entry, return a ValidationResult override or None to skip
StatusProvider = Callable[[VaultEntry], ValidationResult | None]


def _default_status_resolver(
    entry: VaultEntry,
    stale_after_seconds: float,
) -> ValidationResult:
    """Default read-only file-age based status resolution."""
    path = Path(entry.source_path)
    if not path.exists():
        return ValidationResult(
            source_path=str(path),
            ok=False,
            status="missing",
            message="source file is missing",
        )

    age = time.time() - path.stat().st_mtime
    if age > stale_after_seconds:
        return ValidationResult(
            source_path=str(path),
            ok=False,
            status="stale",
            message="source file has not been refreshed recently",
        )

    return ValidationResult(
        source_path=str(path),
        ok=True,
        status="active",
        message="source file is present and fresh",
    )


def validate_inventory(
    inventory: VaultInventory,
    *,
    stale_after_days: int = 30,
    status_provider: StatusProvider | None = None,
) -> list[ValidationResult]:
    """Read-only inventory validation.

    This checks source existence and freshness without mutating any vault.

    Args:
        inventory: The vault inventory to validate.
        stale_after_days: File age threshold for stale status (default 30).
        status_provider: Optional hook to inject provider-backed status resolution.
            Receives each VaultEntry and returns a ValidationResult to use,
            or None to fall back to the default file-age resolver.

    The status_provider hook allows callers to replace or augment the default
    file-age check with provider-specific logic (e.g., remote API status lookups)
    while preserving the read-only contract.
    """
    results: list[ValidationResult] = []
    stale_after_seconds = stale_after_days * 24 * 60 * 60

    for entry in inventory.entries:
        if status_provider is not None:
            override = status_provider(entry)
            if override is not None:
                results.append(override)
                continue

        # Fall back to default file-age resolver
        results.append(_default_status_resolver(entry, stale_after_seconds))

    return results
