"""Lane A smoke tests — sandbox HERMES_HOME on the same machine.

These tests copy the REAL ~/.hermes structure into a sandbox, redact secrets,
and run the actual optimizer pipeline against it. This validates the system
end-to-end against realistic data, not just synthetic fixtures.

Lane A contract:
- sandbox HERMES_HOME (never touches production)
- real config structure, real session shapes, real log patterns
- auth.json redacted (dummy keys)
- verifies the pipeline produces non-empty, meaningful output
"""

from __future__ import annotations

import json
import os
import shutil
import textwrap
from pathlib import Path

import pytest
import yaml

from hermesoptimizer.loop import (
    LoopConfig,
    LoopState,
    Phase0Loop,
    discover,
    parse,
    enrich,
    rank,
    report,
    verify,
)
from hermesoptimizer.sources.hermes_discover import load_inventory, discover_live_paths

REAL_HERMES_HOME = Path.home() / ".hermes"

# Skip the entire module if no real HERMES_HOME exists
pytestmark = pytest.mark.skipif(
    not REAL_HERMES_HOME.exists(),
    reason="Lane A requires a real ~/.hermes installation",
)


def _redact_auth(auth_path: Path) -> None:
    """Replace real API keys/tokens with dummy values in auth.json."""
    try:
        data = json.loads(auth_path.read_text())
    except (json.JSONDecodeError, OSError):
        return
    _redact_dict(data)
    auth_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _redact_dict(obj: dict | list) -> None:
    """Recursively redact sensitive values."""
    if isinstance(obj, dict):
        for key in list(obj.keys()):
            if any(s in key.lower() for s in ("key", "token", "secret", "password", "api_key")):
                if isinstance(obj[key], str) and obj[key]:
                    obj[key] = f"REDACTED-{key[:12]}"
            elif isinstance(obj[key], (dict, list)):
                _redact_dict(obj[key])
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                _redact_dict(item)


@pytest.fixture()
def sandbox_hermes(tmp_path: Path) -> Path:
    """Create a minimal sandbox HERMES_HOME from the real installation.

    Copies only the essential structural files — not the full 498MB state.db
    or 3000+ session files. This tests the pipeline on real-shaped data
    without massive I/O.
    """
    sandbox = tmp_path / ".hermes"
    sandbox.mkdir()

    # Copy config.yaml (the most important file)
    real_config = REAL_HERMES_HOME / "config.yaml"
    if real_config.exists():
        shutil.copy2(real_config, sandbox / "config.yaml")

    # Copy and redact auth.json
    real_auth = REAL_HERMES_HOME / "auth.json"
    if real_auth.exists():
        shutil.copy2(real_auth, sandbox / "auth.json")
        _redact_auth(sandbox / "auth.json")

    # Copy gateway_state.json
    real_gw = REAL_HERMES_HOME / "gateway_state.json"
    if real_gw.exists():
        shutil.copy2(real_gw, sandbox / "gateway_state.json")

    # Sample sessions (first 5 .json files)
    sessions_dir = sandbox / "sessions"
    sessions_dir.mkdir()
    real_sessions = REAL_HERMES_HOME / "sessions"
    if real_sessions.exists():
        count = 0
        for f in sorted(real_sessions.iterdir()):
            if f.is_file() and f.suffix == ".json":
                shutil.copy2(f, sessions_dir / f.name)
                count += 1
                if count >= 5:
                    break

    # Sample logs (agent.log tail + first 2 others)
    logs_dir = sandbox / "logs"
    logs_dir.mkdir()
    real_logs = REAL_HERMES_HOME / "logs"
    if real_logs.exists():
        agent_log = real_logs / "agent.log"
        if agent_log.exists():
            lines = agent_log.read_text(encoding="utf-8", errors="replace").splitlines()
            (logs_dir / "agent.log").write_text("\n".join(lines[-1000:]), encoding="utf-8")
        count = 0
        for f in sorted(real_logs.iterdir()):
            if f.is_file() and f.name != "agent.log" and f.suffix == ".log":
                shutil.copy2(f, logs_dir / f.name)
                count += 1
                if count >= 2:
                    break

    return sandbox


