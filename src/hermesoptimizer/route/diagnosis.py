"""
Phase 3 routing diagnosis and prioritized optimization proposals for Hermes.

Infers routing decisions from Hermes config/runtime, detects bad routing /
stale defaults / broken fallback chains, and ranks findings into explainable
priority buckets: CRITICAL > IMPORTANT > GOOD_IDEA > NICE_TO_HAVE > WHATEVER.

All functions are pure: (input, config) -> output. No hidden state.
"""
from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hermesoptimizer.catalog import Finding


# ---------------------------------------------------------------------------
# Priority enum
# ---------------------------------------------------------------------------


class Priority(enum.Enum):
    """Ranking buckets for routing optimization proposals."""

    CRITICAL = "critical"       # Immediate action required; system broken
    IMPORTANT = "important"     # Significant impact; address soon
    GOOD_IDEA = "good_idea"     # Worth doing; clear benefit
    NICE_TO_HAVE = "nice_to_have"  # Low friction; incremental value
    WHATEVER = "whatever"       # No urgency; consider if nothing else

    def sort_key(self) -> int:
        """Lower number = higher urgency (for sorting)."""
        return _SORT_KEYS[self]


# Map each priority to its sort order (0 = highest urgency)
_SORT_KEYS: dict[Priority, int] = {
    Priority.CRITICAL: 0,
    Priority.IMPORTANT: 1,
    Priority.GOOD_IDEA: 2,
    Priority.NICE_TO_HAVE: 3,
    Priority.WHATEVER: 4,
}


# ---------------------------------------------------------------------------
# Diagnosis result types
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class RoutingDiagnosis:
    """
    A routing problem diagnosed from one or more findings.

    Attributes
    ----------
    finding :
        The originating :class:`Finding` that triggered this diagnosis.
    priority :
        How urgent this issue is.
    code :
        Short machine-readable diagnostic code (e.g. ``"AUTH_FAILURE"``).
    summary :
        One-line human-readable description.
    detail :
        Expanded explanation of the problem and its context.
    recommendation :
        Actionable fix the operator should take.
    lane :
        The Hermes lane this diagnosis applies to (or None for global).
    """

    finding: "Finding"
    priority: Priority
    code: str
    summary: str
    detail: str
    recommendation: str
    lane: str | None = None

    def to_rec(self) -> "Recommendation":
        """Convert to aRecommendation for structured output."""
        return Recommendation(
            priority=self.priority,
            code=self.code,
            summary=self.summary,
            detail=self.detail,
            recommendation=self.recommendation,
            lane=self.lane,
            source_fingerprint=self.finding.fingerprint,
        )


@dataclass(slots=True)
class Recommendation:
    """
    Structured optimization proposal surfaced by the rank step.

    Attributes
    ----------
    priority :
        Urgency bucket.
    code :
        Short diagnostic code.
    summary :
        One-line description.
    detail :
        Expanded explanation.
    recommendation :
        Actionable fix.
    lane :
        Affected lane or None for global.
    source_fingerprint :
        Fingerprint of the originating Finding.
    """

    priority: Priority
    code: str
    summary: str
    detail: str
    recommendation: str
    lane: str | None
    source_fingerprint: str | None


# ---------------------------------------------------------------------------
# Routing inference
# ---------------------------------------------------------------------------

# Known deprecated / stale model name fragments.
_STALE_MODEL_FRAGMENTS = (
    "deprecated",
    "obsolete",
    "eol",
    " sunset",
    "discontinued",
)

# Auth-error keywords observed in Hermes logs / sessions.
_AUTH_ERROR_TOKENS = frozenset(["401", "unauthorized", "auth failure", "auth_error", "invalid api key"])
_TIMEOUT_TOKENS   = frozenset(["timeout", "timed out", "exceeded retries", "retries 3"])
_ROUTE_TOKENS     = frozenset(["routing", "route", "lane", "provider selected"])


