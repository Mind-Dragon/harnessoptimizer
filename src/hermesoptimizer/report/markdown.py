from __future__ import annotations

from pathlib import Path

from hermesoptimizer.catalog import Finding, Record


def write_markdown_report(path: str | Path, *, title: str, records: list[Record], findings: list[Finding]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [f"# {title}", ""]

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
