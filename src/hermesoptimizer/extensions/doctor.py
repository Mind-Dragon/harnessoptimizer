"""Extension doctor: validate registry and compare with runtime state."""

from __future__ import annotations

import json
from pathlib import Path

from hermesoptimizer.extensions import build_registry
from hermesoptimizer.extensions.drift import check_all_drift
from hermesoptimizer.extensions.schema import ExtensionEntry, Ownership
from hermesoptimizer.extensions.status import check_all_statuses
from hermesoptimizer.extensions.verify import verify_all


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
        "missing_target": 0,
        "external": 0,
        "verify_passed": 0,
        "verify_failed": 0,
        "drift_warnings": 0,
        "drift_errors": 0,
        "issues": [],
        "entries": [],
    }

    statuses = check_all_statuses(entries, repo_root)
    verify_results = verify_all(entries, cwd=repo_root)
    verify_by_id = {v.id: v for v in verify_results}
    drift_findings = check_all_drift(entries)
    drift_by_id: dict[str, list] = {}
    for finding in drift_findings:
        drift_by_id.setdefault(finding.id, []).append(finding)

    for entry, status in zip(entries, statuses):
        verify_res = verify_by_id.get(entry.id)
        entry_drift = drift_by_id.get(entry.id, [])

        if entry.ownership == Ownership.EXTERNAL_RUNTIME:
            report["external"] += 1
        elif not status.source_ok:
            report["missing_source"] += 1
            report["issues"].append({
                "id": entry.id,
                "issue": "source_path does not exist in repo",
                "source_path": entry.source_path,
            })
        elif status.status == "missing_target":
            report["missing_target"] += 1
            report["issues"].append({
                "id": entry.id,
                "issue": status.detail,
                "source_path": entry.source_path,
            })
        else:
            report["healthy"] += 1

        if verify_res and verify_res.passed:
            report["verify_passed"] += 1
        elif verify_res:
            report["verify_failed"] += 1
            report["issues"].append({
                "id": entry.id,
                "issue": f"verify failed: {verify_res.stderr or verify_res.stdout}",
                "command": verify_res.command,
            })

        for finding in entry_drift:
            if finding.severity == "error":
                report["drift_errors"] += 1
            elif finding.severity == "warning":
                report["drift_warnings"] += 1
            report["issues"].append({
                "id": entry.id,
                "issue": f"drift ({finding.severity}): {finding.detail}",
                "check": finding.check,
            })

        report["entries"].append({
            "id": entry.id,
            "type": entry.type.value,
            "ownership": entry.ownership.value,
            "status": status.status,
            "verify": "pass" if (verify_res and verify_res.passed) else ("fail" if verify_res else "n/a"),
            "drift": len(entry_drift),
        })

    if not dry_run:
        checkpoint = _checkpoint_path()
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        checkpoint.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return report
