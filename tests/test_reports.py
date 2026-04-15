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


def test_json_report_contains_inspected_inputs_header(tmp_path: Path) -> None:
    """JSON report should include an 'inspected_inputs' header section."""
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
    # inspected inputs should list the files and commands that were inspected
    inspected_inputs = [
        {"type": "file", "path": "/home/user/.hermes/config.yaml"},
        {"type": "command", "command": "pgrep -f hermes"},
    ]

    out_dir = tmp_path / "reports"
    write_json_report(
        out_dir / "report.json",
        title="Report",
        records=[record],
        findings=[finding, finding],
        inspected_inputs=inspected_inputs,
    )

    report_text = (out_dir / "report.json").read_text(encoding="utf-8")
    assert "inspected_inputs" in report_text
    assert "/home/user/.hermes/config.yaml" in report_text
    assert "pgrep -f hermes" in report_text
    assert "finding_groups" in report_text


def test_markdown_report_contains_inspected_inputs_header(tmp_path: Path) -> None:
    """Markdown report should include an '## Inspected Inputs' section."""
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
    # inspected inputs should list the files and commands that were inspected
    inspected_inputs = [
        {"type": "file", "path": "/home/user/.hermes/config.yaml"},
        {"type": "command", "command": "pgrep -f hermes"},
    ]

    out_dir = tmp_path / "reports"
    write_markdown_report(
        out_dir / "report.md",
        title="Report",
        records=[record],
        findings=[finding],
        inspected_inputs=inspected_inputs,
    )

    report_text = (out_dir / "report.md").read_text(encoding="utf-8")
    assert "Inspected Inputs" in report_text
    assert "/home/user/.hermes/config.yaml" in report_text
    assert "pgrep -f hermes" in report_text
    assert "Finding Groups" in report_text