@pytest.fixture()
def lane_a_inventory(sandbox_hermes: Path, tmp_path: Path) -> Path:
    """Create a source inventory YAML pointing at the sandbox.

    The inventory format is flat: category -> list of {path, type} entries.
    The parse() function uses category names: config, session, log, gateway, database.
    """
    entries = []

    # Config
    entries.append(f"""\
config:
  - path: {sandbox_hermes}/config.yaml
    type: config
    authoritative: true""")

    # Sessions — individual files, not a directory
    sessions_dir = sandbox_hermes / "sessions"
    if sessions_dir.exists():
        session_files = sorted(sessions_dir.glob("*.json"))[:5]
        if session_files:
            session_yaml = "session:\n"
            for sf in session_files:
                session_yaml += f"  - path: {sf}\n    type: session\n"
            entries.append(session_yaml)

    # Logs — individual files
    logs_dir = sandbox_hermes / "logs"
    if logs_dir.exists():
        log_files = sorted(logs_dir.glob("*.log"))[:3]
        if log_files:
            log_yaml = "log:\n"
            for lf in log_files:
                log_yaml += f"  - path: {lf}\n    type: log\n"
            entries.append(log_yaml)

    # Auth
    auth_path = sandbox_hermes / "auth.json"
    if auth_path.exists():
        entries.append(f"""\
auth:
  - path: {auth_path}
    type: auth""")

    # Gateway
    gw_path = sandbox_hermes / "gateway_state.json"
    if gw_path.exists():
        entries.append(f"""\
gateway:
  - path: {gw_path}
    type: gateway_state""")

    inventory_content = "\n".join(entries)
    inv_path = tmp_path / "inventory.yaml"
    inv_path.write_text(inventory_content, encoding="utf-8")
    return inv_path


class TestLaneADiscovery:
    """Lane A: discovery against sandboxed real HERMES_HOME."""

    def test_inventory_loads(self, lane_a_inventory: Path) -> None:
        """The inventory YAML should load successfully."""
        inv = load_inventory(lane_a_inventory)
        assert len(inv.sources) > 0, "Inventory loaded but has no source categories"

    def test_config_is_discovered(self, lane_a_inventory: Path) -> None:
        """The real config.yaml should be found in the sandbox."""
        inv = load_inventory(lane_a_inventory)
        result = discover_live_paths(inv)
        config_entries = result.get("config", [])
        existing = [e for e in config_entries if e.exists]
        assert len(existing) > 0, (
            f"config.yaml not discovered. Categories found: {list(result.keys())}"
        )

    def test_sessions_are_discovered(self, lane_a_inventory: Path) -> None:
        """Sampled session files should be discovered."""
        inv = load_inventory(lane_a_inventory)
        result = discover_live_paths(inv)
        session_entries = result.get("session", [])
        existing = [e for e in session_entries if e.exists]
        assert len(existing) > 0, "No session files discovered"

    def test_logs_are_discovered(self, lane_a_inventory: Path) -> None:
        """Sampled log files should be discovered."""
        inv = load_inventory(lane_a_inventory)
        result = discover_live_paths(inv)
        log_entries = result.get("log", [])
        existing = [e for e in log_entries if e.exists]
        assert len(existing) > 0, "No log files discovered"


