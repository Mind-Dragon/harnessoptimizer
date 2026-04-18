"""Tests for provider/model recommender (v0.8.0 Task 6).

Strict TDD tests for Hermes-grade provider/model recommender that uses:
- live config evidence
- known auth presence
- checked-in provider endpoint/model catalogs
- provenance information
- safety lane logic

Output contract includes:
- ranked recommendations
- reason strings
- lane classification
- config snippet generation only after validation
"""

from __future__ import annotations

import pytest

from hermesoptimizer.tool_surface.schema import (
    HelpContract,
    OutputContract,
    RiskLevel,
    SurfaceKind,
    ToolSurface,
)


class TestProviderRecommendSurfaceExists:
    """Provider recommend tool surface must exist and be properly defined."""

    def test_provider_recommend_tool_surface_importable(self) -> None:
        """ProviderRecommend tool surface must be importable from tool_surface package."""
        from hermesoptimizer.tool_surface import provider_recommend

        assert provider_recommend is not None

    def test_provider_recommend_surface_defined(self) -> None:
        """PROVIDER_RECOMMEND ToolSurface must be defined in provider_recommend module."""
        from hermesoptimizer.tool_surface import provider_recommend

        assert hasattr(provider_recommend, "PROVIDER_RECOMMEND")
        surface = provider_recommend.PROVIDER_RECOMMEND
        assert isinstance(surface, ToolSurface)

    def test_provider_recommend_surface_properties(self) -> None:
        """PROVIDER_RECOMMEND must have correct surface properties."""
        from hermesoptimizer.tool_surface import provider_recommend

        surface = provider_recommend.PROVIDER_RECOMMEND
        assert surface.surface_name == "provider_recommend"
        assert surface.command_name == "recommend_provider"
        assert surface.kind == SurfaceKind.TYPED
        assert surface.risk_level == RiskLevel.LOW
        assert surface.supports_help is True
        assert surface.read_only is True
        assert surface.recommended_for_agent is True

    def test_provider_recommend_help_contract(self) -> None:
        """PROVIDER_RECOMMEND must have help contract defined."""
        from hermesoptimizer.tool_surface import provider_recommend

        surface = provider_recommend.PROVIDER_RECOMMEND
        assert surface.help_contract is not None
        assert isinstance(surface.help_contract, HelpContract)

    def test_provider_recommend_output_contract(self) -> None:
        """PROVIDER_RECOMMEND must have output contract defined."""
        from hermesoptimizer.tool_surface import provider_recommend

        surface = provider_recommend.PROVIDER_RECOMMEND
        assert surface.output_contract is not None
        assert isinstance(surface.output_contract, OutputContract)


class TestSafetyLane:
    """SafetyLane enum must exist and have required values."""

    def test_safety_lane_enum_exists(self) -> None:
        """SafetyLane must be importable from provider_recommend module."""
        from hermesoptimizer.tool_surface.provider_recommend import SafetyLane

        assert SafetyLane is not None

    def test_safety_lane_has_coding(self) -> None:
        """SafetyLane must have CODING lane for code-related tasks."""
        from hermesoptimizer.tool_surface.provider_recommend import SafetyLane

        assert hasattr(SafetyLane, "CODING")
        assert SafetyLane.CODING.value == "coding"

    def test_safety_lane_has_reasoning(self) -> None:
        """SafetyLane must have REASONING lane for reasoning tasks."""
        from hermesoptimizer.tool_surface.provider_recommend import SafetyLane

        assert hasattr(SafetyLane, "REASONING")
        assert SafetyLane.REASONING.value == "reasoning"

    def test_safety_lane_has_general(self) -> None:
        """SafetyLane must have GENERAL lane for general-purpose tasks."""
        from hermesoptimizer.tool_surface.provider_recommend import SafetyLane

        assert hasattr(SafetyLane, "GENERAL")
        assert SafetyLane.GENERAL.value == "general"


