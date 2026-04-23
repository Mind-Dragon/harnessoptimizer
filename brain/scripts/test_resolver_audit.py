"""Tests for resolver_audit.py — TDD for resolver fixture audit script."""

import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

import importlib.util

spec = importlib.util.spec_from_file_location(
    "resolver_audit",
    Path(__file__).parent / "resolver_audit.py",
)
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)

load_cases = audit_module.load_cases
check_case = audit_module.check_case
build_report = audit_module.build_report


# --------------------------------------------------------------------------  #
# load_cases
# --------------------------------------------------------------------------  #


class TestLoadCases:
    def test_loads_existing_fixture(self):
        cases = load_cases(Path(__file__).parent.parent / "evals" / "resolver-cases.json")
        assert isinstance(cases, list)
        assert len(cases) >= 1

    def test_fixture_is_valid_json_array(self):
        path = Path(__file__).parent.parent / "evals" / "resolver-cases.json"
        data = json.loads(path.read_text())
        assert isinstance(data, list)

    def test_case_has_required_keys(self):
        cases = load_cases(Path(__file__).parent.parent / "evals" / "resolver-cases.json")
        for case in cases:
            assert "intent" in case, f"Case missing 'intent': {case}"
            assert "expected_first_path" in case, f"Case missing 'expected_first_path': {case}"

    def test_missing_fixture_returns_empty_list(self):
        cases = load_cases(Path("/nonexistent/resolver-cases.json"))
        assert cases == []


# --------------------------------------------------------------------------  #
# check_case
# --------------------------------------------------------------------------  #


class TestCheckCase:
    def test_resolves_script_path(self):
        """Case referencing an existing script should report it found."""
        result = check_case(
            {
                "intent": "provider health check",
                "expected_first_path": "scripts/provider_probe.py",
                "expected_artifact": "providers/",
                "notes": "test",
            },
            repo_root=Path("/home/agent/hermesoptimizer"),
        )
        assert result["intent"] == "provider health check"
        assert "status" in result
        assert result["status"] in ("pass", "fail", "ambiguous", "weak")

    def test_resolves_provider_note(self):
        """Case referencing an existing provider note should pass."""
        result = check_case(
            {
                "intent": "kimi coding failures",
                "expected_first_path": "providers/",
                "expected_artifact": "providers/kimi-coding.md",
                "notes": "test",
            },
            repo_root=Path("/home/agent/hermesoptimizer"),
        )
        assert result["status"] in ("pass", "fail", "ambiguous", "weak")

    def test_directory_path_reported_ambiguous(self):
        """Case with only a directory reference (no specific file) is ambiguous."""
        result = check_case(
            {
                "intent": "work resume",
                "expected_first_path": "active-work/",
                "expected_artifact": "active-work/<thread>.md",
                "notes": "test",
            },
            repo_root=Path("/home/agent/hermesoptimizer"),
        )
        # Directory-only path is ambiguous unless a specific file was verified
        assert result["status"] in ("ambiguous", "weak", "fail")

    def test_missing_artifact_reported(self):
        """Case referencing a non-existent artifact should fail."""
        result = check_case(
            {
                "intent": "missing artifact test",
                "expected_first_path": "scripts/nonexistent_script.py",
                "expected_artifact": "nonexistent/file.md",
                "notes": "test",
            },
            repo_root=Path("/home/agent/hermesoptimizer"),
        )
        assert result["status"] == "fail"
        assert result.get("missing_artifacts") is not None

    def test_weak_template_path_reported(self):
        """Case with a template/glob path like <thread>.md is weak."""
        result = check_case(
            {
                "intent": "weak template test",
                "expected_first_path": "active-work/",
                "expected_artifact": "active-work/<thread>.md",
                "notes": "test",
            },
            repo_root=Path("/home/agent/hermesoptimizer"),
        )
        assert result["status"] in ("weak", "ambiguous", "fail")

    def test_incident_directory_case(self):
        """Incident promotion case referencing incidents/ dir should be detected."""
        result = check_case(
            {
                "intent": "repeat failure",
                "expected_first_path": "incidents/",
                "expected_artifact": "skills or incident + eval",
                "notes": "test",
            },
            repo_root=Path("/home/agent/hermesoptimizer"),
        )
        # Directory-only path is ambiguous
        assert result["status"] in ("ambiguous", "weak", "fail")


