"""Concrete RotationAdapter implementations for vault credential rotation.

This module provides concrete RotationAdapter implementations that demonstrate
the full rotation lifecycle. These adapters are intentionally minimal and
demonstrate the contract without requiring real cloud credentials.

Each adapter:
- implements the RotationAdapter interface
- provides clear supports() semantics based on entry metadata
- implements rotate() and rollback() with observable side effects
- is suitable for testing and demonstration purposes

For production use, providers should implement their own RotationAdapter
subclasses that handle actual credential rotation via provider APIs.

Example usage:
    from hermesoptimizer.vault.providers.rotation import StubRotationAdapter
    from hermesoptimizer.vault import RotationExecutor, VaultEntry

    adapter = StubRotationAdapter()
    executor = RotationExecutor([adapter])
    entry = VaultEntry(path, "env", "API_KEY", "oldfp")
    result = executor.execute(entry, "new-secret")

Available adapters:
- StubRotationAdapter: A minimal adapter that simulates rotation for any entry.
  Used for testing and demonstration. Does not modify any files or credentials.
- EnvFileRotationAdapter: Adapter for .env files with atomic writes and rollback.
- VaultFileRotationAdapter: Adapter for vault-native encrypted storage.
"""
from __future__ import annotations

import os
import time
import weakref
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import ClassVar

from hermesoptimizer.vault import RotationAdapter, VaultEntry


class StubRotationAdapter(RotationAdapter):
    """A minimal concrete RotationAdapter for testing and demonstration.

    This adapter supports any VaultEntry and simulates rotation by recording
    the rotation attempt. It does not modify any files or credentials.

    Use this adapter to:
    - test the RotationExecutor workflow
    - demonstrate the rotation interface
    - validate the rollback behavior

    For production rotation, implement a provider-specific adapter that
    calls the actual provider API (AWS, GCP, Azure, etc.).
    """

    _registry: ClassVar[weakref.WeakSet["StubRotationAdapter"]] = weakref.WeakSet()

    def __init__(self) -> None:
        self.rotated: list[str] = []
        self.rolled_back: list[str] = []
        self._supports_all: bool = True
        StubRotationAdapter._registry.add(self)

    def supports(self, entry: VaultEntry) -> bool:
        """This stub adapter supports all entries by default.

        Override this method in subclasses to implement provider-specific
        support logic (e.g., only support AWS entries based on key_name pattern).
        """
        return self._supports_all

    def rotate(self, entry: VaultEntry, new_secret: str) -> bool:
        """Simulate rotation by recording the attempt.

        In a real adapter, this would call the provider's rotation API.
        """
        self.rotated.append(entry.key_name)
        return True

    def rollback(self, entry: VaultEntry) -> bool:
        """Simulate rollback by recording the attempt.

        In a real adapter, this would restore the previous credential.
        """
        self.rolled_back.append(entry.key_name)
        return True

    def set_support(self, supported: bool) -> None:
        """Control which entries this adapter supports (for testing)."""
        self._supports_all = supported

    @classmethod
    def cleanup_registry(cls) -> None:
        """Clean up the registry.

        Note: With WeakSet, this is a no-op since WeakSet automatically
        removes dead references. This method exists for API compatibility.
        """
        # WeakSet handles cleanup automatically, but we provide this
        # method for explicit cleanup if needed
        pass

    @classmethod
    def registry_size(cls) -> int:
        """Return the current size of the registry for testing."""
        return len(cls._registry)


