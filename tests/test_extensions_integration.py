from __future__ import annotations

from pathlib import Path

from hermesoptimizer.extensions import build_registry
from hermesoptimizer.extensions.schema import ExtensionType, Ownership


def test_loads_all_repo_extensions() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    registry_dir = repo_root / "extensions"
    entries = build_registry(registry_dir)

    ids = {e.id for e in entries}
    expected = {
        "caveman",
        "dreams",
        "vault_plugins",
        "tool_surface",
        "scripts",
        "skills",
        "cron",
    }
    assert ids == expected, f"Missing or extra extensions: {ids ^ expected}"

    # Verify specific entry shapes
    caveman = next(e for e in entries if e.id == "caveman")
    assert caveman.type == ExtensionType.CONFIG
    assert caveman.ownership == Ownership.REPO_EXTERNAL
    assert "caveman_mode" in caveman.metadata.get("config_key", "")

    dreams = next(e for e in entries if e.id == "dreams")
    assert dreams.type == ExtensionType.SIDECAR
    assert dreams.ownership == Ownership.REPO_EXTERNAL
    assert "cron_job_id" in dreams.metadata

    vault = next(e for e in entries if e.id == "vault_plugins")
    assert vault.type == ExtensionType.VAULT_PLUGIN
    assert "HermesPlugin" in vault.metadata.get("plugins", [])

    tool = next(e for e in entries if e.id == "tool_surface")
    assert tool.type == ExtensionType.COMMAND_SURFACE
    assert tool.ownership == Ownership.REPO_ONLY
    assert "provider list" in tool.metadata.get("commands", [])

    scripts = next(e for e in entries if e.id == "scripts")
    assert scripts.type == ExtensionType.SCRIPT
    assert scripts.ownership == Ownership.REPO_ONLY

    skills = next(e for e in entries if e.id == "skills")
    assert skills.type == ExtensionType.SKILL
    assert skills.ownership == Ownership.EXTERNAL_RUNTIME

    cron = next(e for e in entries if e.id == "cron")
    assert cron.type == ExtensionType.CRON
    assert cron.ownership == Ownership.EXTERNAL_RUNTIME


def test_no_duplicate_ids() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    entries = build_registry(repo_root / "extensions")
    ids = [e.id for e in entries]
    assert len(ids) == len(set(ids)), f"Duplicate ids found: {ids}"
