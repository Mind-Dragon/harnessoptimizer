"""Tests for persistent caveman config support."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestCavemanConfigDefault:
    """Tests that caveman mode defaults to OFF when no config exists."""

    def test_caveman_disabled_by_default_no_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When config.yaml does not exist, caveman mode should be OFF by default."""
        # Point HOME to a temp directory with no config
        hermes_dir = tmp_path / ".hermes"
        hermes_dir.mkdir(parents=True)
        monkeypatch.setenv("HOME", str(tmp_path))
        
        # Clear any cached module state
        monkeypatch.delenv("PYTHONPATH", raising=False)
        
        # Re-import to pick up fresh state
        import importlib
        import hermesoptimizer.caveman as caveman_module
        importlib.reload(caveman_module)
        
        assert caveman_module.is_enabled() is False


class TestCavemanConfigReadback:
    """Tests for reading caveman_mode from config.yaml."""

    def test_is_enabled_true_when_config_true(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When config.yaml has caveman_mode: true, is_enabled() returns True."""
        hermes_dir = tmp_path / ".hermes"
        hermes_dir.mkdir(parents=True)
        config_file = hermes_dir / "config.yaml"
        config_file.write_text(yaml.dump({"caveman_mode": True}), encoding="utf-8")
        monkeypatch.setenv("HOME", str(tmp_path))
        
        import importlib
        import hermesoptimizer.caveman as caveman_module
        importlib.reload(caveman_module)
        
        assert caveman_module.is_enabled() is True

    def test_is_enabled_false_when_config_false(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When config.yaml has caveman_mode: false, is_enabled() returns False."""
        hermes_dir = tmp_path / ".hermes"
        hermes_dir.mkdir(parents=True)
        config_file = hermes_dir / "config.yaml"
        config_file.write_text(yaml.dump({"caveman_mode": False}), encoding="utf-8")
        monkeypatch.setenv("HOME", str(tmp_path))
        
        import importlib
        import hermesoptimizer.caveman as caveman_module
        importlib.reload(caveman_module)
        
        assert caveman_module.is_enabled() is False

    def test_is_enabled_false_when_config_missing_caveman_key(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When config.yaml exists but has no caveman_mode key, defaults to OFF."""
        hermes_dir = tmp_path / ".hermes"
        hermes_dir.mkdir(parents=True)
        config_file = hermes_dir / "config.yaml"
        config_file.write_text(yaml.dump({"providers": {}}), encoding="utf-8")
        monkeypatch.setenv("HOME", str(tmp_path))
        
        import importlib
        import hermesoptimizer.caveman as caveman_module
        importlib.reload(caveman_module)
        
        assert caveman_module.is_enabled() is False


class TestCavemanConfigWrite:
    """Tests for writing caveman_mode to config.yaml on toggle."""

    def test_toggle_writes_config_true(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """toggle() from OFF to ON should write caveman_mode: true to config.yaml."""
        hermes_dir = tmp_path / ".hermes"
        hermes_dir.mkdir(parents=True)
        config_file = hermes_dir / "config.yaml"
        # Start with empty config
        config_file.write_text("", encoding="utf-8")
        monkeypatch.setenv("HOME", str(tmp_path))
        
        import importlib
        import hermesoptimizer.caveman as caveman_module
        importlib.reload(caveman_module)
        
        # Ensure we're off first
        if caveman_module.is_enabled():
            caveman_module.disable()
        
        result = caveman_module.toggle()
        assert result is True
        
        # Verify config was written
        config_data = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        assert config_data.get("caveman_mode") is True

    def test_toggle_writes_config_false(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """toggle() from ON to OFF should write caveman_mode: false to config.yaml."""
        hermes_dir = tmp_path / ".hermes"
        hermes_dir.mkdir(parents=True)
        config_file = hermes_dir / "config.yaml"
        # Start with caveman_mode: true
        config_file.write_text(yaml.dump({"caveman_mode": True}), encoding="utf-8")
        monkeypatch.setenv("HOME", str(tmp_path))
        
        import importlib
        import hermesoptimizer.caveman as caveman_module
        importlib.reload(caveman_module)
        
        assert caveman_module.is_enabled() is True
        
        result = caveman_module.toggle()
        assert result is False
        
        # Verify config was written
        config_data = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        assert config_data.get("caveman_mode") is False

    def test_enable_writes_config_true(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """enable() should write caveman_mode: true to config.yaml."""
        hermes_dir = tmp_path / ".hermes"
        hermes_dir.mkdir(parents=True)
        config_file = hermes_dir / "config.yaml"
        config_file.write_text("", encoding="utf-8")
        monkeypatch.setenv("HOME", str(tmp_path))
        
        import importlib
        import hermesoptimizer.caveman as caveman_module
        importlib.reload(caveman_module)
        
        caveman_module.enable()
        
        config_data = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        assert config_data.get("caveman_mode") is True

    def test_disable_writes_config_false(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """disable() should write caveman_mode: false to config.yaml."""
        hermes_dir = tmp_path / ".hermes"
        hermes_dir.mkdir(parents=True)
        config_file = hermes_dir / "config.yaml"
        config_file.write_text(yaml.dump({"caveman_mode": True}), encoding="utf-8")
        monkeypatch.setenv("HOME", str(tmp_path))
        
        import importlib
        import hermesoptimizer.caveman as caveman_module
        importlib.reload(caveman_module)
        
        assert caveman_module.is_enabled() is True
        caveman_module.disable()
        
        config_data = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        assert config_data.get("caveman_mode") is False

    def test_config_preserves_other_keys(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Writing caveman_mode should preserve other config keys."""
        hermes_dir = tmp_path / ".hermes"
        hermes_dir.mkdir(parents=True)
        config_file = hermes_dir / "config.yaml"
        original_config = {"providers": {"openai": {"model": "gpt-4"}}, "log": {"level": "debug"}}
        config_file.write_text(yaml.dump(original_config), encoding="utf-8")
        monkeypatch.setenv("HOME", str(tmp_path))
        
        import importlib
        import hermesoptimizer.caveman as caveman_module
        importlib.reload(caveman_module)
        
        caveman_module.enable()
        
        config_data = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        assert config_data.get("caveman_mode") is True
        assert config_data.get("providers") == original_config["providers"]
        assert config_data.get("log") == original_config["log"]


class TestCavemanCLISmoke:
    """Smoke tests for CLI caveman command with persistent config."""

    def _run_cli(self, *args: str, home: Path) -> subprocess.CompletedProcess[str]:
        """Run the CLI with given args and custom HOME."""
        env = dict(os.environ)
        env["HOME"] = str(home)
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        return subprocess.run(
            [sys.executable, "-m", "hermesoptimizer", *args],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_caveman_cli_toggle_persists_across_invocations(self, tmp_path: Path) -> None:
        """Two CLI invocations should see consistent state after toggle."""
        hermes_dir = tmp_path / ".hermes"
        hermes_dir.mkdir(parents=True)
        
        # First call: toggle ON
        result1 = self._run_cli("caveman", home=tmp_path)
        assert result1.returncode == 0
        assert "caveman mode: ON" in result1.stdout
        
        # Second call: should still be ON (not toggled since we don't control order)
        result2 = self._run_cli("caveman", home=tmp_path)
        assert result2.returncode == 0
        
        # Third call: toggle again
        result3 = self._run_cli("caveman", home=tmp_path)
        assert result3.returncode == 0

    def test_caveman_cli_respects_existing_config(self, tmp_path: Path) -> None:
        """CLI should respect pre-existing config with caveman_mode set."""
        hermes_dir = tmp_path / ".hermes"
        hermes_dir.mkdir(parents=True)
        config_file = hermes_dir / "config.yaml"
        config_file.write_text(yaml.dump({"caveman_mode": True}), encoding="utf-8")
        
        result = self._run_cli("caveman", home=tmp_path)
        assert result.returncode == 0
        # Toggling from ON should give OFF
        assert "caveman mode: OFF" in result.stdout

    def test_caveman_cli_default_off_without_config(self, tmp_path: Path) -> None:
        """CLI should default to OFF when no config exists."""
        hermes_dir = tmp_path / ".hermes"
        hermes_dir.mkdir(parents=True)
        # No config file
        
        result = self._run_cli("caveman", home=tmp_path)
        assert result.returncode == 0
        # Toggling from OFF should give ON
        assert "caveman mode: ON" in result.stdout
