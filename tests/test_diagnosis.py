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
from hermesoptimizer.sources.hermes_auth import scan_auth, scan_auth_files
from hermesoptimizer.sources.hermes_diagnosis import (
    Diagnosis,
    diagnose,
    diagnose_all,
    DiagnosisKind,
    Severity,
    Confidence,
)
from hermesoptimizer.sources.hermes_runtime import scan_gateway_health, scan_runtime_paths, scan_cli_status
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
        "auth:\n"
        "  - path: tests/fixtures/hermes/auth.json\n"
        "    type: auth\n"
        "    authoritative: true\n"
        "cli:\n"
        "  - command: echo Hermes Agent Status not logged in\n"
        "    type: cli\n"
        "    authoritative: true\n"
        "cache: []\n"
        "db: []\n"
        "runtime: []\n"
        "gateway:\n"
        "  - command: curl -sf http://127.0.0.1:18789/health\n"
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

    def test_config_rejects_duplicate_provider_family(self, tmp_path: Path) -> None:
        config = tmp_path / "config.yaml"
        config.write_text(
            """version: \"1.0\"\nproviders:\n  kimi:\n    base_url: https://api.example.com/v1\n    auth_type: bearer\n    auth_key_env: KIMI_API_KEY\n    model: kimi-k2\n    lane: coding\n  kimi-for-coding:\n    base_url: https://api.example.com/v1\n    auth_type: bearer\n    auth_key_env: KIMI_API_KEY\n    model: kimi-k2\n    lane: coding\n""",
            encoding="utf-8",
        )
        findings = scan_config(config)
        duplicates = [f for f in findings if f.kind == "config-duplicate-provider"]
        assert len(duplicates) == 1
        assert "kimi-for-coding" in duplicates[0].sample_text

    def test_config_rejects_duplicate_canonical_aliases(self, tmp_path: Path) -> None:
        config = tmp_path / "config.yaml"
        config.write_text(
            """version: \"1.0\"\nproviders:\n  zai:\n    base_url: https://open.bigmodel.cn/api/paas/v4/\n    auth_type: bearer\n    auth_key_env: ZAI_API_KEY\n    model: glm-4.5\n    lane: coding\n  z.ai:\n    base_url: https://open.bigmodel.cn/api/paas/v4/\n    auth_type: bearer\n    auth_key_env: ZAI_API_KEY\n    model: glm-4.5\n    lane: coding\n""",
            encoding="utf-8",
        )
        findings = scan_config(config)
        duplicates = [f for f in findings if f.kind == "config-duplicate-provider"]
        assert len(duplicates) == 1
        assert "z.ai" in duplicates[0].sample_text

    def test_config_accepts_qwen36_plus_model(self, tmp_path: Path) -> None:
        config = tmp_path / "config.yaml"
        config.write_text(
            """version: \"1.0\"\nproviders:\n  bailian:\n    base_url: https://coding.dashscope.aliyuncs.com/v1\n    auth_type: bearer\n    auth_key_env: BAILIAN_API_KEY\n    model: qwen3.6-plus\n    lane: coding\n""",
            encoding="utf-8",
        )
        findings = scan_config(config)
        stale = [f for f in findings if f.kind == "config-stale-provider"]
        assert stale == []

    def test_config_accepts_alibaba_model_scopes(self, tmp_path: Path) -> None:
        accepted_models = [
            "qwen3-max",
            "qwen3-coder-plus",
            "qwen3-vl-plus",
            "qwen3-omni-plus",
            "qwen3-livetranslate-flash",
            "qwen3-asr-flash-realtime",
            "qwen-plus-latest",
            "qwen-flash-2025-07-28",
            "qwen-image-2.0-pro",
            "qwq-32b",
            "qvq-max",
            "wan2.6-t2i",
            "z-image-turbo",
            "cosyvoice-v3-plus",
            "fun-asr",
            "paraformer-v2",
            "tongyi-intent-detect-v3",
            "text-embedding-v4",
            "qwen-mt-plus",
        ]
        for index, model_name in enumerate(accepted_models):
            config = tmp_path / f"config-{index}.yaml"
            config.write_text(
                f"""version: \"1.0\"\nproviders:\n  bailian:\n    base_url: https://coding.dashscope.aliyuncs.com/v1\n    auth_type: bearer\n    auth_key_env: BAILIAN_API_KEY\n    model: {model_name}\n    lane: coding\n""",
                encoding="utf-8",
            )
            findings = scan_config(config)
            stale = [f for f in findings if f.kind == "config-stale-provider"]
            assert stale == [], model_name

    def test_config_flags_stale_model_base_url_and_api_key(self, tmp_path: Path) -> None:
        config = tmp_path / "config.yaml"
        config.write_text(
            """version: \"1.0\"\nmodel:\n  provider: kimi-coding\n  base_url: https://api.moonshot.ai/v1\n  api_key: sk-kimi-abc123\nproviders:\n  kimi-coding:\n    base_url: https://api.moonshot.ai/v1\n    auth_type: bearer\n    auth_key_env: KIMI_API_KEY\n    model: kimi-k2.5\n    lane: coding\n""",
            encoding="utf-8",
        )
        findings = scan_config(config)
        stale_fields = [f for f in findings if f.kind == "config-stale-model-field"]
        assert len(stale_fields) == 2
        assert any("model.base_url" in f.sample_text for f in stale_fields)
        assert any("model.api_key" in f.sample_text for f in stale_fields)
        assert any("stale value was cleared" in f.router_note for f in stale_fields)

    def test_config_flags_conflicting_env_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("KIMI_BASE_URL", "https://api.moonshot.ai")
        config = tmp_path / "config.yaml"
        config.write_text(
            """version: \"1.0\"\nproviders:\n  kimi-coding:\n    base_url: https://api.kimi.com/coding/v1\n    auth_type: bearer\n    auth_key_env: KIMI_API_KEY\n    model: kimi-k2.5\n    lane: coding\n""",
            encoding="utf-8",
        )
        findings = scan_config(config)
        conflicts = [f for f in findings if f.kind == "config-env-override-conflict"]
        assert len(conflicts) == 1
        assert "KIMI_BASE_URL" in conflicts[0].sample_text

    def test_config_flags_model_provider_alias_and_duplicate_fallbacks(self, tmp_path: Path) -> None:
        config = tmp_path / "config.yaml"
        config.write_text(
            """version: \"1.0\"\nmodel:\n  provider: openai-codex\n  base_url: https://chatgpt.com/backend-api/codex\nfallback_providers:\n  - provider: openai-codex\n    model: gpt-5.4-mini\n  - provider: kimi-coding\n    model: kimi-k2.5\nproviders: {}\n""",
            encoding="utf-8",
        )
        findings = scan_config(config)
        stale = [f for f in findings if f.kind == "config-stale-provider"]
        duplicates = [f for f in findings if f.kind == "config-duplicate-provider"]
        assert any("model:provider" in f.fingerprint for f in stale)
        assert any("fallback-alias" in f.fingerprint for f in stale)
        assert len(duplicates) == 1
        assert "fallback provider 'openai-codex'" in duplicates[0].sample_text

    def test_scan_auth_flags_reseeded_and_blank_sources(self, tmp_path: Path) -> None:
        auth = tmp_path / "auth.json"
        auth.write_text(
            """{\n  \"credential_pool\": {\n    \"openai-codex\": [\n      {\"source\": \"manual:device_code\", \"label\": \"openai-codex-oauth-1\", \"auth_type\": \"oauth\"}\n    ],\n    \"copilot\": [\n      {\"source\": \"gh_cli\", \"label\": \"gh auth token\", \"auth_type\": \"api_key\"}\n    ],\n    \"alibaba-coding-plan\": [\n      {\"source\": \"env:DASHSCOPE_API_KEY\", \"label\": \"DASHSCOPE_API_KEY\", \"auth_type\": \"api_key\"}\n    ],\n    \"alibaba\": [\n      {\"source\": \"config:alibaba\", \"label\": \"alibaba\", \"auth_type\": \"api_key\"}\n    ],\n    \"blank\": [\n      {\"source\": \"\", \"label\": \"blank\", \"auth_type\": \"api_key\"}\n    ]\n  }\n}\n""",
            encoding="utf-8",
        )
        findings = scan_auth(auth)
        kinds = [f.kind for f in findings]
        assert "auth-reseeded-credential" in kinds
        assert "auth-blank-source" in kinds
        assert "auth-stale-provider" in kinds
        assert "auth-duplicate-provider" in kinds

    def test_scan_auth_files_delegates_to_scan_auth(self, tmp_path: Path) -> None:
        auth = tmp_path / "auth.json"
        auth.write_text('{"credential_pool": {}}', encoding="utf-8")
        findings = scan_auth_files([auth])
        assert isinstance(findings, list)

    def test_scan_cli_status_distinguishes_ok_down_and_unhealthy(self) -> None:
        ok = scan_cli_status(["printf 'Hermes Agent Status\n  Provider: OpenAI Codex\n  Status: running\n'"])
        unhealthy = scan_cli_status(["printf 'Hermes Agent Status\n  Qwen OAuth ✗ not logged in\n'"])
        down = scan_cli_status(["bash -lc 'exit 2'"])
        assert ok == []
        assert any(f.kind == "cli-unhealthy" for f in unhealthy)
        assert any(f.kind == "cli-down" for f in down)

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
        findings = scan_gateway_health(["curl -sf http://127.0.0.1:18789/health"])
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

    def test_empty_runtime_dir_produces_no_findings(self, tmp_path: Path) -> None:
        rt_dir = tmp_path / "runtime"
        rt_dir.mkdir()
        findings = scan_runtime_paths([rt_dir])
        assert findings == []

    def test_stale_runtime_lock_file_produces_finding(self, tmp_path: Path) -> None:
        rt_dir = tmp_path / "runtime"
        rt_dir.mkdir()
        lock = rt_dir / "agent.lock"
        lock.write_text("123", encoding="utf-8")
        old_mtime = lock.stat().st_mtime - (8 * 24 * 3600)
        lock.touch()
        import os
        os.utime(lock, (old_mtime, old_mtime))
        findings = scan_runtime_paths([rt_dir])
        assert any(f.file_path == str(lock) for f in findings)


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

    def test_phase1_loop_captures_auth_and_cli_signals(self, phase1_loop: Phase1Loop) -> None:
        state = phase1_loop.initial_state()
        final_state = phase1_loop.run(state)
        assert any(f.category == "auth-signal" for f in final_state.findings)
        assert any(f.category == "cli-signal" for f in final_state.findings)

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
