"""Tests for extension drift detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermesoptimizer.extensions.drift import (
    check_caveman_drift,
    check_dreams_drift,
    check_tool_surface_drift,
    check_vault_plugins_drift,
)
from hermesoptimizer.extensions.schema import ExtensionEntry, ExtensionType, Ownership


class TestCavemanDrift:
    def test_no_drift_when_clean(self) -> None:
        entry = ExtensionEntry(
            id="caveman",
            type=ExtensionType.CONFIG,
            description="caveman",
            source_path="src/hermesoptimizer/caveman",
            ownership=Ownership.REPO_EXTERNAL,
        )
        findings = check_caveman_drift(entry)
        # Should not produce errors on a clean machine
        errors = [f for f in findings if f.severity == "error"]
        assert len(errors) == 0

    def test_config_type_drift(self, tmp_path: Path, monkeypatch) -> None:
        entry = ExtensionEntry(
            id="caveman",
            type=ExtensionType.CONFIG,
            description="caveman",
            source_path="src/hermesoptimizer/caveman",
            ownership=Ownership.REPO_EXTERNAL,
        )
        config_file = tmp_path / "config.yaml"
        config_file.write_text("caveman_mode: not_a_bool\n")

        import hermesoptimizer.extensions.drift as drift_mod

        monkeypatch.setattr(drift_mod, "_config_path", lambda: config_file)
        findings = check_caveman_drift(entry)
        assert any(f.check == "config_type" for f in findings)


class TestDreamsDrift:
    def test_missing_db_warning(self, tmp_path: Path, monkeypatch) -> None:
        entry = ExtensionEntry(
            id="dreams",
            type=ExtensionType.SIDECAR,
            description="dreams",
            source_path="src/hermesoptimizer/dreams",
            ownership=Ownership.REPO_EXTERNAL,
        )
        # Point hermes home to empty dir so DB is missing
        hermes_dir = tmp_path / ".hermes" / "dreams"
        hermes_dir.mkdir(parents=True)

        import hermesoptimizer.extensions.drift as drift_mod

        monkeypatch.setattr(
            drift_mod, "Path", lambda p, **kw: tmp_path / ".hermes" / "dreams" / "memory_meta.db" if "memory_meta.db" in p else Path(p).expanduser()
        )
        # Actually easier: monkeypatch the db path directly? The function uses inline Path.
        # Let's just monkeypatch Path.expanduser to redirect ~/.hermes
        real_path = Path

        def redirected_path(p: str) -> Path:
            if p.startswith("~/"):
                return tmp_path / p[2:]
            return real_path(p)

        monkeypatch.setattr(drift_mod, "Path", lambda p: redirected_path(p))
        findings = check_dreams_drift(entry)
        assert any(f.check == "memory_meta_db" for f in findings)


class TestVaultPluginsDrift:
    def test_missing_vault_warning(self, tmp_path: Path, monkeypatch) -> None:
        entry = ExtensionEntry(
            id="vault_plugins",
            type=ExtensionType.VAULT_PLUGIN,
            description="vault",
            source_path="src/hermesoptimizer/vault/plugins",
            ownership=Ownership.REPO_EXTERNAL,
        )

        import hermesoptimizer.extensions.drift as drift_mod

        def redirected_path(p: str) -> Path:
            if ".vault" in p:
                return tmp_path / "no_vault"
            return Path(p).expanduser()

        monkeypatch.setattr(drift_mod, "Path", lambda p: redirected_path(p))
        findings = check_vault_plugins_drift(entry)
        assert any(f.check == "vault_file_missing" for f in findings)


class TestToolSurfaceDrift:
    def test_command_match(self) -> None:
        entry = ExtensionEntry(
            id="tool_surface",
            type=ExtensionType.COMMAND_SURFACE,
            description="tool surface",
            source_path="src/hermesoptimizer/tool_surface",
            ownership=Ownership.REPO_ONLY,
            metadata={"commands": ["provider list", "provider recommend", "workflow list", "dreams inspect", "report latest"]},
        )
        findings = check_tool_surface_drift(entry)
        assert len(findings) == 0

    def test_missing_command(self) -> None:
        entry = ExtensionEntry(
            id="tool_surface",
            type=ExtensionType.COMMAND_SURFACE,
            description="tool surface",
            source_path="src/hermesoptimizer/tool_surface",
            ownership=Ownership.REPO_ONLY,
            metadata={"commands": ["nonexistent command"]},
        )
        findings = check_tool_surface_drift(entry)
        assert any(f.check == "command_missing" for f in findings)
