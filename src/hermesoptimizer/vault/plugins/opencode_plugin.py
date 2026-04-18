"""OpenCodePlugin - Read-only plugin for OpenCode-compatible config generation."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from hermesoptimizer.vault.plugins.base import VaultPlugin
from hermesoptimizer.vault.session import VaultSession

DEFAULT_VAULT_PATH = os.path.expanduser("~/.vault/")
DEFAULT_PASSPHRASE = "hermes-vault-default"


class OpenCodePlugin(VaultPlugin):
    """
    Read-only vault plugin that generates OpenCode-compatible configuration.

    This plugin provides read access to vault entries for generating
    OpenCode configuration files and injecting environment variables.
    Write operations (set/delete) raise NotImplementedError.

    Args:
        vault_path: Path to vault root (default ~/.vault/)
        passphrase: Passphrase for vault decryption (default 'hermes-vault-default')

    Example:
        with OpenCodePlugin() as plugin:
            config = plugin.generate_config("opencode.yaml")
            env_vars = plugin.inject_env()
    """

    def __init__(
        self,
        vault_path: str | Path | None = None,
        passphrase: str = DEFAULT_PASSPHRASE,
    ) -> None:
        import base64
        from hermesoptimizer.vault.crypto import derive_key

        self._vault_path = vault_path or DEFAULT_VAULT_PATH
        self._passphrase = passphrase

        # Create the underlying session
        vault_root = Path(self._vault_path)
        if not vault_root.exists():
            vault_root.mkdir(parents=True, exist_ok=True)

        # Check VAULT_MASTER_KEY env var first (like VaultSession does)
        env_key = os.environ.get("VAULT_MASTER_KEY")
        if env_key:
            try:
                master_key = base64.b64decode(env_key)
            except Exception:
                master_key, _ = derive_key(passphrase)
        else:
            # Try to load salt from existing vault.enc.json to derive consistent key
            enc_path = vault_root / "vault.enc.json"
            stored_salt = self._load_salt_from_vault(enc_path)
            if stored_salt:
                master_key, _ = derive_key(passphrase, stored_salt)
            else:
                master_key, _ = derive_key(passphrase)

        self._session = VaultSession(vault_root=vault_root, master_key=master_key)
        self._session_entered = False

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
        """Get decrypted value for a secret key (read-only access)."""
        # Auto-enter context if not already entered (for convenience)
        if not self._session_entered:
            self._session.__enter__()
            self._session_entered = True
        return self._session.get(key_name)

    def set(self, key_name: str, value: str, is_encrypted: bool = True) -> None:
        """Not implemented - OpenCode vault plugin is read-only."""
        raise NotImplementedError(
            "OpenCode vault plugin is read-only; use Hermes plugin for writes"
        )

    def delete(self, key_name: str) -> None:
        """Not implemented - OpenCode vault plugin is read-only."""
        raise NotImplementedError(
            "OpenCode vault plugin is read-only; use Hermes plugin for writes"
        )

    def list_entries(self) -> list[dict[str, Any]]:
        """List all entries in the vault (read-only access)."""
        # Auto-enter context if not already entered (for convenience)
        if not self._session_entered:
            self._session.__enter__()
            self._session_entered = True
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

    def generate_config(self, output_path: str | Path) -> None:
        """
        Generate an OpenCode-compatible YAML config file.

        The config maps key_name to fingerprint (not actual values) for
        reference purposes.

        Args:
            output_path: Path where to write the YAML config file

        Example output:
            ANTHROPIC_API_KEY:
                fingerprint: fp20:abc123def456
                is_encrypted: true
            API_URL:
                fingerprint: fp20:789xyz
                is_encrypted: false
        """
        entries = self.list_entries()
        config: dict[str, dict[str, Any]] = {}

        for entry in entries:
            key_name = entry["key_name"]
            config[key_name] = {
                "fingerprint": entry["fingerprint"],
                "is_encrypted": entry["is_encrypted"],
            }

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        with open(output, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    def inject_env(self, prefix: str = "VAULT_") -> dict[str, str]:
        """
        Generate environment variables for all secret entries.

        Decrypts and returns real values for all encrypted entries,
        returning them as a dict of {PREFIX_KEY_NAME: value}.

        Args:
            prefix: Prefix for environment variable names (default 'VAULT_')

        Returns:
            Dict mapping environment variable names to their secret values

        Example:
            {"VAULT_ANTHROPIC_API_KEY": "sk-ant-xxxxx", "VAULT_API_URL": "https://..."}
        """
        entries = self.list_entries()
        env_vars: dict[str, str] = {}

        for entry in entries:
            key_name = entry["key_name"]
            # Get the actual decrypted value
            value = self.get(key_name)
            if value is not None:
                env_key = f"{prefix}{key_name}"
                env_vars[env_key] = value

        return env_vars

    def status(self) -> dict[str, Any]:
        """Return plugin status (read-only view)."""
        entries = self.list_entries()
        encrypted_count = sum(1 for e in entries if e.get("is_encrypted", False))
        return {
            "plugin_name": self.__class__.__name__,
            "vault_path": self._vault_path,
            "entry_count": len(entries),
            "encrypted_count": encrypted_count,
            "readonly": True,
        }

    def __enter__(self) -> OpenCodePlugin:
        """Enter context manager - open vault session."""
        self._session.__enter__()
        return self

    def __exit__(self, *args: Any) -> None:
        """Exit context manager - close vault session."""
        self._session.__exit__(*args)
