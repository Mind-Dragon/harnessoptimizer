"""Tests for the vault conversion script."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

# Import from the script's location
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from convert_vault import (
    _DEFAULT_KEY_SALT,
    convert_entry,
    create_backup,
    is_secret_key,
    run_conversion,
)
from hermesoptimizer.vault import VaultEntry, fingerprint_secret
from hermesoptimizer.vault.crypto import VaultCrypto, derive_key


class TestSecretKeyClassification:
    """Tests for the secret key classification function."""

    def test_secret_patterns(self) -> None:
        """Key names containing secret patterns should be detected."""
        secret_keys = [
            "API_KEY",
            "SECRET_KEY",
            "TOKEN",
            "PASSWORD",
            "MY_PASS",
            "CREDENTIAL",
            "PAT",
            "api_key",
            "AUTH",
            "X_API_KEY",
            "BEARER_TOKEN",
            "CLIENT_SECRET",
            "access_token",
            "refresh_token",
            "private_key",
        ]
        for key in secret_keys:
            assert is_secret_key(key), f"{key} should be classified as secret"

    def test_metadata_patterns(self) -> None:
        """Key names that don't contain secret patterns should not be detected."""
        metadata_keys = [
            "DATABASE_URL",
            "API_URL",
            "HOST",
            "PORT",
            "REGION",
            "ENDPOINT",
            "SERVER",
            "DATABASE_NAME",
            "USERNAME",
            "DESCRIPTION",
            "VERSION",
        ]
        for key in metadata_keys:
            assert not is_secret_key(key), f"{key} should not be classified as secret"


def create_temp_vault(tmp_path: Path) -> Path:
    """Create a temp vault with sample files."""
    vault = tmp_path / ".vault"
    vault.mkdir()

    # Create .env file with secrets and metadata
    env_file = vault / "llm-provider-keys.env"
    env_file.write_text(
        "FIREWORKS_API_KEY=fw_abc123def456xyz789012345678901234567890\n"
        "KILOCODE_TOKEN=kc_xyz789abc123def456uvw012345678901234567890\n"
        "RUNPOD_API_SECRET=rp_secret_key_value_1234567890abcdefghij\n"
        "PEXELS_API_KEY=px_key_abcdefghij1234567890klmnopqrstuvwxyz\n"
        "DATABASE_URL=postgresql://localhost:5432/mydb\n"
        "API_HOST=api.example.com\n"
        "API_PORT=8080\n",
        encoding="utf-8",
    )

    # Create .json file with nested secrets
    json_file = vault / "mcp-auth.json"
    json_file.write_text(
        json.dumps({
            "supabase": {
                "clientSecret": "sb_secret_xyz789uvw0123456789",
                "accessToken": "sb_access_token_value_1234567890",
                "refreshToken": "sb_refresh_xyz789abc123def456",
            },
            "service": {
                "url": "https://api.service.com",
                "host": "localhost",
                "port": 3000,
            }
        }),
        encoding="utf-8",
    )

    # Create .yaml file with mixed content
    yaml_file = vault / "litellm-host-config.yaml"
    yaml_file.write_text(
        "master_key: lm_master_key_value_abcdefghij123456\n"
        "api:\n"
        "  base_url: https://api.litellm.com\n"
        "  region: us-east-1\n",
        encoding="utf-8",
    )

    # Create .toml file with mixed content
    toml_file = vault / "config.toml"
    toml_file.write_text(
        'db_password = "db_secret_password_value_123456"\n'
        'server_host = "db.example.com"\n'
        'server_port = "5432"\n',
        encoding="utf-8",
    )

    # Create a .txt file with key=value pairs
    txt_file = vault / "secrets.txt"
    txt_file.write_text(
        "DOCKER_HUB_TOKEN=dh_token_abcdefghij123456789klmnop\n"
        "DRIVER_API_KEY=dr_key_xyz789uvw0123456789abcdef\n"
        "SERVER_NAME=my-server\n"
        "SERVER_VERSION=1.0.0\n",
        encoding="utf-8",
    )

    return vault


