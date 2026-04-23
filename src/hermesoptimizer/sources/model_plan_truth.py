"""
Phase B: Model/Provider/Plan Truth — enforcement layer for truthful model selection.

This module provides strict verification that provider/model/plan/capability must all
agree before a model is considered valid. It implements fail-closed logic to prevent
invalid combinations from being selected.

Key behaviors:
- Model selection must verify provider availability, plan eligibility, and capability match
- Invalid combinations are rejected with specific error codes
- User model choices are preserved and never overwritten by harness defaults
- GLM-5.1V-on-provider-but-not-coding-plan type mismatch is explicitly handled

Design principles (from TODO.md):
- If provider truth and config truth disagree, provider truth wins
- If install safety and convenience disagree, install safety wins
- Best effort means live probe, not assumption
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# -----------------------------------------------------------------------------
# Plan/Lane enums (mirrors SafetyLane from provider_recommend but is authoritative)
# -----------------------------------------------------------------------------


class SafetyLane(str, Enum):
    """Safety lane classification for provider/model recommendations.

    Lanes provide safety isolation for different task categories:
    - CODING: Code generation and editing tasks
    - REASONING: Complex reasoning and analysis tasks
    - GENERAL: General-purpose text tasks
    """

    CODING = "coding"
    REASONING = "reasoning"
    GENERAL = "general"


# -----------------------------------------------------------------------------
# Selection context
# -----------------------------------------------------------------------------


@dataclass(slots=True)
class ModelSelectionContext:
    """
    Context for model selection including plan, provider, and required capabilities.

    This is the input to the model selection verifier. All fields must agree
    for a model to be considered valid.

    Attributes:
        plan: The safety lane/plan type (coding, reasoning, general)
        provider: The provider name (e.g., "openai", "zai", "qwen")
        required_capabilities: List of required capabilities (e.g., ["coding", "text"])
        user_model: The user's explicitly configured model (if any) - preserved, not overwritten
        harness_default_model: The harness's internal default model (separate from user)
    """

    plan: SafetyLane
    provider: str
    required_capabilities: list[str] = field(default_factory=list)
    user_model: str | None = None
    harness_default_model: str | None = None


# -----------------------------------------------------------------------------
# Selection result types
# -----------------------------------------------------------------------------


class SelectionStatus(Enum):
    """Status of a model selection attempt."""

    VALID = "valid"  # Model passes all checks
    UNKNOWN_PROVIDER = "unknown_provider"  # Provider not in truth store
    MODEL_NOT_IN_CATALOG = "model_not_in_catalog"  # Model not found in catalog
    CAPABILITY_MISMATCH = "capability_mismatch"  # Model lacks required capabilities
    PLAN_INELIGIBLE = "plan_ineligible"  # Model not available on this plan
    PROVIDER_UNAVAILABLE = "provider_unavailable"  # Provider not available
    USER_MODEL_PRESERVED = "user_model_preserved"  # User's model was explicitly chosen
    HARNESS_DEFAULT_USED = "harness_default_used"  # No user model, using harness default


@dataclass(slots=True)
class ModelSelectionResult:
    """
    Result of a model selection verification.

    Attributes:
        status: The selection status
        model: The model that was selected (or would be selected)
        provider: The provider
        capabilities: The model's capabilities
        message: Human-readable message explaining the result
        errors: List of specific errors if selection failed
        is_user_model: True if this is the user's explicitly configured model
        is_harness_default: True if this is the harness's internal default
    """

    status: SelectionStatus
    model: str
    provider: str
    capabilities: list[str] = field(default_factory=list)
    message: str = ""
    errors: list[str] = field(default_factory=list)
    is_user_model: bool = False
    is_harness_default: bool = False

    def is_valid(self) -> bool:
        """Return True if selection is valid."""
        return self.status == SelectionStatus.VALID or self.status == SelectionStatus.USER_MODEL_PRESERVED

    def is_rejected(self) -> bool:
        """Return True if selection was rejected (fail-closed)."""
        return self.status in (
            SelectionStatus.UNKNOWN_PROVIDER,
            SelectionStatus.MODEL_NOT_IN_CATALOG,
            SelectionStatus.CAPABILITY_MISMATCH,
            SelectionStatus.PLAN_INELIGIBLE,
            SelectionStatus.PROVIDER_UNAVAILABLE,
        )


# -----------------------------------------------------------------------------
# Capability matrix (maps plan/lane to required capabilities)
# -----------------------------------------------------------------------------


# Required capabilities by plan/lane
_PLAN_REQUIRED_CAPABILITIES: dict[SafetyLane, list[str]] = {
    SafetyLane.CODING: ["coding"],
    SafetyLane.REASONING: ["reasoning"],
    SafetyLane.GENERAL: ["text"],
}


def _get_plan_required_capabilities(plan: SafetyLane) -> list[str]:
    """Get the required capabilities for a given plan."""
    return _PLAN_REQUIRED_CAPABILITIES.get(plan, ["text"])


def _capabilities_satisfy(required: list[str], available: list[str]) -> tuple[bool, list[str]]:
    """
    Check if available capabilities satisfy required capabilities.

    Returns (satisfied, missing_capabilities).
    """
    available_set = set(available)
    missing = [cap for cap in required if cap not in available_set]
    return len(missing) == 0, missing


# -----------------------------------------------------------------------------
# GLM-5.1V scenario handler
#
# The GLM-5.1V issue (from TODO):
# "GLM-5.1V is not selectable on a coding plan if the live plan does not expose it"
#
# This handles the case where:
# - A model exists on the provider (e.g., GLM-4.6V with vision capability)
# - But the model does NOT have the required capability for the plan
#   (e.g., GLM-4.6V lacks "coding" capability, so can't be used on coding plan)
# - The selection must FAIL-CLOSED rather than returning a mismatched model
# -----------------------------------------------------------------------------


@dataclass(slots=True)
class GLMTypeMismatchCase:
    """
    Represents a GLM-type model capability mismatch case.

    Example: GLM-4.6V has vision capability but NOT coding capability.
    If a user requests a coding plan, GLM-4.6V should be rejected.
    """

    model_name: str
    provider: str
    has_coding: bool
    has_vision: bool
    has_reasoning: bool


# Known GLM-type models with their capability profiles (from model_catalog.py)
_GLM_CAPABILITY_PROFILES: dict[str, GLMTypeMismatchCase] = {
    # GLM-5.1 has coding capability
    "glm-5.1": GLMTypeMismatchCase(
        model_name="glm-5.1",
        provider="zai",
        has_coding=True,
        has_vision=False,
        has_reasoning=True,
    ),
    # GLM-5 has coding capability
    "glm-5": GLMTypeMismatchCase(
        model_name="glm-5",
        provider="zai",
        has_coding=True,
        has_vision=False,
        has_reasoning=True,
    ),
    # GLM-4.6 does NOT have coding capability
    "glm-4.6": GLMTypeMismatchCase(
        model_name="glm-4.6",
        provider="zai",
        has_coding=False,
        has_vision=False,
        has_reasoning=True,
    ),
    # GLM-4.6V has vision but NOT coding capability
    "glm-4.6v": GLMTypeMismatchCase(
        model_name="glm-4.6v",
        provider="zai",
        has_coding=False,
        has_vision=True,
        has_reasoning=True,
    ),
}


def check_glm_mismatch(
    model: str,
    provider: str,
    required_capabilities: list[str],
) -> tuple[bool, str]:
    """
    Check if a GLM model has a capability mismatch for the required plan.

    Returns (is_mismatch, error_message).
    If is_mismatch is True, the model should NOT be selected for this plan.
    """
    provider_lower = provider.lower().strip()
    if provider_lower not in ("zai", "glm"):
        return False, ""

    model_lower = model.lower().strip()
    profile = _GLM_CAPABILITY_PROFILES.get(model_lower)
    if profile is None:
        return False, ""

    # Check if coding is required but this model doesn't have it
    if "coding" in required_capabilities and not profile.has_coding:
        return True, (
            f"Model '{model}' on provider '{provider}' lacks 'coding' capability. "
            f"It has: vision={profile.has_vision}, reasoning={profile.has_reasoning}, coding={profile.has_coding}. "
            f"This model cannot be used on a coding plan."
        )

    return False, ""


# -----------------------------------------------------------------------------
# Model selection verifier
# -----------------------------------------------------------------------------


class ModelSelectionVerifier:
    """
    Verifies that a model selection is valid for the given context.

    This implements fail-closed logic: any mismatch in provider/model/plan/capability
    results in rejection, not a fallback to a different model.
    """

    def __init__(
        self,
        catalog: Any | None = None,  # ProviderModelCatalog - lazily imported
        truth_store: Any | None = None,  # ProviderTruthStore - lazily imported
    ) -> None:
        self._catalog = catalog
        self._truth_store = truth_store

    def _get_catalog(self) -> Any:
        """Lazily import and return the model catalog."""
        if self._catalog is None:
            from hermesoptimizer.sources.model_catalog import MODEL_CATALOG
            self._catalog = MODEL_CATALOG
        return self._catalog

    def _get_truth_store(self) -> Any:
        """Lazily import and return the truth store."""
        if self._truth_store is None:
            from hermesoptimizer.sources.provider_truth import ProviderTruthStore
            self._truth_store = ProviderTruthStore()
        return self._truth_store

    def verify(
        self,
        model: str,
        provider: str,
        plan: SafetyLane,
        required_capabilities: list[str] | None = None,
        user_model: str | None = None,
    ) -> ModelSelectionResult:
        """
        Verify that a model is valid for the given context.

        Parameters:
            model: The model name to verify
            provider: The provider name
            plan: The safety lane/plan type
            required_capabilities: Additional required capabilities beyond the plan default
            user_model: The user's explicitly configured model (preserved, not overwritten)

        Returns:
            ModelSelectionResult with status and details
        """
        if required_capabilities is None:
            required_capabilities = []

        # Combine plan-required capabilities with explicitly required ones
        plan_caps = _get_plan_required_capabilities(plan)
        all_required = list(set(plan_caps + required_capabilities))

        # Check for GLM-type mismatches first (specific case from TODO)
        has_glm_mismatch, glm_error = check_glm_mismatch(model, provider, all_required)
        if has_glm_mismatch:
            return ModelSelectionResult(
                status=SelectionStatus.CAPABILITY_MISMATCH,
                model=model,
                provider=provider,
                capabilities=[],
                message=glm_error,
                errors=[glm_error],
                is_user_model=(user_model is not None and model.lower() == user_model.lower()),
            )

        provider_lower = provider.lower().strip()

        # --- Provider rejection: must be known before catalog lookup ---
        catalog = self._get_catalog()
        truth_store = self._get_truth_store()
        rec = truth_store.get(provider_lower)
        known_in_catalog = catalog is not None and provider_lower in catalog.list_providers()

        if rec is None and not known_in_catalog:
            # Provider is unknown to both truth store and catalog — hard reject
            return ModelSelectionResult(
                status=SelectionStatus.UNKNOWN_PROVIDER,
                model=model,
                provider=provider,
                capabilities=[],
                message=f"Provider '{provider}' is unknown (not in truth store or catalog)",
                errors=[f"Provider '{provider}' is unregistered"],
                is_user_model=(user_model is not None and model.lower() == user_model.lower()),
            )

        if rec is not None and not rec.canonical_endpoint:
            # Provider is registered but has no live endpoint — unavailable
            return ModelSelectionResult(
                status=SelectionStatus.PROVIDER_UNAVAILABLE,
                model=model,
                provider=provider,
                capabilities=[],
                message=f"Provider '{provider}' is registered but unavailable (no canonical endpoint)",
                errors=[f"Provider '{provider}' has no canonical endpoint configured"],
                is_user_model=(user_model is not None and model.lower() == user_model.lower()),
            )

        if rec is not None:
            is_stale, stale_msg = truth_store.check_stale_model(provider_lower, model)
            if is_stale:
                return ModelSelectionResult(
                    status=SelectionStatus.MODEL_NOT_IN_CATALOG,
                    model=model,
                    provider=provider,
                    capabilities=[],
                    message=f"Model '{model}' on provider '{provider}' is stale or unknown: {stale_msg}",
                    errors=[stale_msg],
                    is_user_model=(user_model is not None and model.lower() == user_model.lower()),
                )

        # Get the model from catalog
        model_entry = catalog.get(provider_lower, model) if catalog else None

        if model_entry is None:
            # Model not in catalog - check if it's a user-prescribed model
            is_user = user_model is not None and model.lower() == user_model.lower()
            if is_user:
                return ModelSelectionResult(
                    status=SelectionStatus.USER_MODEL_PRESERVED,
                    model=model,
                    provider=provider,
                    capabilities=[],
                    message=f"User-prescribed model '{model}' on '{provider}' - preserving user's choice",
                    is_user_model=True,
                )
            return ModelSelectionResult(
                status=SelectionStatus.MODEL_NOT_IN_CATALOG,
                model=model,
                provider=provider,
                capabilities=[],
                message=f"Model '{model}' not found in catalog for provider '{provider}'",
                errors=[f"Model '{model}' is not in the known model list for '{provider}'"],
            )

        # Check capabilities
        available_caps = list(model_entry.capabilities)
        satisfied, missing = _capabilities_satisfy(all_required, available_caps)
        if not satisfied:
            return ModelSelectionResult(
                status=SelectionStatus.CAPABILITY_MISMATCH,
                model=model,
                provider=provider,
                capabilities=available_caps,
                message=f"Model '{model}' lacks required capabilities: {missing}",
                errors=[f"Missing capabilities: {', '.join(missing)}"],
                is_user_model=(user_model is not None and model.lower() == user_model.lower()),
            )

        # All checks passed
        return ModelSelectionResult(
            status=SelectionStatus.VALID,
            model=model,
            provider=provider,
            capabilities=available_caps,
            message=f"Model '{model}' on '{provider}' is valid for plan '{plan.value}' with capabilities {available_caps}",
            is_user_model=(user_model is not None and model.lower() == user_model.lower()),
        )

    def verify_for_context(self, ctx: ModelSelectionContext) -> ModelSelectionResult:
        """
        Verify model selection for a complete context.

        This checks:
        1. If user has a model, it's preserved (never overwritten)
        2. If no user model, verify the suggested model is valid
        3. Provider/model/plan/capability must all agree
        """
        # If user has a model, verify it or preserve it
        if ctx.user_model:
            result = self.verify(
                model=ctx.user_model,
                provider=ctx.provider,
                plan=ctx.plan,
                required_capabilities=ctx.required_capabilities,
                user_model=ctx.user_model,
            )
            # If user's model is invalid, we fail-closed rather than replacing it
            if result.is_rejected():
                return ModelSelectionResult(
                    status=SelectionStatus.CAPABILITY_MISMATCH,
                    model=ctx.user_model,
                    provider=ctx.provider,
                    message=(
                        f"User's model '{ctx.user_model}' is invalid for plan '{ctx.plan.value}' "
                        f"on provider '{ctx.provider}', but user's choice is PRESERVED (not overwritten). "
                        f"Error: {result.errors}"
                    ),
                    errors=result.errors,
                    is_user_model=True,
                )
            return result

        # No user model - verify harness default if present
        if ctx.harness_default_model:
            result = self.verify(
                model=ctx.harness_default_model,
                provider=ctx.provider,
                plan=ctx.plan,
                required_capabilities=ctx.required_capabilities,
            )
            if result.is_valid():
                return ModelSelectionResult(
                    status=SelectionStatus.HARNESS_DEFAULT_USED,
                    model=result.model,
                    provider=result.provider,
                    capabilities=result.capabilities,
                    message=f"Using harness default: {result.message}",
                    is_harness_default=True,
                )
            # Harness default is invalid - fail-closed
            return ModelSelectionResult(
                status=SelectionStatus.CAPABILITY_MISMATCH,
                model=ctx.harness_default_model,
                provider=ctx.provider,
                message=(
                    f"Harness default model '{ctx.harness_default_model}' is invalid for "
                    f"plan '{ctx.plan.value}' on provider '{ctx.provider}'. "
                    f"Selection cannot proceed without a valid model."
                ),
                errors=result.errors,
                is_harness_default=True,
            )

        # No model at all - can't select
        return ModelSelectionResult(
            status=SelectionStatus.CAPABILITY_MISMATCH,
            model="",
            provider=ctx.provider,
            message="No model specified and no default available",
            errors=["No model available for selection"],
        )


# -----------------------------------------------------------------------------
# Convenience function for simple verification
# -----------------------------------------------------------------------------


def verify_model_for_plan(
    model: str,
    provider: str,
    plan: SafetyLane,
    required_capabilities: list[str] | None = None,
    user_model: str | None = None,
) -> ModelSelectionResult:
    """
    Verify that a model is valid for the given plan.

    This is a convenience function that creates a verifier and checks the model.

    Parameters:
        model: The model name to verify
        provider: The provider name
        plan: The safety lane/plan type (coding, reasoning, general)
        required_capabilities: Additional required capabilities
        user_model: The user's explicitly configured model (preserved)

    Returns:
        ModelSelectionResult with status and details

    Examples:
        >>> result = verify_model_for_plan("glm-4.6v", "zai", SafetyLane.CODING)
        >>> result.is_valid()
        False
        >>> result.status
        <SelectionStatus.CAPABILITY_MISMATCH>
    """
    verifier = ModelSelectionVerifier()
    return verifier.verify(model, provider, plan, required_capabilities, user_model)