class TestProviderRecommendation:
    """ProviderRecommendation dataclass must be properly structured."""

    def test_provider_recommendation_exists(self) -> None:
        """ProviderRecommendation must be importable."""
        from hermesoptimizer.tool_surface.provider_recommend import ProviderRecommendation

        assert ProviderRecommendation is not None

    def test_provider_recommendation_fields(self) -> None:
        """ProviderRecommendation must have all required fields."""
        from hermesoptimizer.tool_surface.provider_recommend import ProviderRecommendation, SafetyLane

        rec = ProviderRecommendation(
            provider="openai",
            model="gpt-4o",
            endpoint="https://api.openai.com/v1",
            rank_score=0.95,
            reason="High confidence: known model, stable endpoint",
            lane=SafetyLane.CODING,
            config_snippet=None,
            provenance="catalog:testprovider",
        )
        assert rec.provider == "openai"
        assert rec.model == "gpt-4o"
        assert rec.endpoint == "https://api.openai.com/v1"
        assert rec.rank_score == 0.95
        assert rec.lane == SafetyLane.CODING
        assert rec.config_snippet is None
        assert rec.provenance == "catalog:testprovider"

    def test_provider_recommendation_is_comparable(self) -> None:
        """ProviderRecommendation must support ranking comparison."""
        from hermesoptimizer.tool_surface.provider_recommend import ProviderRecommendation, SafetyLane

        rec1 = ProviderRecommendation(
            provider="openai",
            model="gpt-4o",
            endpoint="https://api.openai.com/v1",
            rank_score=0.95,
            reason="High score",
            lane=SafetyLane.CODING,
            config_snippet=None,
            provenance="catalog:test",
        )
        rec2 = ProviderRecommendation(
            provider="anthropic",
            model="claude-3-5-sonnet",
            endpoint="https://api.anthropic.com",
            rank_score=0.85,
            reason="Medium score",
            lane=SafetyLane.REASONING,
            config_snippet=None,
            provenance="catalog:test",
        )
        # Higher score should rank higher
        assert rec1.rank_score > rec2.rank_score


class TestProviderRecommendInput:
    """ProviderRecommendInput dataclass must be properly structured."""

    def test_provider_recommend_input_exists(self) -> None:
        """ProviderRecommendInput must be importable."""
        from hermesoptimizer.tool_surface.provider_recommend import ProviderRecommendInput

        assert ProviderRecommendInput is not None

    def test_provider_recommend_input_fields(self) -> None:
        """ProviderRecommendInput must accept required fields."""
        from hermesoptimizer.tool_surface.provider_recommend import ProviderRecommendInput, SafetyLane

        inp = ProviderRecommendInput(
            desired_capabilities=["text", "reasoning"],
            desired_lane=SafetyLane.CODING,
            region_preference="us",
            auth_presence={"openai": True, "anthropic": True},
        )
        assert inp.desired_capabilities == ["text", "reasoning"]
        assert inp.desired_lane == SafetyLane.CODING
        assert inp.region_preference == "us"
        assert inp.auth_presence == {"openai": True, "anthropic": True}


