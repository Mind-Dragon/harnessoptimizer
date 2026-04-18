"""
Report health module for v0.6.0 report-output-improvements.

Provides first-class report surfaces for:
- provider health summary
- model validity summary
- config repair priority
- lane-aware repair tuples
- provenance collisions
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from hermesoptimizer.catalog import Record


@dataclass(slots=True)
class ProviderHealthSummary:
    """Provider health summary with status, auth type, endpoint, and probe results."""

    provider: str
    status: Literal["healthy", "degraded", "failing"]
    auth_type: str
    endpoint_url: str
    last_probe_result: str
    last_probe_timestamp: str
    failure_reason: str | None = None


@dataclass(slots=True)
class ModelValiditySummary:
    """Model validity summary with status and repair guidance."""

    provider: str
    model: str
    status: Literal["valid", "stale", "deprecated", "wrong-endpoint"]
    repair_note: str | None = None
    suggested_replacement: str | None = None


@dataclass(slots=True)
class RepairPriority:
    """Repair priority with priority level, description, lane, and safety level."""

    priority_level: Literal["critical", "important", "good-idea", "nice-to-have", "whatever"]
    description: str
    lane: str | None = None
    safety_level: Literal["auto-fix", "recommend-and-confirm", "human-only"] = "recommend-and-confirm"


@dataclass(slots=True)
class LaneAwareRepairTuple:
    """Lane-aware repair tuple with provider alias, endpoint URL, auth type, region, and model."""

    provider_alias: str
    endpoint_url: str
    auth_type: str
    region: str | None
    model: str
    repair_action: Literal["promote", "demote", "remove", "replace", "quarantine", "renew"]
    priority: str


@dataclass(slots=True)
class ProvenanceCollision:
    """Provenance collision explaining duplicate provider rows as collisions."""

    colliding_providers: list[str]
    collision_type: Literal["duplicate_alias", "same_endpoint", "same_key", "auth_mismatch"]
    explanation: str
    suggested_resolution: str


def _now_iso() -> str:
    """Return current UTC time in ISO format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_provider_health(records: list[Record]) -> list[ProviderHealthSummary]:
    """
    Derive provider health summaries from records.

    Treats a provider as healthy if confidence is high and no failures are recorded.
    """
    seen: dict[str, ProviderHealthSummary] = {}
    for record in records:
        if record.provider not in seen:
            # Determine status based on confidence
            if record.confidence == "high":
                status: Literal["healthy", "degraded", "failing"] = "healthy"
            elif record.confidence == "medium":
                status = "degraded"
            else:
                status = "failing"

            seen[record.provider] = ProviderHealthSummary(
                provider=record.provider,
                status=status,
                auth_type=record.auth_type,
                endpoint_url=record.base_url,
                last_probe_result="ok" if status == "healthy" else "unknown",
                last_probe_timestamp=_now_iso(),
                failure_reason=None,
            )
    return list(seen.values())


def compute_model_validity(records: list[Record]) -> list[ModelValiditySummary]:
    """
    Derive model validity summaries from records.

    Marks models as valid by default. In a full implementation, this would
    cross-reference a model catalog to detect stale/deprecated/wrong-endpoint.
    """
    summaries: list[ModelValiditySummary] = []
    for record in records:
        # Default to valid - full implementation would check against model catalog
        summaries.append(
            ModelValiditySummary(
                provider=record.provider,
                model=record.model,
                status="valid",
                repair_note=None,
                suggested_replacement=None,
            )
        )
    return summaries


def compute_repair_priority(records: list[Record]) -> list[RepairPriority]:
    """
    Compute repair priorities for records that need review.

    Returns an empty list when all records have high confidence. In a full implementation,
    this would generate specific repair recommendations based on findings.
    """
    # By default, no repairs needed for healthy records
    priorities: list[RepairPriority] = []
    for record in records:
        if record.confidence != "high":
            # Suggest repair for low-confidence records
            priorities.append(
                RepairPriority(
                    priority_level="important",
                    description=f"Review {record.provider} provider: low confidence ({record.confidence})",
                    lane=record.lane,
                    safety_level="recommend-and-confirm",
                )
            )
    return priorities


def compute_lane_aware_repairs(records: list[Record]) -> list[LaneAwareRepairTuple]:
    """
    Derive lane-aware repair tuples from records.

    Each tuple includes provider alias, endpoint URL, auth type, region, and model.
    """
    repairs: list[LaneAwareRepairTuple] = []
    for record in records:
        # Default action is promote for high-confidence, quarantine for others
        # (quarantine indicates the record needs review/verification due to lower confidence)
        action: Literal["promote", "demote", "remove", "replace", "quarantine", "renew"] = (
            "promote" if record.confidence == "high" else "quarantine"
        )
        # Map confidence to priority
        if record.confidence == "high":
            priority = "critical"
        elif record.confidence == "medium":
            priority = "important"
        else:
            priority = "critical"

        repairs.append(
            LaneAwareRepairTuple(
                provider_alias=record.provider,
                endpoint_url=record.base_url,
                auth_type=record.auth_type,
                region=record.region,
                model=record.model,
                repair_action=action,
                priority=priority,
            )
        )
    return repairs


def compute_provenance_collisions(records: list[Record]) -> list[ProvenanceCollision]:
    """
    Detect provenance collisions (duplicate provider rows) from records.

    Two records with the same base_url but different provider names are flagged
    as duplicate_alias collisions.
    """
    collisions: list[ProvenanceCollision] = []
    # Group records by base_url to find duplicates
    by_url: dict[str, list[Record]] = {}
    for record in records:
        by_url.setdefault(record.base_url, []).append(record)

    for base_url, url_records in by_url.items():
        if len(url_records) > 1:
            # Multiple providers sharing the same endpoint
            providers = [r.provider for r in url_records]
            # Check if provider names differ (collision)
            unique_providers = set(providers)
            if len(unique_providers) > 1:
                collisions.append(
                    ProvenanceCollision(
                        colliding_providers=providers,
                        collision_type="duplicate_alias",
                        explanation=f"Multiple provider entries ({', '.join(providers)}) resolve to the same endpoint {base_url}",
                        suggested_resolution="Deduplicate by keeping one canonical provider and removing stale aliases",
                    )
                )
    return collisions
