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
"""
from __future__ import annotations

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

    _registry: ClassVar[list[StubRotationAdapter]] = []

    def __init__(self) -> None:
        self.rotated: list[str] = []
        self.rolled_back: list[str] = []
        self._supports_all: bool = True
        StubRotationAdapter._registry.append(self)

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


class EnvFileRotationAdapter(RotationAdapter):
    """A concrete adapter that rotates credentials in .env files.

    This adapter demonstrates a real rotation workflow for env files:
    - supports() returns True for env-kind entries
    - rotate() replaces the old value with the new secret
    - rollback() is not implemented (env files don't support easy rollback)

    WARNING: This adapter actually modifies files. Use with caution and
    always ensure you have backups of your .env files.

    For production use, consider:
    - Using atomic file operations
    - Implementing proper rollback with backup files
    - Adding confirmation prompts before rotation
    """

    def supports(self, entry: VaultEntry) -> bool:
        """Support env-kind entries with valid source paths."""
        if entry.source_kind != "env":
            return False
        path = Path(entry.source_path)
        return path.exists() and path.is_file()

    def rotate(self, entry: VaultEntry, new_secret: str) -> bool:
        """Replace the credential value in the env file.

        This is a simplified implementation that:
        - Reads the file
        - Replaces the line containing the key
        - Writes back the modified content

        A production implementation should:
        - Use atomic file operations
        - Create backup files before modification
        - Handle concurrent access properly
        """
        try:
            path = Path(entry.source_path)
            if not path.exists():
                return False

            # Read current content
            lines = path.read_text().splitlines()

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

            # Write back (simplified - no atomic operation)
            path.write_text("\n".join(new_lines) + "\n")
            return True

        except Exception:
            # File access error - rotation failed
            return False

    def rollback(self, entry: VaultEntry) -> bool:
        """Env files don't support easy rollback.

        This is a known limitation - env file rotation should ideally
        be accompanied by backup files or a version control system.
        """
        return False  # Cannot rollback env file changes


# Alias for backward compatibility
NoOpRotationAdapter = StubRotationAdapter
