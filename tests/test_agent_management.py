from __future__ import annotations

from pathlib import Path

from hermesoptimizer.agent_management import (
    AgentProfile,
    HermesAgentRegistry,
    get_agent_model,
    get_registry,
    init_registry,
)
from hermesoptimizer.loop import LoopConfig, LoopState, enrich
from hermesoptimizer.sources.provider_truth import ProviderTruthStore


def test_init_registry_uses_catalog_best_models() -> None:
    registry = init_registry()
    assert isinstance(registry, HermesAgentRegistry)
    assert registry.get_agent_model("coding") == ("qwen", "qwen3.6-plus")
    assert registry.get_agent_model("vision") == ("qwen", "qwen3-vl-plus")
    assert registry.get_agent_model("reasoning") == ("xai", "grok-4.20-0309-reasoning")


def test_global_registry_helper_matches_init_registry() -> None:
    init_registry()
    assert get_registry().get_agent_model("general") == get_agent_model("general")


def test_registry_unknown_role_returns_none() -> None:
    registry = init_registry()
    assert registry.get_agent_model("not-a-role") is None
    assert registry.get_fallback_chain("not-a-role") == []


def test_registry_fallback_chain_and_capabilities() -> None:
    registry = init_registry()
    chain = registry.get_fallback_chain("fast-chat")
    assert chain
    assert any(provider == "qwen" for provider, _ in chain)
    vision_roles = registry.roles_for_capability("vision")
    assert "vision" in vision_roles


def test_best_role_for_task_prefers_specialized_role() -> None:
    registry = init_registry()
    assert registry.best_role_for_task(["coding", "text"]) == "coding"
    assert registry.best_role_for_task(["vision", "text"]) == "vision"


def test_registry_custom_profile_roundtrip() -> None:
    profile = AgentProfile(
        role="custom",
        provider="qwen",
        model="qwen3.6-plus",
        capabilities=["text", "reasoning"],
        fallback_chain=[("xai", "grok-4.20-0309-reasoning")],
        region_notes="custom",
    )
    registry = HermesAgentRegistry(profiles={"custom": profile}, truth_store=ProviderTruthStore())
    assert registry.get_agent_model("custom") == ("qwen", "qwen3.6-plus")
    assert registry.best_role_for_task(["reasoning", "text"]) == "custom"


def test_enrich_populates_agent_registry(tmp_path: Path) -> None:
    cfg = LoopConfig(inventory_path=tmp_path / "inventory.yaml", db_path=tmp_path / "db.sqlite")
    state = LoopState()
    next_state = enrich(state, cfg)
    assert next_state.agent_registry is not None
    assert next_state.agent_registry.get_agent_model("coding") == ("qwen", "qwen3.6-plus")
