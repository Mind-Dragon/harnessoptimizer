"""Tests for rail_loader_check.py — TDD for SOUL/HEARTBEAT prefill validation."""

import json
import re
import tempfile
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

# Module under test
import importlib.util
spec = importlib.util.spec_from_file_location(
    "rail_loader_check",
    Path(__file__).parent / "rail_loader_check.py",
)
rail_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rail_module)

classify_format = rail_module.classify_format
check_rail_file = rail_module.check_rail_file
scan_log_for_prefill_errors = rail_module.scan_log_for_prefill_errors
build_report = rail_module.build_report


class TestClassifyFormat:
    def test_markdown_plaintext(self, tmp_path):
        p = tmp_path / "SOUL.md"
        p.write_text("# SOUL.md\n\nSome content.\n")
        result = classify_format(p)
        assert result["format"] == "markdown/plaintext"
        assert result["valid_json"] is False

    def test_json_format(self, tmp_path):
        p = tmp_path / "rail.json"
        p.write_text('[{"role": "user", "content": "hello"}]\n')
        result = classify_format(p)
        assert result["format"] == "json"
        assert result["valid_json"] is True

    def test_empty_file(self, tmp_path):
        p = tmp_path / "empty.md"
        p.write_text("")
        result = classify_format(p)
        assert result["format"] == "markdown/plaintext"
        assert result["valid_json"] is False

    def test_whitespace_only(self, tmp_path):
        p = tmp_path / "ws.txt"
        p.write_text("   \n\n  ")
        result = classify_format(p)
        assert result["format"] == "markdown/plaintext"
        assert result["valid_json"] is False


class TestCheckRailFile:
    def test_missing_file(self):
        result = check_rail_file(Path("/nonexistent/SOUL.md"))
        assert result["exists"] is False
        assert result["status"] == "missing"

    def test_markdown_file_known_loader_contract(self, tmp_path):
        p = tmp_path / "SOUL.md"
        p.write_text("# SOUL.md\n\nOperating doctrine.\n")
        result = check_rail_file(p)
        assert result["exists"] is True
        assert result["format"] == "markdown/plaintext"
        assert result["loader_expects"] == "markdown/plaintext"
        assert result["status"] == "ok"

    def test_json_file_with_valid_structure(self, tmp_path):
        p = tmp_path / "messages.json"
        p.write_text('[{"role": "system", "content": "be helpful"}]\n')
        result = check_rail_file(p)
        assert result["exists"] is True
        assert result["format"] == "json"
        assert result["loader_expects"] == "markdown/plaintext"
        assert result["status"] == "ok"


class TestScanLogForPrefillErrors:
    def test_finds_prefill_error(self, tmp_path):
        log = tmp_path / "agent.log"
        log.write_text(
            "2026-04-22 20:11:38,456 WARNING gateway.run: "
            "Failed to load prefill messages from /home/agent/clawd/SOUL.md: "
            "Expecting value: line 1 column 1 (char 0)\n"
            "2026-04-22 20:12:00,001 INFO gateway.run: started\n"
        )
        errors = scan_log_for_prefill_errors([log])
        assert len(errors) == 1
        assert "SOUL.md" in errors[0]["file"]
        assert "Expecting value" in errors[0]["error"]

    def test_no_errors_in_clean_log(self, tmp_path):
        log = tmp_path / "agent.log"
        log.write_text("2026-04-22 20:12:00,001 INFO gateway.run: started\n")
        errors = scan_log_for_prefill_errors([log])
        assert len(errors) == 0

    def test_multiple_files_scanned(self, tmp_path):
        log1 = tmp_path / "agent.log"
        log2 = tmp_path / "errors.log"
        log1.write_text(
            "2026-04-22 20:11:38,456 WARNING gateway.run: "
            "Failed to load prefill messages from /home/agent/clawd/SOUL.md: "
            "Expecting value: line 1 column 1 (char 0)\n"
        )
        log2.write_text(
            "2026-04-22 20:11:38,456 WARNING gateway.run: "
            "Failed to load prefill messages from /home/agent/clawd/HEARTBEAT.md: "
            "Expecting value: line 1 column 1 (char 0)\n"
        )
        errors = scan_log_for_prefill_errors([log1, log2])
        assert len(errors) == 2


class TestBuildReport:
    def test_report_flags_mismatch_risk(self, tmp_path):
        soul = tmp_path / "SOUL.md"
        soul.write_text("# SOUL.md\n\nDoctrine.\n")
        heartbeat = tmp_path / "HEARTBEAT.md"
        heartbeat.write_text("# HEARTBEAT.md\n\nBeat.\n")
        log = tmp_path / "agent.log"
        log.write_text(
            "2026-04-22 20:11:38,456 WARNING gateway.run: "
            "Failed to load prefill messages from /home/agent/clawd/SOUL.md: "
            "Expecting value: line 1 column 1 (char 0)\n"
        )
        report = build_report(
            rail_paths={"SOUL": soul, "HEARTBEAT": heartbeat},
            log_paths=[log],
            dry_run=True,
        )
        assert report["overall_status"] == "fail"
        assert report["mismatch_detected"] is True
        assert any(
            r["rail"] == "SOUL" and r["status"] == "ok"
            for r in report["rails"]
        )

    def test_dry_run_no_live_errors(self, tmp_path):
        soul = tmp_path / "SOUL.md"
        soul.write_text("# SOUL.md\n\nDoctrine.\n")
        report = build_report(
            rail_paths={"SOUL": soul},
            log_paths=[],
            dry_run=True,
        )
        # In dry-run with no logs, readable markdown rails are OK.
        assert any(r["status"] == "ok" for r in report["rails"])
        assert report["overall_status"] == "pass"
        assert report["log_errors_found"] == 0
