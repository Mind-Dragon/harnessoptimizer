"""
Route module – routing decision helpers for Hermes.

Phase 3 adds routing diagnosis: inferring routing from config / runtime,
detecting broken chains / stale defaults / auth failures, and ranking findings
into explainable priority buckets.
"""
from __future__ import annotations

from hermesoptimizer.route.diagnosis import (
    Priority,
    Recommendation,
    RoutingDiagnosis,
    BUCKET_LABELS,
    bucket_by_priority,
    build_recommendations,
    diagnose_findings,
    infer_routing_from_config,
    infer_routing_from_findings,
    rank_diagnoses,
    rank_findings,
)
from hermesoptimizer.route.router import RouteDecision, route_text

__all__ = [
    # router
    "RouteDecision",
    "route_text",
    # diagnosis
    "Priority",
    "Recommendation",
    "RoutingDiagnosis",
    "BUCKET_LABELS",
    "bucket_by_priority",
    "build_recommendations",
    "diagnose_findings",
    "infer_routing_from_config",
    "infer_routing_from_findings",
    "rank_diagnoses",
    "rank_findings",
]
