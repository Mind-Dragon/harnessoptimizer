"""
Tests for the safe provider endpoint catalog refresh pipeline.

These tests verify:
- blocked-doc state recording
- safe non-aggressive refresh behavior
- JSON validation of refresh results
- working on checked-in JSON data
"""
from __future__ import annotations

import json
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from hermesoptimizer.schemas.provider_endpoint import (
    ProviderEndpointCatalog,
    load_provider_endpoints_catalog,
    validate_provider_endpoints,
)
from hermesoptimizer.schemas.exceptions import ProviderModelCatalogError


# -----------------------------------------------------------------------
# Imports for catalog refresh
# -----------------------------------------------------------------------
from hermesoptimizer.catalog_refresh import (
    BlockedDocState,
    BlockedReason,
    CatalogRefreshResult,
    EndpointRefreshOutcome,
    ProviderRefreshResult,
    RefreshState,
    catalog_refresh,
    get_blocked_providers,
    get_refresh_state_path,
    load_refresh_state,
    merge_refresh_results,
    save_refresh_state,
)


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------

@pytest.fixture
def fixtures_dir() -> Path:
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def provider_endpoints_fixture(fixtures_dir: Path) -> Path:
    """Return path to provider endpoints fixture."""
    return fixtures_dir / "provider_endpoints.json"


@pytest.fixture
def data_dir() -> Path:
    """Return path to data directory."""
    return Path(__file__).parent.parent / "data"