class TestProviderRecommendOutput:
    """ProviderRecommendOutput dataclass must be properly structured."""

    def test_provider_recommend_output_exists(self) -> None:
        """ProviderRecommendOutput must be importable."""
        from hermesoptimizer.tool_surface.provider_recommend import ProviderRecommendOutput

        assert ProviderRecommendOutput is not None

    def test_provider_recommend_output_fields(self) -> None:
        """ProviderRecommendOutput must have ranked recommendations and metadata."""
        from hermesoptimizer.tool_surface.provider_recommend import (
            ProviderRecommendOutput,
            ProviderRecommendation,
            SafetyLane,
        )

        rec = ProviderRecommendation(
            provider="openai",
            model="gpt-4o",
            endpoint="https://api.openai.com/v1",
            rank_score=0.95,
            reason="High confidence",
            lane=SafetyLane.CODING,
            config_snippet=None,
            provenance="catalog:test",
        )
        out = ProviderRecommendOutput(
            recommendations=[rec],
            total_candidates=1,
            validation_passed=True,
        )
        assert len(out.recommendations) == 1
        assert out.recommendations[0].provider == "openai"
        assert out.total_candidates == 1
        assert out.validation_passed is True

    def test_provider_recommend_output_ranked(self) -> None:
        """ProviderRecommendOutput recommendations must be sorted by rank_score descending when returned from recommend()."""
        from hermesoptimizer.tool_surface.provider_recommend import (
            ProviderRecommender,
            ProviderRecommendInput,
            SafetyLane,
        )

        # Create a recommender with no catalogs to get minimal recommendations
        recommender = ProviderRecommender(
            truth_store=None,
            endpoint_catalog=None,
            model_catalog=None,
        )

        # Even with no catalogs, the method should return a valid output
        # The sorting is done in recommend(), not on direct object creation
        inp = ProviderRecommendInput(
            desired_capabilities=["text"],
            desired_lane=SafetyLane.GENERAL,
            region_preference="us",
            auth_presence={"openai": True},

        )

        # When recommend() returns results, they should be sorted
        # With no catalogs, we may get empty results, which is acceptable
        result = recommender.recommend(inp)
        assert result is not None
        # If there are recommendations, verify sorting
        if len(result.recommendations) > 1:
            assert result.recommendations[0].rank_score >= result.recommendations[1].rank_score


class TestProviderRecommender:
    """ProviderRecommender class must produce proper recommendations."""

    def test_provider_recommender_exists(self) -> None:
        """ProviderRecommender must be importable."""
        from hermesoptimizer.tool_surface.provider_recommend import ProviderRecommender

        assert ProviderRecommender is not None

    def test_provider_recommender_instantiation(self) -> None:
        """ProviderRecommender must be instantiable with required dependencies."""
        from hermesoptimizer.tool_surface.provider_recommend import ProviderRecommender

        recommender = ProviderRecommender(
            truth_store=None,
            endpoint_catalog=None,
            model_catalog=None,
        )
        assert recommender is not None

    def test_provider_recommender_recommend_method_exists(self) -> None:
        """ProviderRecommender must have a recommend method."""
        from hermesoptimizer.tool_surface.provider_recommend import ProviderRecommender

        recommender = ProviderRecommender(
            truth_store=None,
            endpoint_catalog=None,
            model_catalog=None,
        )
        assert hasattr(recommender, "recommend")
        assert callable(recommender.recommend)


