"""Tests for broader source parsing (YAML, JSON, shell profiles)."""
from __future__ import annotations

from pathlib import Path

import pytest

from hermesoptimizer.vault import (
    VaultEntry,
    build_vault_inventory,
    fingerprint_secret,
)


class TestYamlParsing:
    """Tests for YAML file parsing."""

    def test_parse_simple_yaml(self, tmp_path: Path) -> None:
        """Simple YAML key: value pairs are parsed."""
        vault = tmp_path / ".vault"
        vault.mkdir()
        yaml_file = vault / "config.yaml"
        yaml_file.write_text(
            "api_key: secret123\n"
            "db_password: hunter2\n",
            encoding="utf-8",
        )

        inventory = build_vault_inventory([vault])

        assert len(inventory.entries) == 2
        keys = {e.key_name for e in inventory.entries}
        assert keys == {"api_key", "db_password"}
        assert all(e.source_kind == "yaml" for e in inventory.entries)

    def test_parse_yaml_with_quotes(self, tmp_path: Path) -> None:
        """Quoted YAML values are parsed correctly."""
        vault = tmp_path / ".vault"
        vault.mkdir()
        yaml_file = vault / "config.yaml"
        yaml_file.write_text(
            'api_key: "quoted_secret"\n'
            "db_password: 'single_quoted'\n",
            encoding="utf-8",
        )

        inventory = build_vault_inventory([vault])

        assert len(inventory.entries) == 2
        # Fingerprints should be of the unquoted values
        fps = {e.fingerprint for e in inventory.entries}
        assert fingerprint_secret("quoted_secret") in fps
        assert fingerprint_secret("single_quoted") in fps

    def test_parse_yaml_skips_non_secrets(self, tmp_path: Path) -> None:
        """YAML parser skips booleans, numbers, and paths."""
        vault = tmp_path / ".vault"
        vault.mkdir()
        yaml_file = vault / "config.yaml"
        yaml_file.write_text(
            "debug: true\n"
            "port: 8080\n"
            "log_path: /var/log/app.log\n"
            "api_key: actual_secret\n",
            encoding="utf-8",
        )

        inventory = build_vault_inventory([vault])

        assert len(inventory.entries) == 1
        assert inventory.entries[0].key_name == "api_key"

    def test_parse_yaml_skips_comments_and_lists(self, tmp_path: Path) -> None:
        """YAML parser skips comments and list items."""
        vault = tmp_path / ".vault"
        vault.mkdir()
        yaml_file = vault / "config.yaml"
        yaml_file.write_text(
            "# This is a comment\n"
            "api_key: secret123\n"
            "- list_item: value\n"
            "db_host: localhost\n",
            encoding="utf-8",
        )

        inventory = build_vault_inventory([vault])

        assert len(inventory.entries) == 2
        keys = {e.key_name for e in inventory.entries}
        assert keys == {"api_key", "db_host"}


class TestJsonParsing:
    """Tests for JSON file parsing."""

    def test_parse_simple_json(self, tmp_path: Path) -> None:
        """Simple JSON key-value pairs are parsed."""
        vault = tmp_path / ".vault"
        vault.mkdir()
        json_file = vault / "config.json"
        json_file.write_text(
            '{"api_key": "secret123", "db_password": "hunter2"}',
            encoding="utf-8",
        )

        inventory = build_vault_inventory([vault])

        assert len(inventory.entries) == 2
        keys = {e.key_name for e in inventory.entries}
        assert keys == {"api_key", "db_password"}
        assert all(e.source_kind == "json" for e in inventory.entries)

    def test_parse_nested_json(self, tmp_path: Path) -> None:
        """Nested JSON objects use dot notation for keys."""
        vault = tmp_path / ".vault"
        vault.mkdir()
        json_file = vault / "config.json"
        json_file.write_text(
            '{"database": {"password": "secret123"}, "api": {"key": "apikey"}}',
            encoding="utf-8",
        )

        inventory = build_vault_inventory([vault])

        assert len(inventory.entries) == 2
        keys = {e.key_name for e in inventory.entries}
        assert keys == {"database.password", "api.key"}

    def test_parse_json_skips_non_strings(self, tmp_path: Path) -> None:
        """JSON parser skips non-string values."""
        vault = tmp_path / ".vault"
        vault.mkdir()
        json_file = vault / "config.json"
        json_file.write_text(
            '{"port": 8080, "debug": true, "api_key": "secret"}',
            encoding="utf-8",
        )

        inventory = build_vault_inventory([vault])

        assert len(inventory.entries) == 1
        assert inventory.entries[0].key_name == "api_key"

    def test_parse_json_invalid_json_returns_empty(self, tmp_path: Path) -> None:
        """Invalid JSON returns empty entries."""
        vault = tmp_path / ".vault"
        vault.mkdir()
        json_file = vault / "config.json"
        json_file.write_text("not valid json {", encoding="utf-8")

        inventory = build_vault_inventory([vault])

        assert len(inventory.entries) == 0


