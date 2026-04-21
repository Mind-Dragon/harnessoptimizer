from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

from hermesoptimizer.budget.commands import (
    add_budget_review_subparser,
    add_budget_set_subparser,
    handle_budget_review,
    handle_budget_set,
)
from hermesoptimizer.catalog import (
    Finding,
    Record,
    finish_run,
    get_findings,
    get_records,
    get_run_history,
    init_db,
    start_run,
    upsert_finding,
    upsert_record,
)
from hermesoptimizer.paths import get_db_path
from hermesoptimizer.report.json_export import write_json_report
from hermesoptimizer.report.markdown import write_markdown_report
from hermesoptimizer.report.metrics import compute_report_metrics
from hermesoptimizer.vault import (
    build_vault_inventory,
    default_vault_roots,
    deduplicate_entries,
    execute_write_back,
    plan_write_back,
    validate_inventory,
)


def _report_metrics(records: list[Record], findings: list[Finding], inspected_inputs: list[dict]) -> dict[str, int]:
    return compute_report_metrics(records=records, findings=findings, inspected_inputs=inspected_inputs)


def _delta_metrics(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    keys = set(before) | set(after)
    return {key: after.get(key, 0) - before.get(key, 0) for key in keys}


def _comparison_from_history(db_path: Path, current_metrics: dict[str, int]) -> dict | None:
    history = get_run_history(db_path, limit=1)
    if not history:
        return None
    baseline = history[0]
    baseline_metrics = baseline.get("metrics")
    if not isinstance(baseline_metrics, dict):
        return None
    baseline_metrics_int = {k: int(v) for k, v in baseline_metrics.items() if isinstance(v, int) or isinstance(v, float)}
    baseline_title = f"Run #{baseline.get('id', 'baseline')}"
    if baseline.get("title"):
        baseline_title = str(baseline["title"])
    return {
        "baseline_title": baseline_title,
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


def _vault_audit(args: argparse.Namespace) -> int:
    """Run vault audit: inventory, validate, summarize dedup/rotation, optionally write report."""
    # Determine vault root
    if args.vault_root:
        vault_roots = [Path(args.vault_root)]
    else:
        vault_roots = default_vault_roots()

    # Build inventory
    inventory = build_vault_inventory(vault_roots)

    # Validate entries
    validation_results = validate_inventory(inventory)

    # Deduplicate entries
    dedup_results = deduplicate_entries(inventory.entries)

    # Build validation lookup
    validation_by_source = {vr.source_path: vr for vr in validation_results}

    # Summarize output
    total_entries = len(inventory.entries)
    total_files = len(inventory.files)
    total_roots = len(inventory.roots)
    valid_count = sum(1 for r in validation_results if r.ok)
    invalid_count = total_entries - valid_count
    dedup_groups = len(dedup_results)
    total_dedup = sum(len(d.duplicates) for d in dedup_results)

    # Print summary
    print(f"Vault Audit Summary")
    print(f"  roots: {total_roots}")
    print(f"  files: {total_files}")
    print(f"  total entries: {total_entries}")
    print(f"  validation: {valid_count} ok, {invalid_count} invalid")
    print(f"  dedup: {dedup_groups} groups, {total_dedup} duplicates")

    # Print entries with their validation status
    for entry in inventory.entries:
        path_str = str(entry.source_path)
        vr = validation_by_source.get(path_str)
        status = vr.status if vr else "unknown"
        print(f"  entry {entry.key_name} ({entry.source_kind}): {path_str} [{status}]")

    # Print validation issues (only invalid)
    for vr in validation_results:
        if not vr.ok:
            print(f"  [{vr.status}] {vr.source_path}: {vr.message}")

    # Print dedup summary
    for i, dr in enumerate(dedup_results, 1):
        if dr.duplicates:
            print(f"  dedup group {i}: canonical={dr.canonical.source_path}:{dr.canonical.key_name}")
            for dup in dr.duplicates:
                print(f"    duplicate={dup.source_path}:{dup.key_name}")

    # Write report if requested
    if args.report:
        report_path = Path(args.report)
        lines = [
            "Vault Audit Report",
            "=" * 40,
            f"roots: {total_roots}",
            f"files: {total_files}",
            f"total entries: {total_entries}",
            f"validation: {valid_count} ok, {invalid_count} invalid",
            f"dedup: {dedup_groups} groups, {total_dedup} duplicates",
            "",
            "Entries:",
        ]
        for entry in inventory.entries:
            path_str = str(entry.source_path)
            vr = validation_by_source.get(path_str)
            status = vr.status if vr else "unknown"
            lines.append(f"  {entry.key_name} ({entry.source_kind}): {path_str} [{status}]")

        lines.extend(["", "Validation Issues:"])
        has_issues = False
        for vr in validation_results:
            if not vr.ok:
                has_issues = True
                lines.append(f"  [{vr.status}] {vr.source_path}: {vr.message}")
        if not has_issues:
            lines.append("  (none)")

        lines.extend(["", "Deduplication Groups:"])
        has_dedup = False
        for i, dr in enumerate(dedup_results, 1):
            if dr.duplicates:
                has_dedup = True
                lines.append(f"  Group {i}: canonical={dr.canonical.source_path}:{dr.canonical.key_name}")
                for dup in dr.duplicates:
                    lines.append(f"    duplicate={dup.source_path}:{dup.key_name}")
        if not has_dedup:
            lines.append("  (none)")

        report_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"  report written to {report_path}")

    return 0


def _vault_writeback(args: argparse.Namespace) -> int:
    """Execute write-back operations for vault files with explicit --confirm flow.

    Safety contract:
    - --vault-root is REQUIRED (no auto-discovery to prevent accidental production writes)
    - --confirm must be explicitly provided to actually write changes
    - Without --confirm, only a dry-run is performed
    - Production vault is opt-in via explicit --vault-root
    """
    vault_roots = [Path(args.vault_root)]

    # Build inventory from specified vault root
    inventory = build_vault_inventory(vault_roots)

    # Plan write-back for the specified format
    plan = plan_write_back(inventory, target_format=args.format)

    # Execute write-back with explicit confirm flag
    result = execute_write_back(plan, inventory, confirm=args.confirm)

    if args.confirm:
        print(f"Write-back completed for format={args.format}")
        print(f"  files processed: {result.files_processed}")
        print(f"  files modified: {result.files_modified}")
        print(f"  files preserved: {result.files_preserved}")
        for mutation in result.mutations_logged:
            print(f"  {mutation}")
    else:
        print(f"Write-back dry-run for format={args.format}")
        print(f"  files planned: {len(plan.operations)}")
        print(f"  Use --confirm to actually write changes")

    return 0


def _handle_init_db(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    init_db(db_path)
    print(f"initialized {db_path}")
    return 0


def _handle_add_record(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    init_db(db_path)
    upsert_record(db_path, _record_from_args(args))
    print("record saved")
    return 0


def _handle_add_finding(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    init_db(db_path)
    upsert_finding(db_path, _finding_from_args(args))
    print("finding saved")
    return 0


def _handle_export(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    init_db(db_path)
    run_id = start_run(db_path, "export")
    records = [Record(**{k: v for k, v in row.items() if k in Record.__annotations__}) for row in get_records(db_path)]
    findings = [Finding(**{k: v for k, v in row.items() if k in Finding.__annotations__}) for row in get_findings(db_path)]
    out_dir = Path(args.out_dir)
    inspected_inputs = _inspected_inputs_from_rows(records, findings)
    current_metrics = _report_metrics(records, findings, inspected_inputs)
    comparison = _comparison_from_history(db_path, current_metrics)
    write_json_report(out_dir / "report.json", title=args.title, records=records, findings=findings, inspected_inputs=inspected_inputs, comparison=comparison)
    write_markdown_report(out_dir / "report.md", title=args.title, records=records, findings=findings, inspected_inputs=inspected_inputs, comparison=comparison)
    finish_run(db_path, run_id, record_count=len(records), finding_count=len(findings), metrics=current_metrics)
    print(f"wrote {out_dir}")
    return 0


def _handle_list_records(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    init_db(db_path)
    for row in get_records(db_path):
        print(row)
    return 0


def _handle_list_findings(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    init_db(db_path)
    for row in get_findings(db_path):
        print(row)
    return 0


def _handle_vault_audit(args: argparse.Namespace) -> int:
    return _vault_audit(args)


def _handle_vault_writeback(args: argparse.Namespace) -> int:
    return _vault_writeback(args)


def _handle_budget_review(args: argparse.Namespace) -> int:
    return handle_budget_review(args)


def _handle_budget_set(args: argparse.Namespace) -> int:
    return handle_budget_set(args)


# Legacy command handlers
HANDLERS: dict[str, Callable[[argparse.Namespace], int]] = {
    "init-db": _handle_init_db,
    "add-record": _handle_add_record,
    "add-finding": _handle_add_finding,
    "export": _handle_export,
    "list-records": _handle_list_records,
    "list-findings": _handle_list_findings,
    "vault-audit": _handle_vault_audit,
    "vault-writeback": _handle_vault_writeback,
    "budget-review": _handle_budget_review,
    "budget-set": _handle_budget_set,
}


def add_subparsers(subparsers) -> None:
    """Add legacy subparsers to an existing argparse subparsers object."""
    init_db_cmd = subparsers.add_parser("init-db", help="Initialize the SQLite database")
    init_db_cmd.add_argument("--db", default=str(get_db_path()))

    add_record = subparsers.add_parser("add-record", help="Insert or update a record")
    add_record.add_argument("--db", default=str(get_db_path()))
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

    add_finding = subparsers.add_parser("add-finding", help="Insert a finding")
    add_finding.add_argument("--db", default=str(get_db_path()))
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

    export_cmd = subparsers.add_parser("export", help="Write JSON and Markdown reports")
    export_cmd.add_argument("--db", default=str(get_db_path()))
    export_cmd.add_argument("--out-dir", default="reports")
    export_cmd.add_argument("--title", default="Hermes Optimizer Report")

    list_records = subparsers.add_parser("list-records", help="Print stored records")
    list_records.add_argument("--db", default=str(get_db_path()))

    list_findings = subparsers.add_parser("list-findings", help="Print stored findings")
    list_findings.add_argument("--db", default=str(get_db_path()))

    vault_audit = subparsers.add_parser("vault-audit", help="Audit a vault root for entries, validation, dedup, and rotation state")
    vault_audit.add_argument("--vault-root", help="Path to vault root (default: ~/.vault)")
    vault_audit.add_argument("--report", help="Path to write a simple text audit report")

    vault_writeback = subparsers.add_parser("vault-writeback", help="Execute write-back to vault files with explicit --confirm flow")
    vault_writeback.add_argument("--vault-root", required=True, help="Path to vault root (required for safety — no auto-discovery)")
    vault_writeback.add_argument("--format", required=True, choices=["env", "yaml"], help="Target format for write-back")
    vault_writeback.add_argument("--confirm", action="store_true", help="Explicit confirmation to actually write changes (without this flag, only dry-run)")

    add_budget_review_subparser(subparsers)
    add_budget_set_subparser(subparsers)
