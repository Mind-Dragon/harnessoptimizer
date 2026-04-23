from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

from hermesoptimizer.model_evaluator import RoleRequirement, evaluate_models
from hermesoptimizer.sources.model_catalog import MODEL_CATALOG, ModelCatalogEntry, ProviderModelCatalog
from hermesoptimizer.sources.provider_truth import ProviderTruthStore, seed_from_config

DEFAULT_PRIMARY_CONTEXT = 128_000

AUXILIARY_ROLES: dict[str, dict[str, Any]] = {
    "compression": {
        "required_capabilities": ["text"],
        "prefer_fast": True,
        "prefer_no_reasoning": True,
        "min_context_from_primary": True,
    },
    "vision": {
        "required_capabilities": ["text", "vision"],
        "min_context_window": 32_000,
    },
    "web_extract": {
        "required_capabilities": ["text"],
        "min_context_window": 128_000,
        "prefer_fast": True,
    },
    "session_search": {
        "required_capabilities": ["text"],
        "min_context_window": 32_000,
        "max_context_window": 128_000,
        "prefer_fast": True,
        "prefer_cheap": True,
        "prefer_no_reasoning": True,
    },
    "skills_hub": {
        "required_capabilities": ["text"],
        "min_context_window": 32_000,
    },
    "approval": {
        "required_capabilities": ["text", "reasoning"],
        "min_context_window": 128_000,
    },
    "mcp": {
        "required_capabilities": ["text"],
        "min_context_window": 32_000,
        "prefer_fast": True,
    },
    "flush_memories": {
        "required_capabilities": ["text"],
        "min_context_window": 32_000,
        "max_context_window": 128_000,
        "prefer_fast": True,
        "prefer_cheap": True,
        "prefer_no_reasoning": True,
    },
    "title_generation": {
        "required_capabilities": ["text"],
        "min_context_window": 8_000,
        "max_context_window": 32_000,
        "prefer_fast": True,
        "prefer_cheap": True,
        "prefer_no_reasoning": True,
    },
}


@dataclass(slots=True)
class AuxiliaryEntry:
    role: str
    provider: str
    model: str
    reason: str
    evaluator_score: int
    evaluator_rationale: list[str]


@dataclass(slots=True)
class AuxiliaryDrift:
    role: str
    provider: str
    model: str
    issue: str
    severity: str


def resolve_primary_context(model_name: str, provider: str) -> int:
    entry = MODEL_CATALOG.get(provider, model_name)
    if entry is not None and entry.context_window > 0:
        return entry.context_window
    return DEFAULT_PRIMARY_CONTEXT



def build_role_requirements(primary_context: int) -> dict[str, RoleRequirement]:
    requirements: dict[str, RoleRequirement] = {}
    for role, spec in AUXILIARY_ROLES.items():
        min_context_window = (
            primary_context
            if spec.get("min_context_from_primary")
            else int(spec.get("min_context_window", 0))
        )
        requirements[role] = RoleRequirement(
            role_name=role,
            required_capabilities=list(spec.get("required_capabilities", [])),
            min_context_window=min_context_window,
            max_context_window=spec.get("max_context_window"),
            prefer_fast=bool(spec.get("prefer_fast", False)),
            prefer_cheap=bool(spec.get("prefer_cheap", False)),
            prefer_no_reasoning=bool(spec.get("prefer_no_reasoning", False)),
        )
    return requirements



