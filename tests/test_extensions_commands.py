"""Tests for extension management commands: status, verify, sync, doctor."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from hermesoptimizer.extensions.schema import ExtensionEntry, ExtensionType, Ownership
from hermesoptimizer.extensions.status import check_all_statuses, check_extension_status
from hermesoptimizer.extensions.sync import sync_all, sync_extension
from hermesoptimizer.extensions.verify import verify_all, verify_extension


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def sample_entry(repo_root: Path) -> ExtensionEntry:
    src = repo_root / "src.txt"
    src.write_text("hello")
    target = repo_root / "target.txt"
    target.write_text("hello")
    return ExtensionEntry(
        id="test_ext",
        type=ExtensionType.SCRIPT,
        description="test",
        source_path="src.txt",
        target_paths=[str(target)],
        verify_command="echo ok",
        ownership=Ownership.REPO_ONLY,
    )


@pytest.fixture
def external_entry() -> ExtensionEntry:
    return ExtensionEntry(
        id="ext_runtime",
        type=ExtensionType.CRON,
        description="external",
        source_path="",
        target_paths=[],
        ownership=Ownership.EXTERNAL_RUNTIME,
    )


class TestStatus:
    def test_ok(self, repo_root: Path, sample_entry: ExtensionEntry) -> None:
        st = check_extension_status(sample_entry, repo_root)
        assert st.status == "ok"
        assert st.source_ok is True

    def test_missing_source(self, repo_root: Path) -> None:
        entry = ExtensionEntry(
            id="missing",
            type=ExtensionType.SCRIPT,
            description="missing source",
            source_path="nonexistent.py",
            ownership=Ownership.REPO_ONLY,
        )
        st = check_extension_status(entry, repo_root)
        assert st.status == "missing_source"
        assert st.source_ok is False

    def test_missing_target(self, repo_root: Path) -> None:
        entry = ExtensionEntry(
            id="missing_t",
            type=ExtensionType.SCRIPT,
            description="missing target",
            source_path="src.txt",
            target_paths=[str(repo_root / "nonexistent" / "target.txt")],
            ownership=Ownership.REPO_ONLY,
        )
        (repo_root / "src.txt").write_text("x")
        st = check_extension_status(entry, repo_root)
        assert st.status == "missing_target"
        assert "missing targets" in st.detail

    def test_external(self, repo_root: Path, external_entry: ExtensionEntry) -> None:
        st = check_extension_status(external_entry, repo_root)
        assert st.status == "external"
        assert st.source_ok is True

    def test_all_statuses(self, repo_root: Path, external_entry: ExtensionEntry) -> None:
        ok_entry = ExtensionEntry(
            id="ok",
            type=ExtensionType.SCRIPT,
            description="ok",
            source_path="src.txt",
            target_paths=[str(repo_root / "target.txt")],
            ownership=Ownership.REPO_ONLY,
        )
        (repo_root / "src.txt").write_text("x")
        (repo_root / "target.txt").write_text("x")
        results = check_all_statuses([ok_entry, external_entry], repo_root)
        assert len(results) == 2
        assert results[0].status == "ok"
        assert results[1].status == "external"


class TestVerify:
    def test_verify_pass(self, repo_root: Path) -> None:
        entry = ExtensionEntry(
            id="pass",
            type=ExtensionType.SCRIPT,
            description="passes",
            source_path="src.py",
            verify_command="echo hello",
        )
        res = verify_extension(entry, cwd=repo_root)
        assert res.passed is True
        assert res.exit_code == 0
        assert res.stdout == "hello"

    def test_verify_fail(self, repo_root: Path) -> None:
        entry = ExtensionEntry(
            id="fail",
            type=ExtensionType.SCRIPT,
            description="fails",
            source_path="src.py",
            verify_command="exit 1",
        )
        res = verify_extension(entry, cwd=repo_root)
        assert res.passed is False
        assert res.exit_code == 1

    def test_verify_no_command(self, repo_root: Path) -> None:
        entry = ExtensionEntry(
            id="none",
            type=ExtensionType.SCRIPT,
            description="no command",
            source_path="src.py",
        )
        res = verify_extension(entry, cwd=repo_root)
        assert res.passed is True
        assert res.command is None

    def test_verify_timeout(self, repo_root: Path) -> None:
        entry = ExtensionEntry(
            id="timeout",
            type=ExtensionType.SCRIPT,
            description="timeout",
            source_path="src.py",
            verify_command="sleep 60",
        )
        res = verify_extension(entry, cwd=repo_root)
        assert res.passed is False
        assert "timed out" in res.stderr

    def test_verify_all(self, repo_root: Path) -> None:
        entries = [
            ExtensionEntry(id="a", type=ExtensionType.SCRIPT, description="a", source_path="a.py", verify_command="echo a"),
            ExtensionEntry(id="b", type=ExtensionType.SCRIPT, description="b", source_path="b.py", verify_command="echo b"),
        ]
        results = verify_all(entries, cwd=repo_root)
        assert len(results) == 2
        assert all(r.passed for r in results)


class TestSync:
    def test_sync_dry_run(self, repo_root: Path) -> None:
        entry = ExtensionEntry(
            id="dry",
            type=ExtensionType.SCRIPT,
            description="dry run",
            source_path="src.txt",
            target_paths=[str(repo_root / "new_target.txt")],
            ownership=Ownership.REPO_ONLY,
        )
        (repo_root / "src.txt").write_text("hello")
        res = sync_extension(entry, repo_root, dry_run=True)
        assert res.synced is False
        assert res.skipped is False
        assert any("would copy" in a for a in res.actions)

    def test_sync_external_skipped(self, repo_root: Path, external_entry: ExtensionEntry) -> None:
        res = sync_extension(external_entry, repo_root)
        assert res.skipped is True
        assert res.synced is False

    def test_sync_missing_source(self, repo_root: Path) -> None:
        entry = ExtensionEntry(
            id="missing_src",
            type=ExtensionType.SCRIPT,
            description="missing",
            source_path="nope.py",
            target_paths=["~/.hoptimizer_test/out.py"],
            ownership=Ownership.REPO_ONLY,
        )
        res = sync_extension(entry, repo_root)
        assert res.synced is False
        assert res.skipped is False
        assert any("source_path does not exist" in e for e in res.errors)

    def test_sync_no_targets(self, repo_root: Path) -> None:
        entry = ExtensionEntry(
            id="no_targets",
            type=ExtensionType.SCRIPT,
            description="no targets",
            source_path="src.txt",
            target_paths=[],
            ownership=Ownership.REPO_ONLY,
        )
        (repo_root / "src.txt").write_text("x")
        res = sync_extension(entry, repo_root)
        assert res.skipped is True
        assert "no target_paths defined" in res.actions[0]

    def test_sync_actual_copy(self, repo_root: Path, tmp_path: Path) -> None:
        target = tmp_path / "target.txt"
        entry = ExtensionEntry(
            id="copy",
            type=ExtensionType.SCRIPT,
            description="copy",
            source_path="src.txt",
            target_paths=[str(target)],
            ownership=Ownership.REPO_ONLY,
        )
        (repo_root / "src.txt").write_text("content")
        res = sync_extension(entry, repo_root)
        assert res.synced is True
        assert target.read_text() == "content"

    def test_sync_force_overwrite(self, repo_root: Path, tmp_path: Path) -> None:
        target = tmp_path / "target.txt"
        target.write_text("old")
        entry = ExtensionEntry(
            id="force",
            type=ExtensionType.SCRIPT,
            description="force",
            source_path="src.txt",
            target_paths=[str(target)],
            ownership=Ownership.REPO_ONLY,
        )
        (repo_root / "src.txt").write_text("new")
        res = sync_extension(entry, repo_root, force=True)
        assert res.synced is True
        assert target.read_text() == "new"

    def test_sync_blocked_without_force(self, repo_root: Path, tmp_path: Path) -> None:
        target = tmp_path / "target.txt"
        target.write_text("old")
        entry = ExtensionEntry(
            id="blocked",
            type=ExtensionType.SCRIPT,
            description="blocked",
            source_path="src.txt",
            target_paths=[str(target)],
            ownership=Ownership.REPO_ONLY,
        )
        (repo_root / "src.txt").write_text("new")
        res = sync_extension(entry, repo_root, force=False)
        assert res.synced is False
        assert any("target exists" in e for e in res.errors)

    def test_sync_all(self, repo_root: Path) -> None:
        entries = [
            ExtensionEntry(id="a", type=ExtensionType.SCRIPT, description="a", source_path="a.txt", target_paths=[], ownership=Ownership.REPO_ONLY),
            ExtensionEntry(id="b", type=ExtensionType.CRON, description="b", source_path="", ownership=Ownership.EXTERNAL_RUNTIME),
        ]
        (repo_root / "a.txt").write_text("a")
        results = sync_all(entries, repo_root)
        assert len(results) == 2
        assert results[0].skipped is True  # no targets
        assert results[1].skipped is True  # external


class TestDoctor:
    def test_doctor_report_shape(self, repo_root: Path) -> None:
        from hermesoptimizer.extensions.doctor import run_doctor
        from hermesoptimizer.extensions import build_registry

        # Patch _repo_root to use our temp path
        import hermesoptimizer.extensions.doctor as doctor_mod
        original_repo_root = doctor_mod._repo_root
        doctor_mod._repo_root = lambda: repo_root

        # Create a minimal extension
        ext_dir = repo_root / "extensions"
        ext_dir.mkdir()
        (ext_dir / "test.yaml").write_text(
            "id: test\ntype: script\ndescription: test\nsource_path: src.py\nownership: repo_only\n"
        )
        (repo_root / "src.py").write_text("pass")

        try:
            report = run_doctor(dry_run=True)
            assert "extensions_checked" in report
            assert "healthy" in report
            assert "verify_passed" in report
            assert report["extensions_checked"] == 1
            assert report["healthy"] == 1
        finally:
            doctor_mod._repo_root = original_repo_root

    def test_doctor_dry_run_no_checkpoint(self, repo_root: Path) -> None:
        from hermesoptimizer.extensions.doctor import run_doctor, _checkpoint_path
        import hermesoptimizer.extensions.doctor as doctor_mod

        original_repo_root = doctor_mod._repo_root
        original_checkpoint = doctor_mod._checkpoint_path
        doctor_mod._repo_root = lambda: repo_root
        checkpoint = repo_root / "checkpoint.json"
        doctor_mod._checkpoint_path = lambda: checkpoint

        ext_dir = repo_root / "extensions"
        ext_dir.mkdir()
        (ext_dir / "test.yaml").write_text(
            "id: test\ntype: script\ndescription: test\nsource_path: src.py\nownership: repo_only\n"
        )
        (repo_root / "src.py").write_text("pass")

        try:
            run_doctor(dry_run=True)
            assert not checkpoint.exists()
        finally:
            doctor_mod._repo_root = original_repo_root
            doctor_mod._checkpoint_path = original_checkpoint
