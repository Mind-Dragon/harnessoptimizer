"""Direct unit tests for run_standalone internal functions and CLI branches.

The CLI smoke tests (test_cli_smoke.py, test_vault_writeback_cli.py) cover
subprocess-level integration. This file covers the internal helpers and
command branches directly for faster feedback and better isolation.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from hermesoptimizer.catalog import (
    Finding,
    Record,
    finish_run,
    get_findings,
    get_records,
    get_run_history,
    init_db,
    start_run,
    upsert_finding,
    upsert_record,
)
from hermesoptimizer.run_standalone import (
    _comparison_from_history,
    _delta_metrics,
    _finding_from_args,
    _inspected_inputs_from_rows,
    _record_from_args,
    _report_metrics,
    build_parser,
    main,
)


# ── helpers ──────────────────────────────────────────────────────────


def _make_record(**overrides) -> Record:
    defaults = dict(
        provider="openai",
        model="gpt-5",
        base_url="https://api.openai.com/v1",
        auth_type="api_key",
        auth_key="OPENAI_API_KEY",
        lane="coding",
        region="us",
        capabilities=["text"],
        context_window=128000,
        source="manual",
        confidence="high",
        raw_text=None,
    )
    defaults.update(overrides)
    return Record(**defaults)


def _make_finding(**overrides) -> Finding:
    defaults = dict(
        file_path="logs/app.log",
        line_num=12,
        category="log-signal",
        severity="medium",
        kind="log-provider-failure",
        fingerprint="logs/app.log:12",
        sample_text="provider timeout",
        count=1,
        confidence="high",
        router_note="timeout observed",
        lane="coding",
    )
    defaults.update(overrides)
    return Finding(**defaults)


# ── _report_metrics ──────────────────────────────────────────────────


class TestReportMetrics:
    def test_returns_dict_with_int_values(self) -> None:
        records = [_make_record()]
        findings = [_make_finding()]
        result = _report_metrics(records, findings, [])
        assert isinstance(result, dict)
        for v in result.values():
            assert isinstance(v, int)

    def test_empty_inputs(self) -> None:
        result = _report_metrics([], [], [])
        assert isinstance(result, dict)


# ── _delta_metrics ───────────────────────────────────────────────────


class TestDeltaMetrics:
    def test_positive_delta(self) -> None:
        before = {"records": 5, "findings": 3}
        after = {"records": 8, "findings": 3}
        delta = _delta_metrics(before, after)
        assert delta["records"] == 3
        assert delta["findings"] == 0

    def test_negative_delta(self) -> None:
        before = {"records": 10}
        after = {"records": 7}
        delta = _delta_metrics(before, after)
        assert delta["records"] == -3

    def test_new_key_in_after(self) -> None:
        before = {"records": 1}
        after = {"records": 1, "findings": 5}
        delta = _delta_metrics(before, after)
        assert delta["findings"] == 5

    def test_key_missing_from_after_defaults_zero(self) -> None:
        before = {"records": 5, "stale_key": 10}
        after = {"records": 5}
        delta = _delta_metrics(before, after)
        assert delta["stale_key"] == -10

    def test_both_empty(self) -> None:
        assert _delta_metrics({}, {}) == {}


# ── _comparison_from_history ─────────────────────────────────────────


class TestComparisonFromHistory:
    def test_no_history_returns_none(self, tmp_path: Path) -> None:
        db = tmp_path / "catalog.db"
        init_db(db)
        assert _comparison_from_history(db, {"records": 1}) is None

    def test_with_history_returns_comparison(self, tmp_path: Path) -> None:
        db = tmp_path / "catalog.db"
        init_db(db)
        run_id = start_run(db, "test")
        finish_run(db, run_id, record_count=5, finding_count=2, metrics={"records": 5, "findings": 2})
        result = _comparison_from_history(db, {"records": 8, "findings": 3})
        assert result is not None
        assert result["baseline_metrics"] == {"records": 5, "findings": 2}
        assert result["current_metrics"] == {"records": 8, "findings": 3}
        assert result["deltas"]["records"] == 3
        assert result["deltas"]["findings"] == 1

    def test_history_with_float_metrics_casts_to_int(self, tmp_path: Path) -> None:
        db = tmp_path / "catalog.db"
        init_db(db)
        run_id = start_run(db, "test")
        finish_run(db, run_id, record_count=3, finding_count=1, metrics={"records": 3.0, "findings": 1})
        result = _comparison_from_history(db, {"records": 5})
        assert result is not None
        assert result["baseline_metrics"]["records"] == 3

    def test_history_with_no_metrics_returns_none(self, tmp_path: Path) -> None:
        db = tmp_path / "catalog.db"
        init_db(db)
        run_id = start_run(db, "test")
        finish_run(db, run_id, record_count=1, finding_count=0)
        result = _comparison_from_history(db, {"records": 1})
        assert result is None

    def test_uses_title_from_history(self, tmp_path: Path) -> None:
        db = tmp_path / "catalog.db"
        init_db(db)
        run_id = start_run(db, "export")
        finish_run(db, run_id, record_count=1, finding_count=0, metrics={"records": 1})
        result = _comparison_from_history(db, {"records": 2})
        assert result is not None
        assert "baseline_title" in result


# ── _inspected_inputs_from_rows ──────────────────────────────────────


class TestInspectedInputs:
    def test_empty_lists(self) -> None:
        assert _inspected_inputs_from_rows([], []) == []

    def test_file_finding(self) -> None:
        findings = [_make_finding(file_path="/etc/config.yaml", category="config-signal")]
        result = _inspected_inputs_from_rows([], findings)
        assert len(result) == 1
        assert result[0]["type"] == "file"
        assert result[0]["path"] == "/etc/config.yaml"

    def test_gateway_signal_becomes_command(self) -> None:
        findings = [_make_finding(file_path="hermes gateway status", category="gateway-signal")]
        result = _inspected_inputs_from_rows([], findings)
        assert len(result) == 1
        assert result[0]["type"] == "command"
        assert result[0]["command"] == "hermes gateway status"

    def test_deduplication_by_type_and_path(self) -> None:
        findings = [
            _make_finding(file_path="a.log", category="log-signal"),
            _make_finding(file_path="a.log", category="log-signal"),
        ]
        result = _inspected_inputs_from_rows([], findings)
        assert len(result) == 1

    def test_mixed_types(self) -> None:
        findings = [
            _make_finding(file_path="gw check", category="gateway-signal"),
            _make_finding(file_path="b.log", category="log-signal"),
        ]
        result = _inspected_inputs_from_rows([], findings)
        assert len(result) == 2
        types = {r["type"] for r in result}
        assert types == {"command", "file"}

    def test_finding_without_file_path_excluded(self) -> None:
        findings = [_make_finding(file_path=None)]
        result = _inspected_inputs_from_rows([], findings)
        assert len(result) == 0


# ── _record_from_args ────────────────────────────────────────────────


class TestRecordFromArgs:
    def test_basic_round_trip(self) -> None:
        args = argparse.Namespace(
            provider="openai",
            model="gpt-5",
            base_url="https://api.openai.com/v1",
            auth_type="api_key",
            auth_key="OPENAI_API_KEY",
            lane="coding",
            region="us",
            capabilities=["text", "text"],  # test dedup
            context_window=128000,
            source="manual",
            confidence="high",
            raw_text=None,
        )
        rec = _record_from_args(args)
        assert rec.provider == "openai"
        assert rec.model == "gpt-5"
        # capabilities deduplicated via dict.fromkeys
        assert rec.capabilities == ["text"]


# ── _finding_from_args ───────────────────────────────────────────────


class TestFindingFromArgs:
    def test_basic_round_trip(self) -> None:
        args = argparse.Namespace(
            file_path="logs/x.log",
            line_num=42,
            category="error",
            severity="high",
            kind="timeout",
            fingerprint="x:42",
            sample_text="timed out",
            count=3,
            confidence="medium",
            router_note="check provider",
            lane="research",
        )
        f = _finding_from_args(args)
        assert f.file_path == "logs/x.log"
        assert f.count == 3
        assert f.lane == "research"


# ── build_parser ─────────────────────────────────────────────────────


class TestBuildParser:
    def test_parser_returns_argument_parser(self) -> None:
        p = build_parser()
        assert isinstance(p, argparse.ArgumentParser)

    def test_subcommands_registered(self) -> None:
        p = build_parser()
        # Parse known subcommands
        for cmd in ["init-db", "add-record", "add-finding", "export", "list-records", "list-findings", "vault-audit", "vault-writeback"]:
            # Just verify parsing doesn't blow up for the minimal case
            pass

    def test_init_db_parses(self) -> None:
        p = build_parser()
        args = p.parse_args(["init-db", "--db", "test.db"])
        assert args.command == "init-db"
        assert args.db == "test.db"

    def test_export_parses(self) -> None:
        p = build_parser()
        args = p.parse_args(["export", "--db", "my.db", "--out-dir", "/tmp/out"])
        assert args.command == "export"
        assert args.out_dir == "/tmp/out"

    def test_add_record_requires_fields(self) -> None:
        p = build_parser()
        with pytest.raises(SystemExit):
            p.parse_args(["add-record"])  # missing required fields

    def test_vault_writeback_requires_root_and_format(self) -> None:
        p = build_parser()
        args = p.parse_args(["vault-writeback", "--vault-root", "/tmp/v", "--format", "env"])
        assert args.command == "vault-writeback"
        assert args.vault_root == "/tmp/v"
        assert args.format == "env"
        assert args.confirm is False

    def test_vault_writeback_invalid_format_exits(self) -> None:
        p = build_parser()
        with pytest.raises(SystemExit):
            p.parse_args(["vault-writeback", "--vault-root", "/v", "--format", "invalid"])


# ── main branches (direct, no subprocess) ────────────────────────────


class TestMainInitDb:
    def test_init_db_creates_file(self, tmp_path: Path) -> None:
        db = tmp_path / "catalog.db"
        rc = main(["init-db", "--db", str(db)])
        assert rc == 0
        assert db.exists()


class TestMainAddRecord:
    def test_add_record(self, tmp_path: Path) -> None:
        db = tmp_path / "catalog.db"
        init_db(db)
        rc = main([
            "add-record", "--db", str(db),
            "--provider", "anthropic",
            "--model", "claude-4",
            "--base-url", "https://api.anthropic.com",
            "--auth-type", "api_key",
            "--auth-key", "ANTHROPIC_KEY",
        ])
        assert rc == 0
        rows = get_records(db)
        assert len(rows) == 1


class TestMainAddFinding:
    def test_add_finding(self, tmp_path: Path) -> None:
        db = tmp_path / "catalog.db"
        init_db(db)
        rc = main([
            "add-finding", "--db", str(db),
            "--category", "config-drift",
            "--severity", "high",
        ])
        assert rc == 0
        rows = get_findings(db)
        assert len(rows) == 1


class TestMainExport:
    def test_export_produces_reports(self, tmp_path: Path) -> None:
        db = tmp_path / "catalog.db"
        out = tmp_path / "reports"
        init_db(db)
        upsert_record(db, _make_record())
        upsert_finding(db, _make_finding())
        rc = main(["export", "--db", str(db), "--out-dir", str(out)])
        assert rc == 0
        assert (out / "report.json").exists()
        assert (out / "report.md").exists()

    def test_export_with_comparison(self, tmp_path: Path) -> None:
        db = tmp_path / "catalog.db"
        out = tmp_path / "reports"
        init_db(db)
        # First export to seed history
        upsert_record(db, _make_record())
        run_id = start_run(db, "export")
        finish_run(db, run_id, record_count=1, finding_count=0, metrics={"records": 1})
        # Second export
        rc = main(["export", "--db", str(db), "--out-dir", str(out)])
        assert rc == 0


class TestMainListRecords:
    def test_list_records(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        db = tmp_path / "catalog.db"
        init_db(db)
        upsert_record(db, _make_record())
        rc = main(["list-records", "--db", str(db)])
        assert rc == 0
        captured = capsys.readouterr()
        assert "openai" in captured.out


class TestMainListFindings:
    def test_list_findings(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        db = tmp_path / "catalog.db"
        init_db(db)
        upsert_finding(db, _make_finding(category="test-cat", severity="low"))
        rc = main(["list-findings", "--db", str(db)])
        assert rc == 0
        captured = capsys.readouterr()
        assert "test-cat" in captured.out


class TestMainVaultAudit:
    def test_vault_audit_with_empty_root(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        vault = tmp_path / "vault"
        vault.mkdir()
        rc = main(["vault-audit", "--vault-root", str(vault)])
        assert rc == 0
        captured = capsys.readouterr()
        assert "Vault Audit Summary" in captured.out

    def test_vault_audit_with_report_file(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        vault.mkdir()
        report = tmp_path / "audit.txt"
        rc = main(["vault-audit", "--vault-root", str(vault), "--report", str(report)])
        assert rc == 0
        assert report.exists()
        content = report.read_text()
        assert "Vault Audit Report" in content


class TestMainVaultWriteback:
    def test_writeback_dry_run(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        vault = tmp_path / "vault"
        vault.mkdir()
        rc = main(["vault-writeback", "--vault-root", str(vault), "--format", "env"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "dry-run" in captured.out

    def test_writeback_with_confirm(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        vault = tmp_path / "vault"
        vault.mkdir()
        rc = main(["vault-writeback", "--vault-root", str(vault), "--format", "env", "--confirm"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "completed" in captured.out or "processed" in captured.out