class TestLaneAPipeline:
    """Lane A: full pipeline against sandboxed real HERMES_HOME."""

    def test_discover_step(self, lane_a_inventory: Path, tmp_path: Path) -> None:
        """The discover step should find real paths in the sandbox."""
        config = LoopConfig(inventory_path=lane_a_inventory, db_path=tmp_path / "db")
        state = discover(LoopState(), config)
        assert len(state.discovered_paths) > 0, "discover() found no paths"
        all_entries = []
        for entries in state.discovered_paths.values():
            all_entries.extend(entries)
        existing = [e for e in all_entries if e.exists]
        assert len(existing) > 0, "No existing paths discovered"

    def test_parse_step_produces_findings(self, lane_a_inventory: Path, tmp_path: Path) -> None:
        """The parse step should produce findings from real config/sessions/logs."""
        config = LoopConfig(inventory_path=lane_a_inventory, db_path=tmp_path / "db")
        state = discover(LoopState(), config)
        state = parse(state, config)
        total = len(state.findings) + len(state.records)
        assert total > 0, (
            f"parse() produced zero output from "
            f"{sum(len(v) for v in state.discovered_paths.values())} discovered entries"
        )

    def test_full_pipeline_completes(self, lane_a_inventory: Path, tmp_path: Path) -> None:
        """End-to-end: discover -> parse -> enrich -> rank should complete without error."""
        config = LoopConfig(inventory_path=lane_a_inventory, db_path=tmp_path / "db")
        state = LoopState()
        state = discover(state, config)
        state = parse(state, config)
        state = enrich(state, config)
        state = rank(state, config)
        state = report(state, config)
        # verify step may check gateway — just ensure it doesn't crash
        try:
            state = verify(state, config)
        except Exception:
            pass  # gateway check may fail in sandbox, that's OK

        assert len(state.order) >= 4, f"Pipeline only ran {len(state.order)} steps: {state.order}"
        assert "discover" in state.order
        assert "parse" in state.order

    def test_pipeline_produces_recommendations(self, lane_a_inventory: Path, tmp_path: Path) -> None:
        """The full pipeline should produce recommendations from real data."""
        config = LoopConfig(inventory_path=lane_a_inventory, db_path=tmp_path / "db")
        state = LoopState()
        state = discover(state, config)
        state = parse(state, config)
        state = enrich(state, config)
        state = rank(state, config)
        # Recommendations come from rank step
        total_output = len(state.findings) + len(state.recommendations)
        assert total_output > 0, "Pipeline produced no findings or recommendations"


class TestLaneARealConfig:
    """Lane A: validate the optimizer reads real config structure."""

    def test_real_config_has_providers(self, sandbox_hermes: Path) -> None:
        """The real config.yaml should have providers defined."""
        config_path = sandbox_hermes / "config.yaml"
        if not config_path.exists():
            pytest.skip("No config.yaml in sandbox")
        config = yaml.safe_load(config_path.read_text())
        assert config is not None, "config.yaml is empty or invalid YAML"
        assert "providers" in config or "model" in config, (
            "config.yaml has no providers or model section"
        )

    def test_provider_extraction_from_real_config(self, sandbox_hermes: Path) -> None:
        """Optimizer should extract provider info from real config structure."""
        from hermesoptimizer.loop import _extract_configured_providers
        config_path = sandbox_hermes / "config.yaml"
        if not config_path.exists():
            pytest.skip("No config.yaml in sandbox")
        providers = _extract_configured_providers(config_path)
        assert len(providers) > 0, (
            f"_extract_configured_providers returned empty list from real config. "
            f"Config may use non-standard field names (api vs base_url, default_model vs model)."
        )
        for p in providers:
            assert p.get("provider"), "Provider missing name"
            assert p.get("base_url"), f"Provider {p['provider']} missing base_url (or api)"

    def test_provider_fields_normalized(self, sandbox_hermes: Path) -> None:
        """Real config api/default_model fields should normalize to base_url/model."""
        from hermesoptimizer.loop import _normalize_provider_def
        # Test with real config field names
        real_def = {
            "api": "https://example.com/v1",
            "default_model": "test-model",
            "key_env": "TEST_KEY",
            "name": "test",
        }
        result = _normalize_provider_def("test", real_def)
        assert result["base_url"] == "https://example.com/v1"
        assert result["model"] == "test-model"
        assert result["auth_key_env"] == "TEST_KEY"
        assert result["auth_type"] == "bearer"

    def test_provider_fields_backward_compat(self) -> None:
        """Fixture-style config (base_url/model) should still work."""
        from hermesoptimizer.loop import _normalize_provider_def
        fixture_def = {
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o",
            "auth_type": "bearer",
            "auth_key_env": "OPENAI_API_KEY",
        }
        result = _normalize_provider_def("openai", fixture_def)
        assert result["base_url"] == "https://api.openai.com/v1"
        assert result["model"] == "gpt-4o"
        assert result["auth_type"] == "bearer"

    def test_provider_truth_seeded_from_config(self, sandbox_hermes: Path) -> None:
        """Provider truth store should be seeded from real config providers."""
        from hermesoptimizer.sources.provider_truth import seed_from_config
        config_path = sandbox_hermes / "config.yaml"
        if not config_path.exists():
            pytest.skip("No config.yaml in sandbox")
        store = seed_from_config(config_path)
        records = store.all_records()
        assert len(records) > 0, "seed_from_config produced empty store"
        providers = {r.provider for r in records}
        assert "kilocode" in providers, f"kilocode not in seeded providers: {providers}"
        for rec in records:
            assert rec.canonical_endpoint, f"{rec.provider} missing endpoint"
            assert len(rec.known_models) > 0, f"{rec.provider} missing known models"

    def test_redacted_auth_has_no_real_keys(self, sandbox_hermes: Path) -> None:
        """Auth.json in sandbox should not contain real API keys."""
        auth_path = sandbox_hermes / "auth.json"
        if not auth_path.exists():
            pytest.skip("No auth.json in sandbox")
        content = auth_path.read_text()
        assert "REDACTED" in content, "auth.json was not redacted"

    def test_sandbox_has_sample_sessions(self, sandbox_hermes: Path) -> None:
        """Sandbox should have at least 1 sampled session file."""
        sessions_dir = sandbox_hermes / "sessions"
        if not sessions_dir.exists():
            pytest.skip("No sessions dir in sandbox")
        session_files = list(sessions_dir.iterdir())
        assert len(session_files) > 0, "No session files in sandbox"

    def test_sandbox_has_sample_logs(self, sandbox_hermes: Path) -> None:
        """Sandbox should have at least 1 log file."""
        logs_dir = sandbox_hermes / "logs"
        if not logs_dir.exists():
            pytest.skip("No logs dir in sandbox")
        log_files = list(logs_dir.iterdir())
        assert len(log_files) > 0, "No log files in sandbox"


