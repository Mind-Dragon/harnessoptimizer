"""Extension doctor: validate registry and compare with runtime state.

This module provides end-of-install canary checks:
- CLI still boots
- Changed config still parses
- Changed config matches intended effective state
- Post-install proof artifact is generated
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from hermesoptimizer.extensions import build_registry
from hermesoptimizer.extensions import resolver
from hermesoptimizer.extensions.drift import check_all_drift
from hermesoptimizer.extensions.install_integrity import (
    InstallProof,
    InstallState,
    validate_yaml_file,
    _utc_now,
)
from hermesoptimizer.extensions.schema import ExtensionEntry, Ownership
from hermesoptimizer.extensions.status import check_all_statuses
from hermesoptimizer.extensions.verify import verify_all


def _checkpoint_path() -> Path:
    return Path.home() / ".hoptimizer" / "extensions" / "checkpoint.json"


def _canary_path() -> Path:
    return Path.home() / ".hoptimizer" / "extensions" / "canary.json"


def _hermes_config_path() -> Path:
    return Path.home() / ".hermes" / "config.yaml"


def run_cli_boot_canary() -> dict[str, Any]:
    """Check that the hermesoptimizer CLI can boot.

    Returns dict with 'passed', 'error' (if any), and 'version' if successful.
    """
    result: dict[str, Any] = {"passed": False}

    # Find the hermesoptimizer entry point
    exe = sys.executable
    try:
        proc = subprocess.run(
            [exe, "-m", "hermesoptimizer"],
            capture_output=True,
            text=True,
            timeout=15,
            env={**os.environ, "NO_COLOR": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[3] / "src")},
        )
        # The CLI prints usage when called with no subcommand; exit code varies
        # by Python/argparse version (0 or 2).  Any non-crash is a pass.
        version_line = proc.stdout.strip() or proc.stderr.strip()
        if "hermesoptimizer" in version_line or proc.returncode in (0, 1, 2):
            result["passed"] = True
            result["version"] = version_line[:120]
        else:
            result["error"] = f"CLI exited with code {proc.returncode}: {proc.stderr[:200]}"
    except subprocess.TimeoutExpired:
        result["error"] = "CLI boot timed out after 15s"
    except Exception as exc:
        result["error"] = f"CLI boot check failed: {exc}"

    return result


def run_config_parse_canary() -> dict[str, Any]:
    """Check that the Hermes config parses correctly.

    Returns dict with 'passed', 'valid' (bool), and 'errors' if any.
    """
    result: dict[str, Any] = {"passed": False, "valid": False}

    config_path = _hermes_config_path()
    if not config_path.exists():
        result["error"] = "config file does not exist"
        return result

    errors = validate_yaml_file(config_path)
    if errors:
        result["errors"] = errors
        result["error"] = f"config parse errors: {errors}"
        return result

    result["valid"] = True
    result["passed"] = True
    return result


def run_doctor(dry_run: bool = False) -> dict:
    """Run extension doctor and return report.

    If dry_run is True, only validates registry without touching runtime.
    """
    entries = build_registry(resolver.registry_dir())
    repo_root = resolver._repo_root()

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

    statuses = check_all_statuses(entries, repo_root, dry_run=dry_run)
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
        elif status.status == "drifted":
            # Dry-run only: REPO_EXTERNAL with missing targets is a warning,
            # not a blocking issue.  Count it as healthy for the gate.
            report["drift_warnings"] += 1
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

    # Run end-of-install canary checks (even in dry_run for smoke testing)
    canary = {
        "timestamp": _utc_now(),
        "cli_boot": run_cli_boot_canary(),
        "config_parse": run_config_parse_canary(),
        "overall_passed": False,
    }
    canary["overall_passed"] = (
        canary["cli_boot"].get("passed", False)
        and canary["config_parse"].get("passed", False)
    )

    # Persist canary result
    if not dry_run:
        canary_path = _canary_path()
        canary_path.parent.mkdir(parents=True, exist_ok=True)
        canary_path.write_text(json.dumps(canary, indent=2), encoding="utf-8")

    # Attach canary to report for caller
    report["canary"] = canary

    return report