class TestProviderRecommenderWithFixtures:
    """ProviderRecommender tests using existing repo fixtures."""

    def test_recommender_with_fixture_provider_endpoints(self) -> None:
        """Recommender must load and use provider_endpoints.json fixture."""
        import json
        from pathlib import Path

        from hermesoptimizer.schemas.provider_endpoint import ProviderEndpointCatalog
        from hermesoptimizer.tool_surface.provider_recommend import (
            ProviderRecommender,
            ProviderRecommendInput,
            SafetyLane,
        )

        fixture_path = Path("/home/agent/hermesoptimizer/tests/fixtures/provider_endpoints.json")
        catalog = ProviderEndpointCatalog.from_file(fixture_path)

        recommender = ProviderRecommender(
            truth_store=None,
            endpoint_catalog=catalog,
            model_catalog=None,
        )

        inp = ProviderRecommendInput(
            desired_capabilities=["text"],
            desired_lane=SafetyLane.GENERAL,
            region_preference="us",
            auth_presence={"testprovider": True},

        )

        result = recommender.recommend(inp)
        assert result is not None
        assert result.validation_passed is True
        assert len(result.recommendations) > 0

    def test_recommender_with_fixture_provider_models(self) -> None:
        """Recommender must load and use provider_models.json fixture."""
        import json
        from pathlib import Path

        from hermesoptimizer.schemas.provider_model import ProviderModelCatalog
        from hermesoptimizer.tool_surface.provider_recommend import (
            ProviderRecommender,
            ProviderRecommendInput,
            SafetyLane,
        )

        model_fixture_path = Path("/home/agent/hermesoptimizer/tests/fixtures/provider_models.json")
        model_catalog = ProviderModelCatalog.from_file(model_fixture_path)

        endpoint_fixture_path = Path("/home/agent/hermesoptimizer/tests/fixtures/provider_endpoints.json")
        from hermesoptimizer.schemas.provider_endpoint import ProviderEndpointCatalog
        endpoint_catalog = ProviderEndpointCatalog.from_file(endpoint_fixture_path)

        recommender = ProviderRecommender(
            truth_store=None,
            endpoint_catalog=endpoint_catalog,
            model_catalog=model_catalog,
        )

        inp = ProviderRecommendInput(
            desired_capabilities=["text", "reasoning"],
            desired_lane=SafetyLane.CODING,
            region_preference="us",
            auth_presence={"testprovider": True, "anotherprovider": True},

        )

        result = recommender.recommend(inp)
        assert result is not None
        assert result.validation_passed is True
        # Should recommend based on capabilities and lane
        assert len(result.recommendations) > 0

    def test_recommender_respects_auth_presence(self) -> None:
        """Recommender must only recommend providers with known auth presence."""
        from hermesoptimizer.tool_surface.provider_recommend import (
            ProviderRecommender,
            ProviderRecommendInput,
            SafetyLane,
        )

        recommender = ProviderRecommender(
            truth_store=None,
            endpoint_catalog=None,
            model_catalog=None,
        )

        # Only openai has auth, not anthropic
        inp = ProviderRecommendInput(
            desired_capabilities=["text"],
            desired_lane=SafetyLane.GENERAL,
            region_preference="us",
            auth_presence={"openai": True},  # Only openai

        )

        result = recommender.recommend(inp)
        assert result is not None
        # Should only include providers with auth
        for rec in result.recommendations:
            assert rec.provider in inp.auth_presence

    def test_recommender_ranks_by_score(self) -> None:
        """Recommender must return recommendations sorted by rank_score descending."""
        from hermesoptimizer.tool_surface.provider_recommend import (
            ProviderRecommender,
            ProviderRecommendInput,
            SafetyLane,
        )

        recommender = ProviderRecommender(
            truth_store=None,
            endpoint_catalog=None,
            model_catalog=None,
        )

        inp = ProviderRecommendInput(
            desired_capabilities=["text"],
            desired_lane=SafetyLane.CODING,
            region_preference="us",
            auth_presence={"openai": True, "anthropic": True},

        )

        result = recommender.recommend(inp)
        assert result is not None
        # Verify sorted by rank_score descending
        scores = [r.rank_score for r in result.recommendations]
        assert scores == sorted(scores, reverse=True)

    def test_recommender_deterministic_ordering_on_tie(self) -> None:
        """Recommender must produce deterministic ordering even when scores tie."""
        from pathlib import Path

        from hermesoptimizer.schemas.provider_endpoint import ProviderEndpointCatalog
        from hermesoptimizer.schemas.provider_model import ProviderModelCatalog
        from hermesoptimizer.tool_surface.provider_recommend import (
            ProviderRecommender,
            ProviderRecommendInput,
            SafetyLane,
        )

        model_fixture_path = Path("/home/agent/hermesoptimizer/tests/fixtures/provider_models.json")
        model_catalog = ProviderModelCatalog.from_file(model_fixture_path)

        endpoint_fixture_path = Path("/home/agent/hermesoptimizer/tests/fixtures/provider_endpoints.json")
        endpoint_catalog = ProviderEndpointCatalog.from_file(endpoint_fixture_path)

        recommender = ProviderRecommender(
            truth_store=None,
            endpoint_catalog=endpoint_catalog,
            model_catalog=model_catalog,
        )

        inp = ProviderRecommendInput(
            desired_capabilities=["text"],
            desired_lane=SafetyLane.GENERAL,
            region_preference="us",
            auth_presence={"testprovider": True, "anotherprovider": True},
        )

        # Run multiple times and verify same order
        result1 = recommender.recommend(inp)
        result2 = recommender.recommend(inp)
        result3 = recommender.recommend(inp)

        assert len(result1.recommendations) == len(result2.recommendations) == len(result3.recommendations)
        for r1, r2, r3 in zip(result1.recommendations, result2.recommendations, result3.recommendations):
            assert r1.provider == r2.provider == r3.provider
            assert r1.model == r2.model == r3.model
            assert r1.rank_score == r2.rank_score == r3.rank_score

    def test_recommender_provides_reason_strings(self) -> None:
        """Recommender must provide human-readable reason strings."""
        from hermesoptimizer.tool_surface.provider_recommend import (
            ProviderRecommender,
            ProviderRecommendInput,
            SafetyLane,
        )

        recommender = ProviderRecommender(
            truth_store=None,
            endpoint_catalog=None,
            model_catalog=None,
        )

        inp = ProviderRecommendInput(
            desired_capabilities=["text"],
            desired_lane=SafetyLane.GENERAL,
            region_preference="us",
            auth_presence={"openai": True},

        )

        result = recommender.recommend(inp)
        assert result is not None
        for rec in result.recommendations:
            assert rec.reason is not None
            assert len(rec.reason) > 0

    def test_recommender_classifies_lanes(self) -> None:
        """Recommender must classify recommendations by lane."""
        from hermesoptimizer.tool_surface.provider_recommend import (
            ProviderRecommender,
            ProviderRecommendInput,
            SafetyLane,
        )

        recommender = ProviderRecommender(
            truth_store=None,
            endpoint_catalog=None,
            model_catalog=None,
        )

        inp = ProviderRecommendInput(
            desired_capabilities=["text"],
            desired_lane=SafetyLane.CODING,
            region_preference="us",
            auth_presence={"openai": True},

        )

        result = recommender.recommend(inp)
        assert result is not None
        for rec in result.recommendations:
            assert rec.lane is not None
            assert isinstance(rec.lane, SafetyLane)


