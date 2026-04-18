"""Tool Surface registry (v0.8.0 Task 2).

This module provides a static registry of ToolSurface and CommandSurface entries
mapped from real HermesOptimizer surfaces.

The registry covers 4 families:
1. provider/config: provider_truth, config_fix, provider_management, endpoints
2. workflow: workflow/schema, workflow/store, todo_cmd, devdo_cmd
3. dreams/memory: memory_meta, decay, sweep, recall
4. report: markdown, json_export, health, issues, issues_grouping

Design principles:
- Static registry (no runtime discovery)
- Small and deterministic
- Reuses schema types from tool_surface.schema
- No scoring/audit/presentation logic here
"""

from __future__ import annotations

from hermesoptimizer.tool_surface.schema import (
    CommandSurface,
    HelpContract,
    OutputContract,
    RiskLevel,
    SurfaceKind,
    ToolSurface,
)


# ---------------------------------------------------------------------------
# Provider/Config family surfaces
# ---------------------------------------------------------------------------


PROVIDER_TRUTH_INSPECT = ToolSurface(
    surface_name="provider_truth_inspect",
    command_name="inspect_provider_truth",
    kind=SurfaceKind.TYPED,
    risk_level=RiskLevel.LOW,
    supports_help=True,
    supports_partial_discovery=False,
    supports_overflow_handle=False,
    supports_binary_guard=False,
    read_only=True,
    recommended_for_agent=True,
    notes="Read-only inspection of ProviderTruthStore for canonical provider info, known models, and endpoint candidates. Backed by sources/provider_truth.py.",
    help_contract=HelpContract(usage="help provider_truth_inspect"),
    output_contract=OutputContract(format="json"),
)

ENDPOINT_VERIFICATION = ToolSurface(
    surface_name="endpoint_verification",
    command_name="verify_endpoint",
    kind=SurfaceKind.TYPED,
    risk_level=RiskLevel.LOW,
    supports_help=True,
    supports_partial_discovery=False,
    supports_overflow_handle=False,
    supports_binary_guard=False,
    read_only=True,
    recommended_for_agent=True,
    notes="Verify provider/endpoint/model config against provider truth. Detects stale aliases, deprecated models, RKWE, endpoint drift. Also covers provider health tracking, endpoint quarantine with TTL/decay, and credential provenance. Backed by verify/endpoints.py and verify/provider_management.py.",
    help_contract=HelpContract(usage="help endpoint_verification"),
    output_contract=OutputContract(format="json"),
)

CONFIG_FIX_PRODUCE = ToolSurface(
    surface_name="config_fix_produce",
    command_name="produce_fixes",
    kind=SurfaceKind.TYPED,
    risk_level=RiskLevel.MEDIUM,
    supports_help=True,
    supports_partial_discovery=False,
    supports_overflow_handle=False,
    supports_binary_guard=False,
    read_only=False,
    recommended_for_agent=True,
    notes="Produce ConfigFix recommendations from endpoint verification results. Classifies actions as AUTO_FIX, RECOMMEND, or HUMAN_ONLY. Backed by verify/config_fix.py.",
    help_contract=HelpContract(usage="help config_fix_produce"),
    output_contract=OutputContract(format="json"),
)


# ---------------------------------------------------------------------------
# Workflow family surfaces
# ---------------------------------------------------------------------------


WORKFLOW_PLAN_MANAGE = CommandSurface(
    surface_name="workflow_plan_manage",
    command_name="workflow",
    kind=SurfaceKind.TEXTUAL,
    risk_level=RiskLevel.MEDIUM,
    supports_help=True,
    supports_partial_discovery=True,
    supports_overflow_handle=True,
    supports_binary_guard=False,
    read_only=False,
    recommended_for_agent=True,
    notes="Workflow plan management: create_plan, update_plan, freeze_plan, add_task, list_plans. Backed by commands/todo_cmd.py and workflow/schema.py.",
    help_contract=HelpContract(usage="workflow --help"),
    subcommands=["create", "update", "freeze", "add-task", "list"],
)

WORKFLOW_RUN_CONTROL = CommandSurface(
    surface_name="workflow_run_control",
    command_name="devdo",
    kind=SurfaceKind.TEXTUAL,
    risk_level=RiskLevel.HIGH,
    supports_help=True,
    supports_partial_discovery=True,
    supports_overflow_handle=True,
    supports_binary_guard=False,
    read_only=False,
    recommended_for_agent=True,
    notes="Workflow execution control: start_run, update_task_status, record_checkpoint, record_blocker, resolve_run. Backed by commands/devdo_cmd.py.",
    help_contract=HelpContract(usage="devdo --help"),
    subcommands=["start", "task", "checkpoint", "block", "resolve"],
)

WORKFLOW_INSPECT = ToolSurface(
    surface_name="workflow_inspect",
    command_name="inspect_workflow",
    kind=SurfaceKind.TYPED,
    risk_level=RiskLevel.LOW,
    supports_help=True,
    supports_partial_discovery=False,
    supports_overflow_handle=False,
    supports_binary_guard=False,
    read_only=True,
    recommended_for_agent=True,
    notes="Read-only inspection of workflow plans, runs, tasks, checkpoints, and blockers. Backed by workflow/store.py.",
    help_contract=HelpContract(usage="help workflow_inspect"),
    output_contract=OutputContract(format="json"),
)


