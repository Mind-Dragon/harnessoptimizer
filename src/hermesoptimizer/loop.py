"""
Hermes optimizer loop skeleton.

Phase 0 implements:
  discover -> parse -> enrich -> rank -> report -> verify -> repeat

Phase 1 inserts a diagnose step after parse:
  discover -> parse -> diagnose -> enrich -> rank -> report -> verify -> repeat

The loop is intentionally explicit and testable. The step functions are
small and mostly pure; they return a new LoopState while preserving the
same list/dict objects where practical so the tests can inspect step order.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from hermesoptimizer.catalog import Finding, finish_run, init_db, start_run, upsert_finding
from hermesoptimizer.route.diagnosis import Recommendation, build_recommendations, rank_findings
from hermesoptimizer.sources.hermes_config import scan_config_paths
from hermesoptimizer.sources.hermes_diagnosis import Diagnosis, diagnose_all
from hermesoptimizer.sources.hermes_discover import discover_live_paths, load_inventory
from hermesoptimizer.sources.hermes_logs import scan_log_paths
from hermesoptimizer.sources.hermes_runtime import scan_gateway_health, scan_runtime_paths
from hermesoptimizer.sources.hermes_sessions import scan_session_files
from hermesoptimizer.sources.provider_truth import ProviderTruthStore, load_provider_truth
from hermesoptimizer.verify.endpoints import EndpointCheckResult, verify_provider_truth


@dataclass(slots=True)
class LoopConfig:
    inventory_path: Path
    db_path: Path
    fixtures_mode: bool = False
    provider_truth_path: Path | None = None


@dataclass(slots=True)
class LoopState:
    findings: list[Finding] = field(default_factory=list)
    records: list[Any] = field(default_factory=list)
    discovered_paths: dict[str, list] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    current_step: str | None = None
    run_marker: str | None = None
    diagnoses: list[Diagnosis] = field(default_factory=list)
    recommendations: list[Recommendation] = field(default_factory=list)
    provider_truth_store: ProviderTruthStore | None = None
    verification_results: list[EndpointCheckResult] = field(default_factory=list)

    def record_step(self, step: str) -> None:
        self.order.append(step)
        self.current_step = step


def _clone_state(state: LoopState, **updates: Any) -> LoopState:
    payload: dict[str, Any] = {
        "findings": state.findings,
        "records": state.records,
        "discovered_paths": state.discovered_paths,
        "order": state.order,
        "current_step": state.current_step,
        "run_marker": state.run_marker,
        "diagnoses": state.diagnoses,
        "recommendations": state.recommendations,
        "provider_truth_store": state.provider_truth_store,
        "verification_results": state.verification_results,
    }
    payload.update(updates)
    return LoopState(**payload)


def _expand(path: str | Path) -> Path:
    return Path(path).expanduser()


def _extract_configured_providers(config_path: Path) -> list[dict[str, Any]]:
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    providers = data.get("providers", {})
    if not isinstance(providers, dict):
        return []
    configured: list[dict[str, Any]] = []
    for provider_name, provider_def in providers.items():
        if not isinstance(provider_def, dict):
            continue
        configured.append(
            {
                "provider": provider_name,
                "base_url": provider_def.get("base_url", ""),
                "model": provider_def.get("model"),
            }
        )
    return configured


def discover(state: LoopState, config: LoopConfig) -> LoopState:
    state.record_step("discover")
    inv = load_inventory(config.inventory_path)
    live = discover_live_paths(inv)
    return _clone_state(state, discovered_paths=live)


def parse(state: LoopState, config: LoopConfig) -> LoopState:
    state.record_step("parse")
    findings: list[Finding] = list(state.findings)

    for category, entries in state.discovered_paths.items():
        for entry in entries:
            if not entry.exists:
                continue
            path = _expand(entry.expand_path())
            if category == "config":
                findings.extend(scan_config_paths([path]))
            elif category == "session":
                findings.extend(scan_session_files([path]))
            elif category == "log":
                findings.extend(scan_log_paths([path]))
            elif category == "runtime":
                findings.extend(scan_runtime_paths([path]))
            elif category == "gateway" and entry.command:
                findings.extend(scan_gateway_health([entry.command]))

    return _clone_state(state, findings=findings)


def diagnose(state: LoopState, config: LoopConfig) -> LoopState:
    state.record_step("diagnose")
    diagnoses = diagnose_all(state.findings)
    return _clone_state(state, diagnoses=diagnoses)


def enrich(state: LoopState, config: LoopConfig) -> LoopState:
    state.record_step("enrich")
    truth_store = state.provider_truth_store
    if config.provider_truth_path and config.provider_truth_path.exists():
        truth_store = load_provider_truth(config.provider_truth_path)
    elif truth_store is None:
        truth_store = ProviderTruthStore()
    return _clone_state(state, provider_truth_store=truth_store)


def rank(state: LoopState, config: LoopConfig) -> LoopState:
    state.record_step("rank")
    diagnoses = rank_findings(state.findings)
    recommendations = build_recommendations(diagnoses)
    return _clone_state(state, diagnoses=state.diagnoses or diagnoses, recommendations=recommendations)


def report(state: LoopState, config: LoopConfig) -> LoopState:
    state.record_step("report")
    return _clone_state(state)


def verify(state: LoopState, config: LoopConfig) -> LoopState:
    state.record_step("verify")
    verification_results: list[EndpointCheckResult] = []
    for category, entries in state.discovered_paths.items():
        if category != "config":
            continue
        for entry in entries:
            if not entry.exists:
                continue
            config_path = _expand(entry.expand_path())
            configured = _extract_configured_providers(config_path)
            if configured:
                truth_store = state.provider_truth_store or ProviderTruthStore()
                verification_results.extend(verify_provider_truth(configured, truth_store))
    return _clone_state(state, verification_results=verification_results)


def repeat(state: LoopState, config: LoopConfig) -> LoopState:
    state.record_step("repeat")
    init_db(config.db_path)
    run_id = start_run(config.db_path, "phase1" if "diagnose" in state.order else "phase0")
    for finding in state.findings:
        upsert_finding(config.db_path, finding)
    finish_run(
        config.db_path,
        run_id,
        record_count=len(state.records),
        finding_count=len(state.findings),
    )
    marker = str(uuid.uuid4())[:8]
    return _clone_state(state, run_marker=marker)


class Phase0Loop:
    def __init__(self, config: LoopConfig) -> None:
        self.config = config

    def initial_state(self) -> LoopState:
        return LoopState()

    def run(self, state: LoopState) -> LoopState:
        state = discover(state, self.config)
        state = parse(state, self.config)
        state = enrich(state, self.config)
        state = rank(state, self.config)
        state = report(state, self.config)
        state = verify(state, self.config)
        state = repeat(state, self.config)
        return state


class Phase1Loop(Phase0Loop):
    def run(self, state: LoopState) -> LoopState:
        state = discover(state, self.config)
        state = parse(state, self.config)
        state = diagnose(state, self.config)
        state = enrich(state, self.config)
        state = rank(state, self.config)
        state = report(state, self.config)
        state = verify(state, self.config)
        state = repeat(state, self.config)
        return state