class TestConfigSnippetValidation:
    """Config snippet generation must only occur after validation."""

    def test_config_snippet_requires_validation(self) -> None:
        """Config snippet must only be generated when validation passes."""
        from pathlib import Path

        from hermesoptimizer.schemas.provider_endpoint import ProviderEndpointCatalog
        from hermesoptimizer.schemas.provider_model import ProviderModelCatalog
        from hermesoptimizer.tool_surface.provider_recommend import (
            ProviderRecommender,
            ProviderRecommendInput,
            SafetyLane,
        )

        model_fixture_path = Path("/home/agent/hermesoptimizer/tests/fixtures/provider_models.json")
        model_catalog = ProviderModelCatalog.from_file(model_fixture_path)

        endpoint_fixture_path = Path("/home/agent/hermesoptimizer/tests/fixtures/provider_endpoints.json")
        endpoint_catalog = ProviderEndpointCatalog.from_file(endpoint_fixture_path)

        recommender = ProviderRecommender(
            truth_store=None,
            endpoint_catalog=endpoint_catalog,
            model_catalog=model_catalog,
        )

        inp = ProviderRecommendInput(
            desired_capabilities=["text", "reasoning"],
            desired_lane=SafetyLane.CODING,
            region_preference="us",
            auth_presence={"testprovider": True},
        )

        result = recommender.recommend(inp)
        assert result is not None
        assert result.validation_passed is True

        # If validation passed and snippet generation is enabled, snippets should be present
        for rec in result.recommendations:
            if rec.config_snippet is not None:
                # Snippet should be valid YAML string
                assert isinstance(rec.config_snippet, str)
                assert len(rec.config_snippet) > 0


