from __future__ import annotations

from pathlib import Path

from hermesoptimizer.catalog import Finding, Record
from hermesoptimizer.report.issues import group_findings_by_fingerprint


def write_markdown_report(
    path: str | Path,
    *,
    title: str,
    records: list[Record],
    findings: list[Finding],
    inspected_inputs: list[dict] | None = None,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [f"# {title}", ""]

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