def infer_routing_from_config(config: dict) -> dict[str, list[str]]:
    """
    Extract the lane → [provider, ...] routing map from a parsed config dict.

    Parameters
    ----------
    config :
        Parsed ``config.yaml`` as a plain dict (no dataclass required).

    Returns
    -------
    dict[str, list[str]]
        Mapping of lane name → ordered list of provider names used for that
        lane.  When a fallback chain is present the primary is first.
        Empty string key ``""`` represents the global (un-laned) default.
    """
    providers = config.get("providers", {})
    routing: dict[str, list[str]] = {}

    # Build lane → providers from provider definitions
    for provider_name, provider_def in providers.items():
        lane = provider_def.get("lane", "")
        if lane not in routing:
            routing[lane] = []
        if provider_name not in routing[lane]:
            routing[lane].append(provider_name)

    # If a "gateway" block exists with explicit fallback routes, honour it.
    gateway = config.get("gateway", {})
    fallback_str = gateway.get("fallback_routes", "")
    if fallback_str:
        # Format: "lane:provider1>provider2,..."
        for segment in fallback_str.split(","):
            segment = segment.strip()
            if not segment or ":" not in segment:
                continue
            lane_part, chain = segment.split(":", 1)
            lane_part = lane_part.strip()
            providers_in_chain = [p.strip() for p in chain.split(">") if p.strip()]
            if providers_in_chain:
                routing[lane_part] = providers_in_chain

    return routing


def infer_routing_from_findings(findings: list["Finding"]) -> dict[str, list[str]]:
    """
    Extract a best-effort lane → [provider] routing map from discovery findings.

    This uses log-signal and session-signal findings to reconstruct which
    providers were being used for which lanes at scan time.

    Parameters
    ----------
    findings :
        List of findings from the parse step.

    Returns
    -------
    dict[str, list[str]]
        Inferred routing map.
    """
    routing: dict[str, list[str]] = {}
    for f in findings:
        if f.category == "log-signal" and f.sample_text:
            text = f.sample_text.lower()
            # "Provider <name> selected for lane=<lane>"
            m = re.search(r"provider\s+(\w+)\s+selected\s+for\s+lane=(\w+)", text)
            if m:
                prov, lane = m.group(1), m.group(2)
                routing.setdefault(lane, [])
                if prov not in routing[lane]:
                    routing[lane].append(prov)
        elif f.category == "session-signal" and f.sample_text:
            text = f.sample_text.lower()
            m = re.search(r'"provider":\s*"(\w+)"', text)
            if m:
                prov = m.group(1)
                routing.setdefault("", [])
                if prov not in routing[""]:
                    routing[""].append(prov)
    return routing


# ---------------------------------------------------------------------------
# Diagnosis helpers
# ---------------------------------------------------------------------------

# Tokens that appear in Finding.sample_text when auth has failed.
_AUTH_TOKENS_LOWER = frozenset(t.lower() for t in (
    "401", "unauthorized", "auth failure", "auth_error", "invalid api key",
))


def _is_auth_failure(finding: "Finding") -> bool:
    text = (finding.sample_text or "").lower()
    return bool(_AUTH_TOKENS_LOWER & frozenset(text.split()))


def _is_timeout_failure(finding: "Finding") -> bool:
    text = (finding.sample_text or "").lower()
    return bool(_TIMEOUT_TOKENS & frozenset(text.split()))


def diagnose_auth_failures(
    findings: list["Finding"],
    routing: dict[str, list[str]],
) -> list[RoutingDiagnosis]:
    """
    Detect auth failures in findings and map them to affected lanes.

    An auth failure on a lane's primary provider is CRITICAL; on a fallback
    provider it is IMPORTANT (because the whole chain may be compromised).
    """
    diagnoses: list[RoutingDiagnosis] = []
    for f in findings:
        if f.category not in ("log-signal", "session-signal", "config-signal"):
            continue
        if not _is_auth_failure(f):
            continue

        # Find which lane this finding relates to
        lane = f.lane or ""
        chain = routing.get(lane, [])

        # Determine position in fallback chain
        primary = chain[0] if chain else None
        if primary and _extract_provider_from_text(f) == primary:
            priority = Priority.CRITICAL
        else:
            priority = Priority.IMPORTANT

        diagnoses.append(
            RoutingDiagnosis(
                finding=f,
                priority=priority,
                code="AUTH_FAILURE",
                summary="Authentication failure detected for provider on lane",
                detail=(
                    f"Auth error was recorded for lane '{lane}' "
                    f"(chain={chain}). The provider rejected the request "
                    f"with a 401 / unauthorized error, meaning the "
                    f"'auth_key_env' variable may be missing, expired, or "
                    f"revoked."
                ),
                recommendation=(
                    f"Verify the auth key env variable for the provider(s) "
                    f"in lane '{lane}' is set and valid. Check whether the "
                    f"API key has been rotated and update 'auth_key_env' in "
                    f"config.yaml accordingly."
                ),
                lane=lane or None,
            )
        )
    return diagnoses


