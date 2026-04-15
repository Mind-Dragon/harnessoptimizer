"""
Tests for the provider model catalog.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hermesoptimizer.sources.model_catalog import (
    MODEL_CATALOG,
    CatalogValidationError,
    LatencyTier,
    ModelCatalogEntry,
    ProviderModelCatalog,
    RegionAvailability,
    get_best_for_role,
    get_models_by_capability,
    get_models_by_provider,
    get_provider_names,
    load_catalog,
    validate_catalog,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def empty_catalog() -> ProviderModelCatalog:
    return ProviderModelCatalog()


# ---------------------------------------------------------------------------
# ModelCatalogEntry
# ---------------------------------------------------------------------------

def test_model_catalog_entry_basic() -> None:
    entry = ModelCatalogEntry(
        name="qwen3.6-plus",
        display_name="Qwen 3.6 Plus",
        provider="qwen",
        capabilities=["text", "reasoning", "coding"],
        context_window=32000,
    )
    assert entry.name == "qwen3.6-plus"
    assert entry.provider == "qwen"
    assert "reasoning" in entry.capabilities


def test_model_catalog_entry_defaults() -> None:
    entry = ModelCatalogEntry(
        name="test-model",
        display_name="Test Model",
        provider="test",
        capabilities=["text"],
        context_window=8000,
    )
    assert entry.region_availability is None
    assert entry.is_deprecated is False
    assert entry.input_cost_per_mtok is None
    assert entry.output_cost_per_mtok is None
    assert entry.is_best_for is None
    assert entry.endpoint is None
    assert entry.auth_type is None
    assert entry.auth_key_env is None
    assert entry.notes is None


# ---------------------------------------------------------------------------
# ProviderModelCatalog basics
# ---------------------------------------------------------------------------

def test_catalog_empty_by_default(empty_catalog: ProviderModelCatalog) -> None:
    assert empty_catalog.list_providers() == []
    assert empty_catalog.list_models() == []
    assert empty_catalog.list_models("qwen") == []


def test_catalog_add_entry(empty_catalog: ProviderModelCatalog) -> None:
    entry = ModelCatalogEntry(
        name="qwen3.6-plus",
        display_name="Qwen 3.6 Plus",
        provider="qwen",
        capabilities=["text", "reasoning"],
        context_window=32000,
    )
    empty_catalog.add(entry)
    assert empty_catalog.list_providers() == ["qwen"]
    models = empty_catalog.list_models("qwen")
    assert len(models) == 1
    assert models[0].name == "qwen3.6-plus"


def test_catalog_add_duplicate_raises(empty_catalog: ProviderModelCatalog) -> None:
    entry = ModelCatalogEntry(
        name="qwen3.6-plus",
        display_name="Qwen 3.6 Plus",
        provider="qwen",
        capabilities=["text"],
        context_window=32000,
    )
    empty_catalog.add(entry)
    with pytest.raises(CatalogValidationError, match="duplicate"):
        empty_catalog.add(entry)


def test_catalog_all_models_from_all_providers(empty_catalog: ProviderModelCatalog) -> None:
    entry1 = ModelCatalogEntry(name="m1", display_name="M1", provider="p1", capabilities=["text"], context_window=8000)
    entry2 = ModelCatalogEntry(name="m2", display_name="M2", provider="p2", capabilities=["text"], context_window=8000)
    empty_catalog.add(entry1)
    empty_catalog.add(entry2)
    all_models = empty_catalog.list_models()
    assert len(all_models) == 2


# ---------------------------------------------------------------------------
# Provider listing helpers
# ---------------------------------------------------------------------------

def test_get_provider_names_returns_canonical() -> None:
    names = get_provider_names()
    assert isinstance(names, list)
    assert "qwen" in names
    assert "xai" in names
    assert "minimax" in names
    assert "zai" in names
    assert "openai" in names
    assert "anthropic" in names


def test_get_models_by_provider_filters_correctly() -> None:
    models = get_models_by_provider("qwen")
    assert all(m.provider == "qwen" for m in models)


def test_get_models_by_provider_unknown_returns_empty() -> None:
    models = get_models_by_provider("nonexistent-provider")
    assert models == []


# ---------------------------------------------------------------------------
# Qwen 3.6 Plus explicit presence and validation
# ---------------------------------------------------------------------------

def test_qwen_3_6_plus_explicitly_present() -> None:
    """Qwen 3.6 Plus must be explicitly present in the global catalog."""
    qwen_models = get_models_by_provider("qwen")
    names = [m.name for m in qwen_models]
    assert "qwen3.6-plus" in names, f"qwen3.6-plus not found in qwen models: {names}"


def test_qwen_3_6_plus_entry_valid() -> None:
    """Qwen 3.6 Plus entry must have valid capabilities and context window."""
    qwen_models = get_models_by_provider("qwen")
    qwen36 = next((m for m in qwen_models if m.name == "qwen3.6-plus"), None)
    assert qwen36 is not None
    assert qwen36.display_name == "Qwen 3.6 Plus"
    assert "text" in qwen36.capabilities
    assert qwen36.context_window >= 32000


def test_qwen_3_6_plus_is_best_for_reasoning() -> None:
    """Qwen 3.6 Plus should be marked as best-for for reasoning role."""
    qwen_models = get_models_by_provider("qwen")
    qwen36 = next((m for m in qwen_models if m.name == "qwen3.6-plus"), None)
    assert qwen36 is not None
    assert qwen36.is_best_for is not None
    assert "reasoning" in qwen36.is_best_for


# ---------------------------------------------------------------------------
# Global catalog MODEL_CATALOG
# ---------------------------------------------------------------------------

def test_global_catalog_is_valid() -> None:
    """Global MODEL_CATALOG must pass full validation."""
    errors = validate_catalog(MODEL_CATALOG)
    assert errors == [], f"Global catalog has validation errors: {errors}"


def test_global_catalog_has_all_required_providers() -> None:
    required = {"openai", "anthropic", "qwen", "xai", "minimax", "zai"}
    names = get_provider_names()
    missing = required - set(names)
    assert missing == set(), f"Missing required providers: {missing}"


def test_global_catalog_each_provider_has_best_for_role() -> None:
    """Each provider's best-for map should be internally consistent."""
    for provider_name in get_provider_names():
        models = get_models_by_provider(provider_name)
        for model in models:
            if model.is_best_for:
                for role, suggested_name in model.is_best_for.items():
                    # suggested name should exist in the same provider's catalog
                    known_names = [m.name for m in models]
                    assert suggested_name in known_names, (
                        f"Model '{model.name}' claims best_for['{role}']='{suggested_name}' "
                        f"but '{suggested_name}' is not in provider '{provider_name}'"
                    )


