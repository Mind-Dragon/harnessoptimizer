"""
Tests for model-validation rework: stale aliases, deprecated models,
missing capabilities, and wrong-endpoint routing.

Covers:
- Stale alias detection and correction suggestions
- Deprecated model detection with proper status
- Missing capability validation (task requires capability X, model doesn't have it)
- Wrong-endpoint routing detection (model routed to wrong endpoint for its type)
- Integration with ProviderTruthStore and verify_endpoint flow
"""
from __future__ import annotations

import pytest

from hermesoptimizer.sources.provider_truth import (
    EndpointCandidate,
    ProviderTruthRecord,
    ProviderTruthStore,
)
from hermesoptimizer.verify.endpoints import (
    EndpointCheckResult,
    EndpointCheckStatus,
    check_capabilities,
    check_endpoint_routing,
    check_model_alias,
    check_stale_alias,
    reset_http_get,
    set_http_get,
    verify_endpoint,
    verify_endpoint_with_live,
)


# --------------------------------------------------------------------------- #
# Stale alias detection
# --------------------------------------------------------------------------- #

class TestStaleAliasDetection:
    """Tests for stale model alias detection and correction suggestions."""

    def test_check_stale_alias_returns_none_for_valid_model(self) -> None:
        """A known, current model name should not be flagged as a stale alias."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o", "gpt-4o-mini"],
                capabilities=["text", "vision", "reasoning"],
            )
        )
        # gpt-4o is a known current model
        result = check_stale_alias("openai", "gpt-4o", store)
        assert result is None

    def test_check_stale_alias_detects_stale_alias(self) -> None:
        """A known stale alias should be detected and return the correct model."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
                stale_aliases={
                    "gpt-5": "gpt-4o",
                    "gpt-4.5": "gpt-4o",
                    "gpt-3.5": "gpt-3.5-turbo",
                },
                capabilities=["text", "vision", "reasoning"],
            )
        )
        result = check_stale_alias("openai", "gpt-5", store)
        assert result is not None
        assert result.correct_model == "gpt-4o"
        assert result.is_stale_alias is True

    def test_check_stale_alias_returns_none_for_unknown_model(self) -> None:
        """An unknown model that's not a stale alias should return None (handled by stale model check)."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                stale_aliases={},
                capabilities=["text"],
            )
        )
        # Not a known alias - should return None so stale model check handles it
        result = check_stale_alias("openai", "completely-unknown-model", store)
        assert result is None

    def test_check_stale_alias_requires_provider_match(self) -> None:
        """Alias mapping should only apply within the same provider."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                stale_aliases={"gpt-5": "gpt-4o"},
                capabilities=["text"],
            )
        )
        store.add(
            ProviderTruthRecord(
                provider="anthropic",
                canonical_endpoint="https://api.anthropic.com",
                known_models=["claude-3.5-sonnet"],
                stale_aliases={},
                capabilities=["text"],
            )
        )
        # gpt-5 is an OpenAI alias, not Anthropic
        result = check_stale_alias("anthropic", "gpt-5", store)
        assert result is None

    def test_stale_alias_with_unknown_provider(self) -> None:
        """Unknown provider should return None (handled by unknown provider check)."""
        store = ProviderTruthStore()
        result = check_stale_alias("completely-unknown", "some-model", store)
        assert result is None


class TestStaleAliasResult:
    """Tests for StaleAliasResult dataclass."""

    def test_stale_alias_result_attributes(self) -> None:
        """StaleAliasResult should contain correct model and alias info."""
        from hermesoptimizer.verify.endpoints import StaleAliasResult
        result = StaleAliasResult(
            original_model="gpt-5",
            correct_model="gpt-4o",
            provider="openai",
            is_stale_alias=True,
        )
        assert result.original_model == "gpt-5"
        assert result.correct_model == "gpt-4o"
        assert result.provider == "openai"
        assert result.is_stale_alias is True


# --------------------------------------------------------------------------- #
# Deprecated model detection
# --------------------------------------------------------------------------- #

