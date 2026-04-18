"""
v0.6 provider-management-controls: dedupe, fallback hygiene,
endpoint quarantine TTL/decay, credential-source provenance, and
known-good model pin / repeated failure memory.

This module provides explicit, testable provider management surfaces
without magical behavior or direct config mutation.

Key behaviors:
- dedupe/canonical collapse recommendations: identify duplicate provider
  aliases and recommend collapsing them onto a single canonical entry
- fallback hygiene: recommend reordering fallback chains when healthier
  providers consistently outperform higher-priority ones
- endpoint quarantine TTL: temporarily quarantine bad endpoints (not
  permanent blacklist) with TTL/expiry and decay
- credential-source provenance: track where credentials came from for
  provider-management decisions
- known-good model pin / repeated failure memory: track health history
  and known-good models to feed recommendations
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# --------------------------------------------------------------------------- #
# CredentialSource provenance
# --------------------------------------------------------------------------- #


class CredentialSource(Enum):
    """
    Known credential source types for provider-management decisions.

    Records where credentials were obtained for provenance tracking.
    """

    ENV = "env"  # Environment variable
    AUTH_JSON = "auth_json"  # auth.json file
    CREDENTIAL_POOL = "credential_pool"  # Credential pool / vault
    OAUTH_STORE = "oauth_store"  # OAuth token store
    RUNTIME_ONLY = "runtime_only"  # Runtime-only (not persisted)
    UNKNOWN = "unknown"


# Map source enum values to human-readable labels
_CREDENTIAL_SOURCE_LABELS: dict[str, str] = {
    "env": "environment variable",
    "auth_json": "auth.json file",
    "credential_pool": "credential pool / vault",
    "oauth_store": "OAuth token store",
    "runtime_only": "runtime-only (not persisted)",
    "unknown": "unknown source",
}


def get_credential_source_label(source: str) -> str:
    """
    Return a human-readable label for a credential source string.

    Parameters
    ----------
    source :
        Credential source string (e.g. "env", "auth_json")

    Returns
    -------
    str
        Human-readable label
    """
    return _CREDENTIAL_SOURCE_LABELS.get(source, source)


@dataclass(slots=True)
class CredentialProvenance:
    """
    Records the source of credentials for a provider.

    Attributes
    ----------
    source :
        Where the credential was obtained (e.g. "env", "auth_json")
    variable_name :
        Name of the environment variable (for env source)
    path :
        File path (for file-based sources)
    note :
        Additional provenance note
    """

    source: str
    variable_name: str | None = None
    path: str | None = None
    note: str | None = None


def get_credential_provenance(
    source: str,
    *,
    variable_name: str | None = None,
    path: str | None = None,
    note: str | None = None,
) -> CredentialProvenance:
    """
    Build a CredentialProvenance record.

    This is the primary constructor for provenance records used
    in provider-management decisions.

    Parameters
    ----------
    source :
        Credential source string
    variable_name :
        Environment variable name (for env source)
    path :
        File path (for file-based sources)
    note :
        Additional note

    Returns
    -------
    CredentialProvenance
    """
    return CredentialProvenance(
        source=source,
        variable_name=variable_name,
        path=path,
        note=note,
    )


# --------------------------------------------------------------------------- #
# Provider health record and memory
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class ProviderHealthRecord:
    """
    Tracks health history and known-good model for a provider.

    Attributes
    ----------
    provider :
        Provider name (canonical)
    successes :
        Total successful requests
    failures :
        Total failed requests
    last_success :
        Unix timestamp of last successful request
    last_failure :
        Unix timestamp of last failed request
    consecutive_failures :
        Current streak of consecutive failures
    known_good_model :
        Model confirmed to work with this provider (if known)
    """

    provider: str
    successes: int = 0
    failures: int = 0
    last_success: float = 0.0
    last_failure: float = 0.0
    consecutive_failures: int = 0
    known_good_model: str | None = None

    @property
    def success_rate(self) -> float:
        """Return success rate as a float between 0 and 1."""
        total = self.successes + self.failures
        if total == 0:
            return 1.0  # No data means assume healthy
        return self.successes / total

    def is_healthy(self, threshold: float = 0.7) -> bool:
        """
        Return True if the provider is considered healthy.

        Parameters
        ----------
        threshold :
            Minimum success_rate to be considered healthy (default 0.7)

        Returns
        -------
        bool
        """
        return self.success_rate >= threshold


class ProviderHealthStore:
    """
    In-memory store of provider health records.

    Tracks successes, failures, consecutive failures, and known-good models
    per provider. This is the memory surface that feeds fallback hygiene
    and other provider-management recommendations.
    """

    def __init__(self) -> None:
        self._records: dict[str, ProviderHealthRecord] = {}

    def record_success(self, provider: str) -> None:
        """Record a successful request for a provider."""
        if provider not in self._records:
            self._records[provider] = ProviderHealthRecord(provider=provider)
        rec = self._records[provider]
        rec.successes += 1
        rec.consecutive_failures = 0
        rec.last_success = time.time()

    def record_failure(self, provider: str) -> None:
        """Record a failed request for a provider."""
        if provider not in self._records:
            self._records[provider] = ProviderHealthRecord(provider=provider)
        rec = self._records[provider]
        rec.failures += 1
        rec.consecutive_failures += 1
        rec.last_failure = time.time()

    def get(self, provider: str) -> ProviderHealthRecord | None:
        """Get health record for a provider."""
        return self._records.get(provider)

    def set_known_good_model(self, provider: str, model: str) -> None:
        """Pin a known-good model for a provider."""
        if provider not in self._records:
            self._records[provider] = ProviderHealthRecord(provider=provider)
        self._records[provider].known_good_model = model

    def all_records(self) -> list[ProviderHealthRecord]:
        """Return all health records."""
        return list(self._records.values())

    def get_healthy_providers(self, threshold: float = 0.7) -> list[str]:
        """Return list of providers considered healthy."""
        return [
            rec.provider
            for rec in self._records.values()
            if rec.is_healthy(threshold)
        ]


# --------------------------------------------------------------------------- #
# Endpoint health memory (for quarantine tracking)
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class EndpointHealthRecord:
    """
    Tracks health history for a specific endpoint.

    Attributes
    ----------
    endpoint :
        Endpoint URL
    successes :
        Total successful probes
    failures :
        Total failed probes
    last_success :
        Unix timestamp of last success
    last_failure :
        Unix timestamp of last failure
    health_score :
        Computed health score (0-1, updated on each event)
    """

    endpoint: str
    successes: int = 0
    failures: int = 0
    last_success: float = 0.0
    last_failure: float = 0.0
    health_score: float = 1.0

    def update_health_score(self) -> None:
        """Recompute health score based on success/failure ratio."""
        total = self.successes + self.failures
        if total == 0:
            self.health_score = 1.0
        else:
            self.health_score = self.successes / total


class EndpointHealthMemory:
    """
    In-memory store of endpoint-level health records.

    Tracks successes and failures per endpoint URL for use by
    the endpoint quarantine system.
    """

    def __init__(self) -> None:
        self._records: dict[str, EndpointHealthRecord] = {}

    def record_success(self, endpoint: str) -> None:
        """Record a successful probe for an endpoint."""
        if endpoint not in self._records:
            self._records[endpoint] = EndpointHealthRecord(endpoint=endpoint)
        rec = self._records[endpoint]
        rec.successes += 1
        rec.last_success = time.time()
        rec.update_health_score()

    def record_failure(self, endpoint: str) -> None:
        """Record a failed probe for an endpoint."""
        if endpoint not in self._records:
            self._records[endpoint] = EndpointHealthRecord(endpoint=endpoint)
        rec = self._records[endpoint]
        rec.failures += 1
        rec.last_failure = time.time()
        rec.update_health_score()

    def get_record(self, endpoint: str) -> EndpointHealthRecord | None:
        """Get health record for an endpoint."""
        return self._records.get(endpoint)

    def get_success_count(self, endpoint: str) -> int:
        """Return success count for an endpoint."""
        rec = self._records.get(endpoint)
        return rec.successes if rec else 0

    def get_failure_count(self, endpoint: str) -> int:
        """Return failure count for an endpoint."""
        rec = self._records.get(endpoint)
        return rec.failures if rec else 0

    def get_health_score(self, endpoint: str) -> float:
        """Return health score for an endpoint (0-1)."""
        rec = self._records.get(endpoint)
        return rec.health_score if rec else 1.0

    def apply_decay(self, factor: float = 0.5) -> None:
        """
        Apply decay to success and failure counts, reducing them by factor.

        This simulates time-based decay of health memory so that
        temporary issues don't permanently affect health scores. Decay
        is applied symmetrically to both successes and failures to
        prevent artificial health score inflation (which would occur if
        only failures were decayed).

        Parameters
        ----------
        factor :
            Decay factor (0-1). A factor of 0.5 halves all counts.
        """
        for rec in self._records.values():
            rec.successes = max(0, int(rec.successes * factor))
            rec.failures = max(0, int(rec.failures * factor))
            rec.update_health_score()

    def all_records(self) -> list[EndpointHealthRecord]:
        """Return all endpoint health records."""
        return list(self._records.values())


# --------------------------------------------------------------------------- #
# Endpoint quarantine with TTL and decay
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class QuarantinedEndpoint:
    """
    Represents a quarantined endpoint with TTL information.

    Attributes
    ----------
    endpoint :
        The quarantined endpoint URL
    quarantined_at :
        Unix timestamp when quarantine started
    ttl_seconds :
        Time-to-live in seconds (0 means permanent)
    failure_count :
        Number of failures that triggered this quarantine
    is_permanent :
        True if this is a permanent quarantine (not TTL-based)
    """

    endpoint: str
    quarantined_at: float
    ttl_seconds: int
    failure_count: int = 0
    is_permanent: bool = False

    def is_expired(self, now: float | None = None) -> bool:
        """Return True if this quarantine has expired."""
        if self.is_permanent:
            return False
        if self.ttl_seconds == 0:
            return False  # No TTL means no expiry check
        if now is None:
            now = time.time()
        return (now - self.quarantined_at) >= self.ttl_seconds


class EndpointQuarantine:
    """
    Tracks temporarily quarantined endpoints with TTL and decay.

    Endpoints that repeatedly fail are quarantined for a TTL period
    rather than being permanently blacklisted. After the TTL expires,
    the endpoint can be retried. Permanent blacklist is available
    for extreme cases.

    Key behaviors:
    - Quarantine with TTL: endpoints are quarantined for a fixed period
    - Permanent quarantine: for permanently bad endpoints (opt-in)
    - Decay: failure counts decay over time to allow recovery
    - Expiry check: TTL-based quarantines automatically expire
    """

    def __init__(self, default_ttl_seconds: int = 300) -> None:
        """
        Initialize endpoint quarantine tracker.

        Parameters
        ----------
        default_ttl_seconds :
            Default TTL for new quarantines (default 300 = 5 minutes)
        """
        self._quarantined: dict[str, QuarantinedEndpoint] = {}
        self._default_ttl = default_ttl_seconds

    def quarantine(
        self,
        endpoint: str,
        *,
        ttl_seconds: int | None = None,
        failure_count: int = 1,
    ) -> None:
        """
        Quarantine an endpoint for a TTL period.

        Parameters
        ----------
        endpoint :
            Endpoint URL to quarantine
        ttl_seconds :
            TTL in seconds (uses default if None)
        failure_count :
            Number of failures that triggered this quarantine
        """
        if ttl_seconds is None:
            ttl_seconds = self._default_ttl
        normalized = self._normalize_endpoint(endpoint)
        self._quarantined[normalized] = QuarantinedEndpoint(
            endpoint=normalized,
            quarantined_at=time.time(),
            ttl_seconds=ttl_seconds,
            failure_count=failure_count,
            is_permanent=False,
        )

    def quarantine_permanent(self, endpoint: str, *, failure_count: int = 1) -> None:
        """
        Permanently quarantine an endpoint (no automatic expiry).

        Parameters
        ----------
        endpoint :
            Endpoint URL to permanently quarantine
        failure_count :
            Number of failures that triggered this quarantine
        """
        normalized = self._normalize_endpoint(endpoint)
        self._quarantined[normalized] = QuarantinedEndpoint(
            endpoint=normalized,
            quarantined_at=time.time(),
            ttl_seconds=0,
            failure_count=failure_count,
            is_permanent=True,
        )

    def release(self, endpoint: str) -> None:
        """
        Manually release an endpoint from quarantine.

        Parameters
        ----------
        endpoint :
            Endpoint URL to release
        """
        normalized = self._normalize_endpoint(endpoint)
        self._quarantined.pop(normalized, None)

    def is_quarantined(self, endpoint: str) -> bool:
        """
        Return True if an endpoint is currently quarantined (and not expired).

        Parameters
        ----------
        endpoint :
            Endpoint URL to check

        Returns
        -------
        bool
        """
        normalized = self._normalize_endpoint(endpoint)
        qe = self._quarantined.get(normalized)
        if qe is None:
            return False
        if qe.is_expired():
            # Auto-remove expired quarantines on check
            self._quarantined.pop(normalized, None)
            return False
        return True

    def get_quarantined_endpoints(self) -> list[QuarantinedEndpoint]:
        """Return all active (non-expired) quarantined endpoints.

        Note: this method no longer mutates internal state. Expired entries
        are still returned in the list but are not removed. Callers that
        want to clean up expired entries should use remove_expired() explicitly.
        """
        now = time.time()
        return [
            qe for qe in self._quarantined.values()
            if not qe.is_expired(now)
        ]

    def remove_expired(self) -> int:
        """Remove expired quarantine entries from internal state.

        Returns the number of entries removed.
        """
        now = time.time()
        expired = [
            endpoint for endpoint, qe in self._quarantined.items()
            if qe.is_expired(now)
        ]
        for endpoint in expired:
            self._quarantined.pop(endpoint, None)
        return len(expired)

    def apply_decay(self, factor: float = 0.5) -> None:
        """
        Apply decay to all failure counts.

        This reduces the stored failure count for all quarantined endpoints,
        simulating time-based recovery. Use this periodically to allow
        endpoints to recover from temporary issues.

        Parameters
        ----------
        factor :
            Decay factor (0-1). A factor of 0.5 halves the failure counts.
        """
        for qe in self._quarantined.values():
            qe.failure_count = max(0, int(qe.failure_count * factor))

    def get_failure_count(self, endpoint: str) -> int:
        """Return failure count for a quarantined endpoint."""
        normalized = self._normalize_endpoint(endpoint)
        qe = self._quarantined.get(normalized)
        return qe.failure_count if qe else 0

    @staticmethod
    def _normalize_endpoint(endpoint: str) -> str:
        """Normalize an endpoint URL for consistent lookup."""
        return endpoint.rstrip("/")

    def __repr__(self) -> str:
        active = [qe.endpoint for qe in self.get_quarantined_endpoints()]
        return f"EndpointQuarantine(active={active})"


# --------------------------------------------------------------------------- #
# Record endpoint success/failure helpers (for health memory integration)
# --------------------------------------------------------------------------- #


def record_endpoint_success(
    endpoint: str,
    health_memory: EndpointHealthMemory,
) -> None:
    """
    Record a successful endpoint probe.

    Parameters
    ----------
    endpoint :
        Endpoint URL that succeeded
    health_memory :
        EndpointHealthMemory to update
    """
    health_memory.record_success(endpoint)


def record_endpoint_failure(
    endpoint: str,
    health_memory: EndpointHealthMemory,
) -> None:
    """
    Record a failed endpoint probe.

    Parameters
    ----------
    endpoint :
        Endpoint URL that failed
    health_memory :
        EndpointHealthMemory to update
    """
    health_memory.record_failure(endpoint)


# --------------------------------------------------------------------------- #
# Model pin
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class ModelPin:
    """
    Represents a known-good model pin for a provider.

    Attributes
    ----------
    provider :
        Provider name (canonical)
    model :
        Model name confirmed to work
    pinned_at :
        Unix timestamp when pin was set
    provenance :
        How this pin was determined (e.g. "runtime_verification", "config_default")
    note :
        Additional note about this pin
    """

    provider: str
    model: str
    pinned_at: float
    provenance: str = "unknown"
    note: str | None = None


# --------------------------------------------------------------------------- #
# Dedup aliases / canonical collapse
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class CollapseRecommendation:
    """
    Recommendation to collapse duplicate provider aliases onto a canonical entry.

    Attributes
    ----------
    alias_provider :
        The alias provider name to remove
    canonical_provider :
        The canonical provider name to keep
    reason :
        Human-readable explanation of why collapse is recommended
    action :
        The recommended action (always "collapse_alias")
    lane :
        The lane this collapse applies to (or None for global)
    """

    alias_provider: str
    canonical_provider: str
    reason: str
    action: str = "collapse_alias"
    lane: str | None = None


@dataclass
class DedupResult:
    """
    Result of a deduplication analysis.

    Attributes
    ----------
    collapse_recommendations :
        List of collapse recommendations for duplicate aliases
    provenance_collisions :
        List of provider configs that are aliases of each other
    total_providers :
        Total number of provider configs analyzed
    unique_canonical :
        Number of unique canonical providers
    """

    collapse_recommendations: list[CollapseRecommendation] = field(default_factory=list)
    provenance_collisions: list[tuple[str, str]] = field(default_factory=list)
    total_providers: int = 0
    unique_canonical: int = 0


def _canonical_from_config(config: dict[str, Any]) -> str:
    """
    Extract canonical provider name from a config dict.

    Parameters
    ----------
    config :
        Provider config dict with at least "provider" key

    Returns
    -------
    str
        Canonical provider name
    """
    from hermesoptimizer.sources.provider_truth import canonical_provider_name

    provider = config.get("provider", "")
    return canonical_provider_name(provider)


def collapse_duplicates(
    configs: list[dict[str, Any]],
    health_store: ProviderHealthStore,
) -> DedupResult:
    """
    Analyze provider configs and recommend collapsing duplicate aliases.

    Identifies providers that are aliases of the same canonical provider
    (based on endpoint contract) and produces collapse recommendations.

    Parameters
    ----------
    configs :
        List of provider config dicts with "provider" and optionally "base_url"
    health_store :
        ProviderHealthStore with health history (used for context)

    Returns
    -------
    DedupResult
        Contains collapse recommendations and collision information
    """
    result = DedupResult()
    result.total_providers = len(configs)

    if not configs:
        return result

    # Group by canonical provider name
    canonical_groups: dict[str, list[dict[str, Any]]] = {}
    for config in configs:
        canonical = _canonical_from_config(config)
        if canonical not in canonical_groups:
            canonical_groups[canonical] = []
        canonical_groups[canonical].append(config)

    result.unique_canonical = len(canonical_groups)

    # For each canonical group with multiple entries, create a collapse recommendation
    for canonical, group in canonical_groups.items():
        if len(group) <= 1:
            continue

        # Multiple configs for the same canonical provider = aliases
        # Pick the first as canonical, recommend collapsing others
        canonical_config = group[0]
        for alias_config in group[1:]:
            alias_name = alias_config.get("provider", "")
            base_url = alias_config.get("base_url", "")

            # Build reason based on what we can detect
            if base_url == canonical_config.get("base_url", ""):
                reason = (
                    f"Provider '{alias_name}' is an alias of '{canonical}' "
                    f"(same endpoint: {base_url}). "
                    f"Collapse onto the canonical entry to reduce picker noise."
                )
            else:
                reason = (
                    f"Provider '{alias_name}' is an alias of '{canonical}'. "
                    f"Both target the same provider family but appear as separate entries. "
                    f"Collapse onto the canonical entry."
                )

            rec = CollapseRecommendation(
                alias_provider=alias_name,
                canonical_provider=canonical,
                reason=reason,
                action="collapse_alias",
            )
            result.collapse_recommendations.append(rec)
            result.provenance_collisions.append((alias_name, canonical))

    return result


# --------------------------------------------------------------------------- #
# Fallback-order hygiene
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class FallbackHealthSummary:
    """
    Health summary for a provider in a fallback chain.

    Attributes
    ----------
    provider :
        Provider name
    successes :
        Total successful requests
    failures :
        Total failed requests
    success_rate :
        Success rate as a float (0-1)
    is_healthy :
        True if provider is considered healthy
    """

    provider: str
    successes: int
    failures: int
    success_rate: float
    is_healthy: bool


@dataclass(slots=True)
class FallbackReorderRecommendation:
    """
    Recommendation to reorder a fallback chain.

    Attributes
    ----------
    code :
        Short diagnostic code (always "FALLBACK_REORDER")
    summary :
        One-line human-readable description
    detail :
        Expanded explanation of the problem and context
    recommendation :
        Actionable fix recommendation
    lane :
        The lane this reorder applies to (or None for global)
    current_order :
        Current fallback order
    recommended_order :
        Recommended new fallback order
    """

    code: str
    summary: str
    detail: str
    recommendation: str
    lane: str | None
    current_order: list[str]
    recommended_order: list[str]


def _get_health_summary(
    provider: str,
    health_store: ProviderHealthStore,
) -> FallbackHealthSummary | None:
    """Get health summary for a provider from the health store."""
    record = health_store.get(provider)
    if record is None:
        return None
    return FallbackHealthSummary(
        provider=provider,
        successes=record.successes,
        failures=record.failures,
        success_rate=record.success_rate,
        is_healthy=record.is_healthy(),
    )


def recommend_fallback_reorder(
    routing: dict[str, list[str]],
    health_store: ProviderHealthStore,
    *,
    health_threshold: float = 0.7,
    min_observation_count: int = 3,
) -> FallbackReorderRecommendation | None:
    """
    Analyze fallback chains and recommend reordering when healthier
    providers consistently outperform higher-priority ones.

    Detects when a fallback provider has better health than a higher-priority
    provider and recommends moving the healthier one up in the chain.

    Parameters
    ----------
    routing :
        Mapping of lane name to ordered list of provider names
        (e.g. {"default": ["primary", "fallback"]})
    health_store :
        ProviderHealthStore with health history
    health_threshold :
        Minimum success rate to be considered healthy (default 0.7)
    min_observation_count :
        Minimum number of total requests before recommending reorder (default 3)

    Returns
    -------
    FallbackReorderRecommendation | None
        Recommendation if reordering would improve the chain, None otherwise
    """
    for lane, chain in routing.items():
        if len(chain) <= 1:
            continue

        # Get health summaries for all providers in the chain
        summaries: list[FallbackHealthSummary] = []
        for provider in chain:
            summary = _get_health_summary(provider, health_store)
            if summary is not None:
                summaries.append(summary)

        if len(summaries) < 2:
            continue

        # Check if any lower-priority provider is healthier than a higher-priority one
        for i in range(len(summaries) - 1):
            higher_priority = summaries[i]
            for j in range(i + 1, len(summaries)):
                lower_priority = summaries[j]

                # Check if lower priority is significantly healthier
                total_obs_higher = higher_priority.successes + higher_priority.failures
                total_obs_lower = lower_priority.successes + lower_priority.failures

                if total_obs_lower < min_observation_count:
                    continue
                if total_obs_higher < min_observation_count:
                    continue

                # Lower priority is healthier and has enough observations
                if lower_priority.is_healthy and not higher_priority.is_healthy:
                    # Recommend swapping: move healthier provider up
                    new_chain = list(chain)
                    # Swap positions of the two providers
                    idx_higher = new_chain.index(higher_priority.provider)
                    idx_lower = new_chain.index(lower_priority.provider)
                    new_chain[idx_higher], new_chain[idx_lower] = (
                        new_chain[idx_lower],
                        new_chain[idx_higher],
                    )

                    return FallbackReorderRecommendation(
                        code="FALLBACK_REORDER",
                        summary=(
                            f"Reorder fallback chain for '{lane}': "
                            f"'{lower_priority.provider}' outperforms '{higher_priority.provider}'"
                        ),
                        detail=(
                            f"Provider '{lower_priority.provider}' succeeded "
                            f"{lower_priority.successes} times with {lower_priority.failures} failures "
                            f"(success rate: {lower_priority.success_rate:.1%}) "
                            f"vs '{higher_priority.provider}' with {higher_priority.successes} successes "
                            f"and {higher_priority.failures} failures "
                            f"(success rate: {higher_priority.success_rate:.1%}). "
                            f"Move '{lower_priority.provider}' up in the fallback order."
                        ),
                        recommendation=(
                            f"Reorder fallback_providers for lane '{lane}' to: "
                            + " > ".join(new_chain)
                        ),
                        lane=lane,
                        current_order=list(chain),
                        recommended_order=new_chain,
                    )

    return None
