"""
Phase 1 diagnostics tests for Hermes.

Tests the Phase 1 scanners and unified diagnosis model:
- hermes_config: full YAML field validation, endpoint checks, stale providers
- hermes_sessions: structured JSON extraction for errors/retries/crashes/timeouts
- hermes_logs: regex patterns for auth/provider/runtime failures
- hermes_diagnosis: Diagnosis wrapper, severity/confidence enrichment
- hermes_runtime: gateway health scanning, runtime path checks
- loop.Phase1Loop: full loop with diagnose step
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hermesoptimizer.catalog import Finding
from hermesoptimizer.sources.hermes_config import scan_config, scan_config_paths
from hermesoptimizer.sources.hermes_sessions import scan_session, scan_session_files
from hermesoptimizer.sources.hermes_logs import scan_log, scan_log_paths
from hermesoptimizer.sources.hermes_diagnosis import (
    Diagnosis,
    diagnose,
    diagnose_all,
    DiagnosisKind,
    Severity,
    Confidence,
)
from hermesoptimizer.sources.hermes_runtime import scan_gateway_health, scan_runtime_paths
from hermesoptimizer.loop import (
    LoopConfig,
    LoopState,
    Phase0Loop,
    Phase1Loop,
    discover,
    parse,
    diagnose as loop_diagnose,
    enrich,
    rank,
    report,
    verify,
    repeat,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "hermes"


@pytest.fixture
def good_config() -> Path:
    return FIXTURE_DIR / "config.yaml"


@pytest.fixture
def bad_config() -> Path:
    return FIXTURE_DIR / "config_bad.yaml"


@pytest.fixture
def session_error() -> Path:
    return FIXTURE_DIR / "session_001.json"


@pytest.fixture
def session_crash() -> Path:
    return FIXTURE_DIR / "session_crash.json"


@pytest.fixture
def session_ok() -> Path:
    return FIXTURE_DIR / "session_ok.json"


@pytest.fixture
def app_log() -> Path:
    return FIXTURE_DIR / "app.log"


@pytest.fixture
def phase0_loop(tmp_path: Path) -> Phase0Loop:
    db = tmp_path / "catalog.db"
    inv_file = tmp_path / "inventory.yaml"
    inv_file.write_text(
        "config:\n"
        "  - path: tests/fixtures/hermes/config.yaml\n"
        "    type: config\n"
        "    authoritative: true\n"
        "session:\n"
        "  - path: tests/fixtures/hermes/session_001.json\n"
        "    type: session\n"
        "    authoritative: true\n"
        "  - path: tests/fixtures/hermes/session_002.json\n"
        "    type: session\n"
        "    authoritative: true\n"
        "log:\n"
        "  - path: tests/fixtures/hermes/app.log\n"
        "    type: log\n"
        "    authoritative: true\n"
        "cache: []\n"
        "db: []\n"
        "runtime: []\n"
        "gateway: []\n",
        encoding="utf-8",
    )
    cfg = LoopConfig(inventory_path=inv_file, db_path=db, fixtures_mode=True)
    return Phase0Loop(cfg)


@pytest.fixture
def phase1_loop(tmp_path: Path) -> Phase1Loop:
    db = tmp_path / "catalog.db"
    inv_file = tmp_path / "inventory.yaml"
    inv_file.write_text(
        "config:\n"
        "  - path: tests/fixtures/hermes/config.yaml\n"
        "    type: config\n"
        "    authoritative: true\n"
        "session:\n"
        "  - path: tests/fixtures/hermes/session_001.json\n"
        "    type: session\n"
        "    authoritative: true\n"
        "  - path: tests/fixtures/hermes/session_crash.json\n"
        "    type: session\n"
        "    authoritative: true\n"
        "log:\n"
        "  - path: tests/fixtures/hermes/app.log\n"
        "    type: log\n"
        "    authoritative: true\n"
        "cache: []\n"
        "db: []\n"
        "runtime: []\n"
        "gateway:\n"
        "  - command: echo 'gateway running'\n"
        "    type: gateway\n"
        "    authoritative: true\n",
        encoding="utf-8",
    )
    cfg = LoopConfig(inventory_path=inv_file, db_path=db, fixtures_mode=True)
    return Phase1Loop(cfg)


# ---------------------------------------------------------------------------
# hermes_config tests
# ---------------------------------------------------------------------------

class TestScanConfig:
    def test_good_config_finds_no_errors(self, good_config: Path) -> None:
        findings = scan_config(good_config)
        # Good config should have no missing-field or bad-endpoint findings
        missing = [f for f in findings if f.kind == "config-missing-field"]
        bad_ep = [f for f in findings if f.kind == "config-bad-endpoint"]
        assert missing == []
        assert bad_ep == []

    def test_bad_config_finds_missing_fields(self, bad_config: Path) -> None:
        findings = scan_config(bad_config)
        missing = [f for f in findings if f.kind == "config-missing-field"]
        assert len(missing) >= 1
        # bad_provider should be missing base_url, auth_key_env, model
        assert any("bad_provider" in f.sample_text for f in missing)
        assert any("base_url" in f.sample_text or "auth_key_env" in f.sample_text or "model" in f.sample_text for f in missing)

    def test_bad_config_finds_bad_endpoints(self, bad_config: Path) -> None:
        findings = scan_config(bad_config)
        bad_eps = [f for f in findings if f.kind == "config-bad-endpoint"]
        assert len(bad_eps) >= 1
        # insecure_provider uses http, not https
        assert any("http://" in f.sample_text for f in bad_eps)

    def test_bad_config_finds_stale_provider(self, bad_config: Path) -> None:
        findings = scan_config(bad_config)
        stale = [f for f in findings if f.kind == "config-stale-provider"]
        assert len(stale) >= 1
        assert any("stale_provider" in f.sample_text or "old-model" in f.sample_text for f in stale)

    def test_scan_config_paths_delegates_to_scan_config(self, bad_config: Path) -> None:
        findings = scan_config_paths([bad_config])
        assert len(findings) >= 1


# ---------------------------------------------------------------------------
# hermes_sessions tests
# ---------------------------------------------------------------------------

class TestScanSession:
    def test_error_session_finds_error(self, session_error: Path) -> None:
        findings = scan_session(session_error)
        assert len(findings) >= 1
        assert any(f.kind in {"session-error", "session-timeout"} for f in findings)

    def test_error_session_finds_retries(self, session_error: Path) -> None:
        findings = scan_session(session_error)
        retries = [f for f in findings if f.kind == "session-retry"]
        assert len(retries) >= 1
        # session_001 has retries=3
        assert any(f.count == 3 for f in retries)

    def test_crash_session_finds_crash(self, session_crash: Path) -> None:
        findings = scan_session(session_crash)
        crashes = [f for f in findings if f.kind == "session-crash"]
        assert len(crashes) >= 1
        assert any("crash" in f.sample_text.lower() for f in crashes)

    def test_ok_session_finds_no_errors(self, session_ok: Path) -> None:
        findings = scan_session(session_ok)
        errors = [f for f in findings if f.kind in {"session-error", "session-timeout", "session-crash"}]
        assert errors == []

    def test_scan_session_files_delegates(self, session_error: Path) -> None:
        findings = scan_session_files([session_error])
        assert len(findings) >= 1


# ---------------------------------------------------------------------------
# hermes_logs tests
# ---------------------------------------------------------------------------

class TestScanLog:
    def test_app_log_finds_auth_failures(self, app_log: Path) -> None:
        findings = scan_log(app_log)
        auth = [f for f in findings if f.kind == "log-auth-failure"]
        assert len(auth) >= 1
        assert any("401" in f.sample_text or "auth" in f.sample_text.lower() for f in auth)

    def test_app_log_finds_provider_failures(self, app_log: Path) -> None:
        findings = scan_log(app_log)
        provider = [f for f in findings if f.kind == "log-provider-failure"]
        assert len(provider) >= 1
        assert any("timeout" in f.sample_text.lower() or "retry" in f.sample_text.lower() for f in provider)

    def test_app_log_finds_runtime_failures(self, app_log: Path) -> None:
        findings = scan_log(app_log)
        runtime = [f for f in findings if f.kind == "log-runtime-failure"]
        assert len(runtime) >= 1
        assert any("exception" in f.sample_text.lower() or "worker" in f.sample_text.lower() for f in runtime)

    def test_scan_log_paths_delegates(self, app_log: Path) -> None:
        findings = scan_log_paths([app_log])
        assert len(findings) >= 1

    def test_findings_have_correct_fields(self, app_log: Path) -> None:
        findings = scan_log(app_log)
        for f in findings:
            assert f.file_path is not None
            assert f.line_num is not None
            assert f.category == "log-signal"
            assert f.kind is not None
            assert f.severity in {s.value for s in Severity}
            assert f.confidence in {c.value for c in Confidence}
            assert f.router_note is not None


# ---------------------------------------------------------------------------
# hermes_diagnosis tests
# ---------------------------------------------------------------------------

class TestDiagnosis:
    def test_diagnose_enriches_finding(self) -> None:
        f = Finding(
            file_path="/test.yaml",
            line_num=1,
            category="config-signal",
            severity="medium",
            kind="config-missing-field",
            fingerprint="/test.yaml:1",
            sample_text="missing base_url",
            count=1,
            confidence="low",
            router_note="stub",
            lane=None,
        )
        diag = diagnose(f)
        assert isinstance(diag, Diagnosis)
        assert diag.root_cause is not None
        assert diag.kind == DiagnosisKind.CONFIG_MISSING_FIELD.value
        assert diag.finding.severity == "high"
        assert diag.finding.confidence == "high"
        assert "[phase1:" in diag.finding.router_note

    def test_diagnose_all(self) -> None:
        findings = [
            Finding(file_path="/a", line_num=1, category="c", severity="medium",
                   kind="config-missing-field", fingerprint="a", sample_text="x",
                   count=1, confidence="low", router_note="t", lane=None),
            Finding(file_path="/b", line_num=2, category="c", severity="low",
                   kind="session-retry", fingerprint="b", sample_text="y",
                   count=1, confidence="low", router_note="t", lane=None),
        ]
        diags = diagnose_all(findings)
        assert len(diags) == 2
        assert all(isinstance(d, Diagnosis) for d in diags)

    def test_diagnosis_roundtrip(self) -> None:
        f = Finding(
            file_path="/test.yaml",
            line_num=1,
            category="config-signal",
            severity="medium",
            kind="session-error",
            fingerprint="/test.yaml:1",
            sample_text="error",
            count=1,
            confidence="high",
            router_note="stub",
            lane=None,
        )
        diag = diagnose(f)
        f2 = diag.to_finding()
        assert f2.file_path == f.file_path
        assert f2.kind == f.kind


# ---------------------------------------------------------------------------
# hermes_runtime tests
# ---------------------------------------------------------------------------

class TestGatewayHealth:
    def test_echo_ok_command_produces_no_error_finding(self) -> None:
        findings = scan_gateway_health(["echo 'ok'"])
        critical = [f for f in findings if f.severity == "critical"]
        assert critical == []

    def test_exit_nonzero_produces_critical_finding(self) -> None:
        findings = scan_gateway_health(["exit 1"])
        assert len(findings) >= 1
        assert any(f.severity == "critical" and f.kind == "gateway-down" for f in findings)

    def test_gateway_finding_has_required_fields(self) -> None:
        findings = scan_gateway_health(["exit 1"])
        for f in findings:
            assert f.category == "gateway-signal"
            assert f.kind in {"gateway-down", "gateway-unhealthy"}
            assert f.router_note is not None


class TestRuntimePaths:
    def test_nonexistent_path_produces_no_findings(self, tmp_path: Path) -> None:
        findings = scan_runtime_paths([tmp_path / "nonexistent"])
        assert findings == []

    def test_empty_runtime_dir_produces_low_severity_finding(self, tmp_path: Path) -> None:
        rt_dir = tmp_path / "runtime"
        rt_dir.mkdir()
        findings = scan_runtime_paths([rt_dir])
        assert len(findings) >= 1
        assert any(f.severity == "low" for f in findings)


# ---------------------------------------------------------------------------
# Phase1Loop tests
# ---------------------------------------------------------------------------

class TestPhase1Loop:
    def test_phase1_loop_has_diagnose_step(self, phase1_loop: Phase1Loop) -> None:
        state = phase1_loop.initial_state()
        final_state = phase1_loop.run(state)
        assert "diagnose" in final_state.order

    def test_phase1_loop_order_is_correct(self, phase1_loop: Phase1Loop) -> None:
        state = phase1_loop.initial_state()
        final_state = phase1_loop.run(state)
        expected_order = ["discover", "parse", "diagnose", "enrich", "rank", "report", "verify", "repeat"]
        assert final_state.order == expected_order

    def test_phase1_loop_finds_crash_in_session(self, phase1_loop: Phase1Loop) -> None:
        state = phase1_loop.initial_state()
        final_state = phase1_loop.run(state)
        crash_findings = [f for f in final_state.findings if f.kind == "session-crash"]
        assert len(crash_findings) >= 1

    def test_phase1_loop_runs_end_to_end(self, phase1_loop: Phase1Loop) -> None:
        state = phase1_loop.initial_state()
        final_state = phase1_loop.run(state)
        assert final_state.current_step == "repeat"
        assert final_state.run_marker is not None
        assert phase1_loop.config.db_path.exists()


class TestDiagnoseStep:
    def test_diagnose_step_enriches_findings(self, phase1_loop: Phase1Loop) -> None:
        state = phase1_loop.initial_state()
        state = discover(state, phase1_loop.config)
        state = parse(state, phase1_loop.config)
        state = loop_diagnose(state, phase1_loop.config)
        assert "diagnose" in state.order
        # After diagnosis, findings should have enriched router_notes
        for f in state.findings:
            if f.kind:
                assert "[phase1:" in (f.router_note or "")


# ---------------------------------------------------------------------------
# Phase0Loop backward compatibility
# ---------------------------------------------------------------------------

class TestPhase0Loop:
    def test_phase0_loop_still_works(self, phase0_loop: Phase0Loop) -> None:
        state = phase0_loop.initial_state()
        final_state = phase0_loop.run(state)
        expected_order = ["discover", "parse", "enrich", "rank", "report", "verify", "repeat"]
        assert final_state.order == expected_order
        assert final_state.run_marker is not None

    def test_phase0_loop_no_diagnose_step(self, phase0_loop: Phase0Loop) -> None:
        state = phase0_loop.initial_state()
        final_state = phase0_loop.run(state)
        assert "diagnose" not in final_state.order

    def test_phase0_loop_runs_end_to_end(self, phase0_loop: Phase0Loop) -> None:
        state = phase0_loop.initial_state()
        final_state = phase0_loop.run(state)
        assert final_state.current_step == "repeat"
        assert final_state.run_marker is not None
        assert phase0_loop.config.db_path.exists()
