"""Todo command module - planning half of the workflow system."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hermesoptimizer.workflow.schema import WorkflowPlan, WorkflowTask
from hermesoptimizer.workflow.store import (
    init_workflow_dir,
    list_workflows,
    load_plan,
    save_plan,
    save_task,
)


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def create_plan(
    objective: str,
    scope: list[str] | None = None,
    non_goals: list[str] | None = None,
    acceptance_criteria: list[str] | None = None,
    test_plan: str = "",
    risks: list[str] | None = None,
    next_action: str = "",
    base_dir: Path | None = None,
) -> WorkflowPlan:
    """Create a new workflow plan with status 'draft'."""
    if base_dir is None:
        base_dir = Path(".")

    workflow_id = str(uuid.uuid4())
    now = _now_iso()

    plan = WorkflowPlan(
        workflow_id=workflow_id,
        schema_version="1.0",
        objective=objective,
        scope=scope if scope is not None else [],
        non_goals=non_goals if non_goals is not None else [],
        acceptance_criteria=acceptance_criteria if acceptance_criteria is not None else [],
        test_plan=test_plan,
        risks=risks if risks is not None else [],
        next_action=next_action,
        created_at=now,
        updated_at=now,
        status="draft",
        tasks=[],
    )

    # Initialize the workflow directory structure
    plan_dir = init_workflow_dir(base_dir, workflow_id)

    # Save the plan
    save_plan(plan_dir, plan)

    return plan


def update_plan(
    workflow_id: str,
    objective: str | None = None,
    scope: list[str] | None = None,
    non_goals: list[str] | None = None,
    acceptance_criteria: list[str] | None = None,
    test_plan: str | None = None,
    risks: list[str] | None = None,
    next_action: str | None = None,
    tasks: list[WorkflowTask] | None = None,
    base_dir: Path | None = None,
) -> WorkflowPlan:
    """Update an existing workflow plan."""
    if base_dir is None:
        base_dir = Path(".")

    plan_dir = base_dir / ".hermes" / "workflows" / workflow_id
    plan = load_plan(plan_dir)

    # Update only non-None fields
    if objective is not None:
        plan.objective = objective
    if scope is not None:
        plan.scope = scope
    if non_goals is not None:
        plan.non_goals = non_goals
    if acceptance_criteria is not None:
        plan.acceptance_criteria = acceptance_criteria
    if test_plan is not None:
        plan.test_plan = test_plan
    if risks is not None:
        plan.risks = risks
    if next_action is not None:
        plan.next_action = next_action
    if tasks is not None:
        plan.tasks = tasks

    plan.updated_at = _now_iso()

    save_plan(plan_dir, plan)
    return plan


def freeze_plan(
    workflow_id: str,
    base_dir: Path | None = None,
) -> WorkflowPlan:
    """Freeze a workflow plan after validation."""
    if base_dir is None:
        base_dir = Path(".")

    plan_dir = base_dir / ".hermes" / "workflows" / workflow_id
    plan = load_plan(plan_dir)

    # Validate the plan
    from hermesoptimizer.workflow.store import validate_plan

    errors = validate_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))

    plan.status = "frozen"
    plan.updated_at = _now_iso()

    save_plan(plan_dir, plan)
    return plan


def add_task(
    workflow_id: str,
    description: str,
    role: str = "implement",
    dependencies: list[str] | None = None,
    parent_id: str | None = None,
    exit_criteria: list[str] | None = None,
    expected_artifact: str | None = None,
    base_dir: Path | None = None,
) -> WorkflowTask:
    """Add a task to a workflow plan."""
    if base_dir is None:
        base_dir = Path(".")

    plan_dir = base_dir / ".hermes" / "workflows" / workflow_id
    plan = load_plan(plan_dir)

    task_id = str(uuid.uuid4())

    task = WorkflowTask(
        task_id=task_id,
        parent_id=parent_id,
        dependencies=dependencies if dependencies is not None else [],
        role=role,
        description=description,
        expected_artifact=expected_artifact,
        exit_criteria=exit_criteria if exit_criteria is not None else [],
        status="pending",
        assigned_to=None,
        artifact_path=None,
    )

    plan.tasks.append(task)
    plan.updated_at = _now_iso()

    # Save task and plan
    save_task(plan_dir, task)
    save_plan(plan_dir, plan)

    return task


def list_plans(
    base_dir: Path | None = None,
) -> list[WorkflowPlan]:
    """List all workflow plans."""
    if base_dir is None:
        base_dir = Path(".")

    workflow_ids = list_workflows(base_dir)
    plans: list[WorkflowPlan] = []

    for wf_id in workflow_ids:
        plan_dir = base_dir / ".hermes" / "workflows" / wf_id
        try:
            plan = load_plan(plan_dir)
            plans.append(plan)
        except FileNotFoundError:
            # Skip plans without plan.yaml
            continue

    return plans
