"""
Report issue helpers for Hermes optimizer.

Provides grouping and surfacing helpers for both raw findings and
Phase 3 routing-diagnosis recommendations.
"""
from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from hermesoptimizer.catalog import Finding

if TYPE_CHECKING:
    from hermesoptimizer.route.diagnosis import Priority, Recommendation


def group_findings(findings: list[Finding]) -> dict[str, list[Finding]]:
    """Group findings by their ``category`` field."""
    grouped: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        grouped[finding.category].append(finding)
    return dict(grouped)


def group_by_severity(findings: list[Finding]) -> dict[str, list[Finding]]:
    """Group findings by their ``severity`` field."""
    grouped: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        grouped[finding.severity].append(finding)
    return dict(grouped)


# ---------------------------------------------------------------------------
# Routing recommendation helpers (Phase 3)
# ---------------------------------------------------------------------------

def recommendations_by_priority(
    recommendations: list["Recommendation"],
) -> dict["Priority", list["Recommendation"]]:
    """
    Bucket recommendations into priority tiers.

    Returns a dict mapping :class:`Priority` → list of recommendations
    in that tier, ordered as returned by :func:`rank_findings`.
    """
    from collections import defaultdict
    buckets: dict["Priority", list["Recommendation"]] = defaultdict(list)
    for rec in recommendations:
        buckets[rec.priority].append(rec)
    return dict(buckets)


def recommendation_summary(
    recommendations: list["Recommendation"],
    *,
    include_detail: bool = False,
) -> list[str]:
    """
    Render recommendations as a list of human-readable lines.

    Parameters
    ----------
    recommendations :
        Output of :func:`build_recommendations`.
    include_detail :
        If True, append the ``detail`` field after each recommendation.

    Returns
    -------
    list[str]
        One string per recommendation, prefixed with the priority emoji
        and diagnostic code.
    """
    lines: list[str] = []
    for rec in recommendations:
        label = rec.priority.value.upper()
        line = f"[{label}] {rec.code}: {rec.summary}"
        lines.append(line)
        if include_detail:
            lines.append(f"  → {rec.detail}")
            lines.append(f"  → Recommendation: {rec.recommendation}")
    return lines
