"""
Phase 0 loop skeleton tests.

These tests verify the discover -> parse -> enrich -> rank -> report -> verify -> repeat
loop contract. The loop must be:
- explicit and testable (not hidden in one big script)
- stable in order
- able to operate on fixtures without crashing
- able to set and check a run marker for repeatability
"""
from __future__ import annotations

from pathlib import Path
import json

import pytest

from hermesoptimizer.loop import (
    LoopState,
    LoopConfig,
    Phase0Loop,
    discover,
    parse,
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
    cfg = LoopConfig(
        inventory_path=inv_file,
        db_path=db,
        fixtures_mode=True,
    )
    return Phase0Loop(cfg)


@pytest.fixture
def loop_state(phase0_loop: Phase0Loop) -> LoopState:
    return phase0_loop.initial_state()


# ---------------------------------------------------------------------------
# LoopState dataclass tests
# ---------------------------------------------------------------------------

class TestLoopState:
    def test_initial_state_has_no_findings(self, loop_state: LoopState) -> None:
        assert loop_state.findings == []
        assert loop_state.records == []

    def test_initial_state_has_no_run_marker(self, loop_state: LoopState) -> None:
        assert loop_state.run_marker is None

    def test_initial_state_has_empty_discovered_paths(self, loop_state: LoopState) -> None:
        assert loop_state.discovered_paths == {}

    def test_state_tracks_pass_through_order(self, loop_state: LoopState) -> None:
        assert loop_state.order == []
        assert loop_state.current_step is None

    def test_state_can_record_step(self, loop_state: LoopState) -> None:
        loop_state.record_step("discover")
        assert "discover" in loop_state.order
        assert loop_state.current_step == "discover"


# ---------------------------------------------------------------------------
# LoopConfig tests
# ---------------------------------------------------------------------------

class TestLoopConfig:
    def test_config_stores_inventory_path(self, tmp_path: Path) -> None:
        inv = tmp_path / "inv.yaml"
        cfg = LoopConfig(inventory_path=inv, db_path=tmp_path / "db")
        assert cfg.inventory_path == inv

    def test_config_has_fixtures_mode_flag(self, tmp_path: Path) -> None:
        cfg = LoopConfig(
            inventory_path=tmp_path / "inv.yaml",
            db_path=tmp_path / "db",
            fixtures_mode=True,
        )
        assert cfg.fixtures_mode is True


# ---------------------------------------------------------------------------
# Step function tests (TDD - each step returns a modified state)
# ---------------------------------------------------------------------------

class TestDiscoverStep:
    def test_discover_returns_state_with_paths(self, phase0_loop: Phase0Loop, loop_state: LoopState) -> None:
        next_state = discover(loop_state, phase0_loop.config)
        assert next_state.discovered_paths != {}
        assert "config" in next_state.discovered_paths

    def test_discover_sets_current_step(self, phase0_loop: Phase0Loop, loop_state: LoopState) -> None:
        next_state = discover(loop_state, phase0_loop.config)
        assert next_state.current_step == "discover"

    def test_discover_on_fixtures_finds_config(self, phase0_loop: Phase0Loop, loop_state: LoopState) -> None:
        next_state = discover(loop_state, phase0_loop.config)
        config_entries = next_state.discovered_paths.get("config", [])
        assert len(config_entries) >= 1


class TestParseStep:
    def test_parse_returns_state_with_findings(self, phase0_loop: Phase0Loop, loop_state: LoopState) -> None:
        state_after_discover = discover(loop_state, phase0_loop.config)
        next_state = parse(state_after_discover, phase0_loop.config)
        assert next_state.findings != []

    def test_parse_sets_current_step(self, phase0_loop: Phase0Loop, loop_state: LoopState) -> None:
        state_after_discover = discover(loop_state, phase0_loop.config)
        next_state = parse(state_after_discover, phase0_loop.config)
        assert next_state.current_step == "parse"

    def test_parse_on_fixture_logs_finds_errors(self, phase0_loop: Phase0Loop, loop_state: LoopState) -> None:
        state_after_discover = discover(loop_state, phase0_loop.config)
        next_state = parse(state_after_discover, phase0_loop.config)
        # fixture app.log has ERROR lines
        log_findings = [f for f in next_state.findings if f.category == "log-signal"]
        assert len(log_findings) >= 1

    def test_parse_on_fixture_sessions_finds_signals(self, phase0_loop: Phase0Loop, loop_state: LoopState) -> None:
        state_after_discover = discover(loop_state, phase0_loop.config)
        next_state = parse(state_after_discover, phase0_loop.config)
        session_findings = [f for f in next_state.findings if f.category == "session-signal"]
        assert len(session_findings) >= 1


class TestEnrichStep:
    def test_enrich_is_noop_for_phase0(self, phase0_loop: Phase0Loop, loop_state: LoopState) -> None:
        """Phase 0: enrich is a stub that passes findings through unchanged."""
        state = LoopState(
            findings=[], records=[], discovered_paths={},
            order=["discover", "parse"], current_step="parse",
            run_marker=None,
        )
        next_state = enrich(state, phase0_loop.config)
        # Phase 0 just passes through
        assert next_state.findings == state.findings
        assert next_state.current_step == "enrich"


class TestRankStep:
    def test_rank_is_noop_for_phase0(self, phase0_loop: Phase0Loop, loop_state: LoopState) -> None:
        """Phase 0: rank is a stub that passes findings through unchanged."""
        state = LoopState(
            findings=[], records=[], discovered_paths={},
            order=["discover", "parse", "enrich"], current_step="enrich",
            run_marker=None,
        )
        next_state = rank(state, phase0_loop.config)
        assert next_state.findings == state.findings
        assert next_state.current_step == "rank"


class TestReportStep:
    def test_report_sets_current_step(self, phase0_loop: Phase0Loop, loop_state: LoopState) -> None:
        state = LoopState(
            findings=[], records=[], discovered_paths={},
            order=["discover", "parse", "enrich", "rank"], current_step="rank",
            run_marker=None,
        )
        next_state = report(state, phase0_loop.config)
        assert next_state.current_step == "report"


class TestVerifyStep:
    def test_verify_sets_current_step(self, phase0_loop: Phase0Loop, loop_state: LoopState) -> None:
        state = LoopState(
            findings=[], records=[], discovered_paths={},
            order=["discover", "parse", "enrich", "rank", "report"],
            current_step="report",
            run_marker=None,
        )
        next_state = verify(state, phase0_loop.config)
        assert next_state.current_step == "verify"


class TestRepeatStep:
    def test_repeat_sets_run_marker(self, phase0_loop: Phase0Loop, loop_state: LoopState) -> None:
        state = LoopState(
            findings=[], records=[], discovered_paths={},
            order=["discover", "parse", "enrich", "rank", "report", "verify"],
            current_step="verify",
            run_marker=None,
        )
        next_state = repeat(state, phase0_loop.config)
        assert next_state.run_marker is not None
        assert next_state.current_step == "repeat"

    def test_repeat_run_marker_is_string(self, phase0_loop: Phase0Loop, loop_state: LoopState) -> None:
        state = LoopState(
            findings=[], records=[], discovered_paths={},
            order=["discover", "parse", "enrich", "rank", "report", "verify"],
            current_step="verify",
            run_marker=None,
        )
        next_state = repeat(state, phase0_loop.config)
        assert isinstance(next_state.run_marker, str)


# ---------------------------------------------------------------------------
# Phase0Loop full integration tests
# ---------------------------------------------------------------------------

class TestPhase0Loop:
    def test_loop_order_is_stable(self, phase0_loop: Phase0Loop) -> None:
        """The loop must always execute steps in the defined order."""
        state = phase0_loop.initial_state()
        final_state = phase0_loop.run(state)
        expected_order = ["discover", "parse", "enrich", "rank", "report", "verify", "repeat"]
        assert final_state.order == expected_order

    def test_loop_runs_end_to_end_on_fixtures(self, phase0_loop: Phase0Loop) -> None:
        """The loop must complete all steps on fixture data without crashing."""
        state = phase0_loop.initial_state()
        final_state = phase0_loop.run(state)
        assert final_state.current_step == "repeat"
        assert final_state.run_marker is not None

    def test_loop_finds_config_log_session_on_fixtures(self, phase0_loop: Phase0Loop) -> None:
        """On fixture data the loop must produce findings from config, logs, and sessions."""
        state = phase0_loop.initial_state()
        final_state = phase0_loop.run(state)
        categories = {f.category for f in final_state.findings}
        assert "log-signal" in categories or "session-signal" in categories

    def test_loop_db_written_on_run(self, phase0_loop: Phase0Loop) -> None:
        """After a full run the catalog DB must exist."""
        state = phase0_loop.initial_state()
        phase0_loop.run(state)
        assert phase0_loop.config.db_path.exists()

    def test_loop_repeat_produces_new_run_marker(self, phase0_loop: Phase0Loop) -> None:
        """Two consecutive repeat steps must produce different run markers."""
        state = phase0_loop.initial_state()
        s1 = phase0_loop.run(state)
        s2 = phase0_loop.run(s1)
        assert s1.run_marker != s2.run_marker
