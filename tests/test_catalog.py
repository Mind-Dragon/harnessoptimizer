from __future__ import annotations

from pathlib import Path

from hermesoptimizer.catalog import Finding, Record, get_findings, get_records, init_db, upsert_finding, upsert_record
from hermesoptimizer.report.json_export import write_json_report
from hermesoptimizer.report.markdown import write_markdown_report


def test_init_db_and_upsert_record(tmp_path: Path) -> None:
    db = tmp_path / "catalog.db"
    init_db(db)

    record = Record(
        provider="openai",
        model="gpt-5",
        base_url="https://api.openai.com/v1",
        auth_type="bearer",
        auth_key="OPENAI_API_KEY",
        lane="coding",
        region=None,
        capabilities=["text", "reasoning"],
        context_window=128000,
        source="manual",
        confidence="high",
        raw_text="seed",
    )
    upsert_record(db, record)

    records = get_records(db)
    assert len(records) == 1
    assert records[0]["provider"] == "openai"
    assert records[0]["capabilities"] == ["text", "reasoning"]


def test_upsert_finding_and_reports(tmp_path: Path) -> None:
    db = tmp_path / "catalog.db"
    init_db(db)

    finding = Finding(
        file_path="/tmp/example.log",
        line_num=12,
        category="log-signal",
        severity="medium",
        kind="raw",
        fingerprint="example:12",
        sample_text="timeout while calling provider",
        count=2,
        confidence="medium",
        router_note="keyword match",
        lane="auxiliary",
    )
    upsert_finding(db, finding)

    findings = get_findings(db)
    assert len(findings) == 1
    assert findings[0]["category"] == "log-signal"

    out_dir = tmp_path / "reports"
    write_json_report(out_dir / "report.json", title="Test", records=[], findings=[finding])
    write_markdown_report(out_dir / "report.md", title="Test", records=[], findings=[finding])

    assert (out_dir / "report.json").exists()
    assert (out_dir / "report.md").exists()
