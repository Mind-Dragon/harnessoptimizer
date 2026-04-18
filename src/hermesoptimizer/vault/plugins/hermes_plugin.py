"""HermesPlugin - Direct VaultSession integration."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from hermesoptimizer.vault.plugins.base import VaultPlugin
from hermesoptimizer.vault.session import VaultSession

# Default vault path
DEFAULT_VAULT_PATH = os.path.expanduser("~/.vault/")
DEFAULT_PASSPHRASE = "hermes-vault-default"


class HermesPlugin(VaultPlugin):
    """
    Direct VaultSession plugin for hermesoptimizer vault.

    This plugin provides direct Python access to vault credentials
    using the VaultSession context manager internally.

    Args:
        vault_path: Path to the vault root directory (default ~/.vault/)
        passphrase: Passphrase for deriving the master key (default 'hermes-vault-default')

    Example:
        with HermesPlugin() as plugin:
            plugin.set("API_KEY", "secret-value")
            value = plugin.get("API_KEY")
    """

    def __init__(
        self,
        vault_path: str | Path | None = None,
        passphrase: str = DEFAULT_PASSPHRASE,
    ) -> None:
        """
        Initialize HermesPlugin with vault path and passphrase.

        Args:
            vault_path: Path to vault root. Defaults to ~/.vault/
            passphrase: Passphrase for key derivation. Defaults to 'hermes-vault-default'
        """
        import base64
        from hermesoptimizer.vault.crypto import derive_key

        self._vault_path = vault_path or DEFAULT_VAULT_PATH
        vault_root = Path(self._vault_path)
        if not vault_root.exists():
            vault_root.mkdir(parents=True, exist_ok=True)

        # Check VAULT_MASTER_KEY env var first (like VaultSession does)
        env_key = os.environ.get("VAULT_MASTER_KEY")
        if env_key:
            try:
                self._master_key = base64.b64decode(env_key)
            except Exception:
                # Fall back to derive_key if decode fails
                self._master_key, _ = derive_key(passphrase)
        else:
            # Try to load salt from existing vault.enc.json to derive consistent key
            enc_path = vault_root / "vault.enc.json"
            stored_salt = self._load_salt_from_vault(enc_path)
            if stored_salt:
                self._master_key, _ = derive_key(passphrase, stored_salt)
            else:
                self._master_key, _ = derive_key(passphrase)

        # Create internal session (not entered yet)
        self._session = VaultSession(vault_root=vault_root, master_key=self._master_key)

    def _load_salt_from_vault(self, enc_path: Path) -> bytes | None:
        """Load salt from vault.enc.json if it exists."""
        import base64
        import json

        if not enc_path.exists():
            return None

        try:
            content = enc_path.read_text(encoding="utf-8")
            data = json.loads(content)
            salt_b64 = data.get("salt")
            if salt_b64:
                return base64.b64decode(salt_b64)
        except Exception:
            pass
        return None

    def get(self, key_name: str) -> str | None:
        """
        Get the decrypted value for a secret key.

        Args:
            key_name: Name of the entry to retrieve

        Returns:
            Decrypted value if found, None otherwise
        """
        return self._session.get(key_name)

    def set(self, key_name: str, value: str, is_encrypted: bool = True) -> None:
        """
        Store a secret value in the vault.

        Args:
            key_name: Name of the entry
            value: The secret value to store
            is_encrypted: Whether to encrypt the value (default True)
        """
        self._session.set(key_name, value, encrypted=is_encrypted)

    def delete(self, key_name: str) -> None:
        """
        Delete a secret from the vault.

        Args:
            key_name: Name of the entry to delete
        """
        self._session.delete(key_name)

    def list_entries(self) -> list[dict[str, Any]]:
        """
        List all entries in the vault.

        Returns:
            List of dicts with key_name, fingerprint, is_encrypted, source_file
        """
        entries = self._session.list_entries()
        return [
            {
                "key_name": entry.key_name,
                "fingerprint": entry.fingerprint,
                "is_encrypted": entry.is_encrypted,
                "source_file": str(entry.source_path),
            }
            for entry in entries
        ]

    def status(self) -> dict[str, Any]:
        """Return plugin status."""
        entries = self.list_entries()
        encrypted_count = sum(1 for e in entries if e.get("is_encrypted", False))
        return {
            "plugin_name": self.__class__.__name__,
            "vault_path": self._vault_path,
            "entry_count": len(entries),
            "encrypted_count": encrypted_count,
        }

    def __enter__(self) -> HermesPlugin:
        """Enter context manager - open vault session."""
        self._session.__enter__()
        return self

    def __exit__(self, *args: Any) -> None:
        """Exit context manager - close vault session."""
        self._session.__exit__(*args)
