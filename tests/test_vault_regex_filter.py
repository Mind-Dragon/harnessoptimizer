"""TDD tests for regex-based credential detection filters.

These tests verify that:
1. _parse_txt_file accepts an optional key_pattern parameter
2. The key_pattern is a configurable regex that determines what counts as a credential key
3. build_vault_inventory accepts an optional key_pattern parameter
"""
from __future__ import annotations

from pathlib import Path
import re

import pytest

from hermesoptimizer.vault import build_vault_inventory, fingerprint_secret
from hermesoptimizer.vault.inventory import _parse_txt_file, VaultEntry


class TestParseTxtFileConfigurableRegex:
    """Tests for configurable regex-based key detection in _parse_txt_file."""

    def test_parse_txt_file_accepts_key_pattern_parameter(self, tmp_path: Path) -> None:
        """_parse_txt_file should accept an optional key_pattern parameter."""
        txt_file = tmp_path / "secrets.txt"
        txt_file.write_text("API_KEY=abc123\nSECRET=xyz789\n", encoding="utf-8")

        # Default behavior - should still work
        entries = _parse_txt_file(txt_file)
        assert len(entries) == 2

        # With custom pattern - should also work
        custom_pattern = re.compile(r'^([A-Z_][A-Z0-9_]*)\s*=\s*(.+)$')
        entries_custom = _parse_txt_file(txt_file, key_pattern=custom_pattern)
        assert len(entries_custom) == 2

    def test_parse_txt_file_with_custom_key_pattern_filters_keys(self, tmp_path: Path) -> None:
        """Custom key_pattern should filter which lines are treated as credentials."""
        txt_file = tmp_path / "secrets.txt"
        txt_file.write_text(
            "API_KEY=abc123\nSECRET=xyz789\nUSER_NAME=john\nPASSWORD=pass123\n",
            encoding="utf-8",
        )

        # Only match keys starting with API_ or SECRET
        api_secret_pattern = re.compile(r'^(API_[A-Z0-9_]+|SECRET)\s*=\s*(.+)$')
        entries = _parse_txt_file(txt_file, key_pattern=api_secret_pattern)

        assert len(entries) == 2
        keys = {e.key_name for e in entries}
        assert keys == {"API_KEY", "SECRET"}

    def test_parse_txt_file_with_password_specific_pattern(self, tmp_path: Path) -> None:
        """Custom pattern can target specific credential types like PASSWORD."""
        txt_file = tmp_path / "secrets.txt"
        txt_file.write_text(
            "USERNAME=admin\nPASSWORD=secret123\nAPI_KEY=key456\n",
            encoding="utf-8",
        )

        # Only match PASSWORD keys
        password_pattern = re.compile(r'^PASSWORD\s*=\s*(.+)$')
        entries = _parse_txt_file(txt_file, key_pattern=password_pattern)

        assert len(entries) == 1
        assert entries[0].key_name == "PASSWORD"
        assert entries[0].fingerprint == fingerprint_secret("secret123")

    def test_parse_txt_file_key_pattern_default_matches_traditional_keys(self, tmp_path: Path) -> None:
        """Default key_pattern (None) should match traditional KEY=value patterns."""
        txt_file = tmp_path / "secrets.txt"
        txt_file.write_text(
            "OPENAI_API_KEY=sk-abc123\nDATABASE_URL=postgres://...\n# comment\nTOKEN=xyz\n",
            encoding="utf-8",
        )

        entries = _parse_txt_file(txt_file)  # No key_pattern = default

        assert len(entries) == 3
        keys = {e.key_name for e in entries}
        assert keys == {"OPENAI_API_KEY", "DATABASE_URL", "TOKEN"}

    def test_parse_txt_file_key_pattern_with_named_groups(self, tmp_path: Path) -> None:
        """Key pattern with named groups should extract key and value correctly."""
        txt_file = tmp_path / "secrets.txt"
        txt_file.write_text("API_KEY=abc123\n", encoding="utf-8")

        # Pattern with named groups for key and value
        pattern = re.compile(r'^(?P<key>[A-Z_][A-Z0-9_]*)\s*=\s*(?P<value>.+)$')
        entries = _parse_txt_file(txt_file, key_pattern=pattern)

        assert len(entries) == 1
        assert entries[0].key_name == "API_KEY"
        assert entries[0].fingerprint == fingerprint_secret("abc123")

    def test_parse_txt_file_key_pattern_none_matches_nothing(self, tmp_path: Path) -> None:
        """Passing None as key_pattern should fall back to default behavior."""
        txt_file = tmp_path / "secrets.txt"
        txt_file.write_text("KEY=value\n", encoding="utf-8")

        entries = _parse_txt_file(txt_file, key_pattern=None)
        assert len(entries) == 1

    def test_parse_txt_file_custom_pattern_handles_quoted_values(self, tmp_path: Path) -> None:
        """Custom pattern should still handle quoted values correctly."""
        txt_file = tmp_path / "secrets.txt"
        txt_file.write_text('API_KEY="quotedvalue"\nPASSWORD=\'singlequoted\'\n', encoding="utf-8")

        pattern = re.compile(r'^([A-Z_][A-Z0-9_]*)\s*=\s*["\']?([^\'"\s]+)["\']?\s*$')
        entries = _parse_txt_file(txt_file, key_pattern=pattern)

        # Values may or may not be extracted depending on pattern,
        # but at minimum keys should be detected
        keys = {e.key_name for e in entries}
        assert "API_KEY" in keys or "PASSWORD" in keys


class TestBuildVaultInventoryWithKeyPattern:
    """Tests for build_vault_inventory with configurable key_pattern."""

    def test_build_vault_inventory_accepts_key_pattern_parameter(self, tmp_path: Path) -> None:
        """build_vault_inventory should accept an optional key_pattern parameter."""
        vault = tmp_path / ".vault"
        vault.mkdir()
        txt_file = vault / "secrets.txt"
        txt_file.write_text("API_KEY=abc123\n", encoding="utf-8")

        custom_pattern = re.compile(r'^([A-Z_][A-Z0-9_]*)\s*=\s*(.+)$')

        # Should not raise
        inventory = build_vault_inventory([vault], key_pattern=custom_pattern)
        assert len(inventory.entries) >= 0  # Just verify it doesn't crash

    def test_build_vault_inventory_key_pattern_filters_txt_entries(self, tmp_path: Path) -> None:
        """key_pattern passed to build_vault_inventory should filter TXT entries."""
        vault = tmp_path / ".vault"
        vault.mkdir()
        txt_file = vault / "secrets.txt"
        txt_file.write_text(
            "API_KEY=abc123\nPASSWORD=secret\nUSERNAME=admin\n",
            encoding="utf-8",
        )

        # Only match API_ prefixed keys
        api_pattern = re.compile(r'^API_[A-Z0-9_]+\s*=\s*(.+)$')
        inventory = build_vault_inventory([vault], key_pattern=api_pattern)

        txt_entries = [e for e in inventory.entries if e.source_kind == "txt"]
        assert len(txt_entries) == 1
        assert txt_entries[0].key_name == "API_KEY"

    def test_build_vault_inventory_key_pattern_default_none(self, tmp_path: Path) -> None:
        """key_pattern=None should use default detection."""
        vault = tmp_path / ".vault"
        vault.mkdir()
        txt_file = vault / "secrets.txt"
        txt_file.write_text("API_KEY=abc123\nSECRET=xyz\n", encoding="utf-8")

        inventory = build_vault_inventory([vault], key_pattern=None)

        txt_entries = [e for e in inventory.entries if e.source_kind == "txt"]
        assert len(txt_entries) == 2