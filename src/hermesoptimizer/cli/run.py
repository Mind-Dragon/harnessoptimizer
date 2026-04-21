"""run command – full analysis pipeline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

from hermesoptimizer.catalog import (
    init_db,
    insert_findings_batch,
    start_run,
    finish_run,
    get_records,
    get_findings,
    Finding,
)
from hermesoptimizer.discovery import discover_hermes_surfaces
from hermesoptimizer.paths import get_db_path


HANDLERS: dict[str, Callable[[argparse.Namespace], int]] = {}


def add_subparsers(subparsers) -> None:
    run_parser = subparsers.add_parser("run", help="Run full analysis pipeline")
    run_parser.add_argument(
        "--out-dir",
        default=str(Path.home() / ".hoptimizer" / "reports"),
        help="Directory to write reports (default: ~/.hoptimizer/reports)",
    )
    run_parser.add_argument(
        "--title",
        default="Hermes Optimizer Report",
        help="Report title",
    )
    run_parser.add_argument(
        "--db",
        default=str(get_db_path()),
        help="Path to SQLite catalog (default: ~/.hoptimizer/db/catalog.db)",
    )
    HANDLERS["run"] = handle_run


def _write_json_report(out_dir: Path, title: str, records: list[dict], findings: list[dict], surfaces: list[Path]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "report.json"
    report = {
        "title": title,
        "inspected_inputs": [str(s) for s in surfaces],
        "records": records,
        "findings": findings,
    }
    path.write_text(json.dumps(report, indent=2))
    return path


def _write_markdown_report(out_dir: Path, title: str, records: list[dict], findings: list[dict], surfaces: list[Path]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "report.md"
    lines = [
        f"# {title}",
        "",
        f"Inspected {len(surfaces)} input file(s).",
        "",
        "## Findings Summary",
        "",
    ]
    if findings:
        for f in findings:
            lines.append(
                f"- **{f.get('severity', '?')}** [{f.get('category', '?')}] "
                f"{f.get('sample_text', f.get('kind', 'unknown'))}"
            )
    else:
        lines.append("No findings.")

    lines.extend(["", "## Records", ""])
    if records:
        for r in records:
            lines.append(
                f"- {r.get('provider', '?')}/{r.get('model', '?')} "
                f"(lane={r.get('lane', 'default')}, context={r.get('context_window', '?')})"
            )
    else:
        lines.append("No records.")

    path.write_text("\n".join(lines))
    return path


def handle_run(args: argparse.Namespace) -> int:
    """Run the full analysis pipeline."""
    db_path = args.db
    out_dir = Path(args.out_dir)

    # Initialize DB
    init_db(db_path)

    # Discover files
    surfaces = discover_hermes_surfaces()
    print(f"Discovered {len(surfaces)} input file(s).")

    # Start run
    run_id = start_run(db_path, mode="full")
    print(f"Run {run_id} started.")

    findings: list[Finding] = []

    # ----- Token analysis -----
    try:
        from hermesoptimizer.tokens.analyzer import TokenAnalyzer
        from hermesoptimizer.tokens.optimizer import TokenOptimizer

        json_files = [s for s in surfaces if s.suffix == ".json"]
        if json_files:
            analyzer = TokenAnalyzer(json_files)
            analyzer.analyze()
            optimizer = TokenOptimizer(analyzer)
            recs = optimizer.generate_recommendations()
            print(f"Token analysis: {len(analyzer.usages)} usages, {len(analyzer.wastes)} wastes")

            for w in analyzer.wastes:
                findings.append(
                    Finding(
                        file_path=None,
                        line_num=None,
                        category="token_waste",
                        severity=w.severity,
                        kind=w.waste_type,
                        sample_text=w.description,
                        confidence="high",
                    )
                )
    except Exception as exc:
        print(f"[token analysis] ERROR: {exc}", flush=True)

    # ----- Performance analysis -----
    try:
        from hermesoptimizer.perf.analyzer import PerfAnalyzer

        json_files = [s for s in surfaces if s.suffix == ".json"]
        if json_files:
            analyzer = PerfAnalyzer(json_files)
            analyzer.analyze()
            perf = analyzer.get_provider_perf()
            outages = analyzer.get_outages()
            print(f"Perf analysis: {len(perf)} providers, {len(outages)} outages")

            for p in perf:
                if p.error_rate > 0.1:
                    findings.append(
                        Finding(
                            file_path=None,
                            line_num=None,
                            category="provider_perf",
                            severity="WARNING",
                            kind="high_error_rate",
                            sample_text=f"{p.provider}/{p.model} error_rate={p.error_rate:.1%}",
                            confidence="high",
                        )
                    )
            for o in outages:
                findings.append(
                    Finding(
                        file_path=None,
                        line_num=None,
                        category="provider_outage",
                        severity="CRITICAL",
                        kind="outage_detected",
                        sample_text=f"{o.provider}/{o.model}: {o.error_reason}",
                        confidence="high",
                    )
                )
    except Exception as exc:
        print(f"[perf analysis] ERROR: {exc}", flush=True)

    # ----- Tool analysis -----
    try:
        from hermesoptimizer.tools.analyzer import ToolAnalyzer
        from hermesoptimizer.tools.optimizer import ToolOptimizer

        json_files = [s for s in surfaces if s.suffix == ".json"]
        if json_files:
            analyzer = ToolAnalyzer(json_files)
            analyzer.analyze()
            optimizer = ToolOptimizer(analyzer)
            recs = optimizer.generate_recommendations()
            print(f"Tool analysis: {len(analyzer.usages)} usages, {len(analyzer.misses)} misses")

            for m in analyzer.misses:
                findings.append(
                    Finding(
                        file_path=None,
                        line_num=None,
                        category="tool_miss",
                        severity=m.severity,
                        kind=m.miss_type,
                        sample_text=m.description,
                        confidence="high",
                    )
                )
    except Exception as exc:
        print(f"[tool analysis] ERROR: {exc}", flush=True)

    # ----- Network validation -----
    try:
        from hermesoptimizer.network.validator import validate_config_ports, validate_config_ips
        import yaml

        yaml_files = [s for s in surfaces if s.suffix in (".yaml", ".yml")]
        if yaml_files:
            for yf in yaml_files:
                try:
                    data = yaml.safe_load(yf.read_text()) or {}
                except Exception:
                    continue
                findings.extend(validate_config_ports(data, db_path))
                findings.extend(validate_config_ips(data))
            print(f"Network validation: {len(yaml_files)} config(s) scanned")
    except Exception as exc:
        print(f"[network validation] ERROR: {exc}", flush=True)

    # Store findings
    insert_findings_batch(db_path, findings)
    print(f"Stored {len(findings)} finding(s).")

    # Finish run
    finish_run(
        db_path,
        run_id,
        record_count=0,
        finding_count=len(findings),
        metrics={"title": args.title, "surfaces": len(surfaces)},
    )
    print(f"Run {run_id} finished.")

    # Generate reports
    records = get_records(db_path)
    db_findings = get_findings(db_path)

    json_path = _write_json_report(out_dir, args.title, records, db_findings, surfaces)
    md_path = _write_markdown_report(out_dir, args.title, records, db_findings, surfaces)

    print(f"\nReports written to:")
    print(f"  JSON: {json_path}")
    print(f"  MD:   {md_path}")

    # Console summary
    print(f"\n{'=' * 60}")
    print(f"ANALYSIS COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Files inspected: {len(surfaces)}")
    print(f"  Findings:        {len(findings)}")
    print(f"  Records:         {len(records)}")

    return 0