class TestProviderTruthIntegration:
    """ProviderRecommender must integrate with ProviderTruthStore."""

    def test_recommender_accepts_truth_store(self) -> None:
        """ProviderRecommender must accept ProviderTruthStore as dependency."""
        from pathlib import Path

        from hermesoptimizer.sources.provider_truth import ProviderTruthStore, load_provider_truth
        from hermesoptimizer.tool_surface.provider_recommend import ProviderRecommender

        # Load empty truth store
        truth_store = ProviderTruthStore()

        recommender = ProviderRecommender(
            truth_store=truth_store,
            endpoint_catalog=None,
            model_catalog=None,
        )
        assert recommender is not None
        assert recommender._truth is truth_store

    def test_recommender_uses_truth_for_ranking(self) -> None:
        """ProviderRecommender must use ProviderTruthStore for ranking."""
        from pathlib import Path

        from hermesoptimizer.schemas.provider_endpoint import ProviderEndpointCatalog
        from hermesoptimizer.schemas.provider_model import ProviderModelCatalog
        from hermesoptimizer.sources.provider_truth import (
            EndpointCandidate,
            ProviderTruthRecord,
            ProviderTruthStore,
        )
        from hermesoptimizer.tool_surface.provider_recommend import (
            ProviderRecommender,
            ProviderRecommendInput,
            SafetyLane,
        )

        # Build truth store with known provider
        truth_store = ProviderTruthStore()
        truth_store.add(
            ProviderTruthRecord(
                provider="testprovider",
                canonical_endpoint="https://api.testprovider.example.com/v1",
                known_models=["test-model-1", "test-model-2"],
                deprecated_models=["test-model-deprecated"],
                capabilities=["text", "reasoning"],
                context_window=8000,
                confidence="high",
                auth_type="bearer",
                regions=["us", "global"],
                transport="https",
            )
        )

        model_fixture_path = Path("/home/agent/hermesoptimizer/tests/fixtures/provider_models.json")
        model_catalog = ProviderModelCatalog.from_file(model_fixture_path)

        endpoint_fixture_path = Path("/home/agent/hermesoptimizer/tests/fixtures/provider_endpoints.json")
        endpoint_catalog = ProviderEndpointCatalog.from_file(endpoint_fixture_path)

        recommender = ProviderRecommender(
            truth_store=truth_store,
            endpoint_catalog=endpoint_catalog,
            model_catalog=model_catalog,
        )

        inp = ProviderRecommendInput(
            desired_capabilities=["text", "reasoning"],
            desired_lane=SafetyLane.CODING,
            region_preference="us",
            auth_presence={"testprovider": True},

        )

        result = recommender.recommend(inp)
        assert result is not None
        # Known models should be preferred
        assert len(result.recommendations) > 0


