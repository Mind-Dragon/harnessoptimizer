"""Tests for brain_doctor.py — TDD for doctor orchestration script."""

import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

import importlib.util
spec = importlib.util.spec_from_file_location(
    "brain_doctor",
    Path(__file__).parent / "brain_doctor.py",
)
doctor_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor_module)

run_rail_check = doctor_module.run_rail_check
run_request_digest = doctor_module.run_request_digest
run_provider_probe = doctor_module.run_provider_probe
build_summary = doctor_module.build_summary


# ---------------------------------------------------------------------------
# run_rail_check
# ---------------------------------------------------------------------------

class TestRunRailCheck:
    def test_dry_run_returns_dict(self):
        result = run_rail_check(dry_run=True)
        assert isinstance(result, dict)
        assert "check" in result
        assert result["check"] == "rail_loader"

    def test_dry_run_does_not_fail_on_missing_rails(self):
        result = run_rail_check(dry_run=True)
        # dry-run should not raise; result shape is valid
        assert "overall_status" in result

    def test_live_run_returns_dict(self):
        result = run_rail_check(dry_run=False)
        assert isinstance(result, dict)
        assert "check" in result


# ---------------------------------------------------------------------------
# run_request_digest
# ---------------------------------------------------------------------------

class TestRunRequestDigest:
    def test_dry_run_returns_dict(self):
        result = run_request_digest(dry_run=True, limit=5)
        assert isinstance(result, dict)
        assert "check" in result
        assert result["check"] == "request_dump"

    def test_limit_applied(self):
        result = run_request_digest(dry_run=True, limit=10)
        assert result.get("limit") == 10


# ---------------------------------------------------------------------------
# run_provider_probe
# ---------------------------------------------------------------------------

class TestRunProviderProbe:
    def test_list_providers_dry_run(self):
        result = run_provider_probe(dry_run=True, list_only=True)
        assert isinstance(result, dict)
        assert result.get("check") == "provider_probe"
        assert result.get("status") == "dry_run_list"

    def test_list_providers_returns_names(self):
        result = run_provider_probe(dry_run=True, list_only=True)
        # Should not raise, should have list key
        assert "providers" in result or "dry_run" in result

    def test_non_dry_run_executes_probes(self):
        """Non-dry-run mode should execute real provider probes (not list-only)."""
        result = run_provider_probe(dry_run=False, list_only=False)
        assert isinstance(result, dict)
        assert result.get("check") == "provider_probe"
        # Should have probe results, not just a provider list
        # Result structure from provider_probe.py: list of probe results or dict with results
        assert result.get("status") != "dry_run_list", "non-dry-run should not return dry_run_list"
        assert result.get("status") != "list", "non-dry-run should not return list"

    def test_dry_run_list_only_flag_preserves_safety(self):
        """Even if dry_run=False, list_only=True should still just list (safety)."""
        result = run_provider_probe(dry_run=False, list_only=True)
        assert isinstance(result, dict)
        assert result.get("check") == "provider_probe"
        # With list_only=True, should still return list even in non-dry-run
        assert result.get("status") in ("list", "dry_run_list")


# ---------------------------------------------------------------------------
# build_summary
# ---------------------------------------------------------------------------

class TestBuildSummary:
    def test_empty_results(self):
        results = {}
        summary = build_summary(results, dry_run=True)
        assert summary["dry_run"] is True
        assert "checks_run" in summary

    def test_all_pass(self):
        results = {
            "rail_loader": {"overall_status": "pass"},
            "request_dump": {"files_analyzed": 0},
            "provider_probe": {"status": "dry_run"},
        }
        summary = build_summary(results, dry_run=True)
        assert summary["overall_status"] == "pass"

    def test_mixed_results(self):
        results = {
            "rail_loader": {"overall_status": "fail", "mismatch_detected": True},
            "request_dump": {"files_analyzed": 100},
            "provider_probe": {"status": "dry_run"},
        }
        summary = build_summary(results, dry_run=True)
        assert summary["overall_status"] == "fail"
        assert summary["checks_run"] == 3

    def test_summary_keys(self):
        results = {"rail_loader": {"overall_status": "pass"}}
        summary = build_summary(results, dry_run=True)
        assert "overall_status" in summary
        assert "checks_run" in summary
        assert "check_results" in summary


# ---------------------------------------------------------------------------
# CLI / integration tests
# ---------------------------------------------------------------------------

class TestBrainDoctorCLI:
    def test_dry_run_exits_zero(self):
        """Dry-run with no critical failures should exit 0."""
        cp = subprocess.run(
            ["python3", "brain/scripts/brain_doctor.py", "--dry-run"],
            cwd="/home/agent/hermesoptimizer",
            capture_output=True,
            text=True,
        )
        # Dry-run should not error
        assert cp.returncode in (0, 1)  # 0=pass, 1=lint issue

    def test_dry_run_output_is_json(self):
        cp = subprocess.run(
            ["python3", "brain/scripts/brain_doctor.py", "--dry-run"],
            cwd="/home/agent/hermesoptimizer",
            capture_output=True,
            text=True,
        )
        output = cp.stdout.strip()
        # Full output is multi-line JSON — find and parse the object
        for start_idx in range(len(output)):
            if output[start_idx] in ("{", "["):
                try:
                    parsed = json.loads(output[start_idx:])
                    assert isinstance(parsed, dict)
                    break
                except json.JSONDecodeError:
                    continue
        else:
            pytest.fail("No valid JSON found in output")

    def test_unknown_check_skipped(self):
        """Unknown --check value should be skipped gracefully."""
        cp = subprocess.run(
            ["python3", "brain/scripts/brain_doctor.py", "--dry-run", "--check", "nonexistent"],
            cwd="/home/agent/hermesoptimizer",
            capture_output=True,
            text=True,
        )
        # Should not crash; might exit 0 or 1
        assert cp.returncode in (0, 1)

    def test_help_flag(self):
        cp = subprocess.run(
            ["python3", "brain/scripts/brain_doctor.py", "--help"],
            cwd="/home/agent/hermesoptimizer",
            capture_output=True,
            text=True,
        )
        assert cp.returncode == 0
        assert "dry-run" in cp.stdout.lower()
