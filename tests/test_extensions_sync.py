"""Dedicated tests for extension sync behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermesoptimizer.extensions.schema import ExtensionEntry, ExtensionType, Ownership
from hermesoptimizer.extensions.sync import sync_all, sync_extension


class TestSyncExtension:
    def test_sync_dry_run(self, tmp_path: Path) -> None:
        entry = ExtensionEntry(
            id="dry",
            type=ExtensionType.SCRIPT,
            description="dry run",
            source_path="src.txt",
            target_paths=[str(tmp_path / "new_target.txt")],
            ownership=Ownership.REPO_ONLY,
        )
        (tmp_path / "src.txt").write_text("hello")
        res = sync_extension(entry, tmp_path, dry_run=True)
        assert res.synced is False
        assert any("would copy" in a for a in res.actions)

    def test_sync_external_skipped(self, tmp_path: Path) -> None:
        entry = ExtensionEntry(
            id="ext",
            type=ExtensionType.CRON,
            description="external",
            source_path="",
            target_paths=[],
            ownership=Ownership.EXTERNAL_RUNTIME,
        )
        res = sync_extension(entry, tmp_path)
        assert res.skipped is True

    def test_sync_skips_not_selected(self, tmp_path: Path) -> None:
        entry = ExtensionEntry(
            id="not-selected",
            type=ExtensionType.SCRIPT,
            description="not selected",
            source_path="src.txt",
            target_paths=[str(tmp_path / "target.txt")],
            ownership=Ownership.REPO_ONLY,
            selected=False,
        )
        (tmp_path / "src.txt").write_text("hello")
        res = sync_extension(entry, tmp_path, dry_run=True)
        assert res.synced is False
        assert res.skipped is True
        assert any("not selected" in a for a in res.actions)

    def test_repo_only_no_sync_metadata_is_reported(self, tmp_path: Path) -> None:
        entry = ExtensionEntry(
            id="repo-only-no-sync",
            type=ExtensionType.SCRIPT,
            description="repo only no sync",
            source_path="src.txt",
            target_paths=[],
            ownership=Ownership.REPO_ONLY,
            metadata={
                "install_mode": "repo_only_no_sync",
                "no_sync_reason": "imported from package",
            },
        )
        (tmp_path / "src.txt").write_text("hello")
        res = sync_extension(entry, tmp_path, dry_run=True)
        assert res.synced is False
        assert res.skipped is True
        assert res.errors == []
        assert any("repo_only_no_sync" in action for action in res.actions)
        assert any("imported from package" in action for action in res.actions)

    def test_sync_dry_run_idempotent_on_existing_target(self, tmp_path: Path) -> None:
        target = tmp_path / "target.txt"
        target.write_text("existing")
        entry = ExtensionEntry(
            id="idempotent",
            type=ExtensionType.SCRIPT,
            description="idempotent dry run",
            source_path="src.txt",
            target_paths=[str(target)],
            ownership=Ownership.REPO_ONLY,
        )
        (tmp_path / "src.txt").write_text("new")
        res = sync_extension(entry, tmp_path, dry_run=True)
        assert res.synced is False
        assert res.skipped is False
        assert res.errors == []
        assert any("target exists" in a for a in res.actions)
        assert any("would copy" in a for a in res.actions)

    def test_fresh_root_remaps_tilde_targets(self, tmp_path: Path) -> None:
        fresh_root = tmp_path / "fresh"
        entry = ExtensionEntry(
            id="fresh",
            type=ExtensionType.SCRIPT,
            description="fresh root",
            source_path="src.txt",
            target_paths=["~/.hermes/test.txt"],
            ownership=Ownership.REPO_ONLY,
        )
        (tmp_path / "src.txt").write_text("hello")
        res = sync_extension(entry, tmp_path, dry_run=True, fresh_root=fresh_root)
        expected = fresh_root / ".hermes" / "test.txt"
        assert res.errors == []
        assert any(str(expected) in a for a in res.actions)

    def test_fresh_root_leaves_non_tilde_targets_unchanged(self, tmp_path: Path) -> None:
        fresh_root = tmp_path / "fresh"
        target = tmp_path / "target.txt"
        entry = ExtensionEntry(
            id="absolute",
            type=ExtensionType.SCRIPT,
            description="absolute path",
            source_path="src.txt",
            target_paths=[str(target)],
            ownership=Ownership.REPO_ONLY,
        )
        (tmp_path / "src.txt").write_text("hello")
        res = sync_extension(entry, tmp_path, dry_run=True, fresh_root=fresh_root)
        assert any(str(target) in a for a in res.actions)

    def test_sync_actual_copy(self, tmp_path: Path) -> None:
        target = tmp_path / "target.txt"
        entry = ExtensionEntry(
            id="copy",
            type=ExtensionType.SCRIPT,
            description="copy",
            source_path="src.txt",
            target_paths=[str(target)],
            ownership=Ownership.REPO_ONLY,
        )
        (tmp_path / "src.txt").write_text("content")
        res = sync_extension(entry, tmp_path)
        assert res.synced is True
        assert target.read_text() == "content"

    def test_sync_blocked_without_force(self, tmp_path: Path) -> None:
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
        (tmp_path / "src.txt").write_text("new")
        res = sync_extension(entry, tmp_path, force=False)
        assert res.synced is False
        assert any("target exists" in e for e in res.errors)


class TestSyncAll:
    def test_mixed_entries(self, tmp_path: Path) -> None:
        entries = [
            ExtensionEntry(
                id="a",
                type=ExtensionType.SCRIPT,
                description="a",
                source_path="a.txt",
                target_paths=[],
                ownership=Ownership.REPO_ONLY,
            ),
            ExtensionEntry(
                id="b",
                type=ExtensionType.CRON,
                description="b",
                source_path="",
                ownership=Ownership.EXTERNAL_RUNTIME,
            ),
        ]
        (tmp_path / "a.txt").write_text("a")
        results = sync_all(entries, tmp_path)
        assert len(results) == 2
        assert results[0].skipped is True  # no targets
        assert results[1].skipped is True  # external
