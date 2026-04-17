"""Tests for target-format-aware write-back planning.

These tests verify that plan_write_back correctly filters operations
based on target_format (env vs yaml/yml) while preserving the
non-destructive contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hermesoptimizer.vault import (
    VaultInventory,
    build_vault_inventory,
    plan_write_back,
)


def _make_inventory(tmp_path: Path, files: list[tuple[str, str]]) -> VaultInventory:
    """Helper: create a VaultInventory with given file names and content."""
    vault = tmp_path / ".vault"
    vault.mkdir()
    for fname, content in files:
        (vault / fname).write_text(content, encoding="utf-8")
    return build_vault_inventory([vault])


class TestEnvTargetFormat:
    """Tests for env target_format write-back planning."""

    def test_env_format_includes_only_env_files(self, tmp_path: Path) -> None:
        """When target_format=env, only .env files should be in operations."""
        inventory = _make_inventory(tmp_path, [
            ("alpha.env", "TOKEN=alpha\n"),
            ("beta.yaml", "secrets:\n  token: beta\n"),
            ("gamma.yml", "token: gamma\n"),
        ])
        plan = plan_write_back(inventory, target_format="env")

        assert plan.target_format == "env"
        assert plan.preserve_existing is True
        env_files = [op for op in plan.operations if op.endswith(".env")]
        other_files = [op for op in plan.operations if not op.endswith(".env")]
        assert len(env_files) == 1
        assert env_files[0].endswith("alpha.env")
        assert len(other_files) == 0

    def test_env_format_empty_when_no_env_files(self, tmp_path: Path) -> None:
        """When target_format=env and no .env files exist, operations should be empty."""
        inventory = _make_inventory(tmp_path, [
            ("beta.yaml", "secrets:\n  token: beta\n"),
        ])
        plan = plan_write_back(inventory, target_format="env")

        assert plan.target_format == "env"
        assert plan.preserve_existing is True
        assert plan.operations == []

    def test_env_format_with_multiple_env_files(self, tmp_path: Path) -> None:
        """When target_format=env, all .env files should be included."""
        inventory = _make_inventory(tmp_path, [
            ("a.env", "KEY_A=value_a\n"),
            ("b.env", "KEY_B=value_b\n"),
            ("c.env", "KEY_C=value_c\n"),
        ])
        plan = plan_write_back(inventory, target_format="env")

        assert plan.target_format == "env"
        assert plan.preserve_existing is True
        assert len(plan.operations) == 3
        for op in plan.operations:
            assert op.endswith(".env")


class TestYamlTargetFormat:
    """Tests for yaml target_format write-back planning."""

    def test_yaml_format_includes_yaml_and_yml_files(self, tmp_path: Path) -> None:
        """When target_format=yaml, both .yaml and .yml files should be in operations."""
        inventory = _make_inventory(tmp_path, [
            ("alpha.env", "TOKEN=alpha\n"),
            ("beta.yaml", "secrets:\n  token: beta\n"),
            ("gamma.yml", "token: gamma\n"),
        ])
        plan = plan_write_back(inventory, target_format="yaml")

        assert plan.target_format == "yaml"
        assert plan.preserve_existing is True
        yaml_files = [op for op in plan.operations if op.endswith(".yaml") or op.endswith(".yml")]
        other_files = [op for op in plan.operations if not (op.endswith(".yaml") or op.endswith(".yml"))]
        assert len(yaml_files) == 2
        assert len(other_files) == 0

    def test_yaml_format_empty_when_no_yaml_files(self, tmp_path: Path) -> None:
        """When target_format=yaml and no yaml/yml files exist, operations should be empty."""
        inventory = _make_inventory(tmp_path, [
            ("alpha.env", "TOKEN=alpha\n"),
        ])
        plan = plan_write_back(inventory, target_format="yaml")

        assert plan.target_format == "yaml"
        assert plan.preserve_existing is True
        assert plan.operations == []

    def test_yaml_format_with_mixed_yaml_extensions(self, tmp_path: Path) -> None:
        """When target_format=yaml, both .yaml and .yml extensions should be included."""
        inventory = _make_inventory(tmp_path, [
            ("a.yaml", "key: value\n"),
            ("b.yml", "key: value\n"),
        ])
        plan = plan_write_back(inventory, target_format="yaml")

        assert plan.target_format == "yaml"
        assert plan.preserve_existing is True
        assert len(plan.operations) == 2


class TestNonDestructiveContract:
    """Tests that verify the non-destructive contract is preserved."""

    def test_preserve_existing_always_true_for_env(self, tmp_path: Path) -> None:
        """plan_write_back must always preserve_existing=True for env format."""
        inventory = _make_inventory(tmp_path, [
            ("alpha.env", "TOKEN=alpha\n"),
        ])
        plan = plan_write_back(inventory, target_format="env")

        assert plan.preserve_existing is True

    def test_preserve_existing_always_true_for_yaml(self, tmp_path: Path) -> None:
        """plan_write_back must always preserve_existing=True for yaml format."""
        inventory = _make_inventory(tmp_path, [
            ("beta.yaml", "secrets:\n  token: beta\n"),
        ])
        plan = plan_write_back(inventory, target_format="yaml")

        assert plan.preserve_existing is True

    def test_no_file_mutation_during_planning(self, tmp_path: Path) -> None:
        """plan_write_back must not modify any files during planning."""
        inventory = _make_inventory(tmp_path, [
            ("alpha.env", "TOKEN=alpha\n"),
            ("beta.yaml", "secrets:\n  token: beta\n"),
        ])

        # Capture file contents before planning
        env_file = tmp_path / ".vault" / "alpha.env"
        yaml_file = tmp_path / ".vault" / "beta.yaml"
        env_content_before = env_file.read_text(encoding="utf-8")
        yaml_content_before = yaml_file.read_text(encoding="utf-8")

        # Run planning
        plan = plan_write_back(inventory, target_format="env")

        # Verify no mutation occurred
        assert env_file.read_text(encoding="utf-8") == env_content_before
        assert yaml_file.read_text(encoding="utf-8") == yaml_content_before
        assert plan.preserve_existing is True
