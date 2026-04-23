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