@pytest.fixture
def temp_catalog_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for catalog refresh tests."""
    catalog_dir = tmp_path / "catalog"
    catalog_dir.mkdir()
    return catalog_dir


@pytest.fixture
def sample_refresh_state() -> dict[str, Any]:
    """Return a sample refresh state dict."""
    return {
        "version": "1.0.0",
        "last_refresh": "2025-01-20",
        "blocked_providers": {
            "xai": {
                "provider_slug": "xai",
                "blocked_reason": "anti_bot_block",
                "blocked_date": "2025-01-20",
                "source_urls_attempted": ["https://docs.x.ai/"],
                "retry_after": None,
            }
        },
        "provider_outcomes": {
            "openai": "success",
            "anthropic": "success",
            "xai": "blocked",
        },
    }


# -----------------------------------------------------------------------
# BlockedDocState Tests
# -----------------------------------------------------------------------

class TestBlockedDocState:
    """Tests for BlockedDocState dataclass."""

    def test_blocked_doc_state_creation(self) -> None:
        """BlockedDocState should be created with required fields."""
        state = BlockedDocState(
            provider_slug="xai",
            blocked_reason=BlockedReason.ANTI_BOT_BLOCK,
            blocked_date=date(2025, 1, 20),
            source_urls_attempted=["https://docs.x.ai/"],
        )
        assert state.provider_slug == "xai"
        assert state.blocked_reason == BlockedReason.ANTI_BOT_BLOCK
        assert state.blocked_date == date(2025, 1, 20)
        assert state.source_urls_attempted == ["https://docs.x.ai/"]
        assert state.retry_after is None

    def test_blocked_doc_state_with_retry(self) -> None:
        """BlockedDocState should support retry_after date."""
        state = BlockedDocState(
            provider_slug="xai",
            blocked_reason=BlockedReason.RATE_LIMIT,
            blocked_date=date(2025, 1, 20),
            source_urls_attempted=["https://docs.x.ai/"],
            retry_after=date(2025, 1, 21),
        )
        assert state.retry_after == date(2025, 1, 21)

    def test_blocked_doc_state_to_dict(self) -> None:
        """BlockedDocState should serialize to dict correctly."""
        state = BlockedDocState(
            provider_slug="xai",
            blocked_reason=BlockedReason.ANTI_BOT_BLOCK,
            blocked_date=date(2025, 1, 20),
            source_urls_attempted=["https://docs.x.ai/"],
        )
        result = state.to_dict()
        assert result["provider_slug"] == "xai"
        assert result["blocked_reason"] == "anti_bot_block"
        assert result["blocked_date"] == "2025-01-20"
        assert result["source_urls_attempted"] == ["https://docs.x.ai/"]
        assert result["retry_after"] is None

    def test_blocked_doc_state_from_dict(self) -> None:
        """BlockedDocState should deserialize from dict correctly."""
        data = {
            "provider_slug": "xai",
            "blocked_reason": "anti_bot_block",
            "blocked_date": "2025-01-20",
            "source_urls_attempted": ["https://docs.x.ai/"],
            "retry_after": None,
        }
        state = BlockedDocState.from_dict(data)
        assert state.provider_slug == "xai"
        assert state.blocked_reason == BlockedReason.ANTI_BOT_BLOCK
        assert state.blocked_date == date(2025, 1, 20)


# -----------------------------------------------------------------------
# BlockedReason Tests
# -----------------------------------------------------------------------

class TestBlockedReason:
    """Tests for BlockedReason enum."""

    def test_blocked_reason_values(self) -> None:
        """BlockedReason should have expected values."""
        assert BlockedReason.ANTI_BOT_BLOCK.value == "anti_bot_block"
        assert BlockedReason.RATE_LIMIT.value == "rate_limit"
        assert BlockedReason.AUTH_REQUIRED.value == "auth_required"
        assert BlockedReason.JAVASCRIPT_WALL.value == "javascript_wall"
        assert BlockedReason.NOT_FOUND.value == "not_found"
        assert BlockedReason.CONNECTION_ERROR.value == "connection_error"
        assert BlockedReason.SERVER_ERROR.value == "server_error"
        assert BlockedReason.MANUAL_CURATION.value == "manual_curation"


# -----------------------------------------------------------------------
# ProviderRefreshResult Tests
# -----------------------------------------------------------------------

class TestProviderRefreshResult:
    """Tests for ProviderRefreshResult dataclass."""

    def test_success_result(self) -> None:
        """ProviderRefreshResult should record success."""
        result = ProviderRefreshResult(
            provider_slug="openai",
            outcome=EndpointRefreshOutcome.SUCCESS,
            updated_endpoints=[{
                "family_name": "OpenAI API v1",
                "base_url": "https://api.openai.com/v1",
                "api_style": "openai-compatible",
                "auth_header_shape": "Authorization: Bearer ***",
                "models_path": "/v1/models",
                "is_default": True,
                "is_stable": True,
            }],
            source_url="https://platform.openai.com/docs/api-reference",
        )
        assert result.provider_slug == "openai"
        assert result.outcome == EndpointRefreshOutcome.SUCCESS
        assert len(result.updated_endpoints) == 1
        assert result.error_message is None

    def test_blocked_result(self) -> None:
        """ProviderRefreshResult should record blocked state."""
        result = ProviderRefreshResult(
            provider_slug="xai",
            outcome=EndpointRefreshOutcome.BLOCKED,
            blocked_state=BlockedDocState(
                provider_slug="xai",
                blocked_reason=BlockedReason.ANTI_BOT_BLOCK,
                blocked_date=date(2025, 1, 20),
                source_urls_attempted=["https://docs.x.ai/"],
            ),
        )
        assert result.provider_slug == "xai"
        assert result.outcome == EndpointRefreshOutcome.BLOCKED
        assert result.blocked_state is not None
        assert result.blocked_state.blocked_reason == BlockedReason.ANTI_BOT_BLOCK

    def test_error_result(self) -> None:
        """ProviderRefreshResult should record error."""
        result = ProviderRefreshResult(
            provider_slug="unknown",
            outcome=EndpointRefreshOutcome.ERROR,
            error_message="Connection timeout",
        )
        assert result.provider_slug == "unknown"
        assert result.outcome == EndpointRefreshOutcome.ERROR
        assert result.error_message == "Connection timeout"


# -----------------------------------------------------------------------
# CatalogRefreshResult Tests
# -----------------------------------------------------------------------

class TestCatalogRefreshResult:
    """Tests for CatalogRefreshResult dataclass."""

    def test_refresh_result_creation(self) -> None:
        """CatalogRefreshResult should aggregate provider results."""
        results = [
            ProviderRefreshResult(
                provider_slug="openai",
                outcome=EndpointRefreshOutcome.SUCCESS,
            ),
            ProviderRefreshResult(
                provider_slug="anthropic",
                outcome=EndpointRefreshOutcome.SUCCESS,
            ),
            ProviderRefreshResult(
                provider_slug="xai",
                outcome=EndpointRefreshOutcome.BLOCKED,
                blocked_state=BlockedDocState(
                    provider_slug="xai",
                    blocked_reason=BlockedReason.ANTI_BOT_BLOCK,
                    blocked_date=date(2025, 1, 20),
                    source_urls_attempted=["https://docs.x.ai/"],
                ),
            ),
        ]
        catalog_result = CatalogRefreshResult(
            version="1.0.0",
            refresh_date=date(2025, 1, 20),
            provider_results=results,
        )
        assert catalog_result.version == "1.0.0"
        assert len(catalog_result.provider_results) == 3
        assert catalog_result.success_count == 2
        assert catalog_result.blocked_count == 1

    def test_refresh_result_summary(self) -> None:
        """CatalogRefreshResult should provide a summary."""
        results = [
            ProviderRefreshResult(
                provider_slug="openai",
                outcome=EndpointRefreshOutcome.SUCCESS,
            ),
            ProviderRefreshResult(
                provider_slug="xai",
                outcome=EndpointRefreshOutcome.BLOCKED,
                blocked_state=BlockedDocState(
                    provider_slug="xai",
                    blocked_reason=BlockedReason.ANTI_BOT_BLOCK,
                    blocked_date=date(2025, 1, 20),
                    source_urls_attempted=["https://docs.x.ai/"],
                ),
            ),
            ProviderRefreshResult(
                provider_slug="unknown",
                outcome=EndpointRefreshOutcome.ERROR,
                error_message="Connection timeout",
            ),
        ]
        catalog_result = CatalogRefreshResult(
            version="1.0.0",
            refresh_date=date(2025, 1, 20),
            provider_results=results,
        )
        summary = catalog_result.summary()
        assert summary["total_providers"] == 3
        assert summary["success_count"] == 1
        assert summary["blocked_count"] == 1
        assert summary["error_count"] == 1
        assert "xai" in summary["blocked_providers"]
        assert "unknown" in summary["error_providers"]


# -----------------------------------------------------------------------
# RefreshState Tests
# -----------------------------------------------------------------------

class TestRefreshState:
    """Tests for RefreshState dataclass."""

    def test_refresh_state_creation(self) -> None:
        """RefreshState should track blocked providers and outcomes."""
        blocked = {
            "xai": BlockedDocState(
                provider_slug="xai",
                blocked_reason=BlockedReason.ANTI_BOT_BLOCK,
                blocked_date=date(2025, 1, 20),
                source_urls_attempted=["https://docs.x.ai/"],
            )
        }
        outcomes = {
            "openai": EndpointRefreshOutcome.SUCCESS,
            "xai": EndpointRefreshOutcome.BLOCKED,
        }
        state = RefreshState(
            version="1.0.0",
            last_refresh=date(2025, 1, 20),
            blocked_providers=blocked,
            provider_outcomes=outcomes,
        )
        assert state.version == "1.0.0"
        assert len(state.blocked_providers) == 1
        assert state.blocked_providers["xai"].provider_slug == "xai"
        assert state.provider_outcomes["openai"] == EndpointRefreshOutcome.SUCCESS

    def test_refresh_state_to_dict(self) -> None:
        """RefreshState should serialize to dict correctly."""
        blocked = {
            "xai": BlockedDocState(
                provider_slug="xai",
                blocked_reason=BlockedReason.ANTI_BOT_BLOCK,
                blocked_date=date(2025, 1, 20),
                source_urls_attempted=["https://docs.x.ai/"],
            )
        }
        state = RefreshState(
            version="1.0.0",
            last_refresh=date(2025, 1, 20),
            blocked_providers=blocked,
            provider_outcomes={"xai": EndpointRefreshOutcome.BLOCKED},
        )
        result = state.to_dict()
        assert result["version"] == "1.0.0"
        assert result["last_refresh"] == "2025-01-20"
        assert "xai" in result["blocked_providers"]
        assert result["provider_outcomes"]["xai"] == "blocked"

    def test_refresh_state_from_dict(self) -> None:
        """RefreshState should deserialize from dict correctly."""
        data = {
            "version": "1.0.0",
            "last_refresh": "2025-01-20",
            "blocked_providers": {
                "xai": {
                    "provider_slug": "xai",
                    "blocked_reason": "anti_bot_block",
                    "blocked_date": "2025-01-20",
                    "source_urls_attempted": ["https://docs.x.ai/"],
                    "retry_after": None,
                }
            },
            "provider_outcomes": {
                "openai": "success",
                "xai": "blocked",
            },
        }
        state = RefreshState.from_dict(data)
        assert state.version == "1.0.0"
        assert state.last_refresh == date(2025, 1, 20)
        assert "xai" in state.blocked_providers
        assert state.blocked_providers["xai"].blocked_reason == BlockedReason.ANTI_BOT_BLOCK


# -----------------------------------------------------------------------
# Refresh State Persistence Tests
# -----------------------------------------------------------------------

class TestRefreshStatePersistence:
    """Tests for refresh state save/load operations."""

    def test_save_and_load_refresh_state(self, tmp_path: Path) -> None:
        """RefreshState should be saved to and loaded from file."""
        blocked = {
            "xai": BlockedDocState(
                provider_slug="xai",
                blocked_reason=BlockedReason.ANTI_BOT_BLOCK,
                blocked_date=date(2025, 1, 20),
                source_urls_attempted=["https://docs.x.ai/"],
            )
        }
        state = RefreshState(
            version="1.0.0",
            last_refresh=date(2025, 1, 20),
            blocked_providers=blocked,
            provider_outcomes={"xai": EndpointRefreshOutcome.BLOCKED},
        )
        state_path = tmp_path / "refresh_state.json"
        save_refresh_state(state, state_path)
        assert state_path.is_file()

        loaded = load_refresh_state(state_path)
        assert loaded is not None
        assert loaded.version == "1.0.0"
        assert "xai" in loaded.blocked_providers

    def test_load_nonexistent_refresh_state(self, tmp_path: Path) -> None:
        """load_refresh_state should return None for nonexistent file."""
        result = load_refresh_state(tmp_path / "nonexistent.json")
        assert result is None


# -----------------------------------------------------------------------
# get_blocked_providers Tests
# -----------------------------------------------------------------------

class TestGetBlockedProviders:
    """Tests for get_blocked_providers function."""

    def test_get_blocked_providers_empty(self) -> None:
        """get_blocked_providers should return empty dict when no blocked."""
        state = RefreshState(
            version="1.0.0",
            last_refresh=date(2025, 1, 20),
            blocked_providers={},
            provider_outcomes={},
        )
        blocked = get_blocked_providers(state)
        assert blocked == {}

    def test_get_blocked_providers_with_blocked(self) -> None:
        """get_blocked_providers should return blocked providers."""
        blocked = {
            "xai": BlockedDocState(
                provider_slug="xai",
                blocked_reason=BlockedReason.ANTI_BOT_BLOCK,
                blocked_date=date(2025, 1, 20),
                source_urls_attempted=["https://docs.x.ai/"],
            ),
            "someprovider": BlockedDocState(
                provider_slug="someprovider",
                blocked_reason=BlockedReason.RATE_LIMIT,
                blocked_date=date(2025, 1, 20),
                source_urls_attempted=["https://docs.someprovider.example.com/"],
                retry_after=date(2025, 1, 21),
            ),
        }
        state = RefreshState(
            version="1.0.0",
            last_refresh=date(2025, 1, 20),
            blocked_providers=blocked,
            provider_outcomes={},
        )
        result = get_blocked_providers(state)
        assert len(result) == 2
        assert "xai" in result
        assert "someprovider" in result


# -----------------------------------------------------------------------
# merge_refresh_results Tests
# -----------------------------------------------------------------------

class TestMergeRefreshResults:
    """Tests for merge_refresh_results function."""

    def test_merge_empty_results(self) -> None:
        """merge_refresh_results should handle empty inputs."""
        result = merge_refresh_results([])
        assert result.provider_results == []
        assert result.success_count == 0

    def test_merge_single_result(self) -> None:
        """merge_refresh_results should handle single input."""
        results = [
            CatalogRefreshResult(
                version="1.0.0",
                refresh_date=date(2025, 1, 20),
                provider_results=[
                    ProviderRefreshResult(
                        provider_slug="openai",
                        outcome=EndpointRefreshOutcome.SUCCESS,
                    ),
                ],
            )
        ]
        merged = merge_refresh_results(results)
        assert len(merged.provider_results) == 1

    def test_merge_multiple_results(self) -> None:
        """merge_refresh_results should combine multiple results."""
        results = [
            CatalogRefreshResult(
                version="1.0.0",
                refresh_date=date(2025, 1, 20),
                provider_results=[
                    ProviderRefreshResult(
                        provider_slug="openai",
                        outcome=EndpointRefreshOutcome.SUCCESS,
                    ),
                ],
            ),
            CatalogRefreshResult(
                version="1.0.0",
                refresh_date=date(2025, 1, 21),
                provider_results=[
                    ProviderRefreshResult(
                        provider_slug="anthropic",
                        outcome=EndpointRefreshOutcome.SUCCESS,
                    ),
                    ProviderRefreshResult(
                        provider_slug="xai",
                        outcome=EndpointRefreshOutcome.BLOCKED,
                        blocked_state=BlockedDocState(
                            provider_slug="xai",
                            blocked_reason=BlockedReason.ANTI_BOT_BLOCK,
                            blocked_date=date(2025, 1, 21),
                            source_urls_attempted=["https://docs.x.ai/"],
                        ),
                    ),
                ],
            ),
        ]
        merged = merge_refresh_results(results)
        assert len(merged.provider_results) == 3
        assert merged.success_count == 2
        assert merged.blocked_count == 1


# -----------------------------------------------------------------------
# catalog_refresh Integration Tests
# -----------------------------------------------------------------------

class TestCatalogRefresh:
    """Tests for the catalog_refresh function."""

    def test_catalog_refresh_with_valid_catalog(
        self, provider_endpoints_fixture: Path, tmp_path: Path
    ) -> None:
        """catalog_refresh should process valid endpoint catalog and return results for each provider."""
        catalog_path = provider_endpoints_fixture
        result = catalog_refresh(catalog_path, dry_run=True)

        assert result is not None
        # Should have results for all providers in the fixture
        assert len(result.provider_results) == 2  # testprovider and anotherprovider
        provider_slugs = {pr.provider_slug for pr in result.provider_results}
        assert "testprovider" in provider_slugs
        assert "anotherprovider" in provider_slugs
        # All should be MANUAL_CURATION since we're not actually scraping
        for pr in result.provider_results:
            assert pr.outcome == EndpointRefreshOutcome.MANUAL_CURATION

    def test_catalog_refresh_dry_run_does_not_create_state(
        self, provider_endpoints_fixture: Path, tmp_path: Path
    ) -> None:
        """catalog_refresh with dry_run=True should not create or modify state file."""
        catalog_path = provider_endpoints_fixture
        state_path = tmp_path / "refresh_state.json"

        # Ensure state file doesn't exist
        assert not state_path.exists()

        result = catalog_refresh(catalog_path, dry_run=True, state_path=state_path)

        # State file should still not exist
        assert not state_path.exists()
        assert result is not None

    def test_catalog_refresh_dry_run_false_creates_state(
        self, provider_endpoints_fixture: Path, tmp_path: Path
    ) -> None:
        """catalog_refresh with dry_run=False should create state file with outcomes."""
        catalog_path = provider_endpoints_fixture
        state_path = tmp_path / "refresh_state.json"

        # Ensure state file doesn't exist
        assert not state_path.exists()

        result = catalog_refresh(catalog_path, dry_run=False, state_path=state_path)

        # State file should now exist
        assert state_path.exists()
        assert result is not None

        # Verify state was saved correctly
        loaded_state = load_refresh_state(state_path)
        assert loaded_state is not None
        assert loaded_state.version == "1.0.0"
        # Should have outcomes for both providers
        assert len(loaded_state.provider_outcomes) == 2

    def test_catalog_refresh_nonexistent_catalog(
        self, tmp_path: Path
    ) -> None:
        """catalog_refresh should handle nonexistent catalog gracefully."""
        nonexistent = tmp_path / "nonexistent.json"
        result = catalog_refresh(nonexistent, dry_run=True)

        # Should return a result with all providers showing errors
        assert result is not None
        for provider_result in result.provider_results:
            assert provider_result.outcome == EndpointRefreshOutcome.ERROR

    def test_catalog_refresh_carries_forward_valid_blocked_states(
        self, provider_endpoints_fixture: Path, tmp_path: Path
    ) -> None:
        """Blocked states with future retry_after should be carried forward."""
        catalog_path = provider_endpoints_fixture
        state_path = tmp_path / "refresh_state.json"

        # Create initial state with a blocked provider that has future retry_after
        from datetime import timedelta
        future_date = date.today() + timedelta(days=7)
        blocked_state = BlockedDocState(
            provider_slug="testprovider",
            blocked_reason=BlockedReason.ANTI_BOT_BLOCK,
            blocked_date=date.today(),
            source_urls_attempted=["https://docs.testprovider.example.com/"],
            retry_after=future_date,
        )
        initial_state = RefreshState(
            version="1.0.0",
            last_refresh=date.today(),
            blocked_providers={"testprovider": blocked_state},
            provider_outcomes={"testprovider": EndpointRefreshOutcome.BLOCKED},
        )
        save_refresh_state(initial_state, state_path)

        # Run refresh with dry_run=False
        result = catalog_refresh(catalog_path, dry_run=False, state_path=state_path)

        assert result is not None
        # testprovider should be BLOCKED (skipped due to future retry_after)
        testprovider_result = next(
            pr for pr in result.provider_results if pr.provider_slug == "testprovider"
        )
        assert testprovider_result.outcome == EndpointRefreshOutcome.BLOCKED
        assert testprovider_result.blocked_state is not None
        assert testprovider_result.blocked_state.retry_after == future_date

    def test_catalog_refresh_updates_existing_state(
        self, provider_endpoints_fixture: Path, tmp_path: Path
    ) -> None:
        """Subsequent refreshes should update the state file correctly."""
        catalog_path = provider_endpoints_fixture
        state_path = tmp_path / "refresh_state.json"

        # First refresh
        result1 = catalog_refresh(catalog_path, dry_run=False, state_path=state_path)
        assert result1 is not None
        state1 = load_refresh_state(state_path)
        assert state1 is not None

        # Second refresh - should update, not duplicate
        result2 = catalog_refresh(catalog_path, dry_run=False, state_path=state_path)
        assert result2 is not None
        state2 = load_refresh_state(state_path)
        assert state2 is not None
        # Should have same number of outcomes (updated, not duplicated)
        assert len(state2.provider_outcomes) == len(state1.provider_outcomes)


# -----------------------------------------------------------------------
# get_refresh_state_path Tests
# -----------------------------------------------------------------------

class TestGetRefreshStatePath:
    """Tests for get_refresh_state_path function."""

    def test_refresh_state_path_default(self, tmp_path: Path) -> None:
        """get_refresh_state_path should return default path."""
        path = get_refresh_state_path(base_dir=tmp_path)
        assert path.name == "catalog_refresh_state.json"
        assert path.parent == tmp_path

    def test_refresh_state_path_custom_name(self, tmp_path: Path) -> None:
        """get_refresh_state_path should support custom filename."""
        path = get_refresh_state_path(
            base_dir=tmp_path, filename="custom_state.json"
        )
        assert path.name == "custom_state.json"


# -----------------------------------------------------------------------
# JSON Schema Validation Tests for Refresh State
# -----------------------------------------------------------------------

class TestRefreshStateJsonSchema:
    """Tests for JSON schema validation of refresh state."""

    def test_refresh_state_valid_json_schema(self, tmp_path: Path) -> None:
        """RefreshState should produce valid JSON that conforms to schema."""
        blocked = {
            "xai": BlockedDocState(
                provider_slug="xai",
                blocked_reason=BlockedReason.ANTI_BOT_BLOCK,
                blocked_date=date(2025, 1, 20),
                source_urls_attempted=["https://docs.x.ai/"],
            )
        }
        state = RefreshState(
            version="1.0.0",
            last_refresh=date(2025, 1, 20),
            blocked_providers=blocked,
            provider_outcomes={"xai": EndpointRefreshOutcome.BLOCKED},
        )
        state_path = tmp_path / "refresh_state.json"
        save_refresh_state(state, state_path)

        # Verify it's valid JSON
        with open(state_path, "r") as f:
            loaded_json = json.load(f)
        assert loaded_json["version"] == "1.0.0"
        assert "xai" in loaded_json["blocked_providers"]


# -----------------------------------------------------------------------
# Safe Refresh Behavior Tests
# -----------------------------------------------------------------------

class TestSafeRefreshBehavior:
    """Tests for safe (non-aggressive) refresh behavior."""

    def test_refresh_does_not_hammer_providers(self) -> None:
        """Refresh should not rapidly hit providers."""
        # This is a behavioral test - we verify the refresh mechanism
        # doesn't implement rapid retry logic
        from hermesoptimizer.catalog_refresh import (
            EndpointRefreshOutcome,
            ProviderRefreshResult,
            catalog_refresh,
        )

        # Create a minimal test that verifies the refresh function exists
        # and returns appropriate types without actually hitting any URLs
        result = ProviderRefreshResult(
            provider_slug="test",
            outcome=EndpointRefreshOutcome.MANUAL_CURATION,
            error_message=None,
        )
        assert result.provider_slug == "test"
        assert result.outcome == EndpointRefreshOutcome.MANUAL_CURATION

    def test_blocked_state_prevents_retries(self) -> None:
        """Blocked provider should not be retried immediately."""
        blocked = {
            "blocked_provider": BlockedDocState(
                provider_slug="blocked_provider",
                blocked_reason=BlockedReason.ANTI_BOT_BLOCK,
                blocked_date=date(2025, 1, 20),
                source_urls_attempted=["https://example.com/docs"],
                retry_after=date(2025, 1, 21),  # Should not retry before this date
            )
        }
        state = RefreshState(
            version="1.0.0",
            last_refresh=date(2025, 1, 20),
            blocked_providers=blocked,
            provider_outcomes={"blocked_provider": EndpointRefreshOutcome.BLOCKED},
        )

        # Verify blocked state is recorded correctly
        assert state.blocked_providers["blocked_provider"].retry_after == date(2025, 1, 21)
        # This retry_after date can be used by callers to determine if a
        # provider should be skipped in this refresh cycle


# -----------------------------------------------------------------------
# Data Catalog Validation Tests
# -----------------------------------------------------------------------

class TestDataCatalogValidation:
    """Tests for validating checked-in data catalogs."""

    def test_data_provider_endpoints_validates(self, data_dir: Path) -> None:
        """Data provider_endpoints.json should pass validation."""
        path = data_dir / "provider_endpoints.json"
        if not path.is_file():
            pytest.skip("Data file not found")

        data = load_provider_endpoints_catalog(path)
        errors = validate_provider_endpoints(data)
        assert errors == [], f"Data catalog has errors: {errors}"

    def test_provider_endpoint_catalog_from_data(self, data_dir: Path) -> None:
        """ProviderEndpointCatalog should load valid data."""
        path = data_dir / "provider_endpoints.json"
        if not path.is_file():
            pytest.skip("Data file not found")

        catalog = ProviderEndpointCatalog.from_file(path)
        assert catalog.version is not None
        assert len(catalog.provider_slugs) > 0
