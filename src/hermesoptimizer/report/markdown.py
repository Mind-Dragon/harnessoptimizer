from __future__ import annotations

from pathlib import Path

from hermesoptimizer.catalog import Finding, Record
from hermesoptimizer.report.health import (
    LaneAwareRepairTuple,
    ModelValiditySummary,
    ProvenanceCollision,
    ProviderHealthSummary,
    RepairPriority,
)
from hermesoptimizer.report.issues import group_findings_by_fingerprint
from hermesoptimizer.report.metrics import compute_report_metrics


def _render_metrics_table(metrics: dict[str, int]) -> list[str]:
    lines = ["| metric | value |", "| --- | --- |"]
    for key in sorted(metrics):
        lines.append(f"| {key} | {metrics[key]} |")
    return lines


def _render_before_after(comparison: dict | None) -> list[str]:
    if not comparison:
        return []
    lines = ["## Before / After", ""]
    baseline = comparison.get("baseline_metrics", {})
    current = comparison.get("current_metrics", {})
    deltas = comparison.get("deltas", {})
    baseline_title = comparison.get("baseline_title", "Baseline")
    lines.append(f"Compared to: {baseline_title}")
    lines.append("")
    lines.append("| metric | before | after | delta |")
    lines.append("| --- | --- | --- | --- |")
    for key in sorted(set(baseline) | set(current) | set(deltas)):
        lines.append(f"| {key} | {baseline.get(key, '')} | {current.get(key, '')} | {deltas.get(key, '')} |")
    lines.append("")
    return lines


def write_markdown_report(
    path: str | Path,
    *,
    title: str,
    records: list[Record],
    findings: list[Finding],
    inspected_inputs: list[dict] | None = None,
    comparison: dict | None = None,
    provider_health: list[ProviderHealthSummary] | None = None,
    model_validity: list[ModelValiditySummary] | None = None,
    repair_priority: list[RepairPriority] | None = None,
    lane_repairs: list[LaneAwareRepairTuple] | None = None,
    provenance_collisions: list[ProvenanceCollision] | None = None,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    metrics = compute_report_metrics(records=records, findings=findings, inspected_inputs=inspected_inputs)
    lines: list[str] = [f"# {title}", ""]

    lines.append("## Metrics")
    lines.append("")
    lines.extend(_render_metrics_table(metrics))
    lines.append("")

    lines.extend(_render_before_after(comparison))

    # Inspected inputs section
    lines.append("## Inspected Inputs")
    lines.append("")
    if inspected_inputs:
        for inp in inspected_inputs:
            if inp.get("type") == "file":
                lines.append(f"- file: `{inp['path']}`")
            elif inp.get("type") == "command":
                lines.append(f"- command: `{inp['command']}`")
    else:
        lines.append("No inputs inspected.")
    lines.append("")

    lines.append("## Finding Groups")
    lines.append("")
    grouped = group_findings_by_fingerprint(findings)
    if grouped:
        lines.append("| fingerprint | count | category | severity | lane | sample |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for fingerprint, items in grouped.items():
            sample = (items[0].sample_text or "").replace("|", "\\|")
            lines.append(
                f"| {fingerprint} | {len(items)} | {items[0].category} | {items[0].severity} | {items[0].lane or ''} | {sample} |"
            )
    else:
        lines.append("No findings.")
    lines.append("")

    lines.append("## Records")
    lines.append("")
    if records:
        lines.append("| provider | model | base_url | lane | confidence |")
        lines.append("| --- | --- | --- | --- | --- |")
        for record in records:
            lines.append(
                f"| {record.provider} | {record.model} | {record.base_url} | {record.lane or ''} | {record.confidence} |"
            )
    else:
        lines.append("No records.")
    lines.append("")

    lines.append("## Findings")
    lines.append("")
    if findings:
        lines.append("| category | severity | file_path | line_num | lane | confidence |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for finding in findings:
            lines.append(
                f"| {finding.category} | {finding.severity} | {finding.file_path or ''} | {finding.line_num or ''} | {finding.lane or ''} | {finding.confidence or ''} |"
            )
    else:
        lines.append("No findings.")
    lines.append("")

    # v0.6.0 report output improvements: Provider Health Summary
    lines.append("## Provider Health Summary")
    lines.append("")
    if provider_health:
        lines.append("| provider | status | auth_type | endpoint | probe_result | probe_timestamp | failure_reason |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for h in provider_health:
            lines.append(
                f"| {h.provider} | {h.status} | {h.auth_type} | {h.endpoint_url} | {h.last_probe_result} | {h.last_probe_timestamp} | {h.failure_reason or ''} |"
            )
    else:
        lines.append("No provider health data.")
    lines.append("")

    # v0.6.0 report output improvements: Model Validity Summary
    lines.append("## Model Validity Summary")
    lines.append("")
    if model_validity:
        lines.append("| provider | model | status | repair_note | suggested_replacement |")
        lines.append("| --- | --- | --- | --- | --- |")
        for v in model_validity:
            lines.append(
                f"| {v.provider} | {v.model} | {v.status} | {v.repair_note or ''} | {v.suggested_replacement or ''} |"
            )
    else:
        lines.append("No model validity data.")
    lines.append("")

    # v0.6.0 report output improvements: Repair Priority
    lines.append("## Repair Priority")
    lines.append("")
    if repair_priority:
        lines.append("| priority | description | lane | safety_level |")
        lines.append("| --- | --- | --- | --- |")
        for p in repair_priority:
            lines.append(f"| {p.priority_level} | {p.description} | {p.lane or ''} | {p.safety_level} |")
    else:
        lines.append("No repair priorities.")
    lines.append("")

    # v0.6.0 report output improvements: Lane-Aware Repair Tuples
    lines.append("## Lane-Aware Repairs")
    lines.append("")
    if lane_repairs:
        lines.append("| provider_alias | endpoint_url | auth_type | region | model | repair_action | priority |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for r in lane_repairs:
            lines.append(
                f"| {r.provider_alias} | {r.endpoint_url} | {r.auth_type} | {r.region or ''} | {r.model} | {r.repair_action} | {r.priority} |"
            )
    else:
        lines.append("No lane-aware repairs.")
    lines.append("")

    # v0.6.0 report output improvements: Provenance Collisions
    lines.append("## Provenance Collisions")
    lines.append("")
    if provenance_collisions:
        for i, c in enumerate(provenance_collisions, 1):
            lines.append(f"### Collision {i}")
            lines.append(f"- **Type**: {c.collision_type}")
            lines.append(f"- **Colliding Providers**: {', '.join(c.colliding_providers)}")
            lines.append(f"- **Explanation**: {c.explanation}")
            lines.append(f"- **Suggested Resolution**: {c.suggested_resolution}")
            lines.append("")
    else:
        lines.append("No provenance collisions detected.")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