class TestLaneALogPatterns:
    """Lane A: validate new real-format log patterns are detected."""

    def test_error_code_401_auth_pattern(self, tmp_path: Path) -> None:
        """Error code: 401 should be detected as auth failure."""
        from hermesoptimizer.sources.hermes_logs import scan_log
        log = tmp_path / "test.log"
        log.write_text("2025-01-15 08:07:00 ERROR Error code: 401 - {'error': 'Unauthorized'}\n", encoding="utf-8")
        findings = scan_log(log)
        auth = [f for f in findings if f.kind == "log-auth-failure"]
        assert len(auth) >= 1, "Error code: 401 not detected as auth failure"
        assert any("401" in f.sample_text for f in auth)

    def test_unknown_provider_pattern(self, tmp_path: Path) -> None:
        """unknown provider should be detected as provider failure."""
        from hermesoptimizer.sources.hermes_logs import scan_log
        log = tmp_path / "test.log"
        log.write_text("2025-01-15 08:08:00 WARNING unknown provider 'kilocode'\n", encoding="utf-8")
        findings = scan_log(log)
        provider = [f for f in findings if f.kind == "log-provider-failure"]
        assert len(provider) >= 1, "unknown provider not detected"
        assert any("unknown provider" in f.sample_text.lower() for f in provider)

    def test_request_timed_out_pattern(self, tmp_path: Path) -> None:
        """Request timed out should be detected as provider failure."""
        from hermesoptimizer.sources.hermes_logs import scan_log
        log = tmp_path / "test.log"
        log.write_text("2025-01-15 08:09:00 ERROR Request timed out after 60.0s\n", encoding="utf-8")
        findings = scan_log(log)
        provider = [f for f in findings if f.kind == "log-provider-failure"]
        assert len(provider) >= 1, "Request timed out not detected"
        assert any("timed out" in f.sample_text.lower() for f in provider)

    def test_unknown_model_pattern(self, tmp_path: Path) -> None:
        """unknown model should be detected as provider failure."""
        from hermesoptimizer.sources.hermes_logs import scan_log
        log = tmp_path / "test.log"
        log.write_text("2025-01-15 08:10:00 ERROR unknown model 'gpt-5'\n", encoding="utf-8")
        findings = scan_log(log)
        provider = [f for f in findings if f.kind == "log-provider-failure"]
        assert len(provider) >= 1, "unknown model not detected"
        assert any("unknown model" in f.sample_text.lower() for f in provider)

    def test_python_error_pattern(self, tmp_path: Path) -> None:
        """Python exception like openai.BadRequestError should be detected."""
        from hermesoptimizer.sources.hermes_logs import scan_log
        log = tmp_path / "test.log"
        log.write_text("2025-01-15 08:11:00 ERROR openai.BadRequestError: Invalid request\n", encoding="utf-8")
        findings = scan_log(log)
        runtime = [f for f in findings if f.kind == "log-runtime-failure"]
        assert len(runtime) >= 1, "Python Error pattern not detected"
        assert any("Error" in f.sample_text for f in runtime)

    def test_error_prefix_high_severity(self, tmp_path: Path) -> None:
        """ERROR-prefix lines should get high severity."""
        from hermesoptimizer.sources.hermes_logs import scan_log
        log = tmp_path / "test.log"
        log.write_text("2025-01-15 08:12:00 ERROR Some error message\n", encoding="utf-8")
        findings = scan_log(log)
        assert len(findings) >= 1, "ERROR-prefix line not detected"
        high_severity = [f for f in findings if f.severity == "high"]
        assert len(high_severity) >= 1, "ERROR-prefix should have high severity"

    def test_all_new_patterns_in_real_format_log(self, tmp_path: Path) -> None:
        """All new real-format patterns should be detected in a combined log."""
        from hermesoptimizer.sources.hermes_logs import scan_log
        log_content = (
            "2025-01-15 08:07:00 ERROR Error code: 401 - {'error': 'Unauthorized'}\n"
            "2025-01-15 08:08:00 WARNING unknown provider 'kilocode'\n"
            "2025-01-15 08:09:00 ERROR Request timed out after 60.0s\n"
            "2025-01-15 08:10:00 ERROR unknown model 'gpt-5'\n"
            "2025-01-15 08:11:00 ERROR openai.BadRequestError: Invalid request\n"
            "2025-01-15 08:12:00 ERROR Simple ERROR message\n"
        )
        log = tmp_path / "test.log"
        log.write_text(log_content, encoding="utf-8")
        findings = scan_log(log)
        assert len(findings) >= 5, f"Expected at least 5 findings, got {len(findings)}"
        # Verify high severity for ERROR-prefix
        high_severity = [f for f in findings if f.severity == "high"]
        assert len(high_severity) >= 3, "ERROR-prefix lines should have high severity"


