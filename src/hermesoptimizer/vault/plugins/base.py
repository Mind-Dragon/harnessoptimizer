"""Abstract base class for vault plugins."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class VaultPlugin(ABC):
    """
    Abstract base class for vault plugins.

    All vault plugins must implement the core CRUD interface and support
    the context manager protocol for session management.
    """

    @abstractmethod
    def get(self, key_name: str) -> str | None:
        """
        Get the value for a secret key.

        Args:
            key_name: Name of the entry to retrieve

        Returns:
            Decrypted value if found, None otherwise
        """
        ...

    @abstractmethod
    def set(self, key_name: str, value: str, is_encrypted: bool = True) -> None:
        """
        Store a secret value in the vault.

        Args:
            key_name: Name of the entry
            value: The secret value to store
            is_encrypted: Whether to encrypt the value (default True)
        """
        ...

    @abstractmethod
    def delete(self, key_name: str) -> None:
        """
        Delete a secret from the vault.

        Args:
            key_name: Name of the entry to delete
        """
        ...

    @abstractmethod
    def list_entries(self) -> list[dict[str, Any]]:
        """
        List all entries in the vault.

        Returns:
            List of entry dicts, each containing key_name and other metadata
        """
        ...

    def status(self) -> dict[str, Any]:
        """
        Return plugin status information.

        Returns:
            Dict containing plugin_name, vault_path, entry_count, and encrypted_count
        """
        entries = self.list_entries()
        encrypted_count = sum(1 for e in entries if e.get("is_encrypted", False))
        return {
            "plugin_name": self.__class__.__name__,
            "vault_path": getattr(self, "_vault_path", None),
            "entry_count": len(entries),
            "encrypted_count": encrypted_count,
        }

    def __enter__(self) -> VaultPlugin:
        """Enter the context manager session."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Exit the context manager session and clean up resources."""
        pass