# ---------------------------------------------------------------------------
# Capability-based lookup
# ---------------------------------------------------------------------------

def test_get_models_by_capability_filters() -> None:
    models = get_models_by_capability("vision")
    assert all("vision" in m.capabilities for m in models)


def test_get_models_by_capability_unknown_returns_empty() -> None:
    models = get_models_by_capability("nonexistent-capability-xyz")
    assert models == []


def test_global_catalog_capability_coverage() -> None:
    """Every model in global catalog should have at least one capability."""
    for model in MODEL_CATALOG.list_models():
        assert model.capabilities, f"Model '{model.name}' has no capabilities"


# ---------------------------------------------------------------------------
# Role-based best model lookup
# ---------------------------------------------------------------------------

def test_get_best_for_role_reasoning() -> None:
    model = get_best_for_role("reasoning")
    assert model is not None
    assert "reasoning" in model.capabilities


def test_get_best_for_role_coding() -> None:
    model = get_best_for_role("coding")
    assert model is not None
    assert "coding" in model.capabilities or "text" in model.capabilities


def test_get_best_for_role_vision() -> None:
    model = get_best_for_role("vision")
    assert model is not None
    assert "vision" in model.capabilities


def test_get_best_for_role_unknown_returns_none() -> None:
    model = get_best_for_role("nonexistent-role-xyz")
    assert model is None


def test_get_best_for_role_with_provider_filter() -> None:
    model = get_best_for_role("coding", provider="qwen")
    assert model is not None
    assert model.provider == "qwen"
    assert "coding" in model.capabilities or "text" in model.capabilities


# ---------------------------------------------------------------------------
# Region-aware validation and lookup
# ---------------------------------------------------------------------------

def test_region_aware_best_model_available_in_region() -> None:
    model = MODEL_CATALOG.region_aware_best("coding", "us")
    if model is not None:
        # If region availability is set, 'us' must be in it
        if model.region_availability is not None:
            assert "us" in model.region_availability


def test_region_aware_best_model_falls_back_when_region_unavailable() -> None:
    """If best model for a role is not available in region, catalog should still return something or None gracefully."""
    # This should not raise; just return None or a fallback
    result = MODEL_CATALOG.region_aware_best("vision", "cn")
    # Just ensure no exception
    assert result is None or isinstance(result, ModelCatalogEntry)