def diagnose_timeouts(
    findings: list["Finding"],
    routing: dict[str, list[str]],
) -> list[RoutingDiagnosis]:
    """
    Detect provider timeouts in findings and map them to affected lanes.

    Excessive retries (>= 3) or explicit timeout messages are flagged.
    A timeout on the only provider for a lane is CRITICAL; otherwise
    it is IMPORTANT.
    """
    diagnoses: list[RoutingDiagnosis] = []
    for f in findings:
        if f.category not in ("log-signal", "session-signal"):
            continue
        if not _is_timeout_failure(f):
            continue

        lane = f.lane or ""
        chain = routing.get(lane, [])

        # Detect excessive retries
        retry_count = 0
        if f.sample_text:
            m = re.search(r"retries?\s*(\d+)", f.sample_text.lower())
            if m:
                retry_count = int(m.group(1))

        if retry_count >= 3:
            priority = Priority.CRITICAL
        else:
            priority = Priority.IMPORTANT

        diagnoses.append(
            RoutingDiagnosis(
                finding=f,
                priority=priority,
                code="PROVIDER_TIMEOUT",
                summary="Provider timeout or excessive retries detected",
                detail=(
                    f"Timeout detected on lane '{lane}' "
                    f"(chain={chain}). "
                    f"{retry_count} retries were attempted before giving up, "
                    f"indicating the provider is unreachable or responding "
                    f"beyond the configured timeout threshold."
                ),
                recommendation=(
                    f"Check network connectivity to the provider for lane "
                    f"'{lane}'. Consider increasing the timeout threshold "
                    f"or adding a healthy fallback provider to "
                    f"'{lane}' in config.yaml."
                ),
                lane=lane or None,
            )
        )
    return diagnoses


def diagnose_stale_defaults(
    findings: list["Finding"],
    routing: dict[str, list[str]],
) -> list[RoutingDiagnosis]:
    """
    Detect stale model names and deprecated provider configurations.

    Finds config-signal findings where the model name contains known
    deprecation markers, or where the provider is the sole entry for
    a lane (no fallback).
    """
    diagnoses: list[RoutingDiagnosis] = []
    for f in findings:
        if f.category != "config-signal":
            continue
        sample = (f.sample_text or "").lower()

        # Check for stale model fragments
        is_stale = any(frag in sample for frag in _STALE_MODEL_FRAGMENTS)
        # Check for model: line with a deprecated marker
        m = re.search(r"model:\s*([^\s,]+)", sample)

        if is_stale and m:
            model_name = m.group(1)
            diagnoses.append(
                RoutingDiagnosis(
                    finding=f,
                    priority=Priority.IMPORTANT,
                    code="STALE_MODEL",
                    summary=f"Model '{model_name}' appears to be deprecated or EOL",
                    detail=(
                        f"The model '{model_name}' was detected in "
                        f"config.yaml and contains a known deprecation "
                        f"marker (deprecated / obsolete / EOL / sunset). "
                        f"Using a deprecated model risks unexpected "
                        f"behaviour and lack of support."
                    ),
                    recommendation=(
                        f"Replace model '{model_name}' in config.yaml with "
                        f"its current successor (e.g. gpt-4o → gpt-4o-mini "
                        f"if a newer variant is available, or the latest "
                        f"stable claude-3-5 release)."
                    ),
                    lane=f.lane,
                )
            )
    return diagnoses


def diagnose_broken_fallback_chains(
    findings: list["Finding"],
    routing: dict[str, list[str]],
) -> list[RoutingDiagnosis]:
    """
    Detect lanes with no fallback provider (single point of failure).

    If a lane has exactly one provider and that provider appears in
    error findings (auth / timeout), the chain is considered broken.
    """
    diagnoses: list[RoutingDiagnosis] = []
    for lane, chain in routing.items():
        if len(chain) <= 1:
            continue  # Multi-provider chain; can't diagnose from structure alone

        # Check if any provider in the chain appears in error findings
        errored_providers = set()
        for f in findings:
            if f.category not in ("log-signal", "session-signal"):
                continue
            prov = _extract_provider_from_text(f)
            if prov in chain:
                errored_providers.add(prov)

        # If only one of N providers is failing, the chain is partially broken
        if errored_providers and errored_providers < set(chain):
            failed = list(errored_providers)
            still_up = [p for p in chain if p not in errored_providers]
            diagnoses.append(
                RoutingDiagnosis(
                    finding=findings[0],
                    priority=Priority.IMPORTANT,
                    code="BROKEN_FALLBACK",
                    summary=f"Fallback chain for lane '{lane}' is degraded",
                    detail=(
                        f"Lane '{lane}' has fallback chain {chain}. "
                        f"Provider(s) {failed} are erroring, leaving only "
                        f"{still_up} operational. Requests will be routed "
                        f"to {still_up} but if those also fail there is no "
                        f"further fallback."
                    ),
                    recommendation=(
                        f"Add an additional healthy provider to lane '{lane}' "
                        f"to complete the fallback chain, or investigate "
                        f"why {failed} are failing (auth / timeout)."
                    ),
                    lane=lane or None,
                )
            )
    return diagnoses


