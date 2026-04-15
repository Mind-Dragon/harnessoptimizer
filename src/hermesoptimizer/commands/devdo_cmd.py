"""Devdo command module - execution half of the workflow system."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from hermesoptimizer.workflow.schema import WorkflowBlocker, WorkflowCheckpoint, WorkflowPlan, WorkflowRun, WorkflowTask
from hermesoptimizer.workflow.store import (
    append_checkpoint,
    init_workflow_dir,
    load_all_tasks,
    load_plan,
    load_run,
    save_blocker,
    save_run,
    save_task,
)


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def start_run(
    workflow_id: str,
    base_dir: Path | None = None,
) -> WorkflowRun:
    """Start a run for a frozen workflow plan."""
    if base_dir is None:
        base_dir = Path(".hermes")

    plan_dir = base_dir / ".hermes" / "workflows" / workflow_id
    plan = load_plan(plan_dir)

    # Verify plan is frozen
    if plan.status != "frozen":
        raise ValueError(f"Plan must be frozen to start a run, but status is '{plan.status}'")

    run_id = str(uuid.uuid4())
    now = _now_iso()

    run = WorkflowRun(
        run_id=run_id,
        workflow_id=workflow_id,
        plan_version=plan.schema_version,
        status="initialized",
        active_tasks=[],
        owner="devdo",
        guard_state="clean",
        last_checkpoint_id=None,
        created_at=now,
        updated_at=now,
    )

    save_run(plan_dir, run)
    return run


def load_run_state(
    workflow_id: str,
    base_dir: Path | None = None,
) -> tuple[WorkflowPlan, WorkflowRun, list[WorkflowTask]]:
    """Load plan, run, and all tasks for a workflow."""
    if base_dir is None:
        base_dir = Path(".hermes")

    plan_dir = base_dir / ".hermes" / "workflows" / workflow_id
    plan = load_plan(plan_dir)
    run = load_run(plan_dir)
    tasks = load_all_tasks(plan_dir)

    return plan, run, tasks


def update_task_status(
    workflow_id: str,
    task_id: str,
    status: str,
    artifact_path: str | None = None,
    assigned_to: str | None = None,
    base_dir: Path | None = None,
) -> WorkflowTask:
    """Update a task's status."""
    if base_dir is None:
        base_dir = Path(".hermes")

    plan_dir = base_dir / ".hermes" / "workflows" / workflow_id

    # Load, update, and save the task
    from hermesoptimizer.workflow.store import load_task

    task = load_task(plan_dir, task_id)
    task.status = status
    if artifact_path is not None:
        task.artifact_path = artifact_path
    if assigned_to is not None:
        task.assigned_to = assigned_to

    save_task(plan_dir, task)
    return task


def record_checkpoint(
    workflow_id: str,
    milestone: str,
    task_ids: list[str] | None = None,
    message: str = "",
    base_dir: Path | None = None,
) -> WorkflowCheckpoint:
    """Record a checkpoint for a run."""
    if base_dir is None:
        base_dir = Path(".hermes")

    plan_dir = base_dir / ".hermes" / "workflows" / workflow_id
    run = load_run(plan_dir)

    checkpoint_id = str(uuid.uuid4())
    now = _now_iso()

    checkpoint = WorkflowCheckpoint(
        checkpoint_id=checkpoint_id,
        run_id=run.run_id,
        milestone=milestone,
        task_ids=task_ids if task_ids is not None else [],
        message=message,
        created_at=now,
    )

    append_checkpoint(plan_dir, checkpoint)

    # Update run's last_checkpoint_id
    run.last_checkpoint_id = checkpoint_id
    run.updated_at = now
    save_run(plan_dir, run)

    return checkpoint


def record_blocker(
    workflow_id: str,
    reason: str,
    task_id: str | None = None,
    evidence: str = "",
    replan_needed: bool = False,
    base_dir: Path | None = None,
) -> WorkflowBlocker:
    """Record a blocker for a workflow."""
    if base_dir is None:
        base_dir = Path(".hermes")

    plan_dir = base_dir / ".hermes" / "workflows" / workflow_id

    blocker_id = str(uuid.uuid4())
    now = _now_iso()

    blocker = WorkflowBlocker(
        blocker_id=blocker_id,
        task_id=task_id,
        reason=reason,
        evidence=evidence,
        replan_needed=replan_needed,
        created_at=now,
    )

    save_blocker(plan_dir, blocker)
    return blocker


def resolve_run(
    workflow_id: str,
    status: str,
    base_dir: Path | None = None,
) -> WorkflowRun:
    """Resolve a run with the given status (completed or failed)."""
    if base_dir is None:
        base_dir = Path(".hermes")

    plan_dir = base_dir / ".hermes" / "workflows" / workflow_id
    run = load_run(plan_dir)

    run.status = status
    run.updated_at = _now_iso()

    save_run(plan_dir, run)
    return run