class TestDeprecatedModelDetection:
    """Tests for deprecated model detection with proper status reporting."""

    def test_deprecated_model_returns_deprecated_status(self) -> None:
        """A deprecated model should be flagged with clear deprecated status."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                deprecated_models=["gpt-4", "gpt-3.5-turbo"],
                capabilities=["text"],
            )
        )
        # gpt-4 is deprecated
        result = verify_endpoint("openai", "https://api.openai.com/v1", "gpt-4", store)
        assert result.status == EndpointCheckStatus.DEPRECATED_MODEL

    def test_deprecated_model_in_details(self) -> None:
        """Deprecated model result should include deprecation info in details."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                deprecated_models=["gpt-4"],
                capabilities=["text"],
            )
        )
        result = verify_endpoint("openai", "https://api.openai.com/v1", "gpt-4", store)
        assert result.status == EndpointCheckStatus.DEPRECATED_MODEL
        assert result.details.get("is_deprecated") is True

    def test_unknown_model_returns_stale_not_deprecated(self) -> None:
        """An unknown model (not in deprecated list) should return STALE_MODEL, not DEPRECATED_MODEL."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                deprecated_models=["gpt-4"],
                capabilities=["text"],
            )
        )
        # completely-unknown is not in deprecated list either
        result = verify_endpoint("openai", "https://api.openai.com/v1", "completely-unknown", store)
        assert result.status == EndpointCheckStatus.STALE_MODEL
        assert result.details.get("is_deprecated") is not True


# --------------------------------------------------------------------------- #
# Missing capabilities validation
# --------------------------------------------------------------------------- #

class TestMissingCapabilitiesValidation:
    """Tests for missing capabilities validation."""

    def test_check_capabilities_returns_none_when_model_has_required(self) -> None:
        """Model with all required capabilities should return None (pass)."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                capabilities=["text", "vision", "reasoning"],
            )
        )
        result = check_capabilities("openai", "gpt-4o", ["text", "vision"], store)
        assert result is None

    def test_check_capabilities_detects_missing_capability(self) -> None:
        """Model missing a required capability should be flagged."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                capabilities=["text", "reasoning"],  # No vision
            )
        )
        result = check_capabilities("openai", "gpt-4o", ["vision"], store)
        assert result is not None
        assert result.status == EndpointCheckStatus.MISSING_CAPABILITY
        assert "vision" in result.message

    def test_check_capabilities_multiple_missing(self) -> None:
        """Multiple missing capabilities should all be listed."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                capabilities=["text"],  # Only text
            )
        )
        result = check_capabilities("openai", "gpt-4o", ["vision", "reasoning", "embedding"], store)
        assert result is not None
        assert result.status == EndpointCheckStatus.MISSING_CAPABILITY
        assert "vision" in result.message
        assert "reasoning" in result.message
        assert "embedding" in result.message

    def test_check_capabilities_unknown_provider(self) -> None:
        """Unknown provider should return None (handled by other checks)."""
        store = ProviderTruthStore()
        result = check_capabilities("unknown", "some-model", ["text"], store)
        assert result is None

    def test_check_capabilities_unknown_model(self) -> None:
        """Unknown model should return None (handled by stale model check)."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                capabilities=["text"],
            )
        )
        result = check_capabilities("openai", "unknown-model", ["text"], store)
        assert result is None

    def test_check_capabilities_empty_required_list(self) -> None:
        """Empty required capabilities list should always pass."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                capabilities=["text"],
            )
        )
        result = check_capabilities("openai", "gpt-4o", [], store)
        assert result is None


# --------------------------------------------------------------------------- #
# Wrong-endpoint routing validation
# --------------------------------------------------------------------------- #

class TestWrongEndpointRouting:
    """Tests for wrong-endpoint routing detection."""

    def test_check_endpoint_routing_returns_none_when_correct(self) -> None:
        """Model using correct endpoint should return None (pass)."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                capabilities=["text", "vision"],
            )
        )
        result = check_endpoint_routing("openai", "https://api.openai.com/v1", "gpt-4o", store)
        assert result is None

    def test_check_endpoint_routing_detects_wrong_endpoint(self) -> None:
        """Model using wrong endpoint should be flagged."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                capabilities=["text", "vision"],
                # Model-specific endpoint override
                model_endpoints={
                    "gpt-4o": "https://api.openai.com/v1",
                },
            )
        )
        # Using wrong endpoint
        result = check_endpoint_routing("openai", "https://wrong.endpoint.com/v1", "gpt-4o", store)
        assert result is not None
        assert result.status == EndpointCheckStatus.WRONG_ENDPOINT_ROUTING
        assert "gpt-4o" in result.message
        assert "api.openai.com" in result.message or "correct" in result.message.lower()

    def test_check_endpoint_routing_with_region_mismatch(self) -> None:
        """Model endpoint should match region-specific endpoint when configured."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                capabilities=["text"],
                # EU-specific endpoint
                endpoint_candidates=[
                    EndpointCandidate(
                        endpoint="https://api.openai.com/v1",
                        api_style="openai-compatible",
                        auth_type="bearer",
                        region_scope=["us", "global"],
                        is_stable=True,
                    ),
                    EndpointCandidate(
                        endpoint="https://api.openai.eu/v1",
                        api_style="openai-compatible",
                        auth_type="bearer",
                        region_scope=["eu"],
                        is_stable=True,
                    ),
                ],
            )
        )
        # EU model using US endpoint when EU is available
        result = check_endpoint_routing(
            "openai", "https://api.openai.com/v1", "gpt-4o", store, region="eu"
        )
        assert result is not None
        assert result.status == EndpointCheckStatus.WRONG_ENDPOINT_ROUTING

    def test_check_endpoint_routing_unknown_provider(self) -> None:
        """Unknown provider should return None (handled by other checks)."""
        store = ProviderTruthStore()
        result = check_endpoint_routing("unknown", "https://example.com", "model", store)
        assert result is None

    def test_check_endpoint_routing_unknown_model(self) -> None:
        """Unknown model should return None (handled by stale model check)."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                capabilities=["text"],
            )
        )
        result = check_endpoint_routing("openai", "https://api.openai.com/v1", "unknown-model", store)
        assert result is None


