from __future__ import annotations

import argparse
from pathlib import Path
import sys

from hermesoptimizer.catalog import (
    Finding,
    Record,
    finish_run,
    get_findings,
    get_records,
    init_db,
    start_run,
    upsert_finding,
    upsert_record,
)
from hermesoptimizer.report.json_export import write_json_report
from hermesoptimizer.report.markdown import write_markdown_report


def _report_metrics(records: list[Record], findings: list[Finding], inspected_inputs: list[dict]) -> dict[str, int]:
    metrics: dict[str, int] = {
        "records_total": len(records),
        "findings_total": len(findings),
        "inspected_inputs_total": len(inspected_inputs),
        "finding_groups_total": len({f.fingerprint or f"{f.category}:{f.file_path or ''}:{f.line_num or ''}:{f.kind or ''}" for f in findings}),
        "gateway_findings": sum(1 for f in findings if f.category == "gateway-signal"),
        "config_findings": sum(1 for f in findings if f.category == "config-signal"),
        "session_findings": sum(1 for f in findings if f.category == "session-signal"),
        "log_findings": sum(1 for f in findings if f.category == "log-signal"),
        "runtime_findings": sum(1 for f in findings if f.category == "runtime-signal"),
    }
    return metrics


def _delta_metrics(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    keys = set(before) | set(after)
    return {key: after.get(key, 0) - before.get(key, 0) for key in keys}


def _load_baseline_report(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        import json

        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _comparison_from_baseline(title: str, baseline: dict | None, current_metrics: dict[str, int]) -> dict | None:
    if not baseline:
        return None
    baseline_metrics = baseline.get("metrics")
    if not isinstance(baseline_metrics, dict):
        return None
    baseline_metrics_int = {k: int(v) for k, v in baseline_metrics.items() if isinstance(v, int) or isinstance(v, float)}
    return {
        "baseline_title": baseline.get("title", "Baseline"),
        "baseline_metrics": baseline_metrics_int,
        "current_metrics": current_metrics,
        "deltas": _delta_metrics(baseline_metrics_int, current_metrics),
    }


def _inspected_inputs_from_rows(records: list[Record], findings: list[Finding]) -> list[dict]:
    inspected: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for finding in findings:
        if finding.file_path and finding.category == "gateway-signal":
            key = ("command", finding.file_path)
            if key not in seen:
                seen.add(key)
                inspected.append({"type": "command", "command": finding.file_path})
        elif finding.file_path:
            key = ("file", finding.file_path)
            if key not in seen:
                seen.add(key)
                inspected.append({"type": "file", "path": finding.file_path})
    return inspected


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hermesoptimizer")
    sub = parser.add_subparsers(dest="command", required=True)

    init_db_cmd = sub.add_parser("init-db", help="Initialize the SQLite database")
    init_db_cmd.add_argument("--db", default="catalog.db")

    add_record = sub.add_parser("add-record", help="Insert or update a record")
    add_record.add_argument("--db", default="catalog.db")
    add_record.add_argument("--provider", required=True)
    add_record.add_argument("--model", required=True)
    add_record.add_argument("--base-url", required=True)
    add_record.add_argument("--auth-type", required=True)
    add_record.add_argument("--auth-key", required=True)
    add_record.add_argument("--lane")
    add_record.add_argument("--region")
    add_record.add_argument("--capability", action="append", dest="capabilities", default=[])
    add_record.add_argument("--context-window", type=int, default=0)
    add_record.add_argument("--source", default="manual")
    add_record.add_argument("--confidence", default="medium")
    add_record.add_argument("--raw-text")

    add_finding = sub.add_parser("add-finding", help="Insert a finding")
    add_finding.add_argument("--db", default="catalog.db")
    add_finding.add_argument("--category", required=True)
    add_finding.add_argument("--severity", required=True)
    add_finding.add_argument("--file-path")
    add_finding.add_argument("--line-num", type=int)
    add_finding.add_argument("--kind")
    add_finding.add_argument("--fingerprint")
    add_finding.add_argument("--sample-text")
    add_finding.add_argument("--count", type=int, default=1)
    add_finding.add_argument("--confidence")
    add_finding.add_argument("--router-note")
    add_finding.add_argument("--lane")

    export_cmd = sub.add_parser("export", help="Write JSON and Markdown reports")
    export_cmd.add_argument("--db", default="catalog.db")
    export_cmd.add_argument("--out-dir", default="reports")
    export_cmd.add_argument("--title", default="Hermes Optimizer Report")

    list_records = sub.add_parser("list-records", help="Print stored records")
    list_records.add_argument("--db", default="catalog.db")

    list_findings = sub.add_parser("list-findings", help="Print stored findings")
    list_findings.add_argument("--db", default="catalog.db")

    return parser


def _record_from_args(args: argparse.Namespace) -> Record:
    return Record(
        provider=args.provider,
        model=args.model,
        base_url=args.base_url,
        auth_type=args.auth_type,
        auth_key=args.auth_key,
        lane=args.lane,
        region=args.region,
        capabilities=list(dict.fromkeys(args.capabilities)),
        context_window=args.context_window,
        source=args.source,
        confidence=args.confidence,
        raw_text=args.raw_text,
    )


def _finding_from_args(args: argparse.Namespace) -> Finding:
    return Finding(
        file_path=args.file_path,
        line_num=args.line_num,
        category=args.category,
        severity=args.severity,
        kind=args.kind,
        fingerprint=args.fingerprint,
        sample_text=args.sample_text,
        count=args.count,
        confidence=args.confidence,
        router_note=args.router_note,
        lane=args.lane,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    db_path = Path(getattr(args, "db", "catalog.db"))

    if args.command == "init-db":
        init_db(db_path)
        print(f"initialized {db_path}")
        return 0

    if args.command == "add-record":
        init_db(db_path)
        upsert_record(db_path, _record_from_args(args))
        print("record saved")
        return 0

    if args.command == "add-finding":
        init_db(db_path)
        upsert_finding(db_path, _finding_from_args(args))
        print("finding saved")
        return 0

    if args.command == "export":
        init_db(db_path)
        records = [Record(**{k: v for k, v in row.items() if k in Record.__annotations__}) for row in get_records(db_path)]
        findings = [Finding(**{k: v for k, v in row.items() if k in Finding.__annotations__}) for row in get_findings(db_path)]
        out_dir = Path(args.out_dir)
        inspected_inputs = _inspected_inputs_from_rows(records, findings)
        current_metrics = _report_metrics(records, findings, inspected_inputs)
        baseline_json = _load_baseline_report(out_dir / "report.json")
        comparison = _comparison_from_baseline(args.title, baseline_json, current_metrics)
        write_json_report(out_dir / "report.json", title=args.title, records=records, findings=findings, inspected_inputs=inspected_inputs, comparison=comparison)
        write_markdown_report(out_dir / "report.md", title=args.title, records=records, findings=findings, inspected_inputs=inspected_inputs, comparison=comparison)
        print(f"wrote {out_dir}")
        return 0

    if args.command == "list-records":
        init_db(db_path)
        for row in get_records(db_path):
            print(row)
        return 0

    if args.command == "list-findings":
        init_db(db_path)
        for row in get_findings(db_path):
            print(row)
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