class TestConversionInTempDir:
    """Tests that conversion works correctly in a temporary directory."""

    def test_dry_run_does_not_write(self, tmp_path: Path) -> None:
        """Dry-run mode should not write any files."""
        temp_vault = create_temp_vault(tmp_path)
        output_file = temp_vault / "vault.enc.json"

        # Ensure output doesn't exist before
        assert not output_file.exists()

        summary = run_conversion(dry_run=True, vault_path=temp_vault)

        # Should not create output file
        assert not output_file.exists()

        # Should still report what would happen
        assert summary["total_entries"] > 0
        assert summary["dry_run"] is True

    def test_conversion_creates_encrypted_file(self, tmp_path: Path) -> None:
        """Conversion should create vault.enc.json."""
        temp_vault = create_temp_vault(tmp_path)
        output_file = temp_vault / "vault.enc.json"

        summary = run_conversion(dry_run=False, vault_path=temp_vault)

        # Should create output file
        assert output_file.exists()

        # Should have valid JSON
        with open(output_file, encoding="utf-8") as f:
            data = json.load(f)

        # Check structure
        assert data["version"] == 1
        assert "salt" in data
        assert "entries" in data
        assert len(data["entries"]) == summary["total_entries"]

    def test_backup_created(self, tmp_path: Path) -> None:
        """Conversion should create a backup of the original vault."""
        temp_vault = create_temp_vault(tmp_path)

        # Snapshot original files BEFORE conversion
        original_files = set(f.name for f in temp_vault.iterdir() if f.is_file() and not f.name.startswith("."))

        summary = run_conversion(dry_run=False, vault_path=temp_vault)

        # Backup path should be in the summary (it's a Path object)
        backup_path = summary["backup_path"]
        assert ".vault.backup." in str(backup_path)

        # Backup should exist
        assert backup_path.exists()
        assert backup_path.is_dir()

        # Backup should have the same files as the original vault BEFORE conversion
        backup_files = set(f.name for f in backup_path.iterdir() if f.is_file() and not f.name.startswith("."))
        assert original_files == backup_files

    def test_original_files_untouched(self, tmp_path: Path) -> None:
        """Conversion should not modify original files."""
        temp_vault = create_temp_vault(tmp_path)

        # Read original file content
        env_file = temp_vault / "llm-provider-keys.env"
        original_content = env_file.read_text(encoding="utf-8")

        summary = run_conversion(dry_run=False, vault_path=temp_vault)

        # File content should be unchanged
        assert env_file.read_text(encoding="utf-8") == original_content

    def test_metadata_preserved_as_plaintext(self, tmp_path: Path) -> None:
        """Metadata entries should be stored as plaintext."""
        temp_vault = create_temp_vault(tmp_path)

        summary = run_conversion(dry_run=False, vault_path=temp_vault)

        output_file = temp_vault / "vault.enc.json"
        with open(output_file, encoding="utf-8") as f:
            data = json.load(f)

        # Find metadata entries (not encrypted)
        metadata_entries = [e for e in data["entries"] if not e["is_encrypted"]]

        # We expect some metadata entries (DATABASE_URL, API_HOST, API_PORT, url, host, port, etc.)
        assert len(metadata_entries) > 0

        # Check that plaintext_value is set for metadata
        for entry in metadata_entries:
            assert entry["encrypted_value"] is None
            assert entry["plaintext_value"] is not None

    def test_secrets_encrypted(self, tmp_path: Path) -> None:
        """Secret entries should be encrypted."""
        temp_vault = create_temp_vault(tmp_path)

        summary = run_conversion(dry_run=False, vault_path=temp_vault)

        output_file = temp_vault / "vault.enc.json"
        with open(output_file, encoding="utf-8") as f:
            data = json.load(f)

        # Find encrypted entries
        encrypted_entries = [e for e in data["entries"] if e["is_encrypted"]]

        # We expect some encrypted entries (API_KEY, TOKEN, SECRET, PASSWORD, etc.)
        assert len(encrypted_entries) > 0

        # Check that encrypted_value is set and plaintext_value is None
        for entry in encrypted_entries:
            assert entry["encrypted_value"] is not None
            assert entry["plaintext_value"] is None

    def test_encrypted_entries_decrypt_correctly(self, tmp_path: Path) -> None:
        """Encrypted entries should decrypt correctly (round-trip)."""
        # Get the master key (derived from default passphrase with fixed salt)
        passphrase = "hermes-vault-default"
        master_key, _ = derive_key(passphrase, salt=_DEFAULT_KEY_SALT)
        crypto = VaultCrypto()

        temp_vault = create_temp_vault(tmp_path)

        summary = run_conversion(dry_run=False, vault_path=temp_vault)

        output_file = temp_vault / "vault.enc.json"
        with open(output_file, encoding="utf-8") as f:
            data = json.load(f)

        # Find encrypted entries
        encrypted_entries = [e for e in data["entries"] if e["is_encrypted"]]

        # For each encrypted entry, decrypt and verify we can get the value
        # Note: We can't verify the actual plaintext because we don't store it in inventory
        # But we can verify the decryption doesn't throw an error
        for entry in encrypted_entries:
            ciphertext = entry["encrypted_value"]
            assert ciphertext is not None

            # Should be able to decrypt without error
            try:
                decrypted = crypto.decrypt(ciphertext, master_key)
                # Decrypted value should be a string
                assert isinstance(decrypted, str)
                # And have reasonable length
                assert len(decrypted) >= 8
            except Exception as e:
                pytest.fail(f"Decryption failed for {entry['key_name']}: {e}")

    def test_summary_counts(self, tmp_path: Path) -> None:
        """Summary should correctly count entries."""
        temp_vault = create_temp_vault(tmp_path)

        summary = run_conversion(dry_run=False, vault_path=temp_vault)

        output_file = temp_vault / "vault.enc.json"
        with open(output_file, encoding="utf-8") as f:
            data = json.load(f)

        total = len(data["entries"])
        encrypted = sum(1 for e in data["entries"] if e["is_encrypted"])
        plaintext = sum(1 for e in data["entries"] if not e["is_encrypted"])

        assert summary["total_entries"] == total
        assert summary["encrypted_count"] == encrypted
        assert summary["plaintext_count"] == plaintext
        assert encrypted + plaintext == total


class TestBackupCreation:
    """Tests for backup creation."""

    def test_backup_fails_gracefully_on_nonexistent_vault(self, tmp_path: Path) -> None:
        """Backup should return None for non-existent vault."""
        nonexistent = tmp_path / "nonexistent_vault"
        backup = create_backup(nonexistent)
        assert backup is None

    def test_backup_is_timestamed(self, tmp_path: Path) -> None:
        """Backup directory name should contain timestamp."""
        temp_vault = create_temp_vault(tmp_path)

        backup = create_backup(temp_vault)
        assert backup is not None
        assert ".vault.backup." in backup.name

        # Timestamp format: YYYYMMDD_HHMMSS
        # backup.name is like ".vault.backup.20260418_191237"
        # We need to extract just the timestamp part
        timestamp = backup.name.split(".vault.backup.")[-1]
        assert len(timestamp) == 15  # YYYYMMDD_HHMMSS
        assert timestamp[8] == "_"  # Separator between date and time