class EnvFileRotationAdapter(RotationAdapter):
    """A concrete adapter that rotates credentials in .env files.

    This adapter demonstrates a real rotation workflow for env files:
    - supports() returns True for env-kind entries
    - rotate() atomically replaces the old value with the new secret
    - rollback() restores from the backup file

    Rotation is performed atomically using:
    1. Create timestamped backup file (*.vault-backup.timestamp)
    2. Write new content to temp file (*.env.tmp)
    3. fsync the temp file
    4. Atomic rename from temp to original

    Rollback restores from the backup file.
    """

    def supports(self, entry: VaultEntry) -> bool:
        """Support env-kind entries with valid source paths."""
        if entry.source_kind != "env":
            return False
        path = Path(entry.source_path)
        return path.exists() and path.is_file()

    def _get_backup_path(self, path: Path) -> Path:
        """Generate a timestamped backup file path.

        Args:
            path: Original file path

        Returns:
            Path with timestamped backup suffix
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        return path.parent / f"{path.stem}.vault-backup.{timestamp}"

    def rotate(self, entry: VaultEntry, new_secret: str) -> bool:
        """Atomically replace the credential value in the env file.

        This implementation:
        - Creates a timestamped backup before modification
        - Writes to a temp file
        - fsyncs the temp file for durability
        - Atomically renames temp to original

        Args:
            entry: The vault entry to rotate
            new_secret: The new secret value to set

        Returns:
            True if rotation succeeded, False otherwise
        """
        try:
            path = Path(entry.source_path)
            if not path.exists():
                return False

            # Read current content
            original_content = path.read_text()
            lines = original_content.splitlines()

            # Find and replace the line with the key
            key_line = f"{entry.key_name}="
            new_lines = []
            found = False
            for line in lines:
                if line.startswith(key_line):
                    new_lines.append(f"{entry.key_name}={new_secret}")
                    found = True
                else:
                    new_lines.append(line)

            if not found:
                # Key not found, append it
                new_lines.append(f"{entry.key_name}={new_secret}")

            new_content = "\n".join(new_lines) + "\n"

            # Step 1: Create timestamped backup with original content
            backup_path = self._get_backup_path(path)
            backup_path.write_text(original_content)

            # Step 2: Write new content to temp file
            temp_path = path.with_suffix(path.suffix + ".tmp")
            temp_path.write_text(new_content)

            # Step 3: fsync the temp file for durability
            with open(temp_path, "r") as f:
                f.flush()
                os.fsync(f.fileno())

            # Step 4: Atomic rename
            os.rename(temp_path, path)

            return True

        except Exception:
            # File access error - rotation failed
            return False

    def rollback(self, entry: VaultEntry) -> bool:
        """Restore the env file from the most recent backup.

        Args:
            entry: The vault entry to rollback

        Returns:
            True if rollback succeeded, False otherwise
        """
        try:
            path = Path(entry.source_path)

            # Find the most recent backup file
            backup_pattern = f"{path.stem}.vault-backup.*"
            backups = sorted(
                path.parent.glob(backup_pattern),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )

            if not backups:
                return False

            # Restore from the most recent backup
            backup_path = backups[0]
            content = backup_path.read_text()
            path.write_text(content)

            # Clean up the backup file after successful restore
            backup_path.unlink()

            return True

        except Exception:
            return False


class VaultFileRotationAdapter(RotationAdapter):
    """A concrete adapter for vault-native encrypted storage.

    This adapter handles rotation for entries with source_kind == 'vault-native'.
    It delegates to VaultSession.set() for the actual rotation and stores
    the previous value for rollback support.
    """

    def __init__(self, session: "VaultSession | None" = None) -> None:
        """Initialize the adapter with an optional VaultSession.

        Args:
            session: VaultSession instance for vault operations.
                   If None, rotation will fail gracefully.
        """
        self._session = session
        self._previous_values: dict[str, str] = {}  # Store previous values for rollback

    def supports(self, entry: VaultEntry) -> bool:
        """Support vault-native entries when session is available."""
        if entry.source_kind != "vault-native":
            return False
        return self._session is not None

    def rotate(self, entry: VaultEntry, new_secret: str) -> bool:
        """Rotate a vault-native entry using VaultSession.

        Args:
            entry: The vault entry to rotate
            new_secret: The new secret value to set

        Returns:
            True if rotation succeeded, False otherwise
        """
        if self._session is None:
            return False

        try:
            # Store previous value for rollback
            previous = self._session.get(entry.key_name)
            if previous is not None:
                self._previous_values[entry.key_name] = previous

            # Call set - note: VaultSession.set() returns None on success
            self._session.set(entry.key_name, new_secret)
            return True
        except Exception:
            return False

    def rollback(self, entry: VaultEntry) -> bool:
        """Restore a vault-native entry to its previous value.

        Args:
            entry: The vault entry to rollback

        Returns:
            True if rollback succeeded, False otherwise
        """
        if self._session is None:
            return False

        try:
            # Get the previous value we stored during rotate
            previous = self._previous_values.pop(entry.key_name, None)
            if previous is None:
                return False

            # Restore the previous value
            self._session.set(entry.key_name, previous)
            return True
        except Exception:
            return False


# --- Backup management utilities ---


def clean_old_backups(vault_root: Path, max_age_days: int = 30) -> int:
    """Delete backup files older than max_age_days.

    Args:
        vault_root: Root directory to search for backups
        max_age_days: Maximum age of backup files in days (default: 30)

    Returns:
        Number of backup files deleted
    """
    deleted = 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    vault_path = Path(vault_root)

    if not vault_path.exists():
        return 0

    # Find all backup files
    for backup_path in vault_path.rglob("*.vault-backup.*"):
        try:
            # Get modification time
            mtime = datetime.fromtimestamp(
                backup_path.stat().st_mtime,
                tz=timezone.utc
            )
            if mtime < cutoff:
                backup_path.unlink()
                deleted += 1
        except Exception:
            # Skip files we can't process
            continue

    return deleted


def find_backup_files(vault_root: Path) -> list[Path]:
    """Find all backup files in the vault root.

    Args:
        vault_root: Root directory to search for backups

    Returns:
        List of backup file paths sorted by modification time (newest first)
    """
    vault_path = Path(vault_root)
    backups: list[Path] = []

    if not vault_path.exists():
        return backups

    for backup_path in vault_path.rglob("*.vault-backup.*"):
        backups.append(backup_path)

    # Sort by modification time, newest first
    backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return backups


# Alias for backward compatibility
NoOpRotationAdapter = StubRotationAdapter
