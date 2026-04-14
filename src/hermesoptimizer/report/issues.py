from __future__ import annotations

from collections import defaultdict

from hermesoptimizer.catalog import Finding


def group_findings(findings: list[Finding]) -> dict[str, list[Finding]]:
    grouped: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        grouped[finding.category].append(finding)
    return dict(grouped)
