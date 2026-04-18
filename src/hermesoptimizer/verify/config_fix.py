"""
Config-fixing pass: safe repair recommendations from provider/model/config evidence.

Turns Hermes config drift into specific safe repair recommendations, classified as:
- auto-fix now: safe to automatically fix without user confirmation
- recommend-and-confirm: needs user confirmation before fixing
- human-only: cannot be automatically fixed, needs human intervention

Reconciles evidence across:
- config findings
- endpoint verification results
- provider truth store

Key behaviors:
- For stale aliases: recommend the correct model name (auto-fix if confidence is high)
- For deprecated models: recommend available replacements (recommend-and-confirm)
- For RKWE: probe known-good endpoints and promote first contract-valid (auto-fix if candidates available)
- For stale API keys: recommend removal and provide replacement key insert path
- For OAuth failures: classify as human-only
- For API key failures: recommend key rotation (recommend-and-confirm)
- For network errors: recommend retry or connectivity check
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from hermesoptimizer.route.diagnosis import Priority
from hermesoptimizer.sources.provider_truth import ProviderTruthStore
from hermesoptimizer.verify.endpoints import EndpointCheckResult, EndpointCheckStatus


# --------------------------------------------------------------------------- #
# Action classification enum
# --------------------------------------------------------------------------- #


class ConfigFixAction(Enum):
    """
    Classification of repair actions by safety and required confirmation level.

    AUTO_FIX: Safe to automatically fix without user confirmation.
              Examples: stale alias correction, endpoint fix with known candidates.
    RECOMMEND: Needs user confirmation before fixing.
               Examples: deprecated model replacement, key rotation, network retry.
    HUMAN_ONLY: Cannot be automatically fixed; requires human intervention.
                Examples: OAuth failures requiring sign-in, unknown providers.
    """

    AUTO_FIX = "auto-fix"
    RECOMMEND = "recommend"
    HUMAN_ONLY = "human-only"

    def sort_key(self) -> int:
        """Lower number = more automated (for sorting)."""
        return _ACTION_SORT_KEYS[self]


# Map each action to its sort order (0 = most automated)
_ACTION_SORT_KEYS: dict[ConfigFixAction, int] = {
    ConfigFixAction.AUTO_FIX: 0,
    ConfigFixAction.RECOMMEND: 1,
    ConfigFixAction.HUMAN_ONLY: 2,
}


# --------------------------------------------------------------------------- #
# ConfigFix result type
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class ConfigFix:
    """
    A repair recommendation for a config drift issue.

    Attributes
    ----------
    provider : Provider name (e.g. "openai")
    model : Configured model name that needs fixing (may be None for endpoint-only issues)
    configured_endpoint : The currently configured endpoint URL
    correct_model : The recommended model name to use (None if no model change needed)
    correct_endpoint : The recommended endpoint URL to use (None if no endpoint change needed)
    action : Classification of required confirmation level
    code : Short diagnostic code (e.g. "STALE_ALIAS", "RKWE", "AUTH_FAILURE")
    summary : One-line human-readable description
    detail : Expanded explanation of the problem and context
    repair_steps : List of concrete repair steps to take
    lane : The Hermes lane this fix applies to (or None for global)
    source_fingerprint : Fingerprint of the originating finding (for dedup)
    """

    provider: str
    model: str | None
    configured_endpoint: str | None
    correct_model: str | None
    correct_endpoint: str | None
    action: ConfigFixAction
    code: str
    summary: str
    detail: str
    repair_steps: list[str] = field(default_factory=list)
    lane: str | None = None
    source_fingerprint: str | None = None

    def __repr__(self) -> str:
        return (
            f"ConfigFix(provider={self.provider!r}, model={self.model!r}, "
            f"action={self.action.value}, code={self.code!r}, "
            f"summary={self.summary!r})"
        )


# --------------------------------------------------------------------------- #
# ConfigFixer
# --------------------------------------------------------------------------- #


class ConfigFixer:
    """
    Produces safe repair recommendations from endpoint verification results
    and provider truth evidence.

    Parameters
    ----------
    truth_store : ProviderTruthStore with canonical provider information
    """

    def __init__(self, truth_store: ProviderTruthStore) -> None:
        self._truth = truth_store

    def produce_fixes(self, results: list[EndpointCheckResult]) -> list[ConfigFix]:
        """
        Convert endpoint verification results into repair recommendations.

        Parameters
        ----------
        results : List of EndpointCheckResult from verify_endpoint()

        Returns
        -------
        List[ConfigFix]
            One ConfigFix per issue that needs repair. OK results and unknown
            providers produce no fixes.
        """
        fixes: list[ConfigFix] = []
        for result in results:
            fix = self._produce_fix(result)
            if fix is not None:
                fixes.append(fix)
        return fixes

    def _produce_fix(self, result: EndpointCheckResult) -> ConfigFix | None:
        """Convert a single EndpointCheckResult to a ConfigFix if needed."""
        # Skip OK and unknown provider cases
        if result.status == EndpointCheckStatus.OK:
            return None
        if result.status == EndpointCheckStatus.UNKNOWN_PROVIDER:
            return None

        # Route to specific handler based on status
        handler_map: dict[EndpointCheckStatus, callable] = {
            EndpointCheckStatus.STALE_ALIAS: self._fix_stale_alias,
            EndpointCheckStatus.DEPRECATED_MODEL: self._fix_deprecated_model,
            EndpointCheckStatus.STALE_MODEL: self._fix_stale_model,
            EndpointCheckStatus.RKWE: self._fix_rkwe,
            EndpointCheckStatus.AUTH_FAILURE: self._fix_auth_failure,
            EndpointCheckStatus.NETWORK_ERROR: self._fix_network_error,
            EndpointCheckStatus.WRONG_ENDPOINT_ROUTING: self._fix_wrong_endpoint_routing,
            EndpointCheckStatus.ENDPOINT_DRIFT: self._fix_endpoint_drift,
            EndpointCheckStatus.MISSING_CAPABILITY: self._fix_missing_capability,
            EndpointCheckStatus.FAILED: self._fix_failed,
        }

        handler = handler_map.get(result.status)
        if handler is None:
            # Fallback for unhandled statuses
            return self._fix_generic(result)

        return handler(result)

    # ------------------------------------------------------------------------- #
    # Status-specific fix builders
    # ------------------------------------------------------------------------- #

    def _fix_stale_alias(self, result: EndpointCheckResult) -> ConfigFix:
        """Fix a stale model alias with the correct model name."""
        correct_model = result.details.get("correct_model", "")
        original_model = result.details.get("original_model", result.model or "")
        lane = result.details.get("lane")

        return ConfigFix(
            provider=result.provider,
            model=original_model,
            configured_endpoint=result.configured_endpoint,
            correct_model=correct_model,
            correct_endpoint=None,
            action=ConfigFixAction.AUTO_FIX,  # Safe: known alias correction
            code="STALE_ALIAS",
            summary=f"Model '{original_model}' is a stale alias, use '{correct_model}'",
            detail=result.message,
            repair_steps=[
                f"Replace model '{original_model}' with '{correct_model}' in config.yaml"
            ],
            lane=lane,
            source_fingerprint=result.details.get("fingerprint"),
        )

    def _fix_deprecated_model(self, result: EndpointCheckResult) -> ConfigFix:
        """Fix a deprecated model by recommending available replacements."""
        rec = self._truth.get(result.provider)
        known_models = rec.known_models if rec else []
        lane = result.details.get("lane")

        # Build repair steps with available replacements
        repair_steps = [
            f"Replace deprecated model '{result.model}' in config.yaml"
        ]
        if known_models:
            replacements = ", ".join(known_models[:5])  # Limit to first 5
            repair_steps.append(f"Available replacements: {replacements}")

        return ConfigFix(
            provider=result.provider,
            model=result.model,
            configured_endpoint=result.configured_endpoint,
            correct_model=None,  # Human should pick from available
            correct_endpoint=None,
            action=ConfigFixAction.RECOMMEND,  # Needs human confirmation
            code="DEPRECATED_MODEL",
            summary=f"Model '{result.model}' is deprecated",
            detail=result.message,
            repair_steps=repair_steps,
            lane=lane,
            source_fingerprint=result.details.get("fingerprint"),
        )

    def _fix_stale_model(self, result: EndpointCheckResult) -> ConfigFix:
        """Fix an unknown/stale model not in the known list."""
        rec = self._truth.get(result.provider)
        known_models = rec.known_models if rec else []
        lane = result.details.get("lane")

        repair_steps = [
            f"Remove unknown model '{result.model}' from config.yaml or replace with a known model"
        ]
        if known_models:
            replacements = ", ".join(known_models[:5])
            repair_steps.append(f"Known models for '{result.provider}': {replacements}")

        return ConfigFix(
            provider=result.provider,
            model=result.model,
            configured_endpoint=result.configured_endpoint,
            correct_model=None,
            correct_endpoint=None,
            action=ConfigFixAction.RECOMMEND,  # Needs confirmation
            code="STALE_MODEL",
            summary=f"Model '{result.model}' is not in known model list",
            detail=result.message,
            repair_steps=repair_steps,
            lane=lane,
            source_fingerprint=result.details.get("fingerprint"),
        )

    def _fix_rkwe(self, result: EndpointCheckResult) -> ConfigFix:
        """Fix right-key-wrong-endpoint by promoting known-good endpoint."""
        rec = self._truth.get(result.provider)
        canonical = rec.canonical_endpoint if rec else result.details.get("canonical_endpoint", "")
        candidates = rec.get_stable_candidates() if rec else []
        lane = result.details.get("lane")

        # Determine correct endpoint: prefer canonical, then first stable candidate
        if canonical:
            correct_endpoint = canonical
        elif candidates:
            correct_endpoint = candidates[0].endpoint
        else:
            correct_endpoint = canonical or ""

        # Action depends on whether we have known-good candidates
        # AUTO_FIX only if we have explicit endpoint candidates (indicating we've probed them)
        # Otherwise recommend confirmation even if canonical endpoint is known
        if candidates:
            action = ConfigFixAction.AUTO_FIX
        else:
            action = ConfigFixAction.RECOMMEND

        repair_steps = [
            f"Update base_url for provider '{result.provider}' from '{result.configured_endpoint}' to '{correct_endpoint}'"
        ]

        return ConfigFix(
            provider=result.provider,
            model=result.model,
            configured_endpoint=result.configured_endpoint,
            correct_model=None,
            correct_endpoint=correct_endpoint,
            action=action,
            code="RKWE",
            summary=f"Endpoint mismatch for provider '{result.provider}'",
            detail=result.message,
            repair_steps=repair_steps,
            lane=lane,
            source_fingerprint=result.details.get("fingerprint"),
        )

    def _fix_auth_failure(self, result: EndpointCheckResult) -> ConfigFix:
        """Fix auth failure based on auth type."""
        rec = self._truth.get(result.provider)
        auth_type = rec.auth_type if rec else "api_key"
        lane = result.details.get("lane")

        if auth_type.lower() == "oauth" or result.details.get("escalation") == "human":
            # OAuth failures require human intervention
            return ConfigFix(
                provider=result.provider,
                model=result.model,
                configured_endpoint=result.configured_endpoint,
                correct_model=None,
                correct_endpoint=None,
                action=ConfigFixAction.HUMAN_ONLY,  # Requires human sign-in
                code="AUTH_FAILURE",
                summary=f"OAuth provider '{result.provider}' requires human sign-off",
                detail=result.message,
                repair_steps=[
                    f"Sign in to {result.provider} account manually",
                    "Renew OAuth credentials",
                    "Update auth configuration in config.yaml",
                ],
                lane=lane,
                source_fingerprint=result.details.get("fingerprint"),
            )

        # API key failures recommend key rotation
        return ConfigFix(
            provider=result.provider,
            model=result.model,
            configured_endpoint=result.configured_endpoint,
            correct_model=None,
            correct_endpoint=None,
            action=ConfigFixAction.RECOMMEND,  # Needs confirmation for key rotation
            code="AUTH_FAILURE",
            summary=f"API key may be stale or revoked for '{result.provider}'",
            detail=result.message,
            repair_steps=[
                "Verify the API key is valid",
                "Rotate the API key if necessary",
                f"Update auth_key_env for '{result.provider}' in config.yaml",
            ],
            lane=lane,
            source_fingerprint=result.details.get("fingerprint"),
        )

    def _fix_network_error(self, result: EndpointCheckResult) -> ConfigFix:
        """Fix network error by recommending retry or connectivity check."""
        lane = result.details.get("lane")

        return ConfigFix(
            provider=result.provider,
            model=result.model,
            configured_endpoint=result.configured_endpoint,
            correct_model=None,
            correct_endpoint=None,
            action=ConfigFixAction.RECOMMEND,  # May be transient
            code="NETWORK_ERROR",
            summary=f"Network error reaching '{result.provider}' - retry or check connectivity",
            detail=result.message,
            repair_steps=[
                "Check network connectivity",
                "Retry the request",
                "Verify the endpoint URL is correct",
            ],
            lane=lane,
            source_fingerprint=result.details.get("fingerprint"),
        )

    def _fix_wrong_endpoint_routing(self, result: EndpointCheckResult) -> ConfigFix:
        """Fix wrong endpoint routing for a specific model."""
        expected = result.details.get("expected_endpoint", "")
        lane = result.details.get("lane")

        repair_steps = [
            f"Update base_url for model '{result.model}' to '{expected}'"
        ]

        return ConfigFix(
            provider=result.provider,
            model=result.model,
            configured_endpoint=result.configured_endpoint,
            correct_model=None,
            correct_endpoint=expected,
            action=ConfigFixAction.AUTO_FIX,  # Routing is config-only
            code="WRONG_ENDPOINT_ROUTING",
            summary=f"Model '{result.model}' is routed to wrong endpoint",
            detail=result.message,
            repair_steps=repair_steps,
            lane=lane,
            source_fingerprint=result.details.get("fingerprint"),
        )

    def _fix_endpoint_drift(self, result: EndpointCheckResult) -> ConfigFix:
        """Fix endpoint drift by promoting the canonical endpoint."""
        rec = self._truth.get(result.provider)
        canonical = rec.canonical_endpoint if rec else ""
        lane = result.details.get("lane")

        return ConfigFix(
            provider=result.provider,
            model=result.model,
            configured_endpoint=result.configured_endpoint,
            correct_model=None,
            correct_endpoint=canonical,
            action=ConfigFixAction.AUTO_FIX,
            code="ENDPOINT_DRIFT",
            summary=f"Endpoint drift detected for '{result.provider}'",
            detail=result.message,
            repair_steps=[
                f"Update base_url from '{result.configured_endpoint}' to '{canonical}'"
            ],
            lane=lane,
            source_fingerprint=result.details.get("fingerprint"),
        )

    def _fix_missing_capability(self, result: EndpointCheckResult) -> ConfigFix:
        """Fix missing capability by recommending models with required capability."""
        missing = result.details.get("missing_capabilities", [])
        lane = result.details.get("lane")

        return ConfigFix(
            provider=result.provider,
            model=result.model,
            configured_endpoint=result.configured_endpoint,
            correct_model=None,
            correct_endpoint=None,
            action=ConfigFixAction.RECOMMEND,
            code="MISSING_CAPABILITY",
            summary=f"Model '{result.model}' is missing required capabilities: {missing}",
            detail=result.message,
            repair_steps=[
                f"Replace model '{result.model}' with one that supports: {', '.join(missing)}"
            ],
            lane=lane,
            source_fingerprint=result.details.get("fingerprint"),
        )

    def _fix_failed(self, result: EndpointCheckResult) -> ConfigFix:
        """Fix general failure with generic recommendation."""
        lane = result.details.get("lane")

        return ConfigFix(
            provider=result.provider,
            model=result.model,
            configured_endpoint=result.configured_endpoint,
            correct_model=None,
            correct_endpoint=None,
            action=ConfigFixAction.HUMAN_ONLY,
            code="FAILED",
            summary=f"General failure for '{result.provider}'",
            detail=result.message,
            repair_steps=[
                "Investigate the error in logs",
                "Verify configuration is correct",
            ],
            lane=lane,
            source_fingerprint=result.details.get("fingerprint"),
        )

    def _fix_generic(self, result: EndpointCheckResult) -> ConfigFix:
        """Fallback handler for any unhandled status."""
        return ConfigFix(
            provider=result.provider,
            model=result.model,
            configured_endpoint=result.configured_endpoint,
            correct_model=None,
            correct_endpoint=None,
            action=ConfigFixAction.RECOMMEND,
            code=result.status.value.upper() if result.status else "UNKNOWN",
            summary=f"Unhandled status: {result.message}",
            detail=result.message,
            repair_steps=["Review configuration and logs"],
            lane=result.details.get("lane"),
            source_fingerprint=result.details.get("fingerprint"),
        )


# --------------------------------------------------------------------------- #
# Priority ranking helpers
# --------------------------------------------------------------------------- #


# Map ConfigFixAction to Priority bucket for ranking
_ACTION_TO_PRIORITY: dict[ConfigFixAction, Priority] = {
    ConfigFixAction.AUTO_FIX: Priority.NICE_TO_HAVE,  # Safe, low urgency
    ConfigFixAction.RECOMMEND: Priority.IMPORTANT,    # Needs attention
    ConfigFixAction.HUMAN_ONLY: Priority.CRITICAL,   # Urgent human action
}


def rank_config_fixes(fixes: list[ConfigFix]) -> list[ConfigFix]:
    """
    Sort config fixes by urgency.

    Priority order (most urgent first):
    1. HUMAN_ONLY (CRITICAL)
    2. RECOMMEND (IMPORTANT)
    3. AUTO_FIX (NICE_TO_HAVE)

    Within the same priority, fixes are sorted by code for determinism.

    Parameters
    ----------
    fixes : List of ConfigFix to sort

    Returns
    -------
    list[ConfigFix]
        Sorted list with most urgent fixes first
    """
    def sort_key(fix: ConfigFix) -> tuple[int, int, str]:
        # Map action to priority bucket
        priority = _ACTION_TO_PRIORITY.get(fix.action, Priority.WHATEVER)
        priority_sort = priority.sort_key()
        # Within same priority, sort by action sort key
        action_sort = fix.action.sort_key()
        # Then by code for determinism
        return (priority_sort, action_sort, fix.code)

    return sorted(fixes, key=sort_key)


def bucket_config_fixes(
    fixes: list[ConfigFix],
) -> dict[ConfigFixAction, list[ConfigFix]]:
    """Group config fixes by action type."""
    buckets: dict[ConfigFixAction, list[ConfigFix]] = {
        ConfigFixAction.AUTO_FIX: [],
        ConfigFixAction.RECOMMEND: [],
        ConfigFixAction.HUMAN_ONLY: [],
    }
    for fix in fixes:
        buckets[fix.action].append(fix)
    return buckets