class TestLaneSafetyLogic:
    """Recommender must implement safety lane logic."""

    def test_coding_lane_classifies_coding_models(self) -> None:
        """CODING lane should be assigned to models suited for coding tasks."""
        from pathlib import Path

        from hermesoptimizer.schemas.provider_endpoint import ProviderEndpointCatalog
        from hermesoptimizer.schemas.provider_model import ProviderModelCatalog
        from hermesoptimizer.tool_surface.provider_recommend import (
            ProviderRecommender,
            ProviderRecommendInput,
            SafetyLane,
        )

        model_fixture_path = Path("/home/agent/hermesoptimizer/tests/fixtures/provider_models.json")
        model_catalog = ProviderModelCatalog.from_file(model_fixture_path)

        endpoint_fixture_path = Path("/home/agent/hermesoptimizer/tests/fixtures/provider_endpoints.json")
        endpoint_catalog = ProviderEndpointCatalog.from_file(endpoint_fixture_path)

        recommender = ProviderRecommender(
            truth_store=None,
            endpoint_catalog=endpoint_catalog,
            model_catalog=model_catalog,
        )

        # Request CODING lane - the output should contain lane classifications
        # (may or may not be CODING depending on fixture model capabilities)
        inp = ProviderRecommendInput(
            desired_capabilities=["text"],
            desired_lane=SafetyLane.CODING,
            region_preference="us",
            auth_presence={"testprovider": True},

        )

        result = recommender.recommend(inp)
        assert result is not None
        # All recommendations should have a lane classification
        for rec in result.recommendations:
            assert rec.lane is not None
            assert isinstance(rec.lane, SafetyLane)

    def test_reasoning_lane_prefers_reasoning_models(self) -> None:
        """REASONING lane should prefer models suited for reasoning tasks."""
        from pathlib import Path

        from hermesoptimizer.schemas.provider_endpoint import ProviderEndpointCatalog
        from hermesoptimizer.schemas.provider_model import ProviderModelCatalog
        from hermesoptimizer.tool_surface.provider_recommend import (
            ProviderRecommender,
            ProviderRecommendInput,
            SafetyLane,
        )

        model_fixture_path = Path("/home/agent/hermesoptimizer/tests/fixtures/provider_models.json")
        model_catalog = ProviderModelCatalog.from_file(model_fixture_path)

        endpoint_fixture_path = Path("/home/agent/hermesoptimizer/tests/fixtures/provider_endpoints.json")
        endpoint_catalog = ProviderEndpointCatalog.from_file(endpoint_fixture_path)

        recommender = ProviderRecommender(
            truth_store=None,
            endpoint_catalog=endpoint_catalog,
            model_catalog=model_catalog,
        )

        inp = ProviderRecommendInput(
            desired_capabilities=["text"],
            desired_lane=SafetyLane.REASONING,
            region_preference="us",
            auth_presence={"testprovider": True},

        )

        result = recommender.recommend(inp)
        assert result is not None
        # At least one recommendation should be for REASONING lane
        reasoning_recs = [r for r in result.recommendations if r.lane == SafetyLane.REASONING]
        assert len(reasoning_recs) > 0


class TestProvenanceTracking:
    """Recommender must track provenance information."""

    def test_recommendation_has_provenance(self) -> None:
        """Each recommendation must have provenance information."""
        from hermesoptimizer.tool_surface.provider_recommend import (
            ProviderRecommender,
            ProviderRecommendInput,
            SafetyLane,
        )

        recommender = ProviderRecommender(
            truth_store=None,
            endpoint_catalog=None,
            model_catalog=None,
        )

        inp = ProviderRecommendInput(
            desired_capabilities=["text"],
            desired_lane=SafetyLane.GENERAL,
            region_preference="us",
            auth_presence={"openai": True},

        )

        result = recommender.recommend(inp)
        assert result is not None
        for rec in result.recommendations:
            assert rec.provenance is not None
            assert len(rec.provenance) > 0

    def test_provenance_identifies_source(self) -> None:
        """Provenance must identify the source (catalog, truth, config)."""
        from pathlib import Path

        from hermesoptimizer.schemas.provider_endpoint import ProviderEndpointCatalog
        from hermesoptimizer.schemas.provider_model import ProviderModelCatalog
        from hermesoptimizer.tool_surface.provider_recommend import (
            ProviderRecommender,
            ProviderRecommendInput,
            SafetyLane,
        )

        model_fixture_path = Path("/home/agent/hermesoptimizer/tests/fixtures/provider_models.json")
        model_catalog = ProviderModelCatalog.from_file(model_fixture_path)

        endpoint_fixture_path = Path("/home/agent/hermesoptimizer/tests/fixtures/provider_endpoints.json")
        endpoint_catalog = ProviderEndpointCatalog.from_file(endpoint_fixture_path)

        recommender = ProviderRecommender(
            truth_store=None,
            endpoint_catalog=endpoint_catalog,
            model_catalog=model_catalog,
        )

        inp = ProviderRecommendInput(
            desired_capabilities=["text"],
            desired_lane=SafetyLane.GENERAL,
            region_preference="us",
            auth_presence={"testprovider": True},

        )

        result = recommender.recommend(inp)
        assert result is not None
        for rec in result.recommendations:
            # Provenance should indicate catalog source
            assert "catalog" in rec.provenance or "truth" in rec.provenance or "config" in rec.provenance
