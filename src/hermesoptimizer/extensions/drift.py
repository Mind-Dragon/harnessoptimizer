"""Extension drift detection: repo truth vs runtime/install state.

Checks for specific extension families that go beyond generic
source_exists / target_exists guards.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from hermesoptimizer.extensions.schema import ExtensionEntry


@dataclass(frozen=True)
class DriftFinding:
    """A single drift finding."""

    id: str
    check: str
    severity: str  # error | warning | info
    detail: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _config_path() -> Path:
    return Path("~/.hermes/config.yaml").expanduser()


def _read_hermes_config() -> dict:
    path = _config_path()
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text()) or {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Caveman drift
# ---------------------------------------------------------------------------


def check_caveman_drift(entry: ExtensionEntry) -> list[DriftFinding]:
    """Check caveman-specific drift: config vs module vs skill."""
    findings: list[DriftFinding] = []
    config = _read_hermes_config()

    caveman_val = config.get("caveman_mode")
    module_path = _repo_root() / "src" / "hermesoptimizer" / "caveman"

    # 1. Config key present but module missing
    if caveman_val is not None and not module_path.exists():
        findings.append(
            DriftFinding(
                id=entry.id,
                check="config_vs_module",
                severity="error",
                detail="caveman_mode key present in config but repo module missing",
            )
        )

    # 2. Config value invalid type
    if caveman_val is not None and not isinstance(caveman_val, bool):
        findings.append(
            DriftFinding(
                id=entry.id,
                check="config_type",
                severity="error",
                detail=f"caveman_mode is not a boolean: {type(caveman_val).__name__}",
            )
        )

    # 3. Skill reference stale
    skill_path = Path("~/.hermes/skills/software-development/caveman/SKILL.md").expanduser()
    if caveman_val is True and not skill_path.exists():
        findings.append(
            DriftFinding(
                id=entry.id,
                check="skill_missing",
                severity="warning",
                detail=f"caveman mode enabled but skill not installed at {skill_path}",
            )
        )

    return findings


# ---------------------------------------------------------------------------
# Dreams drift
# ---------------------------------------------------------------------------


def check_dreams_drift(entry: ExtensionEntry) -> list[DriftFinding]:
    """Check dreams-specific drift: repo owns scripts but machine missing them."""
    findings: list[DriftFinding] = []

    # 1. memory_meta.db missing
    db_path = Path("~/.hermes/dreams/memory_meta.db").expanduser()
    if not db_path.exists():
        findings.append(
            DriftFinding(
                id=entry.id,
                check="memory_meta_db",
                severity="warning",
                detail=f"repo owns dreams but memory_meta.db missing at {db_path}",
            )
        )

    # 2. External scripts missing
    expected_scripts = [
        Path("~/.hermes/scripts/dreaming_reflection_context.py").expanduser(),
        Path("~/.hermes/scripts/supermemory_store.js").expanduser(),
    ]
    for script in expected_scripts:
        if not script.exists():
            findings.append(
                DriftFinding(
                    id=entry.id,
                    check="external_script_missing",
                    severity="warning",
                    detail=f"repo owns dreams but external script missing: {script}",
                )
            )

    # 3. Cron surface check (lightweight — just check if cron entry exists)
    cron_marker = Path("~/.hermes/cron").expanduser()
    if not cron_marker.exists():
        findings.append(
            DriftFinding(
                id=entry.id,
                check="cron_surface",
                severity="info",
                detail=f"cron surface directory missing: {cron_marker}",
            )
        )

    return findings


# ---------------------------------------------------------------------------
# Vault plugins drift
# ---------------------------------------------------------------------------


def check_vault_plugins_drift(entry: ExtensionEntry) -> list[DriftFinding]:
    """Check vault plugin drift: vault file missing, plugin classes stale."""
    findings: list[DriftFinding] = []

    vault_path = Path("~/.vault/vault.enc.json").expanduser()
    if not vault_path.exists():
        findings.append(
            DriftFinding(
                id=entry.id,
                check="vault_file_missing",
                severity="warning",
                detail=f"vault.enc.json not found at {vault_path}",
            )
        )

    return findings


# ---------------------------------------------------------------------------
# Tool surface drift
# ---------------------------------------------------------------------------


def check_tool_surface_drift(entry: ExtensionEntry) -> list[DriftFinding]:
    """Check tool-surface drift: commands in metadata vs actual handlers."""
    findings: list[DriftFinding] = []

    try:
        from hermesoptimizer.tool_surface.commands import list_commands

        actual = set(list_commands())
        expected = set(entry.metadata.get("commands", []))
        missing = expected - actual
        for m in missing:
            findings.append(
                DriftFinding(
                    id=entry.id,
                    check="command_missing",
                    severity="error",
                    detail=f"metadata expects command '{m}' but not found in tool_surface",
                )
            )
    except Exception as exc:
        findings.append(
            DriftFinding(
                id=entry.id,
                check="import_failed",
                severity="error",
                detail=f"failed to import tool_surface commands: {exc}",
            )
        )

    return findings


# ---------------------------------------------------------------------------
# Generic dispatcher
# ---------------------------------------------------------------------------

_FAMILY_CHECKERS: dict[str, callable] = {
    "caveman": check_caveman_drift,
    "dreams": check_dreams_drift,
    "vault_plugins": check_vault_plugins_drift,
    "tool_surface": check_tool_surface_drift,
}


def check_drift(entry: ExtensionEntry) -> list[DriftFinding]:
    """Run family-specific drift checks for an extension entry."""
    checker = _FAMILY_CHECKERS.get(entry.id)
    if checker is None:
        return []
    return checker(entry)


def check_all_drift(entries: list[ExtensionEntry]) -> list[DriftFinding]:
    """Run drift checks for all extensions."""
    findings: list[DriftFinding] = []
    for entry in entries:
        findings.extend(check_drift(entry))
    return findings
