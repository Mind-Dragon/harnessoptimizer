from __future__ import annotations

from pathlib import Path

from hermesoptimizer.catalog import Finding, Record
from hermesoptimizer.report.json_export import write_json_report
from hermesoptimizer.report.markdown import write_markdown_report


def test_json_and_markdown_report(tmp_path: Path) -> None:
    record = Record(
        provider="openai",
        model="gpt-5",
        base_url="https://api.openai.com/v1",
        auth_type="bearer",
        auth_key="OPENAI_API_KEY",
        lane="coding",
        region=None,
        capabilities=["text"],
        context_window=128000,
        source="manual",
        confidence="high",
    )
    finding = Finding(
        file_path="a.log",
        line_num=1,
        category="log-signal",
        severity="medium",
    )

    out_dir = tmp_path / "reports"
    write_json_report(out_dir / "report.json", title="Report", records=[record], findings=[finding])
    write_markdown_report(out_dir / "report.md", title="Report", records=[record], findings=[finding])

    assert "\"title\": \"Report\"" in (out_dir / "report.json").read_text(encoding="utf-8")
    assert "# Report" in (out_dir / "report.md").read_text(encoding="utf-8")