# --------------------------------------------------------------------------- #
# Integration: verify_endpoint with new status types
# --------------------------------------------------------------------------- #

class TestVerifyEndpointIntegration:
    """Integration tests for verify_endpoint with all new status types."""

    def test_verify_endpoint_returns_stale_alias_status(self) -> None:
        """verify_endpoint should return STALE_ALIAS status for known stale aliases."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                stale_aliases={"gpt-5": "gpt-4o"},
                capabilities=["text", "vision"],
            )
        )
        result = verify_endpoint("openai", "https://api.openai.com/v1", "gpt-5", store)
        assert result.status == EndpointCheckStatus.STALE_ALIAS
        assert result.details.get("correct_model") == "gpt-4o"
        assert result.details.get("original_model") == "gpt-5"

    def test_verify_endpoint_returns_deprecated_model_status(self) -> None:
        """verify_endpoint should return DEPRECATED_MODEL status for deprecated models."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                deprecated_models=["gpt-4"],
                capabilities=["text"],
            )
        )
        result = verify_endpoint("openai", "https://api.openai.com/v1", "gpt-4", store)
        assert result.status == EndpointCheckStatus.DEPRECATED_MODEL

    def test_verify_endpoint_checks_order_rkwe_first(self) -> None:
        """RKWE check should take precedence over stale alias check."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                stale_aliases={"gpt-5": "gpt-4o"},
                capabilities=["text"],
            )
        )
        # Wrong endpoint AND stale alias - RKWE should be reported first
        result = verify_endpoint("openai", "https://wrong.endpoint.com/v1", "gpt-5", store)
        assert result.status == EndpointCheckStatus.RKWE

    def test_verify_endpoint_checks_order_stale_alias_before_stale_model(self) -> None:
        """Stale alias check should take precedence over generic stale model check."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                stale_aliases={"gpt-5": "gpt-4o"},
                capabilities=["text"],
            )
        )
        # gpt-5 is a stale alias - should get STALE_ALIAS not STALE_MODEL
        result = verify_endpoint("openai", "https://api.openai.com/v1", "gpt-5", store)
        assert result.status == EndpointCheckStatus.STALE_ALIAS
        # Generic stale model check should not fire for aliases
        assert result.status != EndpointCheckStatus.STALE_MODEL


# --------------------------------------------------------------------------- #
# check_model_alias helper (combined alias + deprecation check)
# --------------------------------------------------------------------------- #

class TestCheckModelAlias:
    """Tests for the combined check_model_alias helper."""

    def test_check_model_alias_stale_alias(self) -> None:
        """check_model_alias should detect stale aliases."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                stale_aliases={"gpt-5": "gpt-4o"},
                capabilities=["text"],
            )
        )
        result = check_model_alias("openai", "gpt-5", store)
        assert result is not None
        assert result.is_stale_alias is True
        assert result.correct_model == "gpt-4o"

    def test_check_model_alias_deprecated_model(self) -> None:
        """check_model_alias should detect deprecated models."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                deprecated_models=["gpt-4"],
                capabilities=["text"],
            )
        )
        result = check_model_alias("openai", "gpt-4", store)
        assert result is not None
        assert result.is_deprecated is True
        assert result.is_stale_alias is False

    def test_check_model_alias_valid_model(self) -> None:
        """check_model_alias should return None for valid models."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                capabilities=["text"],
            )
        )
        result = check_model_alias("openai", "gpt-4o", store)
        assert result is None

    def test_check_model_alias_unknown_model(self) -> None:
        """check_model_alias should return None for unknown models (let stale model check handle)."""
        store = ProviderTruthStore()
        store.add(
            ProviderTruthRecord(
                provider="openai",
                canonical_endpoint="https://api.openai.com/v1",
                known_models=["gpt-4o"],
                capabilities=["text"],
            )
        )
        result = check_model_alias("openai", "completely-unknown", store)
        assert result is None
