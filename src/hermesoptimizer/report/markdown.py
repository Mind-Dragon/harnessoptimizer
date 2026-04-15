from __future__ import annotations

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
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    metrics = _compute_metrics(records=records, findings=findings, inspected_inputs=inspected_inputs)
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

    path.write_text("\n".join(lines), encoding="utf-8")