class TestShellProfileParsing:
    """Tests for shell profile parsing."""

    def test_parse_export_statements(self, tmp_path: Path) -> None:
        """Shell profile export statements are parsed."""
        vault = tmp_path / ".vault"
        vault.mkdir()
        shell_file = vault / ".bashrc"
        shell_file.write_text(
            "export API_KEY=secret123\n"
            'export DB_PASSWORD="hunter2"\n'
            "export PATH=/usr/bin:/bin\n",
            encoding="utf-8",
        )

        inventory = build_vault_inventory([vault])

        assert len(inventory.entries) == 3
        keys = {e.key_name for e in inventory.entries}
        assert keys == {"API_KEY", "DB_PASSWORD", "PATH"}
        assert all(e.source_kind == "shell" for e in inventory.entries)

    def test_parse_shell_skips_comments(self, tmp_path: Path) -> None:
        """Shell profile parser skips comments."""
        vault = tmp_path / ".vault"
        vault.mkdir()
        shell_file = vault / ".bashrc"
        shell_file.write_text(
            "# This is a comment\n"
            "export API_KEY=secret123\n"
            "# Another comment\n",
            encoding="utf-8",
        )

        inventory = build_vault_inventory([vault])

        assert len(inventory.entries) == 1
        assert inventory.entries[0].key_name == "API_KEY"

    def test_parse_shell_multiple_profiles(self, tmp_path: Path) -> None:
        """Multiple shell profile files are parsed."""
        vault = tmp_path / ".vault"
        vault.mkdir()
        bashrc = vault / ".bashrc"
        bashrc.write_text("export BASHRC_KEY=bashrc_secret\n", encoding="utf-8")
        zshrc = vault / ".zshrc"
        zshrc.write_text("export ZSHRC_KEY=zshrc_secret\n", encoding="utf-8")

        inventory = build_vault_inventory([vault])

        assert len(inventory.entries) == 2
        kinds = {e.source_kind for e in inventory.entries}
        assert kinds == {"shell"}


class TestMixedSourceInventory:
    """Tests for mixed source type inventory building."""

    def test_build_inventory_with_multiple_formats(self, tmp_path: Path) -> None:
        """Inventory builds correctly with multiple source formats."""
        vault = tmp_path / ".vault"
        vault.mkdir()

        # Create files of different types
        env_file = vault / "app.env"
        env_file.write_text("ENV_KEY=env_secret\n", encoding="utf-8")

        yaml_file = vault / "config.yaml"
        yaml_file.write_text("yaml_key: yaml_secret\n", encoding="utf-8")

        json_file = vault / "secrets.json"
        json_file.write_text('{"json_key": "json_secret"}', encoding="utf-8")

        bashrc = vault / ".bashrc"
        bashrc.write_text("export SHELL_KEY=shell_secret\n", encoding="utf-8")

        inventory = build_vault_inventory([vault])

        assert len(inventory.entries) == 4
        kinds = {e.source_kind for e in inventory.entries}
        assert kinds == {"env", "yaml", "json", "shell"}
        keys = {e.key_name for e in inventory.entries}
        assert keys == {"ENV_KEY", "yaml_key", "json_key", "SHELL_KEY"}

    def test_build_inventory_yml_extension(self, tmp_path: Path) -> None:
        """YML extension is parsed same as YAML."""
        vault = tmp_path / ".vault"
        vault.mkdir()
        yml_file = vault / "config.yml"
        yml_file.write_text("yml_key: yml_secret\n", encoding="utf-8")

        inventory = build_vault_inventory([vault])

        assert len(inventory.entries) == 1
        assert inventory.entries[0].source_kind == "yaml"
        assert inventory.entries[0].key_name == "yml_key"