def _extract_provider_from_text(finding: "Finding") -> str | None:
    """Best-effort extraction of a provider name from a Finding's sample_text."""
    text = (finding.sample_text or "").lower()
    m = re.search(r'provider["\s:]+(\w+)', text)
    if m:
        return m.group(1)
    m2 = re.search(r'"provider":\s*"(\w+)"', text)
    if m2:
        return m2.group(1)
    return None


# ---------------------------------------------------------------------------
# Main diagnosis entry point
# ---------------------------------------------------------------------------


def diagnose_findings(
    findings: list["Finding"],
    routing: dict[str, list[str]] | None = None,
) -> list[RoutingDiagnosis]:
    """
    Run all routing diagnostics on a list of findings.

    Parameters
    ----------
    findings :
        Findings from the parse step.
    routing :
        Optional routing map. If None, it is inferred from findings.

    Returns
    -------
    list[RoutingDiagnosis]
        All diagnoses sorted by priority (most urgent first).
    """
    if routing is None:
        routing = infer_routing_from_findings(findings)

    diag_list: list[RoutingDiagnosis] = []

    diag_list.extend(diagnose_auth_failures(findings, routing))
    diag_list.extend(diagnose_timeouts(findings, routing))
    diag_list.extend(diagnose_stale_defaults(findings, routing))
    diag_list.extend(diagnose_broken_fallback_chains(findings, routing))

    return rank_diagnoses(diag_list)


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


def rank_diagnoses(diagnoses: list[RoutingDiagnosis]) -> list[RoutingDiagnosis]:
    """
    Sort diagnoses by urgency (most urgent first).

    Within the same priority bucket, deterministic order is preserved.
    """
    return sorted(diagnoses, key=lambda d: (d.priority.sort_key(), d.code))


def rank_findings(
    findings: list["Finding"],
    routing: dict[str, list[str]] | None = None,
) -> list[RoutingDiagnosis]:
    """
    High-level convenience: diagnose and rank a list of findings.

    This is the main entry point for the ``rank`` step in the loop.
    """
    return diagnose_findings(findings, routing)


# ---------------------------------------------------------------------------
# Recommendation builder
# ---------------------------------------------------------------------------


def build_recommendations(diagnoses: list[RoutingDiagnosis]) -> list[Recommendation]:
    """
    Convert a sorted list of diagnoses into structured recommendations.

    Parameters
    ----------
    diagnoses :
        Sorted output of :func:`rank_diagnoses`.

    Returns
    -------
    list[Recommendation]
        One recommendation per unique diagnostic code, preserving sort order.
    """
    seen: set[str] = set()
    recs: list[Recommendation] = []
    for d in diagnoses:
        if d.code in seen:
            continue
        seen.add(d.code)
        recs.append(d.to_rec())
    return recs


# ---------------------------------------------------------------------------
# Bucket helpers (for report integration)
# ---------------------------------------------------------------------------

#: Human-readable label for each priority bucket.
BUCKET_LABELS: dict[Priority, str] = {
    Priority.CRITICAL: "🔴 Critical",
    Priority.IMPORTANT: "🟡 Important",
    Priority.GOOD_IDEA: "🟢 Good Idea",
    Priority.NICE_TO_HAVE: "🔵 Nice to Have",
    Priority.WHATEVER: "⚪ Whatever",
}


def bucket_by_priority(
    recommendations: list[Recommendation],
) -> dict[Priority, list[Recommendation]]:
    """Group recommendations into priority buckets."""
    from collections import defaultdict
    buckets: dict[Priority, list[Recommendation]] = defaultdict(list)
    for rec in recommendations:
        buckets[rec.priority].append(rec)
    return dict(buckets)