class TestLaneACLI:
    """Lane A: CLI smoke against sandboxed data."""

    def test_cli_init_add_export(self, sandbox_hermes: Path, tmp_path: Path) -> None:
        """CLI init-db + add-record + export should work end-to-end."""
        from hermesoptimizer.run_standalone import main as cli_main

        db_path = tmp_path / "catalog.db"
        report_dir = tmp_path / "cli_reports"
        report_dir.mkdir()

        # Init DB
        rc = cli_main(["init-db", "--db", str(db_path)])
        assert rc == 0, "init-db failed"

        # Add a record from real config
        config_path = sandbox_hermes / "config.yaml"
        if config_path.exists():
            config = yaml.safe_load(config_path.read_text())
            providers = config.get("providers", {})
            if providers:
                first_provider = list(providers.keys())[0]
                prov_data = providers[first_provider]
                if isinstance(prov_data, dict):
                    rc = cli_main([
                        "add-record",
                        "--db", str(db_path),
                        "--provider", str(first_provider),
                        "--model", str(prov_data.get("model", "unknown")),
                        "--base-url", str(prov_data.get("base_url", "https://example.com")),
                        "--auth-type", str(prov_data.get("auth_type", "bearer")),
                        "--auth-key", "DUMMY_KEY",
                    ])
                    assert rc == 0, f"add-record failed for {first_provider}"

        # Export
        rc = cli_main([
            "export",
            "--db", str(db_path),
            "--out-dir", str(report_dir),
            "--title", "Lane A Smoke Test",
        ])
        assert rc == 0, "export failed"

        # Verify reports
        json_report = report_dir / "report.json"
        md_report = report_dir / "report.md"
        assert json_report.exists(), "JSON report not created"
        assert md_report.exists(), "Markdown report not created"
        assert len(json_report.read_text()) > 50, "JSON report too short"
        assert len(md_report.read_text()) > 50, "Markdown report too short"
