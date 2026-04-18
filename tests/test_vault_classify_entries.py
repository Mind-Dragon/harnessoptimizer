"""TDD tests for VaultEntry dual-type fields and classification integration."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermesoptimizer.vault import VaultEntry, build_vault_inventory, fingerprint_secret
from hermesoptimizer.vault.classify import classify_key


class TestVaultEntryDualTypeFields:
    """Tests for VaultEntry new fields: is_encrypted, encrypted_value, plaintext_value."""

    def test_vault_entry_has_new_fields_with_defaults(self) -> None:
        """VaultEntry should have is_encrypted, encrypted_value, plaintext_value fields."""
        entry = VaultEntry(
            source_path=Path("/test.env"),
            source_kind="env",
            key_name="TEST_KEY",
            fingerprint="fp20:abc123",
        )
        # Check fields exist and have defaults
        assert hasattr(entry, "is_encrypted")
        assert hasattr(entry, "encrypted_value")
        assert hasattr(entry, "plaintext_value")
        assert entry.is_encrypted is False
        assert entry.encrypted_value is None
        assert entry.plaintext_value is None

    def test_vault_entry_can_be_created_with_all_fields(self) -> None:
        """VaultEntry should accept all fields including new ones."""
        entry = VaultEntry(
            source_path=Path("/test.env"),
            source_kind="env",
            key_name="TEST_KEY",
            fingerprint="fp20:abc123",
            is_encrypted=True,
            encrypted_value="base64ciphertext==",
            plaintext_value=None,
        )
        assert entry.is_encrypted is True
        assert entry.encrypted_value == "base64ciphertext=="
        assert entry.plaintext_value is None

    def test_vault_entry_is_frozen(self) -> None:
        """VaultEntry should remain frozen (immutable) with new fields."""
        entry = VaultEntry(
            source_path=Path("/test.env"),
            source_kind="env",
            key_name="TEST_KEY",
            fingerprint="fp20:abc123",
        )
        with pytest.raises(Exception):  # dataclasses.FrozenInstanceError
            entry.is_encrypted = True


class TestParserClassificationIntegration:
    """Tests that parsers correctly classify entries and populate new fields."""

    def test_parse_env_file_classifies_secret_key(self, tmp_path: Path) -> None:
        """ENV file with SECRET_KEY should be classified as secret."""
        vault = tmp_path / ".vault"
        vault.mkdir()
        env_file = vault / "secrets.env"
        env_file.write_text("MY_SECRET_KEY=super_secret_value\n", encoding="utf-8")

        inventory = build_vault_inventory([vault])

        assert len(inventory.entries) == 1
        entry = inventory.entries[0]
        assert entry.key_name == "MY_SECRET_KEY"
        assert classify_key(entry.key_name) == "secret"
        assert entry.is_encrypted is True
        assert entry.plaintext_value is None  # Secrets don't store raw value
        assert entry.encrypted_value is None  # Encrypted value set later by VaultSession
        assert entry.fingerprint == fingerprint_secret("super_secret_value")

    def test_parse_env_file_classifies_url_as_metadata(self, tmp_path: Path) -> None:
        """ENV file with API_URL should be classified as metadata."""
        vault = tmp_path / ".vault"
        vault.mkdir()
        env_file = vault / "config.env"
        env_file.write_text("DATABASE_URL=postgresql://localhost:5432/db\n", encoding="utf-8")

        inventory = build_vault_inventory([vault])

        assert len(inventory.entries) == 1
        entry = inventory.entries[0]
        assert entry.key_name == "DATABASE_URL"
        assert classify_key(entry.key_name) == "metadata"
        assert entry.is_encrypted is False
        assert entry.plaintext_value == "postgresql://localhost:5432/db"  # Metadata stores raw value
        assert entry.encrypted_value is None
        assert entry.fingerprint == fingerprint_secret("postgresql://localhost:5432/db")

    def test_parse_yaml_file_classifies_keys_correctly(self, tmp_path: Path) -> None:
        """YAML file entries should be classified based on key name patterns."""
        vault = tmp_path / ".vault"
        vault.mkdir()
        yaml_file = vault / "config.yaml"
        yaml_file.write_text(
            "database:\n"
            "  password: db_secret_value\n"
            "  host: localhost\n"
            "api:\n"
            "  key: api_secret_value\n"
            "  url: https://api.example.com\n",
            encoding="utf-8",
        )

        inventory = build_vault_inventory([vault])

        # Should have 4 entries
        assert len(inventory.entries) == 4

        # Check classification by key name
        for entry in inventory.entries:
            classification = classify_key(entry.key_name)
            if classification == "secret":
                assert entry.is_encrypted is True
                assert entry.plaintext_value is None
                assert entry.encrypted_value is None
            else:
                assert entry.is_encrypted is False
                assert entry.plaintext_value is not None
                assert entry.encrypted_value is None

    def test_parse_toml_file_classifies_keys_correctly(self, tmp_path: Path) -> None:
        """TOML file entries should be classified based on key name patterns."""
        vault = tmp_path / ".vault"
        vault.mkdir()
        toml_file = vault / "config.toml"
        toml_file.write_text(
            'db_password = "secret123"\n'
            'api_endpoint = "https://api.example.com"\n',
            encoding="utf-8",
        )

        inventory = build_vault_inventory([vault])

        assert len(inventory.entries) == 2

        for entry in inventory.entries:
            classification = classify_key(entry.key_name)
            if classification == "secret":
                assert entry.is_encrypted is True
                assert entry.plaintext_value is None
            else:
                assert entry.is_encrypted is False
                assert entry.plaintext_value is not None

    def test_build_vault_inventory_mixed_secrets_and_metadata(self, tmp_path: Path) -> None:
        """Mixed env file with secrets and metadata should classify correctly."""
        vault = tmp_path / ".vault"
        vault.mkdir()
        env_file = vault / "app.env"
        env_file.write_text(
            "API_KEY=abc123\n"
            "DATABASE_URL=postgresql://localhost\n"
            "SECRET_TOKEN=xyz789\n"
            "SERVICE_HOST=localhost\n",
            encoding="utf-8",
        )

        inventory = build_vault_inventory([vault])

        assert len(inventory.entries) == 4

        secret_keys = {"API_KEY", "SECRET_TOKEN"}
        metadata_keys = {"DATABASE_URL", "SERVICE_HOST"}

        for entry in inventory.entries:
            if entry.key_name in secret_keys:
                assert entry.is_encrypted is True, f"{entry.key_name} should be encrypted"
                assert entry.plaintext_value is None
            elif entry.key_name in metadata_keys:
                assert entry.is_encrypted is False, f"{entry.key_name} should be metadata"
                assert entry.plaintext_value is not None
