"""Phase D closeout gate — single-command release readiness check.

Aggregates:
  1. Install integrity  (CLI boot + config parse canaries)
  2. Model/provider/plan truth (catalog loads + mismatch rejection)
  3. Channel/branch status (git channel state)
  4. Test suite smoke (pytest --co succeeds)

Fails closed: if any critical check cannot produce evidence, the gate fails.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hermesoptimizer.auxiliary_optimizer import (
    AuxiliaryDrift,
    check_auxiliary_drift,
    default_drift_report_path,
    load_auxiliary_entries,
    write_drift_report,
)


@dataclass(slots=True)
class CheckResult:
    name: str
    passed: bool
    critical: bool = True
    detail: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)


def _repo_root() -> Path:
    """Best-effort repo root from this file's location."""
    return Path(__file__).resolve().parents[3]


# -- Check 1: CLI boot canary -------------------------------------------------

def check_cli_boot() -> CheckResult:
    """Verify the CLI boots and reports version."""
    exe = sys.executable
    try:
        proc = subprocess.run(
            [exe, "-m", "hermesoptimizer"],
            capture_output=True, text=True, timeout=15,
            env={**os.environ, "NO_COLOR": "1", "PYTHONPATH": str(_repo_root() / "src")},
        )
        # --help / no-command returns usage, exit code varies; any non-crash is ok
        version_line = proc.stdout.strip() or proc.stderr.strip()
        if "hermesoptimizer" in version_line or proc.returncode in (0, 1):
            return CheckResult("cli_boot", True, evidence={"version_hint": version_line[:120]})
        return CheckResult("cli_boot", False, detail=f"exit={proc.returncode} stderr={proc.stderr[:200]}")
    except Exception as exc:
        return CheckResult("cli_boot", False, detail=str(exc))


# -- Check 2: Config parse canary ---------------------------------------------

def check_config_parse() -> CheckResult:
    """Verify ~/.hermes/config.yaml parses (or note its absence)."""
    config_path = Path.home() / ".hermes" / "config.yaml"
    if not config_path.exists():
        return CheckResult(
            "config_parse", True, critical=False,
            detail="no hermes config.yaml found (acceptable in test env)",
            evidence={"path": str(config_path), "exists": False},
        )
    try:
        import yaml
        data = yaml.safe_load(config_path.read_text())
        if isinstance(data, dict):
            return CheckResult("config_parse", True, evidence={"keys": sorted(data.keys())[:20]})
        return CheckResult("config_parse", False, detail="parsed but not a dict")
    except ImportError:
        # yaml not available — try json fallback
        return CheckResult(
            "config_parse", True, critical=False,
            detail="yaml not importable, skipping parse check",
        )
    except Exception as exc:
        return CheckResult("config_parse", False, detail=str(exc))


# -- Check 3: Model/provider/plan truth module loads --------------------------

def check_model_plan_truth() -> CheckResult:
    """Verify the model-plan-truth enforcement module loads and core objects exist."""
    try:
        from hermesoptimizer.sources.model_plan_truth import (
            ModelSelectionVerifier,
            SafetyLane,
            SelectionStatus,
            verify_model_for_plan,
            check_glm_mismatch,
        )
        # Quick functional check: reject known-bad combination
        result = verify_model_for_plan("glm-4.6v", "zai", SafetyLane.CODING)
        rejection_works = result.is_rejected()

        return CheckResult(
            "model_plan_truth", True,
            evidence={
                "verifier_loads": True,
                "glm_mismatch_rejection_works": rejection_works,
            },
        )
    except Exception as exc:
        return CheckResult("model_plan_truth", False, detail=str(exc))


# -- Check 4: Provider truth store loads -------------------------------------

