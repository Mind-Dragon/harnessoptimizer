"""
Provider/Model Recommender (v0.8.0 Task 6).

Hermes-grade recommender that produces ranked provider/model recommendations using:
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

This module provides a ToolSurface IR entry for the recommender and does NOT
perform config mutation. It is recommendation planning only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from hermesoptimizer.tool_surface.schema import (
    HelpContract,
    OutputContract,
    RiskLevel,
    SurfaceKind,
    ToolSurface,
)


# --------------------------------------------------------------------------
# Scoring constants
# --------------------------------------------------------------------------


SCORE_BASE_ENDPOINT = 0.5
SCORE_BASE_TRUTH = 0.7
SCORE_BASE_MODEL = 0.5

SCORE_LANE_MATCH_BONUS = 0.2
SCORE_CAPABILITY_MATCH_FRACTION = 0.1
SCORE_REGION_MATCH_BONUS = 0.1
SCORE_LATENCY_FAST_BONUS = 0.1
SCORE_DEPRECATION_PENALTY = 0.3


# --------------------------------------------------------------------------
# Protocol types for catalog interfaces (type safety without heavy deps)
# --------------------------------------------------------------------------


@runtime_checkable
class ModelCatalogReader(Protocol):
    """Minimal protocol for model catalog access."""

    def list_all_models(self) -> list[dict[str, Any]]: ...


@runtime_checkable
class EndpointCatalogReader(Protocol):
    """Minimal protocol for endpoint catalog access."""

    @property
    def provider_slugs(self) -> list[str]: ...

    def get_provider(self, slug: str) -> dict[str, Any] | None: ...

    def get_default_endpoint(self, slug: str) -> dict[str, Any] | None: ...


@runtime_checkable
class TruthStoreReader(Protocol):
    """Minimal protocol for truth store access."""

    def all_records(self) -> list[Any]: ...


# ---------------------------------------------------------------------------
# SafetyLane enum
# ---------------------------------------------------------------------------


class SafetyLane(Enum):
    """
    Safety lane classification for provider/model recommendations.

    Lanes provide safety isolation for different task categories:
    - CODING: Code generation and editing tasks
    - REASONING: Complex reasoning and analysis tasks
    - GENERAL: General-purpose text tasks
    """

    CODING = "coding"
    REASONING = "reasoning"
    GENERAL = "general"


# ---------------------------------------------------------------------------
# ToolSurface definition
# ---------------------------------------------------------------------------


PROVIDER_RECOMMEND = ToolSurface(
    surface_name="provider_recommend",
    command_name="recommend_provider",
    kind=SurfaceKind.TYPED,
    risk_level=RiskLevel.LOW,
    supports_help=True,
    supports_partial_discovery=False,
    supports_overflow_handle=False,
    supports_binary_guard=False,
    read_only=True,
    recommended_for_agent=True,
    notes=(
        "Hermes-grade provider/model recommender using live config evidence, "
        "known auth presence, checked-in endpoint/model catalogs, provenance "
        "tracking, and safety lane logic. Produces ranked recommendations "
        "with reason strings, lane classification, and validated config snippets. "
        "Backed by sources/provider_truth.py, schemas/provider_endpoint.py, "
        "schemas/provider_model.py, and verify/config_fix.py."
    ),
    help_contract=HelpContract(usage="help recommend_provider"),
    output_contract=OutputContract(format="json"),
)


# ---------------------------------------------------------------------------
# Recommendation types
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ProviderRecommendation:
    """
    A single provider/model recommendation with ranking and metadata.

    Attributes:
        provider: Canonical provider name (e.g., "openai", "anthropic")
        model: Recommended model name (e.g., "gpt-4o", "claude-3-5-sonnet")
        endpoint: Recommended endpoint URL
        rank_score: Ranking score (0.0-1.0, higher is better)
        reason: Human-readable reason string explaining the recommendation
        lane: SafetyLane classification for this recommendation
        config_snippet: Validated config YAML snippet (None until validation passes)
        provenance: Source of this recommendation (e.g., "catalog:testprovider")
    """

    provider: str
    model: str
    endpoint: str
    rank_score: float
    reason: str
    lane: SafetyLane
    config_snippet: str | None = None
    provenance: str = ""

    def __post_init__(self) -> None:
        """Validate rank_score is in valid range."""
        if not 0.0 <= self.rank_score <= 1.0:
            raise ValueError(f"rank_score must be between 0.0 and 1.0, got {self.rank_score}")


@dataclass(slots=True)
class ProviderRecommendInput:
    """
    Input parameters for provider/model recommendation.

    Attributes:
        desired_capabilities: List of required capabilities (e.g., ["text", "vision"])
        desired_lane: Preferred safety lane for the recommendation
        region_preference: Preferred region code (e.g., "us", "eu")
        auth_presence: Dict mapping provider names to whether auth is available
    """

    desired_capabilities: list[str] = field(default_factory=list)
    desired_lane: SafetyLane = SafetyLane.GENERAL
    region_preference: str | None = None
    auth_presence: dict[str, bool] = field(default_factory=dict)


@dataclass(slots=True)
class ProviderRecommendOutput:
    """
    Output from provider/model recommendation.

    Attributes:
        recommendations: List of ProviderRecommendation, sorted by rank_score descending
        total_candidates: Total number of candidates considered
        validation_passed: Whether validation passed (enables config_snippet generation)
    """

    recommendations: list[ProviderRecommendation] = field(default_factory=list)
    total_candidates: int = 0
    validation_passed: bool = False


# ---------------------------------------------------------------------------
# ProviderRecommender
# ---------------------------------------------------------------------------


class ProviderRecommender:
    """
    Hermes-grade provider/model recommender.

    Produces ranked recommendations using:
    - ProviderTruthStore for canonical provider information
    - ProviderEndpointCatalog for endpoint information
    - ProviderModelCatalog for model information
    - Config evidence and auth presence signals

    Parameters
    ----------
    truth_store : ProviderTruthStore | None
        Canonical provider truth records
    endpoint_catalog : ProviderEndpointCatalog | None
        Provider endpoint catalog
    model_catalog : ProviderModelCatalog | None
        Provider model catalog
    """

    def __init__(
        self,
        truth_store: TruthStoreReader | None,
        endpoint_catalog: EndpointCatalogReader | None,
        model_catalog: ModelCatalogReader | None,
    ) -> None:
        self._truth = truth_store
        self._endpoints = endpoint_catalog
        self._models = model_catalog

    def recommend(self, inp: ProviderRecommendInput) -> ProviderRecommendOutput:
        """
        Produce ranked provider/model recommendations.

        Parameters
        ----------
        inp : ProviderRecommendInput
            Input parameters for recommendation

        Returns
        -------
        ProviderRecommendOutput
            Ranked recommendations with metadata
        """
        candidates: list[ProviderRecommendation] = []
        total_candidates = 0

        # Collect candidates from available sources
        if self._models is not None:
            model_candidates, total = self._collect_from_model_catalog(inp)
            candidates.extend(model_candidates)
            total_candidates += total

        if self._endpoints is not None:
            endpoint_candidates, total = self._collect_from_endpoint_catalog(inp)
            candidates.extend(endpoint_candidates)
            total_candidates += total

        if self._truth is not None:
            truth_candidates, total = self._collect_from_truth_store(inp)
            candidates.extend(truth_candidates)
            total_candidates += total

        # Filter by auth presence
        candidates = self._filter_by_auth(candidates, inp.auth_presence)

        # Sort by rank_score descending, then provider/model for determinism
        candidates.sort(key=lambda r: (r.rank_score, r.provider, r.model), reverse=True)

        # Validate and potentially generate config snippets
        validation_passed = self._validate_candidates(candidates)
        if validation_passed:
            candidates = self._generate_config_snippets(candidates, inp)

        return ProviderRecommendOutput(
            recommendations=candidates,
            total_candidates=total_candidates,
            validation_passed=validation_passed,
        )

    def _collect_from_model_catalog(
        self, inp: ProviderRecommendInput
    ) -> tuple[list[ProviderRecommendation], int]:
        """Collect recommendations from model catalog."""
        candidates: list[ProviderRecommendation] = []
        if self._models is None:
            return candidates, 0

        total = 0
        for model in self._models.list_all_models():
            total += 1
            rec = self._model_to_recommendation(model, inp)
            if rec is not None:
                candidates.append(rec)

        return candidates, total

    def _collect_from_endpoint_catalog(
        self, inp: ProviderRecommendInput
    ) -> tuple[list[ProviderRecommendation], int]:
        """Collect recommendations from endpoint catalog."""
        candidates: list[ProviderRecommendation] = []
        if self._endpoints is None:
            return candidates, 0

        total = 0
        for slug in self._endpoints.provider_slugs:
            total += 1
            rec = self._endpoint_to_recommendation(slug, inp)
            if rec is not None:
                candidates.append(rec)

        return candidates, total

    def _collect_from_truth_store(
        self, inp: ProviderRecommendInput
    ) -> tuple[list[ProviderRecommendation], int]:
        """Collect recommendations from truth store."""
        candidates: list[ProviderRecommendation] = []
        if self._truth is None:
            return candidates, 0

        total = 0
        for rec in self._truth.all_records():
            total += 1
            recommendation = self._truth_to_recommendation(rec, inp)
            if recommendation is not None:
                candidates.append(recommendation)

        return candidates, total

    def _model_to_recommendation(
        self, model: dict[str, Any], inp: ProviderRecommendInput
    ) -> ProviderRecommendation | None:
        """Convert a model catalog entry to a recommendation."""
        provider_slug = model.get("provider_slug", "")
        model_name = model.get("model_name", "")
        capabilities = model.get("capabilities", [])
        lane = self._infer_lane(model_name, capabilities)
        endpoint_url = model.get("endpoint_url") or ""
        provenance = f"catalog:{provider_slug}"

        # Check if model has required capabilities
        if inp.desired_capabilities:
            if not all(cap in capabilities for cap in inp.desired_capabilities):
                return None

        # Calculate rank score based on capabilities match and lane match
        score = self._calculate_score(model, inp, lane)

        # Build reason string
        reason = self._build_reason(model, capabilities, lane)

        return ProviderRecommendation(
            provider=provider_slug,
            model=model_name,
            endpoint=endpoint_url,
            rank_score=score,
            reason=reason,
            lane=lane,
            config_snippet=None,
            provenance=provenance,
        )

    def _endpoint_to_recommendation(
        self, provider_slug: str, inp: ProviderRecommendInput
    ) -> ProviderRecommendation | None:
        """Convert an endpoint catalog entry to a recommendation."""
        provider = self._endpoints.get_provider(provider_slug)
        if provider is None:
            return None

        default_endpoint = self._endpoints.get_default_endpoint(provider_slug)
        if default_endpoint is None:
            return None

        base_url = default_endpoint.get("base_url", "")
        api_style = default_endpoint.get("api_style", "openai-compatible")

        # Create a basic recommendation for the endpoint
        lane = SafetyLane.GENERAL
        score = SCORE_BASE_ENDPOINT
        provenance = f"catalog:{provider_slug}"

        reason = f"Endpoint available via {api_style} API"

        return ProviderRecommendation(
            provider=provider_slug,
            model="",  # No specific model for endpoint-only recommendation
            endpoint=base_url,
            rank_score=score,
            reason=reason,
            lane=lane,
            config_snippet=None,
            provenance=provenance,
        )

    def _truth_to_recommendation(
        self, rec: Any, inp: ProviderRecommendInput
    ) -> ProviderRecommendation | None:
        """Convert a truth store record to a recommendation."""
        provider = rec.provider
        canonical_endpoint = rec.canonical_endpoint
        known_models = rec.known_models
        capabilities = rec.capabilities
        regions = rec.regions

        # Check region preference
        if inp.region_preference and regions:
            if inp.region_preference not in regions:
                return None

        # Pick best model from known models
        model = known_models[0] if known_models else ""

        lane = SafetyLane.GENERAL
        score = SCORE_BASE_TRUTH

        if capabilities:
            if "reasoning" in capabilities:
                lane = SafetyLane.REASONING
            if "coding" in capabilities or "code" in capabilities:
                lane = SafetyLane.CODING

        provenance = f"truth:{provider}"

        reason = f"Known provider with {len(known_models)} verified models"

        return ProviderRecommendation(
            provider=provider,
            model=model,
            endpoint=canonical_endpoint,
            rank_score=score,
            reason=reason,
            lane=lane,
            config_snippet=None,
            provenance=provenance,
        )

    def _filter_by_auth(
        self,
        candidates: list[ProviderRecommendation],
        auth_presence: dict[str, bool],
    ) -> list[ProviderRecommendation]:
        """Filter candidates by auth presence."""
        if not auth_presence:
            return candidates

        return [
            c for c in candidates
            if auth_presence.get(c.provider, False)
        ]

    def _validate_candidates(
        self, candidates: list[ProviderRecommendation]
    ) -> bool:
        """Validate candidates meet minimum requirements."""
        if not candidates:
            return False

        # All candidates must have valid providers and endpoints
        for c in candidates:
            if not c.provider:
                return False
            if not c.endpoint:
                return False
            if not c.endpoint.startswith(("http://", "https://")):
                return False

        return True

    def _generate_config_snippets(
        self,
        candidates: list[ProviderRecommendation],
        inp: ProviderRecommendInput,
    ) -> list[ProviderRecommendation]:
        """Generate config snippets for validated candidates."""
        result: list[ProviderRecommendation] = []

        for c in candidates:
            snippet = self._build_config_snippet(c, inp)
            result.append(
                ProviderRecommendation(
                    provider=c.provider,
                    model=c.model,
                    endpoint=c.endpoint,
                    rank_score=c.rank_score,
                    reason=c.reason,
                    lane=c.lane,
                    config_snippet=snippet,
                    provenance=c.provenance,
                )
            )

        return result

    def _build_config_snippet(
        self, rec: ProviderRecommendation, inp: ProviderRecommendInput
    ) -> str:
        """Build a config snippet for a recommendation."""
        snippet_lines = [
            f"  {rec.provider}_primary:",
            f"    base_url: {rec.endpoint}",
            f"    auth_type: bearer",
            f"    auth_key_env: {rec.provider.upper()}_API_KEY",
            f"    model: {rec.model}",
            f"    lane: {rec.lane.value}",
        ]
        return "\n".join(snippet_lines)

    def _infer_lane(self, model_name: str, capabilities: list[str]) -> SafetyLane:
        """Infer safety lane from model name and capabilities."""
        model_lower = model_name.lower()

        # Check model name patterns
        if any(kw in model_lower for kw in ["code", "coder", "coding", "gpt-4", "gpt-5"]):
            return SafetyLane.CODING
        if any(kw in model_lower for kw in ["claude", "reason", "think", "o1", "o3", "o4"]):
            return SafetyLane.REASONING

        # Check capabilities
        if "coding" in capabilities or "code" in capabilities:
            return SafetyLane.CODING
        if "reasoning" in capabilities:
            return SafetyLane.REASONING

        return SafetyLane.GENERAL

    def _calculate_score(
        self, model: dict[str, Any], inp: ProviderRecommendInput, lane: SafetyLane
    ) -> float:
        """Calculate rank score for a model."""
        score = SCORE_BASE_MODEL

        # Lane match bonus
        if lane == inp.desired_lane:
            score += SCORE_LANE_MATCH_BONUS

        # Capability match bonus
        capabilities = model.get("capabilities", [])
        if inp.desired_capabilities:
            match_count = sum(1 for cap in inp.desired_capabilities if cap in capabilities)
            score += SCORE_CAPABILITY_MATCH_FRACTION * (match_count / len(inp.desired_capabilities))

        # Region availability
        region_avail = model.get("region_availability")
        if region_avail and inp.region_preference:
            if inp.region_preference in region_avail:
                score += SCORE_REGION_MATCH_BONUS

        # Latency tier bonus
        latency_tier = model.get("latency_tier", "")
        if latency_tier == "fast":
            score += SCORE_LATENCY_FAST_BONUS

        # Deprecation penalty
        if model.get("is_deprecated", False):
            score -= SCORE_DEPRECATION_PENALTY

        return max(0.0, min(1.0, score))

    def _build_reason(
        self, model: dict[str, Any], capabilities: list[str], lane: SafetyLane
    ) -> str:
        """Build human-readable reason string."""
        parts: list[str] = []

        if capabilities:
            parts.append(f"supports {', '.join(capabilities[:3])}")

        parts.append(f"lane={lane.value}")

        if model.get("is_deprecated", False):
            parts.append("(deprecated)")

        latency = model.get("latency_tier")
        if latency:
            parts.append(f"latency={latency}")

        return "; ".join(parts) if parts else "Available model"
