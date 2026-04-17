from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from .inventory import VaultEntry

if TYPE_CHECKING:
    pass


# --- RotationEvent with timestamp ---


@dataclass(frozen=True, slots=True)
class RotationEvent:
    source_path: str
    previous_fingerprint: str
    current_fingerprint: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# --- RotationAdapter interface ---


class RotationAdapter(ABC):
    """Abstract interface for credential rotation implementations.

    Concrete adapters (e.g., StubRotationAdapter, EnvFileRotationAdapter)
    implement this interface. The adapter handles:
    - Checking if it supports a given entry (provider detection)
    - Performing the actual rotation with new secret
    - Rolling back to the previous secret on failure
    """

    @abstractmethod
    def supports(self, entry: VaultEntry) -> bool:
        """Check if this adapter supports rotating the given entry.

        Args:
            entry: The vault entry to check for support.

        Returns:
            True if this adapter can handle rotation for this entry,
            False otherwise.
        """
        ...

    @abstractmethod
    def rotate(self, entry: VaultEntry, new_secret: str) -> bool:
        """Execute rotation for the given entry with the new secret.

        Args:
            entry: The vault entry to rotate.
            new_secret: The new secret value to set.

        Returns:
            True if rotation succeeded, False otherwise.
        """
        ...

    @abstractmethod
    def rollback(self, entry: VaultEntry) -> bool:
        """Rollback a failed rotation to the previous secret.

        Args:
            entry: The vault entry to rollback.

        Returns:
            True if rollback succeeded, False otherwise.
        """
        ...


# --- RotationResult ---


@dataclass
class RotationResult:
    """Result of a rotation execution attempt."""

    success: bool
    event: RotationEvent | None = None
    error: str | None = None
    executed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    previous_fingerprint: str | None = None
    new_fingerprint: str | None = None
    rollback_info: "RotationRollback | None" = None


# --- RotationRollback ---


@dataclass
class RotationRollback:
    """Stores information needed to rollback a failed rotation."""

    entry: VaultEntry
    previous_secret: str
    reason: str


# --- RotationExecutor ---


class RotationExecutor:
    """Executes rotation using one or more provider adapters.

    The executor tries each adapter in order until one supports
    and successfully rotates the entry. If all adapters fail,
    the rotation is considered unsuccessful.
    """

    def __init__(self, adapters: list[RotationAdapter]) -> None:
        self.adapters = adapters

    def execute(self, entry: VaultEntry, new_secret: str) -> RotationResult:
        """Execute rotation for the given entry.

        Args:
            entry: The vault entry to rotate.
            new_secret: The new secret value to set.

        Returns:
            RotationResult indicating success/failure and details.
            On failure, rollback_info is populated with details for manual recovery.
        """
        previous_fingerprint = entry.fingerprint
        last_failed_adapter: RotationAdapter | None = None
        last_error: str | None = None

        for adapter in self.adapters:
            if not adapter.supports(entry):
                continue

            success = adapter.rotate(entry, new_secret)
            if success:
                # Import here to avoid circular dependency at module level
                from .fingerprint import fingerprint_secret

                new_fp = fingerprint_secret(new_secret)
                event = RotationEvent(
                    source_path=str(entry.source_path),
                    previous_fingerprint=previous_fingerprint,
                    current_fingerprint=new_fp,
                    timestamp=datetime.now(timezone.utc),
                )
                return RotationResult(
                    success=True,
                    event=event,
                    previous_fingerprint=previous_fingerprint,
                    new_fingerprint=new_fp,
                )
            # Track the last failed adapter for rollback
            last_failed_adapter = adapter
            last_error = "Adapter failed to rotate"

        # Only reached if no adapter succeeded
        # Check if any adapter even supported this entry
        any_supported = any(a.supports(entry) for a in self.adapters)
        if not any_supported:
            return RotationResult(
                success=False,
                error="No adapter supports this entry",
                previous_fingerprint=previous_fingerprint,
            )

        # All supported adapters failed - call rollback on the last one
        rollback_info: RotationRollback | None = None
        if last_failed_adapter is not None:
            rollback_reason = last_error or "Rotation failed"
            # Attempt rollback on the failed adapter
            rollback_success = last_failed_adapter.rollback(entry)
            rollback_info = RotationRollback(
                entry=entry,
                previous_secret="",  # Caller should fetch from secure storage
                reason=rollback_reason,
            )
            if not rollback_success:
                rollback_info = RotationRollback(
                    entry=entry,
                    previous_secret="",
                    reason=f"{rollback_reason} (rollback also failed)",
                )

        return RotationResult(
            success=False,
            error=last_error or "All adapters failed to rotate",
            previous_fingerprint=previous_fingerprint,
            rollback_info=rollback_info,
        )


# --- Convenience function ---


def execute_rotation(
    entry: VaultEntry,
    new_secret: str,
    *,
    adapters: list[RotationAdapter] | None = None,
) -> RotationResult:
    """Convenience function to execute rotation with adapters.

    Args:
        entry: The vault entry to rotate.
        new_secret: The new secret value to set.
        adapters: Optional list of rotation adapters. If None, uses default
            no-op behavior (for testing/mocking).

    Returns:
        RotationResult indicating success/failure and details.
    """
    if adapters is None:
        adapters = []

    executor = RotationExecutor(adapters)
    return executor.execute(entry, new_secret)


# --- Existing track_rotation (enhanced with timestamp) ---


def track_rotation(previous: VaultEntry | None, current: VaultEntry) -> RotationEvent | None:
    """Detect when a credential has been rotated (fingerprint changed).

    Args:
        previous: The previous vault entry state (or None if new).
        current: The current vault entry state.

    Returns:
        RotationEvent with timestamp if rotation detected, None otherwise.
    """
    if previous is None:
        return None
    if previous.fingerprint == current.fingerprint:
        return None
    return RotationEvent(
        source_path=str(current.source_path),
        previous_fingerprint=previous.fingerprint,
        current_fingerprint=current.fingerprint,
        timestamp=datetime.now(timezone.utc),
    )
