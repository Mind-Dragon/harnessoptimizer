from __future__ import annotations

from hermesoptimizer.catalog import Finding


def assign_lane(finding: Finding) -> str:
    if finding.category.startswith("log"):
        return "auxiliary"
    if finding.category.startswith("session"):
        return "auxiliary"
    return finding.lane or "research"