# ---------------------------------------------------------------------------
# Dreams/Memory family surfaces
# ---------------------------------------------------------------------------


MEMORY_META_QUERY = ToolSurface(
    surface_name="memory_meta_query",
    command_name="query_memory",
    kind=SurfaceKind.TYPED,
    risk_level=RiskLevel.MEDIUM,
    supports_help=True,
    supports_partial_discovery=False,
    supports_overflow_handle=False,
    supports_binary_guard=False,
    read_only=False,
    recommended_for_agent=True,
    notes="Memory metadata DB operations: init_db, upsert, query_by_score, update_recall, set_fidelity. Backed by dreams/memory_meta.py.",
    help_contract=HelpContract(usage="help memory_meta_query"),
    output_contract=OutputContract(format="json"),
)

DREAM_SWEEP = ToolSurface(
    surface_name="dream_sweep",
    command_name="run_sweep",
    kind=SurfaceKind.TYPED,
    risk_level=RiskLevel.LOW,
    supports_help=True,
    supports_partial_discovery=False,
    supports_overflow_handle=False,
    supports_binary_guard=False,
    read_only=True,
    recommended_for_agent=True,
    notes="Dreaming sweep: decay scoring, tier classification (full/summary/essence/gone), and prune/demote/keep decisions. Backed by dreams/decay.py and dreams/sweep.py.",
    help_contract=HelpContract(usage="help dream_sweep"),
    output_contract=OutputContract(format="json"),
)

DREAM_RECALL_REHEAT = ToolSurface(
    surface_name="dream_recall_reheat",
    command_name="reheat_recall",
    kind=SurfaceKind.TYPED,
    risk_level=RiskLevel.MEDIUM,
    supports_help=True,
    supports_partial_discovery=False,
    supports_overflow_handle=False,
    supports_binary_guard=False,
    read_only=False,
    recommended_for_agent=True,
    notes="Recall reheating: parse_session_transcript, scan_sessions_directory, read_recall_log, reheat_recalled_ids. Backed by dreams/recall.py.",
    help_contract=HelpContract(usage="help dream_recall_reheat"),
    output_contract=OutputContract(format="json"),
)


# ---------------------------------------------------------------------------
# Report family surfaces
# ---------------------------------------------------------------------------


REPORT_MARKDOWN_WRITE = ToolSurface(
    surface_name="report_markdown_write",
    command_name="write_markdown_report",
    kind=SurfaceKind.TYPED,
    risk_level=RiskLevel.MEDIUM,
    supports_help=True,
    supports_partial_discovery=False,
    supports_overflow_handle=False,
    supports_binary_guard=False,
    read_only=False,
    recommended_for_agent=True,
    notes="Write Hermes report as markdown. Produces tables for metrics, findings, records, provider health, model validity, repair priority, lane-aware repairs, provenance collisions. Backed by report/markdown.py.",
    help_contract=HelpContract(usage="help report_markdown_write"),
)

REPORT_JSON_EXPORT = ToolSurface(
    surface_name="report_json_export",
    command_name="write_json_report",
    kind=SurfaceKind.TYPED,
    risk_level=RiskLevel.MEDIUM,
    supports_help=True,
    supports_partial_discovery=False,
    supports_overflow_handle=False,
    supports_binary_guard=False,
    read_only=False,
    recommended_for_agent=True,
    notes="Export Hermes report as JSON. Includes metrics, records, findings, grouped findings, before/after comparison, provider health, model validity, repair priority, lane-aware repairs, provenance collisions. Backed by report/json_export.py.",
    help_contract=HelpContract(usage="help report_json_export"),
    output_contract=OutputContract(format="json"),
)

REPORT_HEALTH_COMPUTE = ToolSurface(
    surface_name="report_health_compute",
    command_name="compute_report_health",
    kind=SurfaceKind.TYPED,
    risk_level=RiskLevel.LOW,
    supports_help=True,
    supports_partial_discovery=False,
    supports_overflow_handle=False,
    supports_binary_guard=False,
    read_only=True,
    recommended_for_agent=True,
    notes="Compute report health surfaces: provider health summary, model validity summary, repair priority, lane-aware repairs, provenance collisions. Backed by report/health.py and report/issues.py.",
    help_contract=HelpContract(usage="help report_health_compute"),
    output_contract=OutputContract(format="json"),
)


# ---------------------------------------------------------------------------
# Registry accessor
# ---------------------------------------------------------------------------


def default_surfaces() -> list[ToolSurface | CommandSurface]:
    """Return the default registry of tool surfaces.

    Returns 12 entries covering 4 families:
    - Provider/Config: 3 entries
    - Workflow: 3 entries
    - Dreams/Memory: 3 entries
    - Report: 3 entries
    """
    return [
        # Provider/Config family
        PROVIDER_TRUTH_INSPECT,
        ENDPOINT_VERIFICATION,
        CONFIG_FIX_PRODUCE,
        # Workflow family
        WORKFLOW_PLAN_MANAGE,
        WORKFLOW_RUN_CONTROL,
        WORKFLOW_INSPECT,
        # Dreams/Memory family
        MEMORY_META_QUERY,
        DREAM_SWEEP,
        DREAM_RECALL_REHEAT,
        # Report family
        REPORT_MARKDOWN_WRITE,
        REPORT_JSON_EXPORT,
        REPORT_HEALTH_COMPUTE,
    ]


# Alias for backward compatibility
build_default_registry = default_surfaces