def test_validate_region_aware_entries() -> None:
    """All entries with region_availability set must have valid region codes."""
    valid_regions = {r.value for r in RegionAvailability}
    for model in MODEL_CATALOG.list_models():
        if model.region_availability:
            for region in model.region_availability:
                assert region in valid_regions, (
                    f"Model '{model.name}' has invalid region '{region}'. "
                    f"Valid regions: {valid_regions}"
                )


# ---------------------------------------------------------------------------
# Latency tier validation
# ---------------------------------------------------------------------------

def test_latency_tier_values() -> None:
    """Latency tier values should be from the LatencyTier enum."""
    valid_tiers = {t.value for t in LatencyTier}
    for model in MODEL_CATALOG.list_models():
        if model.latency_tier:
            assert model.latency_tier in valid_tiers, (
                f"Model '{model.name}' has invalid latency_tier '{model.latency_tier}'. "
                f"Valid tiers: {valid_tiers}"
            )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_validate_catalog_catches_duplicate_entries() -> None:
    catalog = ProviderModelCatalog()
    entry = ModelCatalogEntry(
        name="dup-model",
        display_name="Dup",
        provider="test",
        capabilities=["text"],
        context_window=8000,
    )
    catalog.add(entry)
    duplicate = ModelCatalogEntry(
        name="dup-model",
        display_name="Dup 2",
        provider="test",
        capabilities=["text"],
        context_window=8000,
    )
    catalog._entries.append(duplicate)
    catalog._by_provider.setdefault("test", []).append(duplicate)
    errors = validate_catalog(catalog)
    assert any("Duplicate model name 'dup-model'" in err for err in errors)


def test_validate_catalog_catches_missing_capabilities() -> None:
    catalog = ProviderModelCatalog()
    bad = ModelCatalogEntry(
        name="bad-model",
        display_name="Bad",
        provider="test",
        capabilities=[],  # empty capabilities
        context_window=8000,
    )
    catalog._entries.append(bad)
    catalog._by_provider.setdefault("test", []).append(bad)
    errors = validate_catalog(catalog)
    assert any("capabilities" in e.lower() for e in errors), f"Expected capabilities error, got: {errors}"


def test_validate_catalog_catches_negative_context_window() -> None:
    catalog = ProviderModelCatalog()
    bad = ModelCatalogEntry(
        name="neg-context",
        display_name="Neg",
        provider="test",
        capabilities=["text"],
        context_window=-1,
    )
    catalog._entries.append(bad)
    catalog._by_provider.setdefault("test", []).append(bad)
    errors = validate_catalog(catalog)
    assert any("context" in e.lower() for e in errors), f"Expected context window error, got: {errors}"


# ---------------------------------------------------------------------------
# Load from catalog
# ---------------------------------------------------------------------------

def test_load_catalog_returns_copy() -> None:
    """load_catalog should return a fresh catalog instance."""
    catalog = load_catalog()
    assert isinstance(catalog, ProviderModelCatalog)
    assert catalog.list_providers() == MODEL_CATALOG.list_providers()


# ---------------------------------------------------------------------------
# Endpoint and auth consistency
# ---------------------------------------------------------------------------

def test_entries_with_endpoint_have_valid_url() -> None:
    """Entries with an endpoint should have a valid URL scheme."""
    import re
    url_pattern = re.compile(r"^https?://")
    for model in MODEL_CATALOG.list_models():
        if model.endpoint:
            assert url_pattern.match(model.endpoint), (
                f"Model '{model.name}' endpoint '{model.endpoint}' is not a valid URL"
            )


def test_entries_with_endpoint_have_auth_info() -> None:
    """Entries with an endpoint should have auth_type and auth_key_env set."""
    for model in MODEL_CATALOG.list_models():
        if model.endpoint:
            assert model.auth_type, f"Model '{model.name}' has endpoint but no auth_type"
            assert model.auth_key_env, f"Model '{model.name}' has endpoint but no auth_key_env"


# ---------------------------------------------------------------------------
# Model name uniqueness per provider
# ---------------------------------------------------------------------------

def test_no_duplicate_model_names_within_provider() -> None:
    seen: dict[str, set[str]] = {}
    for model in MODEL_CATALOG.list_models():
        if model.provider not in seen:
            seen[model.provider] = set()
        assert model.name not in seen[model.provider], (
            f"Duplicate model name '{model.name}' in provider '{model.provider}'"
        )
        seen[model.provider].add(model.name)
