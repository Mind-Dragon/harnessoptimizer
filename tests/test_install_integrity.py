"""
Tests for Phase A: Install Integrity Gate.

These tests verify:
- Pre-install intent validation works
- Transactional sync with rollback preserves originals on failure
- Post-install canary produces proof artifacts
- Atomic YAML writes validate before rename
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from hermesoptimizer.extensions.install_integrity import (
    InstallIntent,
    InstallProof,
    InstallState,
    InstallValidationError,
    PreInstallIntentError,
    atomic_yaml_write,
    check_pre_install_intent,
    load_install_state,
    restore_from_backup,
    run_install_canary,
    save_install_state,
    transactional_sync,
    validate_yaml_file,
    _backup_target,
)


class TestPreInstallIntent:
    """Tests for pre-install intent validation."""

    def test_valid_intent_passes(self, tmp_path: Path) -> None:
        source = tmp_path / "source.yaml"
        source.write_text("key: value")
        target = tmp_path / "target.yaml"

        intent = InstallIntent(
            id="test-001",
            source_path=source,
            target_paths=[target],
            ownership="repo_only",
        )
        errors = check_pre_install_intent(intent)
        assert errors == [], f"expected no errors, got: {errors}"

    def test_missing_source_fails(self, tmp_path: Path) -> None:
        source = tmp_path / "nonexistent.yaml"
        target = tmp_path / "target.yaml"

        intent = InstallIntent(
            id="test-002",
            source_path=source,
            target_paths=[target],
            ownership="repo_only",
        )
        errors = check_pre_install_intent(intent)
        assert any("does not exist" in e for e in errors)

    def test_empty_id_fails(self, tmp_path: Path) -> None:
        source = tmp_path / "source.yaml"
        source.write_text("key: value")
        target = tmp_path / "target.yaml"

        intent = InstallIntent(
            id="",
            source_path=source,
            target_paths=[target],
            ownership="repo_only",
        )
        errors = check_pre_install_intent(intent)
        assert any("intent.id is empty" in e for e in errors)

    def test_empty_target_paths_fails(self, tmp_path: Path) -> None:
        source = tmp_path / "source.yaml"
        source.write_text("key: value")

        intent = InstallIntent(
            id="test-003",
            source_path=source,
            target_paths=[],
            ownership="repo_only",
        )
        errors = check_pre_install_intent(intent)
        assert any("target_paths is empty" in e for e in errors)


class TestBackupAndRestore:
    """Tests for backup and restore functionality."""

    def test_backup_creates_copy(self, tmp_path: Path) -> None:
        target = tmp_path / "myfile.txt"
        target.write_text("original content")

        backup = _backup_target(target)
        assert backup is not None
        assert backup.exists()
        assert backup.read_text() == "original content"

        # Restore works
        target.unlink()
        restore_from_backup(target, backup)
        assert target.exists()
        assert target.read_text() == "original content"

    def test_backup_none_for_nonexistent(self, tmp_path: Path) -> None:
        target = tmp_path / "nonexistent.txt"
        backup = _backup_target(target)
        assert backup is None


class TestAtomicYamlWrite:
    """Tests for atomic YAML write with validation."""

    def test_valid_yaml_writes(self, tmp_path: Path) -> None:
        target = tmp_path / "config.yaml"
        data = {"caveman_mode": True, "provider": "minimax"}

        atomic_yaml_write(target, data)

        assert target.exists()
        loaded = yaml.safe_load(target.read_text())
        assert loaded["caveman_mode"] is True
        assert loaded["provider"] == "minimax"

    def test_atomic_write_preserves_original_on_rename_failure(self, tmp_path: Path, monkeypatch) -> None:
        target = tmp_path / "config.yaml"
        target.write_text("provider: original\n", encoding="utf-8")
        data = {"provider": "updated"}

        original_rename = Path.rename

        def failing_rename(self: Path, destination: Path):
            if self.parent == target.parent and self.name.startswith(f".{target.name}.tmp."):
                raise OSError("rename failed")
            return original_rename(self, destination)

        monkeypatch.setattr(Path, "rename", failing_rename)

        with pytest.raises(OSError):
            atomic_yaml_write(target, data)

        assert target.read_text(encoding="utf-8") == "provider: original\n"

    def test_invalid_yaml_file_rejected(self, tmp_path: Path) -> None:
        """validate_yaml_file rejects malformed YAML files."""
        bad_file = tmp_path / "corrupt.yaml"
        # Write a file with YAML that parses but produces wrong structure
        # (tab indent is illegal in YAML)
        bad_file.write_text("key: value\n  nested: bad\n    indent: true", encoding="utf-8")

        errors = validate_yaml_file(bad_file)
        assert len(errors) > 0, "expected parse errors for badly-indented YAML"

    def test_no_residue_temp_files_on_success(self, tmp_path: Path) -> None:
        """After successful write, no .tmp or .backup files remain."""
        target = tmp_path / "config.yaml"
        atomic_yaml_write(target, {"clean": True})

        residuals = list(tmp_path.glob(".*"))
        assert residuals == [], f"leftover temp files: {residuals}"

    def test_no_residue_temp_files_on_rename_failure(self, tmp_path: Path, monkeypatch) -> None:
        """After failed write (rename failure), no .tmp or .backup files remain."""
        target = tmp_path / "config.yaml"
        target.write_text("key: original")

        original_rename = Path.rename

        def _failing_rename(self: Path, destination: Path):
            if self.name.startswith(f".{target.name}.tmp."):
                raise OSError("simulated rename failure")
            return original_rename(self, destination)

        monkeypatch.setattr(Path, "rename", _failing_rename)

        with pytest.raises(OSError):
            atomic_yaml_write(target, {"key": "broken"})
        residuals = [f for f in tmp_path.glob(".*") if f.name not in (".", "..")]
        assert residuals == [], f"leftover temp files after failure: {residuals}"


class TestTransactionalSync:
    """Tests for transactional sync with rollback."""

    def test_file_sync_succeeds(self, tmp_path: Path) -> None:
        source = tmp_path / "source.txt"
        source.write_text("hello world")
        target = tmp_path / "target.txt"

        intent = InstallIntent(
            id="sync-001",
            source_path=source,
            target_paths=[target],
            ownership="repo_only",
        )

        state = transactional_sync(intent)
        assert target.exists()
        assert target.read_text() == "hello world"
        assert state.proof is not None
        assert state.proof.canary_passed is True

    def test_sync_rollback_on_canary_failure(self, tmp_path: Path) -> None:
        """When canary fails after write, original file must be restored."""
        source = tmp_path / "source.txt"
        source.write_text("new content")
        target = tmp_path / "target.txt"
        target.write_text("original content")

        intent = InstallIntent(
            id="sync-rollback-001",
            source_path=source,
            target_paths=[target],
            ownership="repo_only",
        )

        # Monkey-patch run_install_canary to force a canary failure
        import hermesoptimizer.extensions.install_integrity as ii
        original_canary = ii.run_install_canary

        def _failing_canary(intent_obj, src, targets):
            return InstallProof(
                id=intent_obj.id,
                timestamp="2025-01-01T00:00:00Z",
                source_valid=True,
                targets_match=True,
                target_contents_match=True,
                canary_passed=False,
                errors=["forced canary failure for test"],
            )

        ii.run_install_canary = _failing_canary
        try:
            with pytest.raises(InstallValidationError):
                transactional_sync(intent)
            # The original content must be restored
            assert target.exists()
            assert target.read_text() == "original content"
        finally:
            ii.run_install_canary = original_canary

    def test_sync_rollback_preserves_original_on_missing_source(self, tmp_path: Path) -> None:
        """If source doesn't exist, pre-install check fails without touching target."""
        source = tmp_path / "nonexistent.txt"
        target = tmp_path / "target.txt"
        target.write_text("unchanged")

        intent = InstallIntent(
            id="sync-rollback-002",
            source_path=source,
            target_paths=[target],
            ownership="repo_only",
        )

        with pytest.raises(PreInstallIntentError):
            transactional_sync(intent)
        assert target.read_text() == "unchanged"

    def test_dry_run_does_not_write(self, tmp_path: Path) -> None:
        source = tmp_path / "source.txt"
        source.write_text("hello")
        target = tmp_path / "target.txt"

        intent = InstallIntent(
            id="dry-001",
            source_path=source,
            target_paths=[target],
            ownership="repo_only",
        )

        state = transactional_sync(intent, dry_run=True)
        assert not target.exists()
        assert state.proof is not None
        assert state.proof.canary_passed is True
        assert "dry run" in state.proof.warnings[0]


