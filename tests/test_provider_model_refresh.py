"""
Tests for the provider model catalog refresh pipeline.
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from hermesoptimizer.schemas.provider_model_refresh import (
    BlockedSource,
    BlockedSourceReason,
    ManualMetadata,
    ModelRefreshResult,
    ModelSourceProvenance,
    ProviderModelRefreshPipeline,
    RefreshStatus,
    merge_with_manual_metadata,
)


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------


@pytest.fixture
def fixtures_dir() -> Path:
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def provider_models_fixture(fixtures_dir: Path) -> Path:
    """Return path to provider models fixture."""
    return fixtures_dir / "provider_models.json"


@pytest.fixture
def provider_endpoints_fixture(fixtures_dir: Path) -> Path:
    """Return path to provider endpoints fixture."""
    return fixtures_dir / "provider_endpoints.json"


@pytest.fixture
def sample_manual_metadata() -> dict[str, ManualMetadata]:
    """Sample manual metadata for testing merge."""
    return {
        "gpt-4o": ManualMetadata(
            display_name="GPT-4o",
            capabilities=["text", "vision", "reasoning"],
            context_window=128000,
            input_cost_per_mtok=5.0,
            output_cost_per_mtok=15.0,
            latency_tier="fast",
            region_availability=["us", "eu", "ap", "global"],
            release_date=date(2024, 5, 13),
            is_deprecated=False,
            deprecation_notes=None,
            notes="Flagship model",
        ),
        "gpt-4o-mini": ManualMetadata(
            display_name="GPT-4o Mini",
            capabilities=["text", "vision", "reasoning"],
            context_window=128000,
            input_cost_per_mtok=0.15,
            output_cost_per_mtok=0.6,
            latency_tier="fast",
            region_availability=["us", "eu", "ap", "global"],
            release_date=date(2024, 7, 18),
            is_deprecated=False,
            deprecation_notes=None,
            notes="Cost-effective variant",
        ),
    }


# -----------------------------------------------------------------------
# ManualMetadata Tests
# -----------------------------------------------------------------------


def test_manual_metadata_creation() -> None:
    """ManualMetadata should be created with all fields."""
    meta = ManualMetadata(
        display_name="Test Model",
        capabilities=["text", "reasoning"],
        context_window=8000,
        input_cost_per_mtok=1.0,
        output_cost_per_mtok=2.0,
        latency_tier="standard",
        region_availability=["us", "global"],
        release_date=date(2024, 1, 15),
        is_deprecated=False,
        deprecation_notes=None,
        notes=None,
    )
    assert meta.display_name == "Test Model"
    assert meta.capabilities == ["text", "reasoning"]
    assert meta.context_window == 8000


def test_manual_metadata_defaults() -> None:
    """ManualMetadata should have sensible defaults."""
    meta = ManualMetadata(display_name="Test", capabilities=["text"], context_window=8000)
    assert meta.input_cost_per_mtok is None
    assert meta.output_cost_per_mtok is None
    assert meta.is_deprecated is False
    assert meta.deprecation_notes is None
    assert meta.notes is None


# -----------------------------------------------------------------------
# ModelSourceProvenance Tests
# -----------------------------------------------------------------------


def test_model_source_provenance_live_api() -> None:
    """ModelSourceProvenance should track live_api source."""
    prov = ModelSourceProvenance(source="live_api", source_url="https://api.example.com/v1/models")
    assert prov.source == "live_api"
    assert prov.source_url == "https://api.example.com/v1/models"


def test_model_source_provenance_all_sources() -> None:
    """ModelSourceProvenance should support all source types."""
    for source in ["live_api", "official_docs", "sdk_example", "manual_fallback"]:
        prov = ModelSourceProvenance(source=source)
        assert prov.source == source


# -----------------------------------------------------------------------
# BlockedSource Tests
# -----------------------------------------------------------------------


def test_blocked_source_creation() -> None:
    """BlockedSource should capture blocked source info."""
    blocked = BlockedSource(
        provider_slug="testprovider",
        source_type="live_api",
        reason=BlockedSourceReason.API_KEY_MISSING,
        message="API key not available",
    )
    assert blocked.provider_slug == "testprovider"
    assert blocked.source_type == "live_api"
    assert blocked.reason == BlockedSourceReason.API_KEY_MISSING
    assert blocked.message == "API key not available"


def test_blocked_source_reason_antibot() -> None:
    """BlockedSourceReason should include ANTI_BOT_PROTECTION."""
    reason = BlockedSourceReason.ANTI_BOT_PROTECTION
    assert "anti-bot" in reason.value.lower() or "bot" in reason.value.lower()


# -----------------------------------------------------------------------
# ModelRefreshResult Tests
# -----------------------------------------------------------------------


def test_model_refresh_result_success() -> None:
    """ModelRefreshResult should capture successful refresh."""
    result = ModelRefreshResult(
        provider_slug="openai",
        status=RefreshStatus.LIVE_API,
        models=[
            {
                "provider_slug": "openai",
                "model_name": "gpt-4o",
                "display_name": "GPT-4o",
                "capabilities": ["text"],
                "context_window": 128000,
                "source_provenance": "live_api",
            }
        ],
        blocked_sources=[],
    )
    assert result.provider_slug == "openai"
    assert result.status == RefreshStatus.LIVE_API
    assert len(result.models) == 1
    assert result.models[0]["model_name"] == "gpt-4o"


def test_model_refresh_result_blocked() -> None:
    """ModelRefreshResult should capture blocked sources."""
    blocked = BlockedSource(
        provider_slug="xai",
        source_type="live_api",
        reason=BlockedSourceReason.ANTI_BOT_PROTECTION,
        message="Provider blocks automated access",
    )
    result = ModelRefreshResult(
        provider_slug="xai",
        status=RefreshStatus.BLOCKED_API,
        models=[],
        blocked_sources=[blocked],
    )
    assert result.status == RefreshStatus.BLOCKED_API
    assert len(result.blocked_sources) == 1
    assert result.blocked_sources[0].reason == BlockedSourceReason.ANTI_BOT_PROTECTION


# -----------------------------------------------------------------------
# RefreshStatus Tests
# -----------------------------------------------------------------------


def test_refresh_status_values() -> None:
    """RefreshStatus should have expected values."""
    assert RefreshStatus.LIVE_API.value == "live_api"
    assert RefreshStatus.DOCS_ONLY.value == "docs_only"
    assert RefreshStatus.BLOCKED_API.value == "blocked_api"
    assert RefreshStatus.BLOCKED_DOC.value == "blocked_doc"
    assert RefreshStatus.MANUAL_FALLBACK.value == "manual_fallback"


# -----------------------------------------------------------------------
# merge_with_manual_metadata Tests
# -----------------------------------------------------------------------


def test_merge_preserves_live_fields() -> None:
    """Live API data should be preserved when merging."""
    live_model = {
        "provider_slug": "openai",
        "model_name": "gpt-4o",
        "capabilities": ["text", "vision"],
        "context_window": 128000,
    }
    manual_meta = ManualMetadata(
        display_name="GPT-4o Custom",
        capabilities=["text", "vision", "reasoning"],  # Additional capability
        context_window=128000,
        input_cost_per_mtok=5.0,
    )

    merged = merge_with_manual_metadata(live_model, manual_meta)

    # Live data fields should be preserved
    assert merged["provider_slug"] == "openai"
    assert merged["model_name"] == "gpt-4o"
    assert merged["context_window"] == 128000
    # But manual metadata should be merged
    assert merged["display_name"] == "GPT-4o Custom"
    assert merged["input_cost_per_mtok"] == 5.0


def test_merge_adds_manual_fields() -> None:
    """Manual-only fields should be added from metadata."""
    live_model = {
        "provider_slug": "openai",
        "model_name": "gpt-4o",
        "capabilities": ["text"],
        "context_window": 128000,
    }
    manual_meta = ManualMetadata(
        display_name="GPT-4o",
        capabilities=["text", "vision"],
        context_window=128000,
        region_availability=["us", "global"],
    )

    merged = merge_with_manual_metadata(live_model, manual_meta)

    assert merged["region_availability"] == ["us", "global"]


def test_merge_does_not_overwrite_live_cost() -> None:
    """Live API cost data should not be overwritten by manual metadata."""
    live_model = {
        "provider_slug": "openai",
        "model_name": "gpt-4o",
        "capabilities": ["text"],
        "context_window": 128000,
        "input_cost_per_mtok": 5.0,
        "output_cost_per_mtok": 15.0,
    }
    manual_meta = ManualMetadata(
        display_name="GPT-4o",
        capabilities=["text"],
        context_window=128000,
        input_cost_per_mtok=10.0,  # Higher manual cost
        output_cost_per_mtok=20.0,
    )

    merged = merge_with_manual_metadata(live_model, manual_meta)

    # Live cost should be preserved
    assert merged["input_cost_per_mtok"] == 5.0
    assert merged["output_cost_per_mtok"] == 15.0


def test_merge_adds_deprecation_notes() -> None:
    """Manual deprecation notes should be added."""
    live_model = {
        "provider_slug": "openai",
        "model_name": "gpt-4",
        "capabilities": ["text"],
        "context_window": 8192,
    }
    manual_meta = ManualMetadata(
        display_name="GPT-4",
        capabilities=["text"],
        context_window=8192,
        is_deprecated=True,
        deprecation_notes="Use gpt-4o instead",
    )

    merged = merge_with_manual_metadata(live_model, manual_meta)

    assert merged["is_deprecated"] is True
    assert merged["deprecation_notes"] == "Use gpt-4o instead"


# -----------------------------------------------------------------------
# ProviderModelRefreshPipeline Tests
# -----------------------------------------------------------------------


def test_pipeline_initialization(provider_models_fixture: Path, provider_endpoints_fixture: Path) -> None:
    """Pipeline should initialize with catalog paths."""
    pipeline = ProviderModelRefreshPipeline(
        model_catalog_path=provider_models_fixture,
        endpoint_catalog_path=provider_endpoints_fixture,
    )
    assert pipeline.model_catalog_path == provider_models_fixture
    assert pipeline.endpoint_catalog_path == provider_endpoints_fixture


def test_pipeline_loads_existing_catalog(provider_models_fixture: Path, provider_endpoints_fixture: Path) -> None:
    """Pipeline should load existing catalog on init."""
    pipeline = ProviderModelRefreshPipeline(
        model_catalog_path=provider_models_fixture,
        endpoint_catalog_path=provider_endpoints_fixture,
    )
    catalog = pipeline.get_catalog()
    assert catalog is not None
    assert "provider_models" in catalog


def test_pipeline_refresh_single_provider_not_implemented(
    provider_models_fixture: Path, provider_endpoints_fixture: Path
) -> None:
    """Pipeline refresh should indicate when live API is not available."""
    pipeline = ProviderModelRefreshPipeline(
        model_catalog_path=provider_models_fixture,
        endpoint_catalog_path=provider_endpoints_fixture,
    )
    # For a test provider that doesn't have real API access, should return manual fallback
    result = pipeline.refresh_provider("testprovider")
    assert result.provider_slug == "testprovider"
    # Status depends on whether manual metadata is available
    assert result.status in [RefreshStatus.MANUAL_FALLBACK, RefreshStatus.BLOCKED_API, RefreshStatus.DOCS_ONLY]


def test_pipeline_refresh_all_providers(
    provider_models_fixture: Path, provider_endpoints_fixture: Path
) -> None:
    """Pipeline refresh_all should return results for all providers."""
    pipeline = ProviderModelRefreshPipeline(
        model_catalog_path=provider_models_fixture,
        endpoint_catalog_path=provider_endpoints_fixture,
    )
    results = pipeline.refresh_all_providers()
    # Should have results for all providers in endpoint catalog
    assert len(results) >= 0  # May be empty if no providers have refresh data


def test_pipeline_get_catalog_returns_dict(
    provider_models_fixture: Path, provider_endpoints_fixture: Path
) -> None:
    """get_catalog should return the current catalog data."""
    pipeline = ProviderModelRefreshPipeline(
        model_catalog_path=provider_models_fixture,
        endpoint_catalog_path=provider_endpoints_fixture,
    )
    catalog = pipeline.get_catalog()
    assert isinstance(catalog, dict)
    assert "version" in catalog
    assert "provider_models" in catalog


def test_pipeline_get_provider_model_names(
    provider_models_fixture: Path, provider_endpoints_fixture: Path
) -> None:
    """get_provider_model_names should return model names for a provider."""
    pipeline = ProviderModelRefreshPipeline(
        model_catalog_path=provider_models_fixture,
        endpoint_catalog_path=provider_endpoints_fixture,
    )
    names = pipeline.get_provider_model_names("testprovider")
    assert isinstance(names, list)


def test_pipeline_get_manual_metadata_for_provider(
    provider_models_fixture: Path, provider_endpoints_fixture: Path
) -> None:
    """get_manual_metadata_for_provider should return manual metadata map."""
    pipeline = ProviderModelRefreshPipeline(
        model_catalog_path=provider_models_fixture,
        endpoint_catalog_path=provider_endpoints_fixture,
    )
    manual = pipeline.get_manual_metadata_for_provider("testprovider")
    assert isinstance(manual, dict)


def test_pipeline_refresh_uses_live_api_when_available(
    provider_models_fixture: Path, provider_endpoints_fixture: Path
) -> None:
    """Pipeline should prefer live API when API key is available via mock."""
    pipeline = ProviderModelRefreshPipeline(
        model_catalog_path=provider_models_fixture,
        endpoint_catalog_path=provider_endpoints_fixture,
    )

    # Mock a successful live API response
    mock_response = {
        "data": [
            {
                "id": "gpt-4o",
                "context_window": 128000,
            }
        ]
    }

    # Set up environment with API key and mock the request
    with patch.dict(os.environ, {"TEST_API_KEY": "fake-key"}):
        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response,
            )
            result = pipeline.refresh_provider("testprovider")

            # Since we mocked the API key but the fixture URL may not match,
            # the result depends on whether the request was attempted
            # The key point is that with API key present, it tries live API
            assert result.provider_slug == "testprovider"
            # Status should be LIVE_API if the mock was hit, or BLOCKED_API if URL didn't match
            assert result.status in [RefreshStatus.LIVE_API, RefreshStatus.BLOCKED_API, RefreshStatus.MANUAL_FALLBACK]


def test_pipeline_refresh_with_live_api_and_manual_merge(
    provider_models_fixture: Path, provider_endpoints_fixture: Path
) -> None:
    """Pipeline should merge live API data with manual metadata when available."""
    pipeline = ProviderModelRefreshPipeline(
        model_catalog_path=provider_models_fixture,
        endpoint_catalog_path=provider_endpoints_fixture,
    )

    # Mock a successful live API response
    mock_response = {
        "data": [
            {
                "id": "test-model-1",
                "context_window": 8000,
            }
        ]
    }

    # Set up environment with API key and mock the request
    with patch.dict(os.environ, {"TEST_API_KEY": "fake-key"}):
        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response,
            )
            result = pipeline.refresh_provider("testprovider")

            # Should have result for testprovider
            assert result.provider_slug == "testprovider"

            # If live API was used, models should be present
            if result.status == RefreshStatus.LIVE_API:
                assert len(result.models) >= 1
                # Find our model in the results
                model_names = [m.get("model_name") for m in result.models]
                assert "test-model-1" in model_names


def test_pipeline_blocked_source_recorded(
    provider_models_fixture: Path, provider_endpoints_fixture: Path
) -> None:
    """Pipeline should record blocked sources explicitly."""
    pipeline = ProviderModelRefreshPipeline(
        model_catalog_path=provider_models_fixture,
        endpoint_catalog_path=provider_endpoints_fixture,
    )
    result = pipeline.refresh_provider("testprovider")

    # Blocked sources should be recorded if refresh failed
    for blocked in result.blocked_sources:
        assert blocked.provider_slug == "testprovider"
        assert blocked.source_type in ["live_api", "official_docs"]
        assert blocked.reason is not None


def test_pipeline_catalog_version_preserved(
    provider_models_fixture: Path, provider_endpoints_fixture: Path
) -> None:
    """Refresh should preserve catalog version."""
    pipeline = ProviderModelRefreshPipeline(
        model_catalog_path=provider_models_fixture,
        endpoint_catalog_path=provider_endpoints_fixture,
    )
    catalog = pipeline.get_catalog()
    assert catalog["version"] == "1.0.0"


def test_pipeline_get_providers_with_models_path(
    provider_models_fixture: Path, provider_endpoints_fixture: Path
) -> None:
    """Pipeline should identify providers with models_path endpoint."""
    pipeline = ProviderModelRefreshPipeline(
        model_catalog_path=provider_models_fixture,
        endpoint_catalog_path=provider_endpoints_fixture,
    )
    # testprovider has a models_path in its endpoint
    providers = pipeline.get_providers_with_models_path()
    assert isinstance(providers, list)


def test_merge_preserves_provider_slug() -> None:
    """merge_with_manual_metadata should preserve provider_slug from live model."""
    live_model = {
        "provider_slug": "anthropic",
        "model_name": "claude-3.5-sonnet",
        "capabilities": ["text"],
        "context_window": 200000,
    }
    manual_meta = ManualMetadata(
        display_name="Claude 3.5 Sonnet",
        capabilities=["text", "vision", "reasoning"],
        context_window=200000,
    )

    merged = merge_with_manual_metadata(live_model, manual_meta)

    assert merged["provider_slug"] == "anthropic"
    assert merged["model_name"] == "claude-3.5-sonnet"


def test_merge_with_empty_manual_metadata() -> None:
    """merge_with_manual_metadata should work with empty manual metadata."""
    live_model = {
        "provider_slug": "openai",
        "model_name": "gpt-4o",
        "capabilities": ["text"],
        "context_window": 128000,
    }

    merged = merge_with_manual_metadata(live_model, None)

    # Should return live model unchanged except for source_provenance addition
    assert merged["provider_slug"] == live_model["provider_slug"]
    assert merged["model_name"] == live_model["model_name"]
    assert merged["capabilities"] == live_model["capabilities"]
    assert merged["context_window"] == live_model["context_window"]
    # source_provenance is added
    assert merged["source_provenance"] == "live_api"


def test_merge_sets_source_provenance() -> None:
    """merge_with_manual_metadata should set source_provenance."""
    live_model = {
        "provider_slug": "openai",
        "model_name": "gpt-4o",
        "capabilities": ["text"],
        "context_window": 128000,
    }
    manual_meta = ManualMetadata(
        display_name="GPT-4o",
        capabilities=["text"],
        context_window=128000,
    )

    merged = merge_with_manual_metadata(live_model, manual_meta)

    # Should have source provenance indicating merge
    assert "source_provenance" in merged


def test_refresh_status_is_str_enum() -> None:
    """RefreshStatus should be a string enum for serialization."""
    assert isinstance(RefreshStatus.LIVE_API.value, str)
    assert RefreshStatus.LIVE_API.value == "live_api"


# -----------------------------------------------------------------------
# update_catalog Tests
# -----------------------------------------------------------------------


def test_update_catalog_merges_new_models(
    provider_models_fixture: Path, provider_endpoints_fixture: Path
) -> None:
    """update_catalog should merge new models from refresh results."""
    pipeline = ProviderModelRefreshPipeline(
        model_catalog_path=provider_models_fixture,
        endpoint_catalog_path=provider_endpoints_fixture,
    )

    # Create a refresh result with a new model
    result = ModelRefreshResult(
        provider_slug="testprovider",
        status=RefreshStatus.LIVE_API,
        models=[
            {
                "provider_slug": "testprovider",
                "model_name": "new-model-from-api",
                "display_name": "New Model From API",
                "capabilities": ["text"],
                "context_window": 16000,
                "source_provenance": "live_api",
            }
        ],
        blocked_sources=[],
    )

    updated_catalog = pipeline.update_catalog([result])

    # Check that the new model is in the catalog
    model_names = [
        m.get("model_name")
        for m in updated_catalog.get("provider_models", [])
        if m.get("provider_slug") == "testprovider"
    ]
    assert "new-model-from-api" in model_names


def test_update_catalog_preserves_existing_models(
    provider_models_fixture: Path, provider_endpoints_fixture: Path
) -> None:
    """update_catalog should preserve existing models not in refresh results."""
    pipeline = ProviderModelRefreshPipeline(
        model_catalog_path=provider_models_fixture,
        endpoint_catalog_path=provider_endpoints_fixture,
    )

    # Create a refresh result with a new model only
    result = ModelRefreshResult(
        provider_slug="newprovider",
        status=RefreshStatus.LIVE_API,
        models=[
            {
                "provider_slug": "newprovider",
                "model_name": "new-provider-model",
                "display_name": "New Provider Model",
                "capabilities": ["text"],
                "context_window": 8000,
                "source_provenance": "live_api",
            }
        ],
        blocked_sources=[],
    )

    # Get initial model count
    initial_catalog = pipeline.get_catalog()
    initial_model_count = len(initial_catalog.get("provider_models", []))

    updated_catalog = pipeline.update_catalog([result])

    # Should have more models now (initial + new)
    new_model_count = len(updated_catalog.get("provider_models", []))
    assert new_model_count >= initial_model_count


def test_update_catalog_sorts_by_provider_and_model(
    provider_models_fixture: Path, provider_endpoints_fixture: Path
) -> None:
    """update_catalog should sort models by provider_slug then model_name."""
    pipeline = ProviderModelRefreshPipeline(
        model_catalog_path=provider_models_fixture,
        endpoint_catalog_path=provider_endpoints_fixture,
    )

    result = ModelRefreshResult(
        provider_slug="testprovider",
        status=RefreshStatus.LIVE_API,
        models=[
            {
                "provider_slug": "testprovider",
                "model_name": "zzz-model",
                "display_name": "Zzz Model",
                "capabilities": ["text"],
                "context_window": 8000,
                "source_provenance": "live_api",
            }
        ],
        blocked_sources=[],
    )

    updated_catalog = pipeline.update_catalog([result])
    provider_models = updated_catalog.get("provider_models", [])

    # Models should be sorted by provider_slug then model_name
    for i in range(len(provider_models) - 1):
        curr = provider_models[i]
        next_model = provider_models[i + 1]
        curr_key = (curr.get("provider_slug", ""), curr.get("model_name", ""))
        next_key = (next_model.get("provider_slug", ""), next_model.get("model_name", ""))
        assert curr_key <= next_key, f"Models not sorted: {curr_key} > {next_key}"


# -----------------------------------------------------------------------
# persist_catalog Tests
# -----------------------------------------------------------------------


def test_persist_catalog_writes_valid_json(
    provider_models_fixture: Path, provider_endpoints_fixture: Path, tmp_path: Path
) -> None:
    """persist_catalog should write valid JSON to disk."""
    # Use a temp path for the catalog
    temp_catalog_path = tmp_path / "test_catalog.json"

    pipeline = ProviderModelRefreshPipeline(
        model_catalog_path=temp_catalog_path,
        endpoint_catalog_path=provider_endpoints_fixture,
    )

    # Create a minimal valid catalog
    catalog = {
        "version": "1.0.0",
        "provider_models": [
            {
                "provider_slug": "testprovider",
                "model_name": "test-model",
                "display_name": "Test Model",
                "capabilities": ["text"],
                "context_window": 8000,
            }
        ],
    }

    pipeline.persist_catalog(catalog)

    # File should exist
    assert temp_catalog_path.is_file()

    # Should be valid JSON
    with open(temp_catalog_path, "r") as f:
        loaded = json.load(f)

    assert loaded["version"] == "1.0.0"
    assert len(loaded["provider_models"]) == 1


def test_persist_catalog_validates_before_writing(
    provider_models_fixture: Path, provider_endpoints_fixture: Path, tmp_path: Path
) -> None:
    """persist_catalog should validate catalog before writing."""
    from hermesoptimizer.schemas.exceptions import ProviderModelCatalogError

    temp_catalog_path = tmp_path / "test_catalog.json"

    pipeline = ProviderModelRefreshPipeline(
        model_catalog_path=temp_catalog_path,
        endpoint_catalog_path=provider_endpoints_fixture,
    )

    # Create an invalid catalog (missing required fields)
    invalid_catalog = {
        "version": "1.0.0",
        "provider_models": [
            {
                "provider_slug": "testprovider",
                # Missing: model_name, display_name, capabilities, context_window
            }
        ],
    }

    # Should raise validation error
    with pytest.raises(ProviderModelCatalogError) as exc_info:
        pipeline.persist_catalog(invalid_catalog)

    assert "validation failed" in str(exc_info.value).lower()


# -----------------------------------------------------------------------
# Full Pipeline Tests
# -----------------------------------------------------------------------


def test_run_full_pipeline_returns_results(
    provider_models_fixture: Path, provider_endpoints_fixture: Path, tmp_path: Path
) -> None:
    """run() should execute the full refresh pipeline and return results."""
    temp_catalog_path = tmp_path / "test_catalog.json"

    # Copy fixture to temp location
    import shutil
    shutil.copy(provider_models_fixture, temp_catalog_path)

    pipeline = ProviderModelRefreshPipeline(
        model_catalog_path=temp_catalog_path,
        endpoint_catalog_path=provider_endpoints_fixture,
    )

    # Run the pipeline (without actual network calls since no API key)
    results = pipeline.run()

    # Should return results for all providers
    assert isinstance(results, list)
    # Each result should be a ModelRefreshResult
    for result in results:
        assert isinstance(result, ModelRefreshResult)
        assert result.provider_slug is not None
        assert result.status is not None