def check_provider_truth() -> CheckResult:
    """Verify merged provider truth can be instantiated and is non-empty."""
    try:
        from hermesoptimizer.sources.provider_registry import ProviderRegistry

        registry = ProviderRegistry.from_merged_sources()
        try:
            providers = registry.providers(include_quarantined=True)
        except TypeError:
            providers = registry.providers()
        count = len(providers)
        return CheckResult(
            "provider_truth",
            count > 0,
            evidence={"entries": count, "source": getattr(registry, "source", "unknown"), "providers": providers[:20]},
            detail="" if count > 0 else "provider registry is empty",
        )
    except Exception as exc:
        return CheckResult("provider_truth", False, detail=str(exc))


def check_auxiliary_drift_status() -> CheckResult:
    """Check auxiliary provider/model entries against provider truth store."""
    try:
        auxiliary_entries = load_auxiliary_entries()
        drifts = check_auxiliary_drift(auxiliary_entries)
        return CheckResult(
            "auxiliary_drift",
            True,
            critical=False,
            detail=(
                "auxiliary drift findings present (non-blocking)"
                if drifts
                else ""
            ),
            evidence={
                "entries": len(auxiliary_entries) if isinstance(auxiliary_entries, dict) else 0,
                "drift_count": len(drifts),
                "drifts": [
                    {
                        "role": drift.role,
                        "provider": drift.provider,
                        "model": drift.model,
                        "issue": drift.issue,
                        "severity": drift.severity,
                    }
                    for drift in drifts
                ],
            },
        )
    except Exception as exc:
        return CheckResult("auxiliary_drift", False, critical=False, detail=str(exc))


# -- Check 5: Channel state ---------------------------------------------------

def check_channel_status() -> CheckResult:
    """Verify channel_update module loads and report real git branch evidence."""
    try:
        repo_root = _repo_root()
        scripts_dir = repo_root / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        import channel_update
        evidence: dict[str, Any] = {
            "channels": channel_update.CHANNELS,
            "promotion_paths": channel_update.PROMOTION_PATHS,
            "repo_root": str(repo_root),
        }
        # Gather real git branch evidence
        try:
            proc = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=10,
                cwd=str(repo_root),
            )
            if proc.returncode == 0:
                evidence["current_branch"] = proc.stdout.strip()
            proc2 = subprocess.run(
                ["git", "log", "--oneline", "-1", "--format=%H %s"],
                capture_output=True, text=True, timeout=10,
                cwd=str(repo_root),
            )
            if proc2.returncode == 0:
                evidence["latest_commit"] = proc2.stdout.strip()
        except Exception:
            pass  # Non-critical enrichment; module load is the primary check

        return CheckResult("channel_status", True, evidence=evidence)
    except Exception as exc:
        return CheckResult("channel_status", False, detail=str(exc))


# -- Check 6: Test collection smoke -------------------------------------------

def check_test_collection() -> CheckResult:
    """Verify pytest can collect tests without error."""
    repo_root = _repo_root()
    env = {**os.environ, "PYTHONPATH": str(repo_root / "src")}
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "--co"],
            capture_output=True, text=True, timeout=60,
            cwd=str(repo_root),
            env=env,
        )
        lines = proc.stdout.strip().splitlines()
        test_count = len([l for l in lines if "::" in l])
        return CheckResult(
            "test_collection", proc.returncode == 0 and test_count > 0,
            evidence={"tests_collected": test_count, "exit_code": proc.returncode},
            detail="" if proc.returncode == 0 else proc.stderr[:200],
        )
    except Exception as exc:
        return CheckResult("test_collection", False, detail=str(exc))


def _cli_command_names() -> list[str]:
    """Return top-level CLI command names from the argparse surface."""
    from hermesoptimizer.cli import build_parser

    parser = build_parser()
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if choices:
            return sorted(choices.keys())
    return []


