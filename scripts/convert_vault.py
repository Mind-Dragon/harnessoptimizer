#!/usr/bin/env python3
"""Vault conversion script: converts plaintext vault entries to encrypted format.

This script:
1. Creates a timestamped backup of ~/.vault
2. Scans ~/.vault using build_vault_inventory()
3. Encrypts secrets (key names matching secret pattern, values >= 8 chars)
4. Keeps metadata as plaintext
5. Writes vault.enc.json with the encrypted entries

Usage:
    python convert_vault.py [--dry-run]
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hermesoptimizer.vault import (
    VaultEntry,
    build_vault_inventory,
    classify_key,
    default_vault_roots,
    fingerprint_secret,
)
from hermesoptimizer.vault.crypto import VaultCrypto, derive_key


# Secret patterns: case-insensitive contains match
_SECRET_PATTERNS = (
    "key", "token", "secret", "password", "pass", "credential", "pat", "api_key", "apikey", "auth"
)


def is_secret_key(key_name: str) -> bool:
    """Check if key name matches secret pattern (case-insensitive contains)."""
    key_lower = key_name.lower()
    for pattern in _SECRET_PATTERNS:
        if pattern in key_lower:
            return True
    return False


# Fixed salt for the default passphrase key derivation
# This ensures the same key is derived every time for the same passphrase
_DEFAULT_KEY_SALT = b"hermes-vault-default-salt-v1"


def get_master_key(vault_path: Path | None = None) -> bytes:
    """Get master key from VAULT_MASTER_KEY env var or derive from default passphrase.

    Uses a fixed salt for the default passphrase to ensure consistent key derivation.
    """
    env_key = os.environ.get("VAULT_MASTER_KEY")
    if env_key:
        try:
            return base64.b64decode(env_key)
        except Exception:
            pass

    # Derive from 'hermes-vault-default' passphrase with fixed salt
    passphrase = "hermes-vault-default"
    derived_key, _ = derive_key(passphrase, salt=_DEFAULT_KEY_SALT)
    return derived_key


def create_backup(vault_path: Path) -> Path | None:
    """Create timestamped backup of vault directory."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = vault_path.parent / f".vault.backup.{timestamp}"

    try:
        # Use shutil.copytree for a proper recursive copy
        shutil.copytree(vault_path, backup_path, dirs_exist_ok=False)
        return backup_path
    except Exception as e:
        print(f"Warning: Backup failed: {e}")
        return None


def convert_entry(entry: VaultEntry, crypto: VaultCrypto, master_key: bytes) -> dict:
    """Convert a VaultEntry to the vault.enc.json format.

    Args:
        entry: The vault entry to convert
        crypto: VaultCrypto instance for encryption
        master_key: 32-byte encryption key

    Returns:
        Dict in the vault.enc.json entry format
    """
    # Get the plaintext value (from inventory, it's in plaintext_value for metadata,
    # but for secrets classified by the parser, it's None since they were not encrypted)
    # We need the actual value - for inventory entries, plaintext_value is only set
    # for metadata entries. For secrets, we need to get the value from the source.
    key_name = entry.key_name
    source_file = entry.source_path.name
    fingerprint = entry.fingerprint

    # Determine if we should encrypt based on key name pattern AND value length
    should_encrypt = is_secret_key(key_name)

    # For entries from build_vault_inventory:
    # - Metadata entries have plaintext_value set
    # - Secret entries have plaintext_value=None (value not stored)

    # We need to read the actual value from the source file to check length and encrypt
    actual_value = entry.plaintext_value

    # If plaintext_value is None (secret entry), we need to get the value from source
    if actual_value is None:
        actual_value = _get_secret_value_from_source(entry)
        if actual_value is None:
            # Could not retrieve value, treat as metadata without encryption
            should_encrypt = False

    # Check value length requirement for encryption
    value_length_ok = actual_value is not None and len(actual_value) >= 8

    if should_encrypt and value_length_ok:
        # Encrypt the value
        encrypted_value = crypto.encrypt(actual_value, master_key)
        return {
            "key_name": key_name,
            "fingerprint": fingerprint,
            "source_file": source_file,
            "is_encrypted": True,
            "encrypted_value": encrypted_value,
            "plaintext_value": None,
        }
    else:
        # Keep as plaintext metadata (or value too short to encrypt)
        return {
            "key_name": key_name,
            "fingerprint": fingerprint,
            "source_file": source_file,
            "is_encrypted": False,
            "encrypted_value": None,
            "plaintext_value": actual_value,
        }


def _get_secret_value_from_source(entry: VaultEntry) -> str | None:
    """Extract the actual secret value from the source file.

    This is needed because inventory entries for secrets don't store the value.
    """
    source_path = entry.source_path
    key_name = entry.key_name

    if not source_path.exists():
        return None

    suffix = source_path.suffix.lower()

    try:
        if suffix == ".env":
            return _get_value_from_env(source_path, key_name)
        elif suffix in (".yaml", ".yml"):
            return _get_value_from_yaml(source_path, key_name)
        elif suffix == ".json":
            return _get_value_from_json(source_path, key_name)
        elif suffix == ".toml":
            return _get_value_from_toml(source_path, key_name)
        else:
            # For other file types, try line-based parsing
            return _get_value_from_text(source_path, key_name)
    except Exception:
        return None


