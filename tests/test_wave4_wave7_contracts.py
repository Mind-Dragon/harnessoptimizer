from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from hermesoptimizer.cli import build_parser
from hermesoptimizer.release.readiness import (
    check_cli_help_smoke,
    check_installer_canary,
    check_provider_truth,
    run_readiness,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _cli_commands() -> set[str]:
    parser = build_parser()
    for action in parser._actions:
        if getattr(action, "choices", None):
            return set(action.choices.keys())
    return set()


def _readme_command_roots() -> set[str]:
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    roots: set[str] = set()
    for match in re.finditer(r"`hermesoptimizer ([^`]+)`", text):
        for part in match.group(1).split("/"):
            root = part.strip().split()[0]
            if root:
                roots.add(root)
    return roots


def test_dodev_help_exits_zero() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "hermesoptimizer", "dodev", "--help"],
        cwd=REPO_ROOT,
        env={"PYTHONPATH": str(REPO_ROOT / "src")},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    assert "workflow" in proc.stdout.lower()


def test_readme_commands_match_cli_surface() -> None:
    missing = sorted(_readme_command_roots() - _cli_commands())
    assert missing == []


def test_readme_test_count_matches_collection() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    match = re.search(r"currently reports ([0-9,]+) collected tests", readme)
    assert match, "README must state collected test count"
    documented = int(match.group(1).replace(",", ""))
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only"],
        cwd=REPO_ROOT,
        env={"PYTHONPATH": str(REPO_ROOT / "src")},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    collected_match = re.search(r"([0-9]+) tests collected", proc.stdout)
    assert collected_match, proc.stdout[-500:]
    assert documented == int(collected_match.group(1))


def test_cli_help_smoke_covers_all_commands() -> None:
    result = check_cli_help_smoke()
    assert result.passed is True
    assert result.evidence["failed"] == []
    assert set(result.evidence["commands_checked"]) == _cli_commands()


def test_provider_truth_fails_closed_when_empty(monkeypatch) -> None:
    class EmptyRegistry:
        def providers(self):
            return []

    monkeypatch.setattr(
        "hermesoptimizer.sources.provider_registry.ProviderRegistry.from_merged_sources",
        classmethod(lambda cls: EmptyRegistry()),
    )
    result = check_provider_truth()
    assert result.passed is False
    assert result.evidence["entries"] == 0


def test_installer_canary_is_release_check() -> None:
    result = check_installer_canary()
    assert result.passed is True
    assert "commands" in result.evidence


def test_gate_passed_iff_all_critical_checks_pass() -> None:
    report = run_readiness(dry_run=True)
    critical = [check for check in report["checks"] if check["critical"]]
    assert report["gate_passed"] == all(check["passed"] for check in critical)


def test_caveman_readme_does_not_claim_native_hermes_consumption() -> None:
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8").lower()
    forbidden = [
        "hermes core reads `caveman_mode`",
        "native hermes caveman",
    ]
    assert not any(token in text for token in forbidden)