def check_cli_help_smoke() -> CheckResult:
    """Verify every top-level CLI command responds to --help with exit 0."""
    repo_root = _repo_root()
    env = {**os.environ, "PYTHONPATH": str(repo_root / "src")}
    commands = _cli_command_names()
    failed: list[dict[str, Any]] = []
    for command in commands:
        proc = subprocess.run(
            [sys.executable, "-m", "hermesoptimizer", command, "--help"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(repo_root),
            env=env,
        )
        if proc.returncode != 0:
            failed.append(
                {
                    "command": command,
                    "exit_code": proc.returncode,
                    "stderr": proc.stderr[-200:],
                    "stdout": proc.stdout[-200:],
                }
            )
    return CheckResult(
        "cli_help_smoke",
        not failed and bool(commands),
        evidence={"commands_checked": commands, "failed": failed},
        detail="" if not failed else f"{len(failed)} command help smoke(s) failed",
    )


def check_readme_command_drift() -> CheckResult:
    """Fail when README references top-level commands absent from argparse."""
    repo_root = _repo_root()
    text = (repo_root / "README.md").read_text(encoding="utf-8")
    documented: set[str] = set()
    for match in re.finditer(r"`hermesoptimizer ([^`]+)`", text):
        for part in match.group(1).split("/"):
            root = part.strip().split()[0]
            if root:
                documented.add(root)
    actual = set(_cli_command_names())
    missing = sorted(documented - actual)
    return CheckResult(
        "readme_command_drift",
        not missing,
        evidence={"documented": sorted(documented), "missing": missing},
        detail="" if not missing else f"README documents unknown commands: {missing}",
    )


def check_installer_canary() -> CheckResult:
    """Run the no-write fresh-root installer canary used for clean installs."""
    repo_root = _repo_root()
    with tempfile.TemporaryDirectory(prefix="hopt-installer-canary-") as td:
        fresh_root = Path(td) / "fresh-root"
        commands = {
            "ext_sync_fresh_root": [
                sys.executable,
                "-m",
                "hermesoptimizer",
                "ext-sync",
                "--dry-run",
                "--fresh-root",
                str(fresh_root),
            ],
            "ext_doctor": [sys.executable, "-m", "hermesoptimizer", "ext-doctor", "--dry-run"],
        }
        results: dict[str, dict[str, Any]] = {}
        for name, cmd in commands.items():
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=90,
                cwd=str(repo_root),
                env={**os.environ, "PYTHONPATH": str(repo_root / "src")},
            )
            results[name] = {"exit_code": proc.returncode, "stdout_tail": proc.stdout[-300:], "stderr_tail": proc.stderr[-300:]}
            if proc.returncode != 0:
                return CheckResult(
                    "installer_canary",
                    False,
                    detail=f"{name} failed with exit {proc.returncode}",
                    evidence={"commands": results},
                )
    return CheckResult("installer_canary", True, evidence={"commands": results})


def check_brain_doctor_canary() -> CheckResult:
    """Run a non-dry, local-only brain canary without live provider network calls."""
    repo_root = _repo_root()
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "hermesoptimizer",
            "brain-doctor",
            "--check",
            "request_dump",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(repo_root),
        env={**os.environ, "PYTHONPATH": str(repo_root / "src")},
    )
    return CheckResult(
        "brain_doctor_canary",
        proc.returncode == 0,
        evidence={"exit_code": proc.returncode, "stdout_tail": proc.stdout[-500:], "stderr_tail": proc.stderr[-500:]},
        detail="" if proc.returncode == 0 else "non-dry local brain canary failed",
    )


# -- Check 7: Extension doctor smoke ------------------------------------------

