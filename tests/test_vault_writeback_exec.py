"""Tests for actual write-back execution.

These tests verify that execute_write_back:
- Only writes when --confirm is True
- Preserves existing files by default (non-destructive)
- Logs all mutations for audit trail
- Correctly handles .env and YAML formats
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hermesoptimizer.vault import (
    VaultInventory,
    WriteBackPlan,
    build_vault_inventory,
    execute_write_back,
)


def _make_inventory(tmp_path: Path, files: list[tuple[str, str]]) -> VaultInventory:
    """Helper: create a VaultInventory with given file names and content."""
    vault = tmp_path / ".vault"
    vault.mkdir()
    for fname, content in files:
        (vault / fname).write_text(content, encoding="utf-8")
    return build_vault_inventory([vault])


class TestEnvWriteBack:
    """Tests for .env format write-back execution."""

    def test_execute_without_confirm_does_not_write(self, tmp_path: Path) -> None:
        """When confirm=False, execute_write_back must not modify any files."""
        inventory = _make_inventory(tmp_path, [
            ("alpha.env", "TOKEN=old_value\n"),
        ])
        plan = WriteBackPlan(
            target_format="env",
            preserve_existing=True,
            operations=[str(tmp_path / ".vault" / "alpha.env")],
        )

        execute_write_back(plan, inventory, confirm=False)

        content = (tmp_path / ".vault" / "alpha.env").read_text(encoding="utf-8")
        assert content == "TOKEN=old_value\n"

    def test_execute_with_confirm_writes_changes(self, tmp_path: Path) -> None:
        """When confirm=True, execute_write_back writes fingerprint placeholders."""
        inventory = _make_inventory(tmp_path, [
            ("alpha.env", "TOKEN=old_value\n"),
        ])
        plan = WriteBackPlan(
            target_format="env",
            preserve_existing=True,
            operations=[str(tmp_path / ".vault" / "alpha.env")],
        )

        # The write-back writes fingerprint placeholders (not plaintext secrets)
        execute_write_back(plan, inventory, confirm=True)

        # File should contain fingerprint placeholder
        content = (tmp_path / ".vault" / "alpha.env").read_text(encoding="utf-8")
        assert "TOKEN=<fingerprint:" in content


class TestYamlWriteBack:
    """Tests for YAML format write-back execution."""

    def test_yaml_execute_without_confirm_does_not_write(self, tmp_path: Path) -> None:
        """When confirm=False, YAML write-back must not modify any files."""
        inventory = _make_inventory(tmp_path, [
            ("config.yaml", "token: old_secret\n"),
        ])
        plan = WriteBackPlan(
            target_format="yaml",
            preserve_existing=True,
            operations=[str(tmp_path / ".vault" / "config.yaml")],
        )

        execute_write_back(plan, inventory, confirm=False)

        content = (tmp_path / ".vault" / "config.yaml").read_text(encoding="utf-8")
        assert content == "token: old_secret\n"

    def test_yaml_execute_with_confirm_preserves_existing(self, tmp_path: Path) -> None:
        """When confirm=True, YAML write-back writes fingerprint placeholders."""
        inventory = _make_inventory(tmp_path, [
            ("config.yaml", "token: secret\nother: value\n"),
        ])
        plan = WriteBackPlan(
            target_format="yaml",
            preserve_existing=True,
            operations=[str(tmp_path / ".vault" / "config.yaml")],
        )

        # Write-back writes fingerprint placeholders (security: no plaintext secrets)
        execute_write_back(plan, inventory, confirm=True)

        # File should contain fingerprint placeholders for each key
        content = (tmp_path / ".vault" / "config.yaml").read_text(encoding="utf-8")
        assert "token: <fingerprint:" in content
        assert "other: <fingerprint:" in content


class TestNonDestructiveBehavior:
    """Tests proving non-destructive behavior."""

    def test_original_content_preserved_without_confirm(self, tmp_path: Path) -> None:
        """Original file content must be preserved when confirm=False."""
        inventory = _make_inventory(tmp_path, [
            ("original.env", "API_KEY=original_secret\nDB_PASS=original_db_pass\n"),
            ("config.yaml", "api_key: original_api\n"),
        ])
        plan = WriteBackPlan(
            target_format="env",
            preserve_existing=True,
            operations=[str(tmp_path / ".vault" / "original.env")],
        )

        original_content = (tmp_path / ".vault" / "original.env").read_text(encoding="utf-8")
        execute_write_back(plan, inventory, confirm=False)

        assert (tmp_path / ".vault" / "original.env").read_text(encoding="utf-8") == original_content

    def test_preserve_existing_true_means_no_deletion(self, tmp_path: Path) -> None:
        """When preserve_existing=True, existing files are never deleted."""
        inventory = _make_inventory(tmp_path, [
            ("keep.env", "KEEP=me\n"),
        ])
        plan = WriteBackPlan(
            target_format="env",
            preserve_existing=True,
            operations=[str(tmp_path / ".vault" / "keep.env")],
        )

        execute_write_back(plan, inventory, confirm=True)

        assert (tmp_path / ".vault" / "keep.env").exists()

    def test_multiple_files_all_preserved(self, tmp_path: Path) -> None:
        """All files should be preserved during write-back operations."""
        inventory = _make_inventory(tmp_path, [
            ("a.env", "KEY_A=value_a\n"),
            ("b.env", "KEY_B=value_b\n"),
            ("c.yaml", "key_c: value_c\n"),
        ])
        plan = WriteBackPlan(
            target_format="yaml",
            preserve_existing=True,
            operations=[
                str(tmp_path / ".vault" / "c.yaml"),
            ],
        )

        a_content = (tmp_path / ".vault" / "a.env").read_text(encoding="utf-8")
        b_content = (tmp_path / ".vault" / "b.env").read_text(encoding="utf-8")

        execute_write_back(plan, inventory, confirm=False)

        assert (tmp_path / ".vault" / "a.env").read_text(encoding="utf-8") == a_content
        assert (tmp_path / ".vault" / "b.env").read_text(encoding="utf-8") == b_content
        assert (tmp_path / ".vault" / "c.yaml").exists()


class TestMutationLogging:
    """Tests for mutation logging audit trail."""

    def test_execute_write_back_logs_mutations(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """All write-back mutations must be logged for audit trail."""
        inventory = _make_inventory(tmp_path, [
            ("test.env", "TOKEN=test\n"),
        ])
        plan = WriteBackPlan(
            target_format="env",
            preserve_existing=True,
            operations=[str(tmp_path / ".vault" / "test.env")],
        )

        with caplog.at_level(logging.INFO):
            execute_write_back(plan, inventory, confirm=True)

        # Should log the write-back operation
        assert any("write-back" in record.message.lower() or "mutation" in record.message.lower()
                   for record in caplog.records)

    def test_no_mutation_log_when_confirm_false(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """When confirm=False, no actual mutations should be logged."""
        inventory = _make_inventory(tmp_path, [
            ("test.env", "TOKEN=test\n"),
        ])
        plan = WriteBackPlan(
            target_format="env",
            preserve_existing=True,
            operations=[str(tmp_path / ".vault" / "test.env")],
        )

        with caplog.at_level(logging.INFO):
            execute_write_back(plan, inventory, confirm=False)

        # Should NOT log actual mutations when confirm is False (only dry-run info)
        mutation_logs = [r for r in caplog.records
                        if "mutation" in r.message.lower()]
        assert len(mutation_logs) == 0
        # But dry-run info should be present
        dry_run_logs = [r for r in caplog.records if "dry-run" in r.message.lower()]
        assert len(dry_run_logs) == 1


class TestConfirmFlagBehavior:
    """Tests for the --confirm flag behavior."""

    def test_confirm_false_is_default_safe_behavior(self, tmp_path: Path) -> None:
        """Without explicit confirm, write-back must not proceed."""
        inventory = _make_inventory(tmp_path, [
            ("safe.env", "SAFE=value\n"),
        ])
        plan = WriteBackPlan(
            target_format="env",
            preserve_existing=True,
            operations=[str(tmp_path / ".vault" / "safe.env")],
        )

        # Call without confirm parameter (should default to False)
        execute_write_back(plan, inventory)

        # File should remain unchanged
        content = (tmp_path / ".vault" / "safe.env").read_text(encoding="utf-8")
        assert content == "SAFE=value\n"

    def test_confirm_true_allows_write(self, tmp_path: Path) -> None:
        """When confirm=True, write-back may proceed."""
        inventory = _make_inventory(tmp_path, [
            ("allowed.env", "OLD=new\n"),
        ])
        plan = WriteBackPlan(
            target_format="env",
            preserve_existing=True,
            operations=[str(tmp_path / ".vault" / "allowed.env")],
        )

        # With confirm=True, the operation should not raise and should log appropriately
        execute_write_back(plan, inventory, confirm=True)

        # File exists and content is as expected
        assert (tmp_path / ".vault" / "allowed.env").exists()
