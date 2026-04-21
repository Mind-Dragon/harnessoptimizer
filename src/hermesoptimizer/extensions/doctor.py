"""Extension doctor: validate registry and compare with runtime state."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from hermesoptimizer.extensions import build_registry
from hermesoptimizer.extensions.schema import ExtensionEntry, Ownership


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _checkpoint_path() -> Path:
    return Path.home() / ".hoptimizer" / "extensions" / "checkpoint.json"


def run_doctor(dry_run: bool = False) -> dict:
    """Run extension doctor and return report.

    If dry_run is True, only validates registry without touching runtime.
    """
    registry_dir = _repo_root() / "extensions"
    entries = build_registry(registry_dir)
    repo_root = _repo_root()

    report = {
        "extensions_checked": len(entries),
        "healthy": 0,
        "missing_source": 0,
        "external": 0,
        "issues": [],
        "entries": [],
    }

    for entry in entries:
        status = "ok"
        if entry.ownership == Ownership.EXTERNAL_RUNTIME:
            status = "external"
            report["external"] += 1
        elif not entry.source_exists(repo_root):
            status = "missing_source"
            report["missing_source"] += 1
            report["issues"].append({
                "id": entry.id,
                "issue": "source_path does not exist in repo",
                "source_path": entry.source_path,
            })
        else:
            report["healthy"] += 1

        report["entries"].append({
            "id": entry.id,
            "type": entry.type.value,
            "ownership": entry.ownership.value,
            "status": status,
        })

    if not dry_run:
        checkpoint = _checkpoint_path()
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        checkpoint.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return report