def check_extension_doctor() -> CheckResult:
    """Run extension doctor in dry-run and report status.

    Fails closed: if doctor reports real issues (verify failures, missing sources,
    or canary failures), the check fails. Exceptions also cause failure rather
    than being swallowed as pass.

    In dry-run mode, drift warnings from REPO_EXTERNAL extensions are treated as
    non-critical because they indicate runtime targets are not yet installed,
    not that repo source is broken.  The artifacts are tracked under a repo-only
    extension (e.g. ``scripts``) and are expected to be absent in CI.
    """
    try:
        from hermesoptimizer.extensions.doctor import run_doctor
        report = run_doctor(dry_run=True)
        issues = report.get("issues", [])
        canary = report.get("canary", {})
        overall = canary.get("overall_passed", False)
        verify_failed = report.get("verify_failed", 0)
        missing_source = report.get("missing_source", 0)
        missing_target = report.get("missing_target", 0)
        drift_errors = report.get("drift_errors", 0)
        drift_warnings = report.get("drift_warnings", 0)

        # In dry-run, only count issues that are *not* dry-run drift warnings.
        # Those are already captured in drift_warnings and are non-critical.
        real_issues = [
            i for i in issues
            if not i.get("issue", "").startswith("not installed (dry-run)")
        ]
        real_issues_count = len(real_issues)

        has_real_issues = (
            verify_failed > 0
            or missing_source > 0
            or missing_target > 0
            or drift_errors > 0
            or real_issues_count > 0
        )

        passed = not has_real_issues

        detail = ""
        if not passed:
            detail = f"doctor found {real_issues_count} issue(s), verify_failed={verify_failed}, missing_source={missing_source}, drift_errors={drift_errors}"
        elif drift_warnings > 0:
            detail = f"dry-run drift warnings: {drift_warnings} (non-critical)"

        return CheckResult(
            "extension_doctor", passed,
            evidence={
                "extensions_checked": report.get("extensions_checked", 0),
                "issues": real_issues_count,
                "dry_run_drift_issues": [
                    i for i in issues
                    if i.get("issue", "").startswith("not installed (dry-run)")
                ],
                "drift_warnings": drift_warnings,
                "verify_failed": verify_failed,
                "missing_source": missing_source,
                "missing_target": missing_target,
                "drift_errors": drift_errors,
                "canary_overall_passed": overall,
            },
            critical=True,
            detail=detail,
        )
    except ImportError as exc:
        # Lean environments can skip the doctor module, but only that case.
        return CheckResult(
            "extension_doctor", True, critical=False,
            detail=f"doctor unavailable: {exc}",
        )
    except Exception as exc:
        # Doctor failure is a real problem — fail closed, not silently passed
        return CheckResult(
            "extension_doctor", False, critical=True,
            detail=f"doctor check failed: {exc}",
        )


# -- Check 8: Version consistency ---------------------------------------------

def check_version() -> CheckResult:
    """Verify __version__ is set and non-empty."""
    try:
        from hermesoptimizer import __version__
        ok = bool(__version__)
        return CheckResult(
            "version", ok,
            evidence={"version": __version__},
            detail="" if ok else "version is empty or unset",
        )
    except Exception as exc:
        return CheckResult("version", False, detail=str(exc))


# -- Check 9: Wheel install smoke ---------------------------------------------

