from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from hermesoptimizer.extensions.schema import ExtensionEntry, ExtensionType, Ownership
from hermesoptimizer.extensions.status import Status, check_extension_status
from hermesoptimizer.extensions.sync import sync_extension
from hermesoptimizer.extensions.verify_contracts import verify_dreams
from hermesoptimizer.resources import read_provider_endpoints, read_provider_models


def test_dreams_verify_skips_when_manifest_unselected() -> None:
    assert verify_dreams() == 0


def test_selected_dreams_sync_maps_individual_scripts(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts" / "dreaming_pre_sweep.py").write_text("print('sweep')\n")
    (repo / "scripts" / "probe_memory_meta.py").write_text("print('probe')\n")
    entry = ExtensionEntry(
        id="dreams",
        type=ExtensionType.SIDECAR,
        description="dreams",
        source_path="src/hermesoptimizer/dreams/",
        target_paths=[
            "~/.hermes/scripts/dreaming_pre_sweep.py",
            "~/.hermes/scripts/probe_memory_meta.py",
        ],
        ownership=Ownership.REPO_EXTERNAL,
        selected=True,
        metadata={"sync_files": {"scripts/dreaming_pre_sweep.py": "~/.hermes/scripts/dreaming_pre_sweep.py", "scripts/probe_memory_meta.py": "~/.hermes/scripts/probe_memory_meta.py"}},
    )

    result = sync_extension(entry, repo, dry_run=True, fresh_root=tmp_path / "fresh")

    assert result.errors == []
    assert any("dreaming_pre_sweep.py" in action for action in result.actions)
    assert any("probe_memory_meta.py" in action for action in result.actions)


def test_selected_external_runtime_with_targets_checks_missing_targets(tmp_path: Path) -> None:
    entry = ExtensionEntry(
        id="caveman",
        type=ExtensionType.CONFIG,
        description="caveman",
        source_path="src/hermesoptimizer/caveman/__init__.py",
        target_paths=[str(tmp_path / "missing" / "SKILL.md")],
        ownership=Ownership.EXTERNAL_RUNTIME,
        selected=True,
    )

    status = check_extension_status(entry, tmp_path)

    assert status.status == Status.MISSING_TARGET
    assert "missing targets" in status.detail


def test_packaged_provider_catalog_resources_load() -> None:
    endpoints = read_provider_endpoints()
    models = read_provider_models()

    assert endpoints is not None
    assert models is not None
    assert endpoints.get("provider_endpoints")
    assert models.get("provider_models")


def test_package_import_uses_no_repo_root_catalog_for_recommend() -> None:
    from hermesoptimizer.cli.orphan import _build_recommender

    recommender = _build_recommender()

    assert recommender is not None


def test_brain_doctor_dry_run_works_from_importable_cli() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "hermesoptimizer", "brain-doctor", "--dry-run"],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "brain_doctor" in proc.stdout or "dry_run" in proc.stdout