def _get_value_from_env(path: Path, key_name: str) -> str | None:
    """Extract value from .env file."""
    content = path.read_text(encoding="utf-8")
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        # Strip quotes
        if v.startswith('"') and v.endswith('"'):
            v = v[1:-1]
        elif v.startswith("'") and v.endswith("'"):
            v = v[1:-1]
        if k == key_name:
            return v
    return None


def _get_value_from_yaml(path: Path, key_name: str) -> str | None:
    """Extract value from YAML file using dot notation for nested keys."""
    import yaml

    content = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError:
        return None

    if not isinstance(data, dict):
        return None

    # Handle nested keys via dot notation
    parts = key_name.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None

    if isinstance(current, str):
        return current
    return None


def _get_value_from_json(path: Path, key_name: str) -> str | None:
    """Extract value from JSON file using dot notation for nested keys."""
    content = path.read_text(encoding="utf-8")
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict):
        return None

    # Handle nested keys via dot notation
    parts = key_name.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None

    if isinstance(current, str):
        return current
    return None


def _get_value_from_toml(path: Path, key_name: str) -> str | None:
    """Extract value from TOML file using dot notation for nested keys."""
    import tomllib

    content = path.read_bytes()
    try:
        data = tomllib.loads(content.decode("utf-8"))
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    # Handle nested keys via dot notation
    parts = key_name.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None

    if isinstance(current, str):
        return current
    return None


def _get_value_from_text(path: Path, key_name: str) -> str | None:
    """Extract value from text file using KEY=value pattern."""
    content = path.read_text(encoding="utf-8")
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        # Strip quotes
        if v.startswith('"') and v.endswith('"'):
            v = v[1:-1]
        elif v.startswith("'") and v.endswith("'"):
            v = v[1:-1]
        if k == key_name:
            return v
    return None


def run_conversion(dry_run: bool = False, vault_path: Path | None = None) -> dict:
    """Run the vault conversion.

    Args:
        dry_run: If True, don't write anything, just report what would happen
        vault_path: Optional custom vault path (default: ~/.vault)

    Returns:
        Summary dict with total, encrypted, plaintext, backup_path
    """
    if vault_path is None:
        vault_path = default_vault_roots()[0]

    vault_path = Path(vault_path)

    # Create backup
    backup_path = None
    if not dry_run:
        backup_path = create_backup(vault_path)
    else:
        # In dry-run, still show what backup would be created
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = vault_path.parent / f".vault.backup.{timestamp}"

    # Scan vault
    inventory = build_vault_inventory([vault_path])

    # Get master key (use vault_path for deterministic salt)
    master_key = get_master_key(vault_path)
    crypto = VaultCrypto()

    # Store the actual salt used for key derivation so consumers can re-derive
    salt_b64 = base64.b64encode(_DEFAULT_KEY_SALT).decode("ascii")

    # Convert entries
    total_entries = 0
    encrypted_count = 0
    plaintext_count = 0
    converted_entries = []

    for entry in inventory.entries:
        total_entries += 1
        converted = convert_entry(entry, crypto, master_key)
        converted_entries.append(converted)

        if converted["is_encrypted"]:
            encrypted_count += 1
        else:
            plaintext_count += 1

    if not dry_run:
        # Write vault.enc.json
        output_path = vault_path / "vault.enc.json"
        output_data = {
            "version": 1,
            "salt": salt_b64,
            "entries": converted_entries,
        }

        # Use atomic write
        tmp_path = output_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(output_data, indent=2), encoding="utf-8")
        os.replace(tmp_path, output_path)

    return {
        "total_entries": total_entries,
        "encrypted_count": encrypted_count,
        "plaintext_count": plaintext_count,
        "backup_path": backup_path if not dry_run else str(backup_path) + " (dry-run)",
        "output_file": str(vault_path / "vault.enc.json") if not dry_run else str(vault_path / "vault.enc.json") + " (dry-run)",
        "dry_run": dry_run,
    }


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Convert vault entries to encrypted format")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without writing anything",
    )
    parser.add_argument(
        "--vault-path",
        type=Path,
        default=None,
        help="Custom vault path (default: ~/.vault)",
    )

    args = parser.parse_args()

    summary = run_conversion(dry_run=args.dry_run, vault_path=args.vault_path)

    print("\n" + "=" * 60)
    print("VAULT CONVERSION SUMMARY")
    print("=" * 60)
    print(f"Total entries processed: {summary['total_entries']}")
    print(f"Secrets encrypted:      {summary['encrypted_count']}")
    print(f"Metadata kept plaintext: {summary['plaintext_count']}")
    print(f"Backup location:        {summary['backup_path']}")
    print(f"Output file:            {summary['output_file']}")
    print("=" * 60)

    if summary["dry_run"]:
        print("\n[DRY-RUN] No files were written.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