def evaluate_auxiliary(config_path: str | Path) -> list[AuxiliaryEntry]:
    config = _load_config(config_path)
    primary_provider, primary_model = _primary_model_info(config)
    requirements = build_role_requirements(resolve_primary_context(primary_model, primary_provider))
    auxiliary_config = _auxiliary_block(config)
    truth_store = _truth_store_for_config(config_path)

    results: list[AuxiliaryEntry] = []
    for role, requirement in requirements.items():
        configured_provider, configured_model = _configured_auxiliary_model(auxiliary_config, role)
        configured_entry = _catalog_entry(configured_provider, configured_model)
        configured_passes = _entry_passes(configured_entry, requirement, truth_store)
        ranked = evaluate_models(requirement, catalog=MODEL_CATALOG, truth_store=truth_store)
        recommended = ranked[0] if ranked else None

        if configured_provider and configured_model and configured_passes:
            results.append(
                AuxiliaryEntry(
                    role=role,
                    provider=configured_provider,
                    model=configured_model,
                    reason="user override preserved",
                    evaluator_score=recommended.score if recommended else 0,
                    evaluator_rationale=[f"user override preserved for {role}"],
                )
            )
            continue

        if recommended is None:
            reason = "no eligible auxiliary model found"
            if configured_provider and configured_model:
                reason = "explicit auxiliary model failed constraints; no replacement candidate found"
            results.append(
                AuxiliaryEntry(
                    role=role,
                    provider=configured_provider,
                    model=configured_model,
                    reason=reason,
                    evaluator_score=0,
                    evaluator_rationale=[],
                )
            )
            continue

        reason = (
            "replacement recommended; explicit auxiliary model failed constraints"
            if configured_provider and configured_model
            else "[AUXILIARY_AUTO_SELECTED] top evaluator pick used"
        )
        results.append(
            AuxiliaryEntry(
                role=role,
                provider=recommended.provider,
                model=recommended.model,
                reason=reason,
                evaluator_score=recommended.score,
                evaluator_rationale=list(recommended.rationale),
            )
        )

    return results



def auxiliary_status(config_path: str | Path) -> dict[str, dict[str, Any]]:
    config = _load_config(config_path)
    primary_provider, primary_model = _primary_model_info(config)
    requirements = build_role_requirements(resolve_primary_context(primary_model, primary_provider))
    auxiliary_config = _auxiliary_block(config)
    truth_store = _truth_store_for_config(config_path)
    recommendations = {entry.role: entry for entry in evaluate_auxiliary(config_path)}

    status: dict[str, dict[str, Any]] = {}
    for role, requirement in requirements.items():
        configured_provider, configured_model = _configured_auxiliary_model(auxiliary_config, role)
        configured_entry = _catalog_entry(configured_provider, configured_model)
        constraint_pass = None
        if configured_provider and configured_model:
            constraint_pass = _entry_passes(configured_entry, requirement, truth_store)

        if configured_provider and configured_model:
            if constraint_pass:
                finding = "user override preserved"
            else:
                finding = "explicit auxiliary model fails constraints; replacement recommended"
        else:
            finding = "[AUXILIARY_AUTO_SELECTED] no explicit setting"

        recommended = recommendations[role]
        status[role] = {
            "role": role,
            "current": _current_record(configured_provider, configured_model),
            "recommended": {
                "provider": recommended.provider,
                "model": recommended.model,
                "reason": recommended.reason,
            },
            "constraint_pass": constraint_pass,
            "finding": finding,
        }

    return status


def load_auxiliary_entries(config_path: str | Path | None = None) -> list[AuxiliaryEntry]:
    path = Path(config_path) if config_path is not None else Path.home() / ".hermes" / "config.yaml"
    auxiliary_config = _auxiliary_block(_load_config(path))
    entries: list[AuxiliaryEntry] = []
    for role, role_config in auxiliary_config.items():
        if not isinstance(role_config, dict):
            continue
        provider, model = _configured_auxiliary_model(auxiliary_config, role)
        if not provider and not model:
            continue
        entries.append(
            AuxiliaryEntry(
                role=role,
                provider=provider,
                model=model,
                reason="configured auxiliary entry",
                evaluator_score=0,
                evaluator_rationale=[],
            )
        )
    return entries


