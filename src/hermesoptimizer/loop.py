"""
Phase 0 loop skeleton for Hermes discovery and scan.

The loop implements:
  discover -> parse -> enrich -> rank -> report -> verify -> repeat

Each step is a pure function (State, Config) -> State.
The loop is fully explicit and testable; no hidden global state.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path

from hermesoptimizer.catalog import Finding, init_db, upsert_finding
from hermesoptimizer.sources.hermes_discover import (
    SourceInventory,
    discover_live_paths,
    load_inventory,
)
from hermesoptimizer.sources.hermes_inventory import load_hermes_inventory
from hermesoptimizer.sources.hermes_config import scan_config_paths
from hermesoptimizer.sources.hermes_logs import scan_log_paths
from hermesoptimizer.sources.hermes_sessions import scan_session_files


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class LoopConfig:
    inventory_path: Path
    db_path: Path
    fixtures_mode: bool = False


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

@dataclass
class LoopState:
    findings: list[Finding]
    records: list  # Reserved for future Record entries
    discovered_paths: dict[str, list]
    order: list[str] = field(default_factory=list)
    current_step: str | None = None
    run_marker: str | None = None

    def record_step(self, step: str) -> None:
        self.order.append(step)
        self.current_step = step


# ---------------------------------------------------------------------------
# Step functions (all pure (State, Config) -> State)
# ---------------------------------------------------------------------------

def discover(state: LoopState, config: LoopConfig) -> LoopState:
    """Discover Hermes source paths from the inventory file."""
    state.record_step("discover")
    inv = load_inventory(config.inventory_path)
    live = discover_live_paths(inv)
    return LoopState(
        findings=state.findings,
        records=state.records,
        discovered_paths=live,
        order=state.order,
        current_step=state.current_step,
        run_marker=state.run_marker,
    )


def parse(state: LoopState, config: LoopConfig) -> LoopState:
    """Parse discovered paths and extract findings."""
    state.record_step("parse")
    new_findings: list[Finding] = list(state.findings)

    for category, entries in state.discovered_paths.items():
        for entry in entries:
            if not entry.exists:
                continue
            p = Path(entry.expand_path())
            if not p.exists():
                continue
            if category == "log":
                new_findings.extend(scan_log_paths([p]))
            elif category == "session":
                new_findings.extend(scan_session_files([p]))
            elif category == "config":
                new_findings.extend(scan_config_paths([p]))

    return LoopState(
        findings=new_findings,
        records=state.records,
        discovered_paths=state.discovered_paths,
        order=state.order,
        current_step=state.current_step,
        run_marker=state.run_marker,
    )


def enrich(state: LoopState, config: LoopConfig) -> LoopState:
    """Phase 0 stub: pass findings through unchanged."""
    state.record_step("enrich")
    return LoopState(
        findings=state.findings,
        records=state.records,
        discovered_paths=state.discovered_paths,
        order=state.order,
        current_step=state.current_step,
        run_marker=state.run_marker,
    )


def rank(state: LoopState, config: LoopConfig) -> LoopState:
    """Phase 0 stub: pass findings through unchanged."""
    state.record_step("rank")
    return LoopState(
        findings=state.findings,
        records=state.records,
        discovered_paths=state.discovered_paths,
        order=state.order,
        current_step=state.current_step,
        run_marker=state.run_marker,
    )


def report(state: LoopState, config: LoopConfig) -> LoopState:
    """Phase 0 stub: record the report step."""
    state.record_step("report")
    return LoopState(
        findings=state.findings,
        records=state.records,
        discovered_paths=state.discovered_paths,
        order=state.order,
        current_step=state.current_step,
        run_marker=state.run_marker,
    )


def verify(state: LoopState, config: LoopConfig) -> LoopState:
    """Phase 0 stub: record the verify step."""
    state.record_step("verify")
    return LoopState(
        findings=state.findings,
        records=state.records,
        discovered_paths=state.discovered_paths,
        order=state.order,
        current_step=state.current_step,
        run_marker=state.run_marker,
    )


def repeat(state: LoopState, config: LoopConfig) -> LoopState:
    """Assign a new run marker and persist findings to the catalog DB."""
    state.record_step("repeat")
    init_db(config.db_path)
    for finding in state.findings:
        upsert_finding(config.db_path, finding)
    marker = str(uuid.uuid4())[:8]
    return LoopState(
        findings=state.findings,
        records=state.records,
        discovered_paths=state.discovered_paths,
        order=state.order,
        current_step=state.current_step,
        run_marker=marker,
    )


# ---------------------------------------------------------------------------
# Phase0Loop runner
# ---------------------------------------------------------------------------

class Phase0Loop:
    """
    Orchestrates the discover -> parse -> enrich -> rank -> report -> verify -> repeat
    loop. Configurable via LoopConfig. Fully testable.
    """

    def __init__(self, config: LoopConfig) -> None:
        self.config = config

    def initial_state(self) -> LoopState:
        return LoopState(
            findings=[],
            records=[],
            discovered_paths={},
            order=[],
            current_step=None,
            run_marker=None,
        )

    def run(self, state: LoopState) -> LoopState:
        state = discover(state, self.config)
        state = parse(state, self.config)
        state = enrich(state, self.config)
        state = rank(state, self.config)
        state = report(state, self.config)
        state = verify(state, self.config)
        state = repeat(state, self.config)
        return state
