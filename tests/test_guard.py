"""Tests for the runtime guard module."""
from __future__ import annotations

from pathlib import Path

import pytest

from hermesoptimizer.workflow.guard import (
    GuardDecision,
    GuardLog,
    GuardViolation,
    boundary_check,
    check_before_complete,
    check_before_write,
    preflight_check,
    repair_drift,
)
from hermesoptimizer.workflow.schema import WorkflowPlan, WorkflowRun, WorkflowTask


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def make_plan(
    workflow_id: str = "wf-123",
    status: str = "frozen",
    objective: str = "Test objective",
    schema_version: str = "1.0",
    next_action: str = "run_tests",
    tasks: list[WorkflowTask] | None = None,
) -> WorkflowPlan:
    """Create a WorkflowPlan with sensible defaults."""
    if tasks is None:
        tasks = [
            WorkflowTask(
                task_id="task-1",
                parent_id=None,
                dependencies=[],
                role="research",
                description="First task",
                expected_artifact=None,
                exit_criteria=["done"],
                status="pending",
            )
        ]
    return WorkflowPlan(
        workflow_id=workflow_id,
        schema_version=schema_version,
        objective=objective,
        status=status,
        next_action=next_action,
        tasks=tasks,
    )


def make_run(
    workflow_id: str = "wf-123",
    plan_version: str = "1.0",
    status: str = "running",
    guard_state: str = "clean",
    run_id: str = "run-456",
) -> WorkflowRun:
    """Create a WorkflowRun with sensible defaults."""
    return WorkflowRun(
        run_id=run_id,
        workflow_id=workflow_id,
        plan_version=plan_version,
        status=status,
        guard_state=guard_state,
    )


def make_tasks(
    statuses: list[str] = None,
) -> list[WorkflowTask]:
    """Create WorkflowTasks with given statuses."""
    if statuses is None:
        statuses = ["pending", "in_progress", "completed"]
    tasks = []
    for i, status in enumerate(statuses, start=1):
        tasks.append(
            WorkflowTask(
                task_id=f"task-{i}",
                parent_id=None,
                dependencies=[],
                role="research",
                description=f"Task {i}",
                expected_artifact=None,
                exit_criteria=["done"],
                status=status,
            )
        )
    return tasks


# ---------------------------------------------------------------------------
# Preflight tests
# ---------------------------------------------------------------------------


def test_preflight_passes_clean():
    """Frozen plan, no run, no violations."""
    plan = make_plan()
    violations, logs = preflight_check(plan, None)

    assert violations == []
    assert len(logs) == 1
    assert logs[0].decision == GuardDecision.ALLOW


def test_preflight_blocks_missing_plan():
    """Pass None for plan, get plan_missing error."""
    violations, logs = preflight_check(None, None)

    assert len(violations) == 1
    assert violations[0].check_name == "plan_missing"
    assert violations[0].severity == "error"
    assert violations[0].repairable is False

    assert len(logs) == 1
    assert logs[0].decision == GuardDecision.BLOCK


def test_preflight_blocks_draft_plan():
    """Draft plan, get plan_not_frozen error."""
    plan = make_plan(status="draft")
    violations, logs = preflight_check(plan, None)

    assert len(violations) == 1
    assert violations[0].check_name == "plan_not_frozen"
    assert violations[0].severity == "error"
    assert violations[0].repairable is False


def test_preflight_blocks_invalid_plan():
    """Plan with no objective, get plan_invalid error."""
    plan = make_plan(objective="")
    violations, logs = preflight_check(plan, None)

    assert len(violations) == 1
    assert violations[0].check_name == "plan_invalid"
    assert violations[0].severity == "error"
    assert "objective" in violations[0].message.lower()


def test_preflight_blocks_run_mismatch():
    """Run with wrong workflow_id, get mismatch error."""
    plan = make_plan(workflow_id="wf-123")
    run = make_run(workflow_id="wf-999")
    violations, logs = preflight_check(plan, run)

    mismatch_violations = [v for v in violations if v.check_name == "run_plan_mismatch"]
    assert len(mismatch_violations) == 1
    assert mismatch_violations[0].severity == "error"


def test_preflight_warns_version_drift():
    """Run with wrong plan_version, get warning (repairable)."""
    plan = make_plan(schema_version="2.0")
    run = make_run(plan_version="1.0")
    violations, logs = preflight_check(plan, run)

    drift_violations = [v for v in violations if v.check_name == "version_drift"]
    assert len(drift_violations) == 1
    assert drift_violations[0].severity == "warning"
    assert drift_violations[0].repairable is True


def test_preflight_blocks_failed_run():
    """Run with status='failed', get error."""
    plan = make_plan()
    run = make_run(status="failed")
    violations, logs = preflight_check(plan, run)

    failed_violations = [v for v in violations if v.check_name == "run_failed"]
    assert len(failed_violations) == 1
    assert failed_violations[0].severity == "error"


def test_preflight_blocks_guard_blocked():
    """Run with guard_state='blocked', get error."""
    plan = make_plan()
    run = make_run(guard_state="blocked")
    violations, logs = preflight_check(plan, run)

    blocked_violations = [v for v in violations if v.check_name == "guard_blocked"]
    assert len(blocked_violations) == 1
    assert blocked_violations[0].severity == "error"


# ---------------------------------------------------------------------------
# Boundary check tests
# ---------------------------------------------------------------------------


def test_boundary_allows_write_clean(tmp_path: Path):
    """Run status=running, guard_state=clean, ALLOW."""
    plan = make_plan()
    run = make_run(status="running", guard_state="clean")
    violations, logs = boundary_check(plan, run, [], action="write")

    assert violations == []
    assert logs[-1].decision == GuardDecision.ALLOW


