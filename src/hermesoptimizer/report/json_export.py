from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from hermesoptimizer.catalog import Finding, Record
from hermesoptimizer.report.issues import group_findings_by_fingerprint
from hermesoptimizer.report.metrics import compute_report_metrics


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
    metrics = compute_report_metrics(records=records, findings=findings, inspected_inputs=inspected_inputs)
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