def check_auxiliary_drift(
    auxiliary_entries: Iterable[AuxiliaryEntry],
    *,
    config_path: str | Path | None = None,
) -> list[AuxiliaryDrift]:
    if config_path is not None:
        truth_store = seed_from_config(config_path)
    else:
        truth_store = ProviderTruthStore()
    drifts: list[AuxiliaryDrift] = []
    for entry in auxiliary_entries:
        provider = str(entry.provider or "").strip()
        model = str(entry.model or "").strip()
        role = str(entry.role or "").strip()
        if not provider and not model:
            continue

        record = truth_store.get(provider)
        if record is None or not record.canonical_endpoint:
            drifts.append(
                AuxiliaryDrift(
                    role=role,
                    provider=provider,
                    model=model,
                    issue=f"provider '{provider}' is unavailable or has no canonical endpoint",
                    severity="error",
                )
            )
            continue

        if not record.is_model_known(model):
            alias_target = record.get_stale_alias_correction(model)
            if alias_target:
                issue = f"model '{model}' is a stale alias for '{alias_target}'"
            elif record.is_model_deprecated(model):
                issue = f"model '{model}' is deprecated for provider '{record.provider}'"
            else:
                issue = f"model '{model}' is not in known model list for provider '{record.provider}'"
            drifts.append(
                AuxiliaryDrift(
                    role=role,
                    provider=provider,
                    model=model,
                    issue=issue,
                    severity="warning",
                )
            )
    return drifts


def default_drift_report_path() -> Path:
    return Path.home() / ".hoptimizer" / "auxiliary_drift_report.json"


def write_drift_report(drifts: Iterable[AuxiliaryDrift], path: str | Path) -> None:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(drift) for drift in drifts]
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _truth_store_for_config(config_path: str | Path) -> ProviderTruthStore:
    return seed_from_config(config_path)



def _load_config(config_path: str | Path) -> dict[str, Any]:
    path = Path(config_path)
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if isinstance(raw, dict):
        return raw
    return {}



def _primary_model_info(config: dict[str, Any]) -> tuple[str, str]:
    model_block = config.get("model")
    if not isinstance(model_block, dict):
        return "", ""
    provider = str(model_block.get("provider") or "").strip()
    model = str(model_block.get("default") or model_block.get("model") or "").strip()
    return provider, model



def _auxiliary_block(config: dict[str, Any]) -> dict[str, Any]:
    auxiliary = config.get("auxiliary")
    if isinstance(auxiliary, dict):
        return auxiliary
    return {}



def _configured_auxiliary_model(auxiliary_config: dict[str, Any], role: str) -> tuple[str, str]:
    role_config = auxiliary_config.get(role)
    if not isinstance(role_config, dict):
        return "", ""
    provider = str(role_config.get("provider") or "").strip()
    model = str(role_config.get("model") or role_config.get("default") or "").strip()
    return provider, model



def _catalog_entry(provider: str, model: str) -> ModelCatalogEntry | None:
    if not provider or not model:
        return None
    return MODEL_CATALOG.get(provider, model)



def _entry_passes(
    entry: ModelCatalogEntry | None,
    requirement: RoleRequirement,
    truth_store: ProviderTruthStore,
) -> bool:
    if entry is None:
        return False
    catalog = ProviderModelCatalog()
    catalog.add(entry)
    return bool(evaluate_models(requirement, catalog=catalog, truth_store=truth_store))



def _current_record(provider: str, model: str) -> dict[str, str] | None:
    if not provider or not model:
        return None
    return {"provider": provider, "model": model}


__all__ = [
    "AUXILIARY_ROLES",
    "AuxiliaryDrift",
    "AuxiliaryEntry",
    "DEFAULT_PRIMARY_CONTEXT",
    "auxiliary_status",
    "build_role_requirements",
    "check_auxiliary_drift",
    "default_drift_report_path",
    "evaluate_auxiliary",
    "load_auxiliary_entries",
    "resolve_primary_context",
    "write_drift_report",
]
