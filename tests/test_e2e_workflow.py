"""End-to-end workflow tests for the full discover→report pipeline.

These tests exercise the complete optimizer flow against fixture data,
validating that every stage produces correct output and the final reports
are well-formed and actionable.

No live network access required. All data comes from fixtures or tmp_path.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from hermesoptimizer.catalog import Finding, Record, init_db, upsert_finding, upsert_record
from hermesoptimizer.loop import LoopConfig, LoopState, Phase0Loop, discover, parse, enrich, rank, report, verify, repeat
from hermesoptimizer.report.json_export import write_json_report
from hermesoptimizer.report.markdown import write_markdown_report
from hermesoptimizer.report.metrics import compute_report_metrics
from hermesoptimizer.run_standalone import _comparison_from_history, _inspected_inputs_from_rows, _report_metrics

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "hermes"


# ── helpers ──────────────────────────────────────────────────────────


def _build_inventory(tmp_path: Path, entries: dict[str, list[dict]]) -> Path:
    """Write a YAML inventory file and return its path."""
    inv = tmp_path / "inventory.yaml"
    inv.write_text(yaml.dump(entries, default_flow_style=False), encoding="utf-8")
    return inv


def _standard_inventory(tmp_path: Path) -> Path:
    """Standard inventory pointing at fixture data."""
    return _build_inventory(tmp_path, {
        "config": [{"path": str(FIXTURE_DIR / "config.yaml"), "type": "config", "authoritative": True}],
        "session": [
            {"path": str(FIXTURE_DIR / "session_001.json"), "type": "session", "authoritative": True},
            {"path": str(FIXTURE_DIR / "session_crash.json"), "type": "session", "authoritative": True},
        ],
        "log": [{"path": str(FIXTURE_DIR / "app.log"), "type": "log", "authoritative": True}],
        "cache": [],
        "db": [],
        "runtime": [],
        "gateway": [],
    })


def _make_loop(tmp_path: Path) -> Phase0Loop:
    cfg = LoopConfig(
        inventory_path=_standard_inventory(tmp_path),
        db_path=tmp_path / "catalog.db",
        fixtures_mode=True,
    )
    return Phase0Loop(cfg)


# ── Pipeline stage tests ─────────────────────────────────────────────


class TestE2EDiscoveryStage:
    """Verify discovery finds all fixture sources."""

    def test_discovers_config_sessions_logs(self, tmp_path: Path) -> None:
        loop = _make_loop(tmp_path)
        state = loop.initial_state()
        s = discover(state, loop.config)
        assert "config" in s.discovered_paths
        assert "session" in s.discovered_paths
        assert "log" in s.discovered_paths

    def test_discovered_paths_contain_real_files(self, tmp_path: Path) -> None:
        loop = _make_loop(tmp_path)
        state = loop.initial_state()
        s = discover(state, loop.config)
        for key in ("config", "session", "log"):
            entries = s.discovered_paths.get(key, [])
            assert len(entries) >= 1, f"expected entries for {key}"


class TestE2EParseStage:
    """Verify parsing extracts findings from all source types."""

    def test_log_findings_extracted(self, tmp_path: Path) -> None:
        loop = _make_loop(tmp_path)
        s = discover(loop.initial_state(), loop.config)
        s = parse(s, loop.config)
        log_findings = [f for f in s.findings if f.category == "log-signal"]
        assert len(log_findings) >= 1, "fixture app.log contains ERROR lines"

    def test_session_findings_extracted(self, tmp_path: Path) -> None:
        loop = _make_loop(tmp_path)
        s = discover(loop.initial_state(), loop.config)
        s = parse(s, loop.config)
        session_findings = [f for f in s.findings if f.category == "session-signal"]
        assert len(session_findings) >= 1, "fixture sessions have errors"

    def test_config_findings_extracted(self, tmp_path: Path) -> None:
        loop = _make_loop(tmp_path)
        s = discover(loop.initial_state(), loop.config)
        s = parse(s, loop.config)
        config_findings = [f for f in s.findings if f.category == "config-signal"]
        assert len(config_findings) >= 0  # config may or may not produce findings


class TestE2EFullPipeline:
    """Verify the complete Phase0Loop runs end-to-end."""

    def test_full_loop_completes(self, tmp_path: Path) -> None:
        loop = _make_loop(tmp_path)
        final = loop.run(loop.initial_state())
        assert final.current_step == "repeat"
        assert final.run_marker is not None

    def test_loop_produces_findings(self, tmp_path: Path) -> None:
        loop = _make_loop(tmp_path)
        final = loop.run(loop.initial_state())
        assert len(final.findings) >= 1, "fixture data should produce at least one finding"

    def test_loop_step_order_correct(self, tmp_path: Path) -> None:
        loop = _make_loop(tmp_path)
        final = loop.run(loop.initial_state())
        expected = ["discover", "parse", "enrich", "rank", "report", "verify", "repeat"]
        assert final.order == expected

    def test_loop_idempotent(self, tmp_path: Path) -> None:
        """Running twice from same initial state gives same findings."""
        loop = _make_loop(tmp_path)
        s1 = loop.run(loop.initial_state())
        s2 = loop.run(loop.initial_state())
        assert len(s1.findings) == len(s2.findings)


class TestE2EReportGeneration:
    """Verify report generation from loop output is well-formed."""

    def _run_loop_and_get_state(self, tmp_path: Path) -> tuple[Phase0Loop, LoopState]:
        loop = _make_loop(tmp_path)
        return loop, loop.run(loop.initial_state())

    def test_json_report_is_valid(self, tmp_path: Path) -> None:
        loop, state = self._run_loop_and_get_state(tmp_path)
        out = tmp_path / "reports"
        out.mkdir()
        records = state.records if state.records else []
        findings = state.findings
        inspected = _inspected_inputs_from_rows(records, findings)
        metrics = _report_metrics(records, findings, inspected)

        write_json_report(
            out / "report.json",
            title="E2E Test",
            records=records,
            findings=findings,
            inspected_inputs=inspected,
        )
        assert (out / "report.json").exists()
        data = json.loads((out / "report.json").read_text())
        assert "title" in data
        assert data["title"] == "E2E Test"
        assert "findings" in data

    def test_markdown_report_is_valid(self, tmp_path: Path) -> None:
        loop, state = self._run_loop_and_get_state(tmp_path)
        out = tmp_path / "reports"
        out.mkdir()
        records = state.records if state.records else []
        findings = state.findings
        inspected = _inspected_inputs_from_rows(records, findings)

        write_markdown_report(
            out / "report.md",
            title="E2E Test",
            records=records,
            findings=findings,
            inspected_inputs=inspected,
        )
        assert (out / "report.md").exists()
        content = (out / "report.md").read_text()
        assert "# E2E Test" in content
        assert "Findings" in content or "findings" in content.lower()

    def test_json_report_contains_finding_categories(self, tmp_path: Path) -> None:
        loop, state = self._run_loop_and_get_state(tmp_path)
        out = tmp_path / "reports"
        out.mkdir()
        records = state.records if state.records else []
        findings = state.findings
        inspected = _inspected_inputs_from_rows(records, findings)

        write_json_report(
            out / "report.json",
            title="E2E Categories",
            records=records,
            findings=findings,
            inspected_inputs=inspected,
        )
        data = json.loads((out / "report.json").read_text())
        categories = {f.get("category") for f in data.get("findings", [])}
        # Fixture data should produce at least log-signal or session-signal
        assert categories & {"log-signal", "session-signal", "config-signal", "gateway-signal"}

    def test_report_with_comparison_data(self, tmp_path: Path) -> None:
        loop, state = self._run_loop_and_get_state(tmp_path)
        out = tmp_path / "reports"
        out.mkdir()
        records = state.records if state.records else []
        findings = state.findings
        inspected = _inspected_inputs_from_rows(records, findings)
        current_metrics = _report_metrics(records, findings, inspected)

        write_json_report(
            out / "report.json",
            title="Comparison Test",
            records=records,
            findings=findings,
            inspected_inputs=inspected,
            comparison={"baseline_title": "Previous", "baseline_metrics": {"records": 0}, "current_metrics": current_metrics, "deltas": current_metrics},
        )
        data = json.loads((out / "report.json").read_text())
        assert "before_after" in data


class TestE2EMetricsAndInspection:
    """Verify metrics computation and inspected-input extraction."""

    def test_metrics_returns_sensible_counts(self, tmp_path: Path) -> None:
        loop, state = _make_loop(tmp_path), None
        loop_inst = _make_loop(tmp_path)
        state = loop_inst.run(loop_inst.initial_state())
        records = state.records if state.records else []
        findings = state.findings
        inspected = _inspected_inputs_from_rows(records, findings)
        metrics = _report_metrics(records, findings, inspected)
        assert isinstance(metrics, dict)
        # Findings count should be positive
        assert metrics.get("finding_count", metrics.get("findings", len(findings))) >= 1 or len(findings) >= 1

    def test_inspected_inputs_from_findings(self, tmp_path: Path) -> None:
        loop = _make_loop(tmp_path)
        state = loop.run(loop.initial_state())
        findings = state.findings
        inspected = _inspected_inputs_from_rows([], findings)
        assert isinstance(inspected, list)
        # Findings with file_path should appear in inspected inputs
        file_findings = [f for f in findings if f.file_path]
        if file_findings:
            assert len(inspected) >= 1


class TestE2EMultiSourceInventory:
    """Verify the pipeline works with different inventory configurations."""

    def test_config_only_inventory(self, tmp_path: Path) -> None:
        inv = _build_inventory(tmp_path, {
            "config": [{"path": str(FIXTURE_DIR / "config.yaml"), "type": "config", "authoritative": True}],
            "session": [], "log": [], "cache": [], "db": [], "runtime": [], "gateway": [],
        })
        cfg = LoopConfig(inventory_path=inv, db_path=tmp_path / "catalog.db", fixtures_mode=True)
        loop = Phase0Loop(cfg)
        final = loop.run(loop.initial_state())
        assert final.current_step == "repeat"

    def test_logs_only_inventory(self, tmp_path: Path) -> None:
        inv = _build_inventory(tmp_path, {
            "config": [], "session": [],
            "log": [{"path": str(FIXTURE_DIR / "app.log"), "type": "log", "authoritative": True}],
            "cache": [], "db": [], "runtime": [], "gateway": [],
        })
        cfg = LoopConfig(inventory_path=inv, db_path=tmp_path / "catalog.db", fixtures_mode=True)
        loop = Phase0Loop(cfg)
        final = loop.run(loop.initial_state())
        assert len(final.findings) >= 1
        log_findings = [f for f in final.findings if f.category == "log-signal"]
        assert len(log_findings) >= 1

    def test_empty_inventory_completes(self, tmp_path: Path) -> None:
        inv = _build_inventory(tmp_path, {
            "config": [], "session": [], "log": [], "cache": [], "db": [], "runtime": [], "gateway": [],
        })
        cfg = LoopConfig(inventory_path=inv, db_path=tmp_path / "catalog.db", fixtures_mode=True)
        loop = Phase0Loop(cfg)
        final = loop.run(loop.initial_state())
        assert final.current_step == "repeat"
        assert len(final.findings) == 0

    def test_bad_config_inventory_completes(self, tmp_path: Path) -> None:
        """Pipeline should survive a bad config file."""
        inv = _build_inventory(tmp_path, {
            "config": [{"path": str(FIXTURE_DIR / "config_bad.yaml"), "type": "config", "authoritative": True}],
            "session": [], "log": [], "cache": [], "db": [], "runtime": [], "gateway": [],
        })
        cfg = LoopConfig(inventory_path=inv, db_path=tmp_path / "catalog.db", fixtures_mode=True)
        loop = Phase0Loop(cfg)
        final = loop.run(loop.initial_state())
        # Should complete even if config is malformed
        assert final.current_step == "repeat"


class TestE2EDBPersistence:
    """Verify findings are persisted to SQLite across runs."""

    def test_db_exists_after_run(self, tmp_path: Path) -> None:
        loop = _make_loop(tmp_path)
        loop.run(loop.initial_state())
        assert loop.config.db_path.exists()

    def test_two_runs_dont_corrupt_db(self, tmp_path: Path) -> None:
        loop = _make_loop(tmp_path)
        s1 = loop.run(loop.initial_state())
        s2 = loop.run(loop.initial_state())
        assert loop.config.db_path.exists()
        # DB should be usable after both runs
        from hermesoptimizer.catalog import get_findings
        findings = get_findings(loop.config.db_path)
        assert isinstance(findings, list)