class TestInstallCanary:
    """Tests for post-install canary checks."""

    def test_canary_passes_for_existing_matching_targets(self, tmp_path: Path) -> None:
        """Canary passes when source and targets both exist and content matches."""
        source = tmp_path / "src.yaml"
        source.write_text("model: gpt-4o")
        # Pre-create the target so canary sees matching content
        target = tmp_path / "dst.yaml"
        target.write_text("model: gpt-4o")

        intent = InstallIntent(
            id="canary-001",
            source_path=source,
            target_paths=[target],
            ownership="repo_only",
        )

        proof = run_install_canary(intent, source, [target])
        assert proof.canary_passed is True
        assert proof.source_valid is True
        assert proof.targets_match is True

    def test_canary_detects_missing_target(self, tmp_path: Path) -> None:
        source = tmp_path / "src.txt"
        source.write_text("content")
        targets = [tmp_path / "nonexistent.txt"]

        intent = InstallIntent(
            id="canary-002",
            source_path=source,
            target_paths=targets,
            ownership="repo_only",
        )

        proof = run_install_canary(intent, source, targets)
        assert proof.canary_passed is False
        assert any("missing after install" in e for e in proof.errors)


class TestStatePersistence:
    """Tests for install state artifact persistence."""

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        state = InstallState(id="state-001")
        state.started_at = "2025-01-01T00:00:00Z"
        state.errors = ["error1"]
        state.warnings = ["warning1"]

        # Patch the state path
        import hermesoptimizer.extensions.install_integrity as ii
        original_path = ii._state_path
        ii._state_path = lambda intent_id: tmp_path / f"{intent_id}.json"

        try:
            save_install_state(state)
            loaded = load_install_state("state-001")
            assert loaded is not None
            assert loaded.id == "state-001"
            assert loaded.errors == ["error1"]
            assert loaded.warnings == ["warning1"]
        finally:
            ii._state_path = original_path


class TestValidateYamlFile:
    """Tests for YAML validation helper."""

    def test_valid_yaml_file(self, tmp_path: Path) -> None:
        f = tmp_path / "valid.yaml"
        f.write_text("key: value\nlist:\n  - a\n  - b")
        errors = validate_yaml_file(f)
        assert errors == []

    def test_malformed_yaml_rejected(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.yaml"
        f.write_text("key: value\n  bad_indent: true")
        errors = validate_yaml_file(f)
        assert len(errors) > 0
        assert any("YAML" in e or "parse" in e.lower() for e in errors)

    def test_nonexistent_file_rejected(self, tmp_path: Path) -> None:
        f = tmp_path / "nonexistent.yaml"
        errors = validate_yaml_file(f)
        assert len(errors) > 0
        assert any("does not exist" in e for e in errors)