def test_boundary_blocks_write_dirty(tmp_path: Path):
    """Run guard_state=drift_detected, get warning."""
    plan = make_plan()
    run = make_run(status="running", guard_state="drift_detected")
    violations, logs = boundary_check(plan, run, [], action="write")

    dirty_violations = [v for v in violations if v.check_name == "guard_state_dirty"]
    assert len(dirty_violations) == 1
    assert dirty_violations[0].severity == "warning"
    assert dirty_violations[0].repairable is True


def test_boundary_blocks_complete_wrong_task():
    """Task not in_progress, get error."""
    plan = make_plan()
    run = make_run(status="running")
    tasks = make_tasks(statuses=["pending", "pending"])  # no in_progress
    violations, logs = boundary_check(plan, run, tasks, action="complete_task")

    assert len(violations) == 1
    assert violations[0].check_name == "task_not_in_progress"
    assert violations[0].severity == "error"


def test_boundary_blocks_phase_with_failed():
    """Failed task exists, get error."""
    plan = make_plan()
    run = make_run(status="running")
    tasks = make_tasks(statuses=["completed", "failed", "pending"])
    violations, logs = boundary_check(plan, run, tasks, action="phase_transition")

    failed_violations = [v for v in violations if v.check_name == "failed_tasks_exist"]
    assert len(failed_violations) == 1
    assert failed_violations[0].severity == "error"


def test_boundary_warns_fan_out_insufficient():
    """Only 1 pending task, get warning."""
    plan = make_plan()
    run = make_run(status="running")
    tasks = make_tasks(statuses=["pending"])  # only 1 pending
    violations, logs = boundary_check(plan, run, tasks, action="fan_out")

    insufficient_violations = [v for v in violations if v.check_name == "insufficient_pending"]
    assert len(insufficient_violations) == 1
    assert insufficient_violations[0].severity == "warning"


# ---------------------------------------------------------------------------
# Repair drift tests
# ---------------------------------------------------------------------------


def test_repair_drift_fixes_version(tmp_path: Path):
    """Mismatched version gets repaired."""
    plan = make_plan(schema_version="2.0")
    run = make_run(plan_version="1.0", guard_state="clean")
    base_dir = tmp_path / "workflow"
    base_dir.mkdir(parents=True)

    repaired_run, logs = repair_drift(plan, run, base_dir)

    assert repaired_run.plan_version == "2.0"
    assert repaired_run.guard_state == "clean"
    assert any(log.decision == GuardDecision.REPAIR for log in logs)


def test_repair_drift_fixes_guard_state(tmp_path: Path):
    """drift_detected gets cleaned."""
    plan = make_plan()
    run = make_run(guard_state="drift_detected")
    base_dir = tmp_path / "workflow"
    base_dir.mkdir(parents=True)

    repaired_run, logs = repair_drift(plan, run, base_dir)

    assert repaired_run.guard_state == "clean"
    assert any(log.decision == GuardDecision.REPAIR for log in logs)


def test_repair_drift_blocks_blocked_state(tmp_path: Path):
    """guard_state=blocked stays unchanged."""
    plan = make_plan()
    run = make_run(guard_state="blocked")
    base_dir = tmp_path / "workflow"
    base_dir.mkdir(parents=True)

    repaired_run, logs = repair_drift(plan, run, base_dir)

    assert repaired_run.guard_state == "blocked"
    assert any(log.decision == GuardDecision.BLOCK for log in logs)


def test_repair_drift_blocks_repairing_state(tmp_path: Path):
    """guard_state=repairing stays unchanged."""
    plan = make_plan()
    run = make_run(guard_state="repairing")
    base_dir = tmp_path / "workflow"
    base_dir.mkdir(parents=True)

    repaired_run, logs = repair_drift(plan, run, base_dir)

    assert repaired_run.guard_state == "repairing"
    assert any(log.decision == GuardDecision.BLOCK for log in logs)


# ---------------------------------------------------------------------------
# Convenience function tests
# ---------------------------------------------------------------------------


def test_check_before_write_allows(tmp_path: Path):
    """Clean state, returns ALLOW."""
    plan = make_plan()
    run = make_run(status="running", guard_state="clean")
    base_dir = tmp_path / "workflow"
    base_dir.mkdir(parents=True)

    decision = check_before_write(plan, run, base_dir)

    assert decision == GuardDecision.ALLOW


def test_check_before_write_repairs(tmp_path: Path):
    """drift_detected, repairs and returns REPAIR."""
    plan = make_plan()
    run = make_run(status="running", guard_state="drift_detected")
    base_dir = tmp_path / "workflow"
    base_dir.mkdir(parents=True)

    decision = check_before_write(plan, run, base_dir)

    assert decision == GuardDecision.REPAIR
    assert run.guard_state == "clean"


def test_check_before_complete_allows(tmp_path: Path):
    """Task in_progress, returns ALLOW."""
    plan = make_plan()
    run = make_run(status="running")
    tasks = make_tasks(statuses=["in_progress"])
    base_dir = tmp_path / "workflow"
    base_dir.mkdir(parents=True)

    decision = check_before_complete(plan, run, "task-1", tasks)

    assert decision == GuardDecision.ALLOW


def test_check_before_complete_blocks(tmp_path: Path):
    """Task not in_progress, returns BLOCK."""
    plan = make_plan()
    run = make_run(status="running")
    tasks = make_tasks(statuses=["pending"])
    base_dir = tmp_path / "workflow"
    base_dir.mkdir(parents=True)

    decision = check_before_complete(plan, run, "task-1", tasks)

    assert decision == GuardDecision.BLOCK
