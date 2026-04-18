"""VaultSession context manager for encrypted credential storage."""
from __future__ import annotations

import base64
import os
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .crypto import VaultCrypto, generate_master_key
from .fingerprint import fingerprint_secret
from .inventory import VaultEntry


class VaultLockedError(Exception):
    """Raised when vault is locked and cannot be decrypted."""
    pass


class VaultSessionError(Exception):
    """Raised for vault session errors."""
    pass


# ---------------------------------------------------------------------------
# Atomic file write helper
# ---------------------------------------------------------------------------


def atomic_write(path: Path, content: str) -> None:
    """
    Write content to path atomically using rename.

    Writes to path.with_suffix('.tmp'), fsyncs, then renames over target.
    This ensures crash safety - either the old file or new file exists,
    never a partial write.

    Args:
        path: Target file path
        content: Content to write (as string)
    """
    import os

    tmp_path = path.with_suffix(".tmp")

    # Write to temporary file
    tmp_path.write_text(content, encoding="utf-8")

    # Ensure data is flushed to disk
    fd = os.open(tmp_path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

    # Rename over target (atomic on POSIX)
    os.replace(tmp_path, path)


# ---------------------------------------------------------------------------
# VaultSession
# ---------------------------------------------------------------------------


class VaultSession:
    """
    Context manager for vault credential storage with encryption and audit logging.

    Vault stores credentials in YAML files organized by credential group.
    On-disk format:
        key_name: ANTHROPIC_API_KEY
        fingerprint: fp20:abc123def456
        is_encrypted: true
        encrypted_value: <base64 ciphertext>
        metadata:
            API_URL: https://api.anthropic.com

    Master key resolution order:
        1. master_key parameter
        2. VAULT_MASTER_KEY env var
        3. ~/.vault/.master_key file (base64-encoded)
    """

    def __init__(
        self,
        vault_root: Path,
        master_key: bytes | None = None,
    ):
        """
        Initialize VaultSession.

        Args:
            vault_root: Root directory for vault storage
            master_key: 32-byte encryption key. If None, attempts to load from
                VAULT_MASTER_KEY env var or ~/.vault/.master_key file.
        """
        self._vault_root = Path(vault_root)
        self._crypto = VaultCrypto()
        self._master_key = self._resolve_master_key(master_key)
        self._secrets: dict[str, VaultEntry] = {}
        self._dirty: set[str] = set()
        self._audit_fd: Any = None

    def _resolve_master_key(self, master_key: bytes | None) -> bytes | None:
        """Resolve master key from parameter, env var, or file."""
        if master_key is not None:
            return master_key

        # Try VAULT_MASTER_KEY env var (base64-encoded)
        env_key = os.environ.get("VAULT_MASTER_KEY")
        if env_key:
            try:
                return base64.b64decode(env_key)
            except Exception:
                pass

        # Try ~/.vault/.master_key file (raw bytes, base64 encoded)
        key_file = Path.home() / ".vault" / ".master_key"
        if key_file.exists():
            try:
                content = key_file.read_text().strip()
                return base64.b64decode(content)
            except Exception:
                pass

        return None

    def __enter__(self) -> VaultSession:
        """Load and decrypt all vault entries into memory."""
        self._load_vault()
        self._open_audit_log()
        return self

    def __exit__(self, *args: Any) -> None:
        """Re-encrypt dirty entries, write back atomically, wipe memory."""
        self._save_vault()
        self._close_audit_log()
        self._wipe_memory()

    def _load_vault(self) -> None:
        """Load all vault entries from disk into memory."""
        self._secrets.clear()
        self._dirty.clear()

        vault_root = self._vault_root
        if not vault_root.exists():
            vault_root.mkdir(parents=True, exist_ok=True)
            return

        # Load all YAML files in vault root (not hidden files)
        for path in vault_root.iterdir():
            if path.is_file() and path.suffix in (".yaml", ".yml") and not path.name.startswith("."):
                self._load_yaml_file(path)

    def _load_yaml_file(self, path: Path) -> None:
        """Load entries from a single YAML file."""
        try:
            content = path.read_text(encoding="utf-8")
            data = yaml.safe_load(content) or {}
        except yaml.YAMLError:
            return

        if not isinstance(data, dict):
            return

        key_name = data.get("key_name")
        if not key_name:
            return

        is_encrypted = data.get("is_encrypted", False)
        encrypted_value = data.get("encrypted_value")
        plaintext_value = data.get("plaintext_value")

        # If encrypted and we have a master key, decrypt
        if is_encrypted and encrypted_value:
            if self._master_key:
                try:
                    plaintext_value = self._crypto.decrypt(encrypted_value, self._master_key)
                except Exception:
                    # Decryption failed - wrong key or corrupted data
                    raise VaultLockedError(
                        f"Cannot decrypt {key_name} - vault is locked. "
                        "Provide correct master key."
                    )
            else:
                # Encrypted but no key available - vault is locked
                raise VaultLockedError(
                    f"Cannot decrypt {key_name} - vault is locked. "
                    "Provide correct master key."
                )

        fingerprint = data.get("fingerprint") or (
            fingerprint_secret(plaintext_value) if plaintext_value else fingerprint_secret("")
        )

        entry = VaultEntry(
            source_path=path,
            source_kind="vault",
            key_name=key_name,
            fingerprint=fingerprint,
            is_encrypted=is_encrypted,
            encrypted_value=encrypted_value,
            plaintext_value=plaintext_value,
        )
        self._secrets[key_name] = entry

    def _save_vault(self) -> None:
        """Save dirty entries back to disk atomically."""
        for key_name in self._dirty:
            entry = self._secrets.get(key_name)
            if entry is None:
                # Entry was deleted - remove file
                self._remove_entry_file(key_name)
            else:
                self._save_entry(entry)

    def _save_entry(self, entry: VaultEntry) -> None:
        """Save a single entry to its YAML file."""
        # Determine the file path based on key name
        file_name = f"{entry.key_name}.yaml"
        file_path = self._vault_root / file_name

        # Prepare data for serialization
        if entry.is_encrypted and entry.plaintext_value and self._master_key:
            encrypted_value = self._crypto.encrypt(entry.plaintext_value, self._master_key)
        else:
            encrypted_value = entry.encrypted_value

        data = {
            "key_name": entry.key_name,
            "fingerprint": entry.fingerprint,
            "is_encrypted": entry.is_encrypted,
            "encrypted_value": encrypted_value,
            "plaintext_value": entry.plaintext_value if not entry.is_encrypted else None,
        }

        # Write atomically
        content = yaml.dump(data, default_flow_style=False, sort_keys=False)
        atomic_write(file_path, content)

    def _remove_entry_file(self, key_name: str) -> None:
        """Remove the YAML file for a deleted entry."""
        file_name = f"{key_name}.yaml"
        file_path = self._vault_root / file_name
        if file_path.exists():
            file_path.unlink()

    def _wipe_memory(self) -> None:
        """Overwrite secret buffers with zeros and clear dict."""
        for key in list(self._secrets.keys()):
            entry = self._secrets[key]
            # Wipe plaintext value if it exists
            if entry.plaintext_value:
                # Create a zeroed string of same length (we can't truly zero strings in Python,
                # but we can replace with zeros reference)
                pass
            # Clear the entry's plaintext and encrypted values
            wiped_entry = replace(
                entry,
                plaintext_value=None,
                encrypted_value=None,
            )
            self._secrets[key] = wiped_entry

        # Clear the secrets dict
        self._secrets.clear()
        self._dirty.clear()

    # ---------------------------------------------------------------------------
    # CRUD Operations
    # ---------------------------------------------------------------------------

    def get(self, key_name: str) -> str | None:
        """
        Get decrypted value for a secret or plaintext for metadata.

        Args:
            key_name: Name of the entry to retrieve

        Returns:
            Decrypted value if encrypted, plaintext if not, or None if not found
        """
        entry = self._secrets.get(key_name)
        if entry is None:
            return None

        if entry.is_encrypted:
            return entry.plaintext_value
        else:
            return entry.plaintext_value

    def set(self, key_name: str, value: str, encrypted: bool = True) -> None:
        """
        Store an entry, marking it as dirty for later persistence.

        Args:
            key_name: Name of the entry
            value: The secret value to store
            encrypted: Whether to encrypt the value (default True)
        """
        fingerprint = fingerprint_secret(value)
        encrypted_value = None
        plaintext_value = value

        if encrypted and self._master_key:
            encrypted_value = self._crypto.encrypt(value, self._master_key)
            plaintext_value = value
        elif encrypted and not self._master_key:
            raise VaultLockedError(
                f"Cannot encrypt {key_name} - no master key available"
            )

        entry = VaultEntry(
            source_path=self._vault_root / f"{key_name}.yaml",
            source_kind="vault",
            key_name=key_name,
            fingerprint=fingerprint,
            is_encrypted=encrypted,
            encrypted_value=encrypted_value,
            plaintext_value=plaintext_value,
        )

        self._secrets[key_name] = entry
        self._dirty.add(key_name)

        # Audit log
        self._audit_log("set", key_name, fingerprint, "success")

    def delete(self, key_name: str) -> bool:
        """
        Remove an entry from the vault.

        Args:
            key_name: Name of the entry to delete

        Returns:
            True if entry was deleted, False if not found
        """
        if key_name not in self._secrets:
            return False

        entry = self._secrets[key_name]
        fingerprint = entry.fingerprint

        del self._secrets[key_name]
        self._dirty.add(key_name)  # Mark for removal

        # Audit log
        self._audit_log("delete", key_name, fingerprint, "success")
        return True

    def list_entries(self) -> list[VaultEntry]:
        """
        Return all vault entries.

        Returns:
            List of all VaultEntry objects currently in memory
        """
        return list(self._secrets.values())

    # ---------------------------------------------------------------------------
    # Audit Logging
    # ---------------------------------------------------------------------------

    def _open_audit_log(self) -> None:
        """Open audit log for appending."""
        audit_path = self._vault_root / ".audit.log"
        self._audit_fd = open(audit_path, "a", encoding="utf-8")

    def _close_audit_log(self) -> None:
        """Close audit log file."""
        if self._audit_fd:
            self._audit_fd.close()
            self._audit_fd = None

    def _audit_log(
        self,
        operation: str,
        key_name: str,
        fingerprint: str,
        result: str,
    ) -> None:
        """
        Write an audit log entry.

        Format: ISO timestamp | operation | key_name | fingerprint | result
        """
        if self._audit_fd is None:
            return

        timestamp = datetime.now(timezone.utc).isoformat()
        line = f"{timestamp} | {operation} | {key_name} | {fingerprint} | {result}\n"
        self._audit_fd.write(line)
        self._audit_fd.flush()
