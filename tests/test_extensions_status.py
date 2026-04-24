from __future__ import annotations

from pathlib import Path

from hermesoptimizer.extensions.schema import ExtensionEntry, ExtensionType, Ownership
from hermesoptimizer.extensions.status import Status, check_extension_status
from hermesoptimizer.extensions.verify import verify_extension


def test_not_selected_extension_reports_not_selected_even_with_missing_targets(tmp_path: Path) -> None:
    entry = ExtensionEntry(
        id="dreams",
        type=ExtensionType.SIDECAR,
        description="Dreams sidecar",
        source_path="src/hermesoptimizer/dreams/",
        target_paths=[str(tmp_path / "missing-script.py")],
        ownership=Ownership.REPO_EXTERNAL,
        selected=False,
    )

    status = check_extension_status(entry, tmp_path)

    assert status.status == Status.NOT_SELECTED
    assert status.source_ok is True
    assert "not selected" in status.detail


def test_not_selected_extension_verify_is_clean_noop(tmp_path: Path) -> None:
    entry = ExtensionEntry(
        id="dreams",
        type=ExtensionType.SIDECAR,
        description="Dreams sidecar",
        source_path="src/hermesoptimizer/dreams/",
        verify_command="python -c 'raise SystemExit(9)'",
        ownership=Ownership.REPO_EXTERNAL,
        selected=False,
    )

    result = verify_extension(entry, cwd=tmp_path)

    assert result.passed is True
    assert result.exit_code == 0
    assert result.stdout == "not selected"
    assert result.command is None


def test_selected_external_runtime_keeps_external_status(tmp_path: Path) -> None:
    entry = ExtensionEntry(
        id="caveman",
        type=ExtensionType.CONFIG,
        description="Caveman",
        source_path="src/hermesoptimizer/caveman/",
        ownership=Ownership.EXTERNAL_RUNTIME,
        selected=True,
    )

    status = check_extension_status(entry, tmp_path)

    assert status.status == Status.EXTERNAL


def test_external_runtime_empty_source_reports_source_ok(tmp_path: Path) -> None:
    """External runtime with empty source_path must still report source_ok=True."""
    entry = ExtensionEntry(
        id="cron",
        type=ExtensionType.CRON,
        description="Cron-linked reflection and sweep jobs",
        source_path="",
        target_paths=[str(tmp_path / "cron")],
        ownership=Ownership.EXTERNAL_RUNTIME,
        selected=True,
    )

    status = check_extension_status(entry, tmp_path)

    assert status.source_ok is True
    assert status.status == Status.MISSING_TARGET


def test_repo_only_no_sync_status_is_ok_when_source_exists(tmp_path: Path) -> None:
    """repo_only_no_sync extensions with no targets report ok when source exists."""
    entry = ExtensionEntry(
        id="scripts",
        type=ExtensionType.SCRIPT,
        description="Repo-managed utility scripts",
        source_path="scripts/",
        target_paths=[],
        ownership=Ownership.REPO_ONLY,
        metadata={"install_mode": "repo_only_no_sync", "no_sync_reason": "imported from package"},
    )
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "validate_testplan.py").write_text("pass")

    status = check_extension_status(entry, tmp_path)

    assert status.status == Status.OK
    assert status.source_ok is True


def test_repo_only_no_sync_status_missing_source_when_source_missing(tmp_path: Path) -> None:
    """repo_only_no_sync extensions report missing_source when source is absent."""
    entry = ExtensionEntry(
        id="scripts",
        type=ExtensionType.SCRIPT,
        description="Repo-managed utility scripts",
        source_path="scripts/",
        target_paths=[],
        ownership=Ownership.REPO_ONLY,
        metadata={"install_mode": "repo_only_no_sync", "no_sync_reason": "imported from package"},
    )

    status = check_extension_status(entry, tmp_path)

    assert status.status == Status.MISSING_SOURCE
    assert status.source_ok is False


def test_unselected_extension_doctor_counts_not_selected(tmp_path: Path) -> None:
    """Doctor report must count unselected extensions separately."""
    from hermesoptimizer.extensions.doctor import run_doctor
    import hermesoptimizer.extensions.resolver as resolver_mod
    import hermesoptimizer.extensions.doctor as doctor_mod

    original_repo_root = resolver_mod._repo_root
    original_registry_dir = resolver_mod.registry_dir
    original_checkpoint = doctor_mod._checkpoint_path

    resolver_mod._repo_root = lambda: tmp_path
    resolver_mod.registry_dir = lambda: tmp_path / "extensions"
    doctor_mod._checkpoint_path = lambda: tmp_path / "checkpoint.json"

    ext_dir = tmp_path / "extensions"
    ext_dir.mkdir()
    (ext_dir / "opt.yaml").write_text(
        "id: opt\ntype: script\ndescription: optional\nsource_path: src.py\nownership: repo_only\nselected: false\n"
    )
    (tmp_path / "src.py").write_text("pass")

    try:
        report = run_doctor(dry_run=True)
        assert report["not_selected"] == 1
        assert report["extensions_checked"] == 1
        assert report["healthy"] == 0
    finally:
        resolver_mod._repo_root = original_repo_root
        resolver_mod.registry_dir = original_registry_dir
        doctor_mod._checkpoint_path = original_checkpoint


def test_unselected_extension_dry_run_drift_is_not_selected_not_drifted(tmp_path: Path) -> None:
    """Unselected extensions report NOT_SELECTED, not DRIFTED, even in dry-run."""
    entry = ExtensionEntry(
        id="dreams",
        type=ExtensionType.SIDECAR,
        description="Dreams sidecar",
        source_path="src/hermesoptimizer/dreams/",
        target_paths=[str(tmp_path / "missing-script.py")],
        ownership=Ownership.REPO_EXTERNAL,
        selected=False,
    )

    status = check_extension_status(entry, tmp_path, dry_run=True)

    assert status.status == Status.NOT_SELECTED
    assert status.source_ok is True
    assert "not selected" in status.detail