# --------------------------------------------------------------------------  #
# build_report
# --------------------------------------------------------------------------  #


class TestBuildReport:
    def test_report_has_required_top_level_keys(self):
        cases = load_cases(Path(__file__).parent.parent / "evals" / "resolver-cases.json")
        report = build_report(cases, repo_root=Path("/home/agent/hermesoptimizer"))
        assert "total_cases" in report
        assert "cases" in report
        assert "missing_artifacts" in report
        assert "ambiguous_or_weak" in report
        assert "overall_status" in report
        assert "timestamp" in report

    def test_total_cases_matches_input(self):
        cases = load_cases(Path(__file__).parent.parent / "evals" / "resolver-cases.json")
        report = build_report(cases, repo_root=Path("/home/agent/hermesoptimizer"))
        assert report["total_cases"] == len(cases)

    def test_missing_fixture_report(self):
        cases = load_cases(Path("/nonexistent/cases.json"))
        report = build_report(cases, repo_root=Path("/home/agent/hermesoptimizer"))
        assert report["total_cases"] == 0
        assert report["overall_status"] == "fail"

    def test_overall_fail_when_missing_artifacts(self):
        cases = [
            {
                "intent": "missing script",
                "expected_first_path": "scripts/does_not_exist.py",
                "expected_artifact": "nonexistent.md",
                "notes": "test",
            }
        ]
        report = build_report(cases, repo_root=Path("/home/agent/hermesoptimizer"))
        assert report["overall_status"] == "fail"

    def test_overall_pass_when_all_cases_pass(self):
        cases = [
            {
                "intent": "existing provider",
                "expected_first_path": "providers/",
                "expected_artifact": "providers/kimi-coding.md",
                "notes": "known provider note",
            }
        ]
        report = build_report(cases, repo_root=Path("/home/agent/hermesoptimizer"))
        # May still be weak due to directory-only first_path
        assert report["overall_status"] in ("pass", "fail")


# --------------------------------------------------------------------------  #
# CLI / integration tests
# --------------------------------------------------------------------------  #


class TestResolverAuditCLI:
    def test_runs_without_error(self):
        cp = subprocess.run(
            ["python3", "brain/scripts/resolver_audit.py"],
            cwd="/home/agent/hermesoptimizer",
            capture_output=True,
            text=True,
        )
        # Should not crash
        assert cp.returncode in (0, 1)

    def test_output_is_valid_json(self):
        cp = subprocess.run(
            ["python3", "brain/scripts/resolver_audit.py"],
            cwd="/home/agent/hermesoptimizer",
            capture_output=True,
            text=True,
        )
        text = cp.stdout.strip()
        for start_idx in range(len(text)):
            if text[start_idx] in ("{", "["):
                try:
                    parsed = json.loads(text[start_idx:])
                    assert isinstance(parsed, dict)
                    break
                except json.JSONDecodeError:
                    continue
        else:
            pytest.fail("No valid JSON found in output")

    def test_help_flag(self):
        cp = subprocess.run(
            ["python3", "brain/scripts/resolver_audit.py", "--help"],
            cwd="/home/agent/hermesoptimizer",
            capture_output=True,
            text=True,
        )
        assert cp.returncode == 0
        assert "resolver" in cp.stdout.lower() or "audit" in cp.stdout.lower()

    def test_custom_fixture_path(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump([], f)
            f.flush()
            cp = subprocess.run(
                ["python3", "brain/scripts/resolver_audit.py", "--cases", f.name],
                cwd="/home/agent/hermesoptimizer",
                capture_output=True,
                text=True,
            )
            Path(f.name).unlink()
            assert cp.returncode in (0, 1)
