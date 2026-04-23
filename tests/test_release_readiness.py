"""Tests for Phase D closeout gate: release-readiness command and module."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hermesoptimizer.release.readiness import (
    CheckResult,
    check_channel_status,
    check_cli_boot,
    check_config_parse,
    check_extension_doctor,
    check_model_plan_truth,
    check_provider_truth,
    check_release_doc_drift,
    check_test_collection,
    check_version,
    format_readiness,
    run_readiness,
)


class TestCheckResult:
    def test_passed_result(self) -> None:
        r = CheckResult("foo", True)
        assert r.passed is True
        assert r.critical is True
        assert r.detail == ""

    def test_failed_non_critical(self) -> None:
        r = CheckResult("bar", False, critical=False, detail="meh")
        assert r.passed is False
        assert r.critical is False


class TestCheckVersion:
    def test_version_is_set(self) -> None:
        result = check_version()
        assert result.passed is True
        assert result.evidence["version"]  # non-empty


class TestCheckCliBoot:
    def test_cli_boots(self) -> None:
        result = check_cli_boot()
        assert result.passed is True


class TestCheckModelPlanTruth:
    def test_truth_module_loads_and_rejects_bad(self) -> None:
        result = check_model_plan_truth()
        assert result.passed is True
        assert result.evidence["glm_mismatch_rejection_works"] is True


class TestCheckProviderTruth:
    def test_provider_truth_loads(self) -> None:
        result = check_provider_truth()
        assert result.passed is True


class TestCheckChannelStatus:
    def test_channel_module_loads(self) -> None:
        result = check_channel_status()
        assert result.passed is True
        assert "dev" in result.evidence["channels"]

    def test_channel_status_includes_git_evidence(self) -> None:
        """Channel check should include real git branch/commit evidence."""
        result = check_channel_status()
        assert result.passed is True
        # These are best-effort; present when in a git repo
        assert "current_branch" in result.evidence or "latest_commit" in result.evidence


class TestCheckTestCollection:
    def test_tests_collect(self) -> None:
        result = check_test_collection()
        assert result.passed is True
        assert result.evidence["tests_collected"] > 0


class TestCheckExtensionDoctor:
    def test_doctor_runs(self) -> None:
        result = check_extension_doctor()
        assert isinstance(result.passed, bool)

    def test_doctor_issues_fail_closed(self) -> None:
        report = {
            "extensions_checked": 1,
            "issues": [{"id": "ext-1", "issue": "broken"}],
            "verify_failed": 0,
            "missing_source": 0,
            "missing_target": 0,
            "drift_errors": 0,
            "drift_warnings": 0,
            "canary": {"overall_passed": True},
        }
        with patch("hermesoptimizer.extensions.doctor.run_doctor", return_value=report):
            result = check_extension_doctor()

        assert result.passed is False
        assert result.critical is True
        assert "doctor found" in result.detail

    def test_doctor_dry_run_drift_warning_is_non_critical(self) -> None:
        """Dry-run drift warnings from REPO_EXTERNAL must not fail the gate."""
        report = {
            "extensions_checked": 1,
            "issues": [{"id": "dreams", "issue": "not installed (dry-run): /a/b.py"}],
            "verify_failed": 0,
            "missing_source": 0,
            "missing_target": 0,
            "drift_errors": 0,
            "drift_warnings": 1,
            "canary": {"overall_passed": True},
        }
        with patch("hermesoptimizer.extensions.doctor.run_doctor", return_value=report):
            result = check_extension_doctor()

        assert result.passed is True
        assert "dry-run drift warnings" in result.detail
        assert result.evidence["drift_warnings"] == 1
        assert result.evidence["issues"] == 0

    def test_doctor_missing_is_non_critical(self, monkeypatch) -> None:
        import builtins

        real_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "hermesoptimizer.extensions.doctor":
                raise ImportError("doctor unavailable")
            return real_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        result = check_extension_doctor()

        assert result.passed is True
        assert result.critical is False
        assert "doctor unavailable" in result.detail.lower()


class TestCheckReleaseDocDrift:
    def test_release_doc_drift_is_clean(self) -> None:
        result = check_release_doc_drift()
        assert result.passed is True
        assert result.evidence["hit_count"] == 0


class TestRunReadiness:
    def test_full_report_structure(self) -> None:
        report = run_readiness()
        assert report["version"] == "0.9.2"
        assert "gate_passed" in report
        assert "checks" in report
        assert len(report["checks"]) >= 7

    def test_all_checks_have_required_fields(self) -> None:
        report = run_readiness()
        for check in report["checks"]:
            assert "name" in check
            assert "passed" in check
            assert "critical" in check

    def test_gate_passes_when_critical_checks_pass(self) -> None:
        report = run_readiness()
        critical_results = [c for c in report["checks"] if c["critical"]]
        # All critical checks should pass in this test environment
        if report["gate_passed"]:
            assert all(c["passed"] for c in critical_results)

    def test_gate_fails_when_critical_check_fails(self) -> None:
        """Simulate a critical check failure."""
        import hermesoptimizer.release.readiness as mod
        original = mod.CHECKS[:]
        try:
            mod.CHECKS = [lambda: CheckResult("version", False, detail="wrong version")]
            report = run_readiness()
            assert report["gate_passed"] is False
            assert report["critical_failures"] >= 1
        finally:
            mod.CHECKS = original


class TestFormatReadiness:
    def test_format_produces_output(self) -> None:
        report = run_readiness()
        text = format_readiness(report)
        assert "0.9.2" in text
        assert "GATE:" in text

    def test_format_shows_pass(self) -> None:
        report = run_readiness()
        if report["gate_passed"]:
            text = format_readiness(report)
            assert "PASSED" in text

    def test_format_shows_fail(self) -> None:
        report = {
            "version": "0.9.2",
            "gate_passed": False,
            "dry_run": False,
            "critical_failures": 1,
            "total_failures": 1,
            "checks": [
                {
                    "name": "version",
                    "passed": False,
                    "critical": True,
                    "detail": "wrong version",
                    "evidence": {},
                },
            ],
        }
        text = format_readiness(report)
        assert "FAILED" in text


class TestReleaseReadinessCLI:
    def test_parser_accepts_release_readiness(self) -> None:
        from hermesoptimizer.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["release-readiness"])
        assert args.command == "release-readiness"

    def test_parser_accepts_dry_run_and_json_out(self) -> None:
        from hermesoptimizer.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["release-readiness", "--dry-run", "--json-out", "/tmp/r.json"])
        assert args.dry_run is True
        assert args.json_out == "/tmp/r.json"

    def test_release_readiness_in_command_list(self) -> None:
        from hermesoptimizer.cli import build_parser

        parser = build_parser()
        commands = set()
        for action in parser._actions:
            if getattr(action, "choices", None):
                commands = set(action.choices.keys())
        assert "release-readiness" in commands