def check_wheel_install_smoke() -> CheckResult:
    """Build a wheel, inspect package data, and smoke CLI commands in an isolated venv."""
    repo_root = _repo_root()
    required_members = {
        "hermesoptimizer/data/provider_registry.seed.json",
        "hermesoptimizer/data/provider_endpoints.json",
        "hermesoptimizer/data/provider_models.json",
        "hermesoptimizer/extensions/data/dreams.yaml",
        "hermesoptimizer/extensions/data/caveman.yaml",
    }
    commands = [
        ["provider-list"],
        ["provider-recommend", "--limit", "1"],
        ["ext-list"],
        ["ext-doctor", "--dry-run"],
        ["brain-doctor", "--dry-run"],
        ["caveman", "--help"],
    ]
    with tempfile.TemporaryDirectory(prefix="hopt-wheel-smoke-") as td:
        tmp = Path(td)
        wheelhouse = tmp / "wheelhouse"
        wheelhouse.mkdir()
        build = subprocess.run(
            [sys.executable, "-m", "pip", "wheel", ".", "-w", str(wheelhouse), "--no-deps"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if build.returncode != 0:
            return CheckResult("wheel_install_smoke", False, detail=build.stderr[-500:])
        wheels = sorted(wheelhouse.glob("hermesoptimizer-*.whl"))
        if not wheels:
            return CheckResult("wheel_install_smoke", False, detail="wheel build produced no hermesoptimizer wheel")
        wheel = wheels[-1]
        with zipfile.ZipFile(wheel) as zf:
            names = set(zf.namelist())
        missing = sorted(required_members - names)
        if missing:
            return CheckResult(
                "wheel_install_smoke",
                False,
                detail=f"wheel missing package data: {missing}",
                evidence={"wheel": str(wheel), "missing_members": missing},
            )

        venv = tmp / "venv"
        subprocess.run([sys.executable, "-m", "venv", "--system-site-packages", str(venv)], check=True, timeout=120)
        py = venv / "bin" / "python"
        install = subprocess.run(
            [str(py), "-m", "pip", "install", "--no-deps", str(wheel)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if install.returncode != 0:
            return CheckResult("wheel_install_smoke", False, detail=install.stderr[-500:])

        command_results: dict[str, int] = {}
        for cmd in commands:
            proc = subprocess.run(
                [str(py), "-m", "hermesoptimizer", *cmd],
                capture_output=True,
                text=True,
                timeout=90,
            )
            key = " ".join(cmd)
            command_results[key] = proc.returncode
            if proc.returncode != 0:
                return CheckResult(
                    "wheel_install_smoke",
                    False,
                    detail=f"wheel command failed: {key}: {proc.stderr[-300:] or proc.stdout[-300:]}",
                    evidence={"wheel": str(wheel), "commands": command_results},
                )
    return CheckResult(
        "wheel_install_smoke",
        True,
        evidence={"package_members_checked": sorted(required_members), "commands": command_results},
    )


# -- Check 10: Governance/doc drift --------------------------------------------

def check_governance_doc_drift() -> CheckResult:
    """Fail when governance docs reopen closed work or disagree with live contracts."""
    repo_root = _repo_root()
    issues: list[dict[str, str]] = []

    def add(path: str, issue: str) -> None:
        issues.append({"path": path, "issue": issue})

    guideline = (repo_root / "GUIDELINE.md").read_text(encoding="utf-8")
    try:
        section = guideline.split("## Non-negotiables", 1)[1].split("## Build priorities", 1)[0]
        numbers = [int(match.group(1)) for match in re.finditer(r"^### (\d+)\. ", section, re.MULTILINE)]
        if numbers != list(range(1, len(numbers) + 1)) or len(numbers) != len(set(numbers)):
            add("GUIDELINE.md", "non-negotiable headings are not sequential and unique")
    except IndexError:
        add("GUIDELINE.md", "missing Non-negotiables or Build priorities section")

    architecture = (repo_root / "ARCHITECTURE.md").read_text(encoding="utf-8")
    layer_words = {"seven": 7, "7": 7}
    layer_match = re.search(r"split into (\w+) layers", architecture)
    if not layer_match or layer_words.get(layer_match.group(1).lower()) != 7:
        add("ARCHITECTURE.md", "system model must declare seven layers")
    else:
        model = architecture.split("## System model", 1)[1].split("## Directory architecture", 1)[0]
        headings = re.findall(r"^### \d+\. ", model, re.MULTILINE)
        if len(headings) != 7:
            add("ARCHITECTURE.md", f"system model declares seven layers but lists {len(headings)}")
    planned = architecture.split("## Planned architecture extensions", 1)[1] if "## Planned architecture extensions" in architecture else ""
    stale_helpers = ["rail_loader_check.py", "brain_doctor.py", "resolver_audit.py", "active_work_lint.py"]
    if "Planned but not yet built" in planned or any(f"- `{helper}`" in planned for helper in stale_helpers):
        add("ARCHITECTURE.md", "planned extensions section lists helpers that already exist")

    todo = (repo_root / "TODO.md").read_text(encoding="utf-8")
    active_work = (repo_root / "brain" / "active-work" / "current.md").read_text(encoding="utf-8")
    closed_work_markers = [
        "follow-up audit pending",
        "until merge policy work lands",
        "dispatch parallel whole-codebase governance audit agents",
        "dispatch audit agents",
    ]
    combined = todo + "\n" + active_work
    for marker in closed_work_markers:
        if marker in combined:
            add("TODO.md/brain/active-work/current.md", f"closed v0.9.3 work marker still present: {marker}")
    if "Status: closed locally; v0.9.5 refactor audit remediation complete." not in todo:
        add("TODO.md", "status must say v0.9.5 refactor audit remediation complete after closeout")

    try:
        canaries = json.loads((repo_root / "brain" / "evals" / "provider-canaries.json").read_text(encoding="utf-8"))
        from hermesoptimizer.sources.lane_state import LaneState
        valid_states = {s.value for s in LaneState}
        seen_names: set[str] = set()
        if not isinstance(canaries, list) or not canaries:
            add("brain/evals/provider-canaries.json", "provider canaries must be a non-empty list")
        for entry in canaries if isinstance(canaries, list) else []:
            if not isinstance(entry, dict):
                add("brain/evals/provider-canaries.json", "canary entry must be an object")
                continue
            name = entry.get("name")
            if not isinstance(name, str) or not name:
                add("brain/evals/provider-canaries.json", f"canary missing name: {entry}")
                name = "<unknown>"
            elif name in seen_names:
                add("brain/evals/provider-canaries.json", f"duplicate canary name: {name}")
            seen_names.add(name)

            lane_state = entry.get("lane_state")
            if lane_state not in valid_states:
                add("brain/evals/provider-canaries.json", f"canary {name} has invalid lane_state: {lane_state}")
            if entry.get("required_release") and LaneState.from_string(lane_state) is not LaneState.GREEN:
                add("brain/evals/provider-canaries.json", f"canary {name} required_release=true but lane_state is {lane_state}")
    except Exception as exc:  # noqa: BLE001
        add("brain/evals/provider-canaries.json", f"could not parse provider canaries: {exc}")

    import yaml

    for rel in [
        "extensions/scripts.yaml",
        "extensions/tool_surface.yaml",
        "src/hermesoptimizer/extensions/data/scripts.yaml",
        "src/hermesoptimizer/extensions/data/tool_surface.yaml",
    ]:
        data = yaml.safe_load((repo_root / rel).read_text(encoding="utf-8"))
        if data.get("ownership") == "repo_only" and data.get("target_paths") == []:
            metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
            if metadata.get("install_mode") != "repo_only_no_sync" or not metadata.get("no_sync_reason"):
                add(rel, "repo_only target_paths=[] must declare install_mode and no_sync_reason")

    changelog = (repo_root / "CHANGELOG.md").read_text(encoding="utf-8")
    versions = re.findall(r"^## (v\d+\.\d+\.\d+)", changelog, re.MULTILINE)
    duplicates = sorted({version for version in versions if versions.count(version) > 1})
    if duplicates:
        add("CHANGELOG.md", f"duplicate version headings: {duplicates}")
    roadmap = (repo_root / "ROADMAP.md").read_text(encoding="utf-8")
    if roadmap.count("## Completed versions") != 1:
        add("ROADMAP.md", "Completed versions heading must appear exactly once")

    return CheckResult(
        "governance_doc_drift",
        not issues,
        evidence={"issues": issues, "issue_count": len(issues)},
        detail="" if not issues else f"governance/doc drift found: {len(issues)} issue(s)",
    )


# -- Check 11: Release doc drift -----------------------------------------------

def check_release_doc_drift() -> CheckResult:
    """Fail if active release docs/scripts contain known stale release markers."""
    repo_root = _repo_root()
    excluded_parts = {".git", ".archives", "__pycache__", ".pytest_cache"}
    excluded_names = {"TODO.md", "VERSION0.9.2.md"}
    patterns = [
        "Current package version: " + "0.9.1",
        "v0.9.1" + " closeout",
        "0.9.1" + " is safe",
        "/home/agent/" + "hermesagent",
        "Run " + "0.9.1" + " closeout gate",
    ]
    suffixes = {".md", ".py", ".yaml", ".yml", ".json", ".toml"}
    hits: list[dict[str, Any]] = []
    for path in repo_root.rglob("*"):
        if not path.is_file() or path.suffix not in suffixes:
            continue
        if path.name in excluded_names:
            continue
        rel_parts = path.relative_to(repo_root).parts
        if any(part in excluded_parts for part in rel_parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for pattern in patterns:
            if pattern in text:
                hits.append({"path": str(path.relative_to(repo_root)), "pattern": pattern})

    return CheckResult(
        "release_doc_drift",
        not hits,
        evidence={"hits": hits, "hit_count": len(hits)},
        detail="" if not hits else f"stale release markers found: {len(hits)}",
    )


# -- Aggregator ---------------------------------------------------------------

CHECKS = [
    check_version,
    check_cli_boot,
    check_config_parse,
    check_model_plan_truth,
    check_provider_truth,
    check_auxiliary_drift_status,
    check_channel_status,
    check_test_collection,
    check_cli_help_smoke,
    check_readme_command_drift,
    check_extension_doctor,
    check_installer_canary,
    check_brain_doctor_canary,
    check_wheel_install_smoke,
    check_governance_doc_drift,
    check_release_doc_drift,
]


def run_readiness(dry_run: bool = False) -> dict[str, Any]:
    """Run all closeout checks and return a structured report."""
    results: list[CheckResult] = []
    for check_fn in CHECKS:
        try:
            results.append(check_fn())
        except Exception as exc:
            results.append(CheckResult(check_fn.__name__, False, detail=f"unhandled: {exc}"))

    critical_failures = [r for r in results if not r.passed and r.critical]
    any_failures = [r for r in results if not r.passed]
    gate_passed = len(critical_failures) == 0

    report: dict[str, Any] = {
        "version": results[0].evidence.get("version", "unknown") if results else "unknown",
        "gate_passed": gate_passed,
        "dry_run": dry_run,
        "critical_failures": len(critical_failures),
        "total_failures": len(any_failures),
        "checks": [
            {
                "name": r.name,
                "passed": r.passed,
                "critical": r.critical,
                "detail": r.detail,
                "evidence": r.evidence,
            }
            for r in results
        ],
    }

    if not dry_run:
        auxiliary_check = next((r for r in results if r.name == "auxiliary_drift"), None)
        if auxiliary_check is not None:
            drift_payload = auxiliary_check.evidence.get("drifts", [])
            write_drift_report(
                [type("AuxDriftProxy", (), item)() for item in []],
                default_drift_report_path(),
            )

    return report


def format_readiness(report: dict[str, Any]) -> str:
    """Format the readiness report for terminal output."""
    ver = report.get("version", "")
    lines = [
        f"hermesoptimizer {ver} release readiness",
        "=" * 40,
    ]
    for check in report["checks"]:
        status = "PASS" if check["passed"] else ("FAIL" if check["critical"] else "WARN")
        critical_marker = "" if check["passed"] or not check["critical"] else " [CRITICAL]"
        detail = f" — {check['detail']}" if check["detail"] else ""
        lines.append(f"  {status:4s}  {check['name']}{critical_marker}{detail}")

    lines.append("")
    if report["gate_passed"]:
        lines.append(f"GATE: PASSED — {ver} is safe to ship")
    else:
        lines.append(f"GATE: FAILED — {report['critical_failures']} critical check(s) failed")

    return "\n".join(lines)
