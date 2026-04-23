"""Tests for config maintainer — backup dedup and merge semantics.

Phase E.1: Config backup dedup and canonical truth
Phase E.2: Config merge (not overwrite) with user-ownership tracking
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
import yaml


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def config_dir(tmp_path: Path) -> Path:
    """Provide a temporary config directory with a config.yaml."""
    d = tmp_path / ".hermes"
    d.mkdir()
    return d


@pytest.fixture()
def sample_config(config_dir: Path) -> Path:
    """Write a sample config.yaml and return its path."""
    cfg = {
        "model": {"default": "gpt-5.4", "provider": "openai"},
        "providers": {
            "openai": {"api_key": "sk-test", "default_model": "gpt-5.4"},
        },
        "agent": {"max_turns": 100, "verbose": False},
    }
    p = config_dir / "config.yaml"
    p.write_text(yaml.dump(cfg), encoding="utf-8")
    return p


@pytest.fixture()
def backup_dir(config_dir: Path) -> Path:
    """Provide the backup directory path (created by maintainer)."""
    return config_dir / "config.backups"


# ---------------------------------------------------------------------------
# E.1: Config backup dedup
# ---------------------------------------------------------------------------


class TestConfigBackup:
    """Tests for backup creation, dedup, previous symlink, and pruning."""

    def test_backup_creates_on_write(self, sample_config: Path, backup_dir: Path) -> None:
        """First write should create a backup of the original."""
        from hermesoptimizer.config_maintainer import backup_config

        result = backup_config(sample_config, backup_dir)

        assert result.success is True
        assert result.backup_path is not None
        assert result.backup_path.exists()
        # Backup content matches original
        assert result.backup_path.read_text() == sample_config.read_text()

    def test_previous_symlink_points_to_last_backup(
        self, sample_config: Path, backup_dir: Path
    ) -> None:
        """After backup, previous.yaml symlink should point to the backup."""
        from hermesoptimizer.config_maintainer import backup_config

        result = backup_config(sample_config, backup_dir)
        previous = backup_dir / "previous.yaml"

        assert previous.exists() or previous.is_symlink()
        assert previous.resolve() == result.backup_path.resolve()

    def test_multiple_backups_dedup(self, sample_config: Path, backup_dir: Path) -> None:
        """Multiple backups of same content should not create duplicates."""
        from hermesoptimizer.config_maintainer import backup_config

        r1 = backup_config(sample_config, backup_dir)
        r2 = backup_config(sample_config, backup_dir)

        # Same content = no new backup
        assert r2.skipped is True
        assert r2.backup_path == r1.backup_path

    def test_changed_content_creates_new_backup(
        self, sample_config: Path, backup_dir: Path
    ) -> None:
        """Changed config should create a new backup."""
        from hermesoptimizer.config_maintainer import backup_config

        r1 = backup_config(sample_config, backup_dir)

        # Modify config
        cfg = yaml.safe_load(sample_config.read_text())
        cfg["agent"]["verbose"] = True
        sample_config.write_text(yaml.dump(cfg), encoding="utf-8")

        r2 = backup_config(sample_config, backup_dir)

        assert r2.success is True
        assert r2.skipped is False
        assert r2.backup_path != r1.backup_path
        assert r2.backup_path.exists()

    def test_prune_keeps_max_n_backups(
        self, sample_config: Path, backup_dir: Path
    ) -> None:
        """Should prune backups to keep at most max_backups."""
        from hermesoptimizer.config_maintainer import backup_config

        for i in range(15):
            cfg = yaml.safe_load(sample_config.read_text())
            cfg["agent"]["max_turns"] = 100 + i
            sample_config.write_text(yaml.dump(cfg), encoding="utf-8")
            backup_config(sample_config, backup_dir, max_backups=10)

        backups = sorted(backup_dir.glob("config.*.yaml"))
        assert len(backups) <= 10

    def test_backup_diff_logged(self, sample_config: Path, backup_dir: Path) -> None:
        """Backup should produce a diff between old and new config."""
        from hermesoptimizer.config_maintainer import backup_config

        r1 = backup_config(sample_config, backup_dir)

        cfg = yaml.safe_load(sample_config.read_text())
        cfg["agent"]["verbose"] = True
        sample_config.write_text(yaml.dump(cfg), encoding="utf-8")

        r2 = backup_config(sample_config, backup_dir)

        assert r2.diff is not None
        assert "verbose" in r2.diff

    def test_no_config_file_returns_failure(
        self, config_dir: Path, backup_dir: Path
    ) -> None:
        """Missing config file should return failure, not crash."""
        from hermesoptimizer.config_maintainer import backup_config

        missing = config_dir / "nonexistent.yaml"
        result = backup_config(missing, backup_dir)

        assert result.success is False
        assert result.error is not None

    def test_previous_symlink_updates_on_new_backup(
        self, sample_config: Path, backup_dir: Path
    ) -> None:
        """previous.yaml should always point to the most recent backup."""
        from hermesoptimizer.config_maintainer import backup_config

        r1 = backup_config(sample_config, backup_dir)

        cfg = yaml.safe_load(sample_config.read_text())
        cfg["agent"]["verbose"] = True
        sample_config.write_text(yaml.dump(cfg), encoding="utf-8")

        r2 = backup_config(sample_config, backup_dir)

        previous = backup_dir / "previous.yaml"
        assert previous.resolve() == r2.backup_path.resolve()
        assert previous.resolve() != r1.backup_path.resolve()


# ---------------------------------------------------------------------------
# E.2: Config merge (not overwrite)
# ---------------------------------------------------------------------------


class TestConfigMerge:
    """Tests for deep-merge semantics with user-ownership tracking."""

    def test_user_keys_preserved_on_merge(self, sample_config: Path) -> None:
        """User's existing keys must not be overwritten by incoming defaults."""
        from hermesoptimizer.config_maintainer import merge_config

        current = yaml.safe_load(sample_config.read_text())
        incoming = {
            "model": {"default": "glm-5.1", "provider": "zai"},  # would overwrite
            "agent": {"max_turns": 500, "verbose": True},  # would overwrite
        }

        merged = merge_config(current, incoming)

        # User's values preserved
        assert merged["model"]["default"] == "gpt-5.4"
        assert merged["model"]["provider"] == "openai"
        assert merged["agent"]["max_turns"] == 100
        assert merged["agent"]["verbose"] is False

    def test_new_keys_added_on_merge(self, sample_config: Path) -> None:
        """New keys from incoming should be added without clobbering existing."""
        from hermesoptimizer.config_maintainer import merge_config

        current = yaml.safe_load(sample_config.read_text())
        incoming = {
            "yolo": {"enabled": True, "mode": "safe"},
            "auxiliary": {"vision": {"provider": "zai", "model": "glm-5.1v"}},
        }

        merged = merge_config(current, incoming)

        # New keys added
        assert merged["yolo"]["enabled"] is True
        assert merged["auxiliary"]["vision"]["provider"] == "zai"
        # Old keys untouched
        assert merged["model"]["default"] == "gpt-5.4"

    def test_nested_dict_merge(self, sample_config: Path) -> None:
        """Nested dicts should merge recursively, not replace."""
        from hermesoptimizer.config_maintainer import merge_config

        current = yaml.safe_load(sample_config.read_text())
        incoming = {
            "agent": {"reasoning_effort": "high"},  # new key in existing section
        }

        merged = merge_config(current, incoming)

        # New key added
        assert merged["agent"]["reasoning_effort"] == "high"
        # Existing keys preserved
        assert merged["agent"]["max_turns"] == 100
        assert merged["agent"]["verbose"] is False

    def test_scalar_list_merge_replaces(self, sample_config: Path) -> None:
        """Lists should be replaced, not concatenated (too unpredictable)."""
        from hermesoptimizer.config_maintainer import merge_config

        current = yaml.safe_load(sample_config.read_text())
        current["toolsets"] = ["hermes-cli"]
        incoming = {"toolsets": ["hermes-cli", "hermes-web"]}

        merged = merge_config(current, incoming)

        # List replaced (user didn't explicitly set this, it came from incoming)
        assert merged["toolsets"] == ["hermes-cli", "hermes-web"]

    def test_user_owned_detection(self, sample_config: Path) -> None:
        """Any key present in current config is user-owned."""
        from hermesoptimizer.config_maintainer import get_user_owned_keys

        current = yaml.safe_load(sample_config.read_text())
        owned = get_user_owned_keys(current)

        assert "model.default" in owned
        assert "model.provider" in owned
        assert "agent.max_turns" in owned
        assert "agent.verbose" in owned
        assert "providers.openai.api_key" in owned

    def test_force_fix_emits_marker(self, sample_config: Path) -> None:
        """When config is destroyed and auto-repaired, emit [HERMES_FORCE_FIX]."""
        from hermesoptimizer.config_maintainer import force_restore

        # Simulate destroyed config
        sample_config.write_text("", encoding="utf-8")

        backup = sample_config.parent / "config.backups"
        backup.mkdir()
        good_config = {"model": {"default": "gpt-5.4"}, "agent": {"max_turns": 100}}
        (backup / "previous.yaml").write_text(yaml.dump(good_config), encoding="utf-8")

        result = force_restore(sample_config, backup)

        assert result.restored is True
        assert "[HERMES_FORCE_FIX]" in result.marker
        restored = yaml.safe_load(sample_config.read_text())
        assert restored["model"]["default"] == "gpt-5.4"

    def test_force_fix_preserves_user_keys_from_backup(
        self, sample_config: Path
    ) -> None:
        """Force restore from backup should bring back the user's config."""
        from hermesoptimizer.config_maintainer import backup_config, force_restore

        backup = sample_config.parent / "config.backups"
        backup_config(sample_config, backup)

        # Destroy
        sample_config.write_text("model:\n  default: unknown\n", encoding="utf-8")

        result = force_restore(sample_config, backup)

        assert result.restored is True
        restored = yaml.safe_load(sample_config.read_text())
        assert restored["model"]["default"] == "gpt-5.4"

    def test_merge_preserves_null_vs_missing(self) -> None:
        """If user explicitly set a key to null, it stays null (not removed)."""
        from hermesoptimizer.config_maintainer import merge_config

        current = {"model": {"default": None, "provider": "openai"}}
        incoming = {"model": {"default": "glm-5.1"}}

        merged = merge_config(current, incoming)

        # User explicitly set None — that's user-owned, keep it
        assert merged["model"]["default"] is None

    def test_config_status_command(self, sample_config: Path, backup_dir: Path) -> None:
        """config-status should report current model, last backup, diff."""
        from hermesoptimizer.config_maintainer import backup_config, config_status

        backup_config(sample_config, backup_dir)
        status = config_status(sample_config, backup_dir)

        assert status.model == "gpt-5.4"
        assert status.provider == "openai"
        assert status.last_backup is not None
