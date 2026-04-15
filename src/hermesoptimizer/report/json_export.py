from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from hermesoptimizer.catalog import Finding, Record
from hermesoptimizer.report.issues import group_findings_by_fingerprint


def _compute_metrics(
    *,
    records: list[Record],
    findings: list[Finding],
    inspected_inputs: list[dict] | None,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    counts["records_total"] = len(records)
    counts["findings_total"] = len(findings)
    counts["finding_groups_total"] = len(group_findings_by_fingerprint(findings))
    counts["inspected_inputs_total"] = len(inspected_inputs or [])
    counts["gateway_findings"] = sum(1 for finding in findings if finding.category == "gateway-signal")
    counts["config_findings"] = sum(1 for finding in findings if finding.category == "config-signal")
    counts["session_findings"] = sum(1 for finding in findings if finding.category == "session-signal")
    counts["log_findings"] = sum(1 for finding in findings if finding.category == "log-signal")
    counts["runtime_findings"] = sum(1 for finding in findings if finding.category == "runtime-signal")
    return counts


def _build_before_after(comparison: dict | None) -> dict | None:
    if not comparison:
        return None
    return comparison


def write_json_report(
    path: str | Path,
    *,
    title: str,
    records: list[Record],
    findings: list[Finding],
    inspected_inputs: list[dict] | None = None,
    comparison: dict | None = None,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    grouped_findings = []
    for fingerprint, items in group_findings_by_fingerprint(findings).items():
        grouped_findings.append(
            {
                "fingerprint": fingerprint,
                "count": len(items),
                "category": items[0].category,
                "severity": items[0].severity,
                "lane": items[0].lane,
                "sample_text": items[0].sample_text,
                "kinds": sorted({item.kind for item in items if item.kind}),
            }
        )
    metrics = _compute_metrics(records=records, findings=findings, inspected_inputs=inspected_inputs)
    payload = {
        "title": title,
        "inspected_inputs": inspected_inputs or [],
        "metrics": metrics,
        "records": [asdict(record) for record in records],
        "findings": [asdict(finding) for finding in findings],
        "finding_groups": grouped_findings,
    }
    before_after = _build_before_after(comparison)
    if before_after is not None:
        payload["before_after"] = before_after
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
