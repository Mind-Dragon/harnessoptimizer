from __future__ import annotations

from hermesoptimizer.catalog import Finding, Record
from hermesoptimizer.report.issues import group_findings_by_fingerprint

METRIC_KEYS: tuple[str, ...] = (
    "records_total",
    "findings_total",
    "finding_groups_total",
    "inspected_inputs_total",
    "gateway_findings",
    "config_findings",
    "session_findings",
    "log_findings",
    "runtime_findings",
)


def compute_report_metrics(
    *,
    records: list[Record],
    findings: list[Finding],
    inspected_inputs: list[dict] | None,
) -> dict[str, int]:
    counts: dict[str, int] = {
        "records_total": len(records),
        "findings_total": len(findings),
        "finding_groups_total": len(group_findings_by_fingerprint(findings)),
        "inspected_inputs_total": len(inspected_inputs or []),
        "gateway_findings": sum(1 for finding in findings if finding.category == "gateway-signal"),
        "config_findings": sum(1 for finding in findings if finding.category == "config-signal"),
        "session_findings": sum(1 for finding in findings if finding.category == "session-signal"),
        "log_findings": sum(1 for finding in findings if finding.category == "log-signal"),
        "runtime_findings": sum(1 for finding in findings if finding.category == "runtime-signal"),
    }
    return {key: counts[key] for key in METRIC_KEYS}
