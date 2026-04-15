"""Persistence layer for Hermes Optimizer workflow system."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from hermesoptimizer.workflow.schema import (
    WorkflowBlocker,
    WorkflowCheckpoint,
    WorkflowPlan,
    WorkflowRun,
    WorkflowTask,
)


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


def save_plan(plan_dir: Path, plan: WorkflowPlan) -> None:
    """Write WorkflowPlan to plan_dir/plan.yaml."""
    path = plan_dir / "plan.yaml"
    data = _plan_to_dict(plan)
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")


def _plan_to_dict(plan: WorkflowPlan) -> dict[str, Any]:
    """Convert WorkflowPlan to dict for serialization."""
    return {
        "workflow_id": plan.workflow_id,
        "schema_version": plan.schema_version,
        "objective": plan.objective,
        "scope": plan.scope,
        "non_goals": plan.non_goals,
        "acceptance_criteria": plan.acceptance_criteria,
        "test_plan": plan.test_plan,
        "risks": plan.risks,
        "execution_hints": plan.execution_hints,
        "next_action": plan.next_action,
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
        "status": plan.status,
        "tasks": [_task_to_dict(t) for t in plan.tasks],
    }


def _task_to_dict(task: WorkflowTask) -> dict[str, Any]:
    """Convert WorkflowTask to dict for serialization."""
    return {
        "task_id": task.task_id,
        "parent_id": task.parent_id,
        "dependencies": task.dependencies,
        "role": task.role,
        "description": task.description,
        "expected_artifact": task.expected_artifact,
        "exit_criteria": task.exit_criteria,
        "retry_policy": task.retry_policy,
        "budget_hints": task.budget_hints,
        "status": task.status,
        "assigned_to": task.assigned_to,
        "artifact_path": task.artifact_path,
    }


def load_plan(plan_dir: Path) -> WorkflowPlan:
    """Read WorkflowPlan from plan_dir/plan.yaml."""
    path = plan_dir / "plan.yaml"
    if not path.exists():
        raise FileNotFoundError(f"plan.yaml not found in {plan_dir}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _dict_to_plan(data)


def _dict_to_plan(data: dict[str, Any]) -> WorkflowPlan:
    """Convert dict to WorkflowPlan."""
    tasks = [_dict_to_task(t) for t in data.get("tasks", [])]
    return WorkflowPlan(
        workflow_id=data["workflow_id"],
        schema_version=data.get("schema_version", "1.0"),
        objective=data.get("objective", ""),
        scope=data.get("scope", []),
        non_goals=data.get("non_goals", []),
        acceptance_criteria=data.get("acceptance_criteria", []),
        test_plan=data.get("test_plan", ""),
        risks=data.get("risks", []),
        execution_hints=data.get("execution_hints", {}),
        next_action=data.get("next_action", ""),
        created_at=data.get("created_at", ""),
        updated_at=data.get("updated_at", ""),
        status=data.get("status", "draft"),
        tasks=tasks,
    )


def _dict_to_task(data: dict[str, Any]) -> WorkflowTask:
    """Convert dict to WorkflowTask."""
    return WorkflowTask(
        task_id=data["task_id"],
        parent_id=data.get("parent_id"),
        dependencies=data.get("dependencies", []),
        role=data["role"],
        description=data["description"],
        expected_artifact=data.get("expected_artifact"),
        exit_criteria=data.get("exit_criteria", []),
        retry_policy=data.get("retry_policy", {"max_retries": 0}),
        budget_hints=data.get("budget_hints", {}),
        status=data.get("status", "pending"),
        assigned_to=data.get("assigned_to"),
        artifact_path=data.get("artifact_path"),
    )


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


def save_run(plan_dir: Path, run: WorkflowRun) -> None:
    """Write WorkflowRun to plan_dir/run.yaml."""
    path = plan_dir / "run.yaml"
    data = _run_to_dict(run)
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")


def _run_to_dict(run: WorkflowRun) -> dict[str, Any]:
    """Convert WorkflowRun to dict for serialization."""
    return {
        "run_id": run.run_id,
        "workflow_id": run.workflow_id,
        "plan_version": run.plan_version,
        "status": run.status,
        "active_tasks": run.active_tasks,
        "owner": run.owner,
        "guard_state": run.guard_state,
        "last_checkpoint_id": run.last_checkpoint_id,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }


def load_run(plan_dir: Path) -> WorkflowRun:
    """Read WorkflowRun from plan_dir/run.yaml."""
    path = plan_dir / "run.yaml"
    if not path.exists():
        raise FileNotFoundError(f"run.yaml not found in {plan_dir}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _dict_to_run(data)


def _dict_to_run(data: dict[str, Any]) -> WorkflowRun:
    """Convert dict to WorkflowRun."""
    return WorkflowRun(
        run_id=data["run_id"],
        workflow_id=data["workflow_id"],
        plan_version=data["plan_version"],
        status=data.get("status", "initialized"),
        active_tasks=data.get("active_tasks", []),
        owner=data.get("owner", "devdo"),
        guard_state=data.get("guard_state", "clean"),
        last_checkpoint_id=data.get("last_checkpoint_id"),
        created_at=data.get("created_at", ""),
        updated_at=data.get("updated_at", ""),
    )


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


def save_task(plan_dir: Path, task: WorkflowTask) -> None:
    """Write WorkflowTask to plan_dir/tasks/{task_id}.yaml."""
    tasks_dir = plan_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    path = tasks_dir / f"{task.task_id}.yaml"
    path.write_text(yaml.dump(_task_to_dict(task), default_flow_style=False, sort_keys=False), encoding="utf-8")


def load_task(plan_dir: Path, task_id: str) -> WorkflowTask:
    """Read WorkflowTask from plan_dir/tasks/{task_id}.yaml."""
    path = plan_dir / "tasks" / f"{task_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"tasks/{task_id}.yaml not found in {plan_dir}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _dict_to_task(data)


def load_all_tasks(plan_dir: Path) -> list[WorkflowTask]:
    """Read all WorkflowTask files from plan_dir/tasks/."""
    tasks_dir = plan_dir / "tasks"
    if not tasks_dir.exists():
        return []
    tasks: list[WorkflowTask] = []
    for path in sorted(tasks_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        tasks.append(_dict_to_task(data))
    return tasks


# ---------------------------------------------------------------------------
# Checkpoints
# ---------------------------------------------------------------------------


def append_checkpoint(plan_dir: Path, checkpoint: WorkflowCheckpoint) -> None:
    """Append WorkflowCheckpoint to plan_dir/checkpoints/history.yaml."""
    checkpoints_dir = plan_dir / "checkpoints"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    history_path = checkpoints_dir / "history.yaml"

    # Read existing checkpoints
    existing: list[dict[str, Any]] = []
    if history_path.exists():
        existing = yaml.safe_load(history_path.read_text(encoding="utf-8")) or []

    # Append new checkpoint
    existing.append(_checkpoint_to_dict(checkpoint))

    # Write back
    history_path.write_text(yaml.dump(existing, default_flow_style=False, sort_keys=False), encoding="utf-8")


def _checkpoint_to_dict(checkpoint: WorkflowCheckpoint) -> dict[str, Any]:
    """Convert WorkflowCheckpoint to dict for serialization."""
    return {
        "checkpoint_id": checkpoint.checkpoint_id,
        "run_id": checkpoint.run_id,
        "milestone": checkpoint.milestone,
        "task_ids": checkpoint.task_ids,
        "message": checkpoint.message,
        "created_at": checkpoint.created_at,
    }


def load_checkpoints(plan_dir: Path) -> list[WorkflowCheckpoint]:
    """Read all checkpoints from plan_dir/checkpoints/history.yaml."""
    history_path = plan_dir / "checkpoints" / "history.yaml"
    if not history_path.exists():
        return []
    data = yaml.safe_load(history_path.read_text(encoding="utf-8")) or []
    return [_dict_to_checkpoint(c) for c in data]


def _dict_to_checkpoint(data: dict[str, Any]) -> WorkflowCheckpoint:
    """Convert dict to WorkflowCheckpoint."""
    return WorkflowCheckpoint(
        checkpoint_id=data["checkpoint_id"],
        run_id=data["run_id"],
        milestone=data["milestone"],
        task_ids=data.get("task_ids", []),
        message=data["message"],
        created_at=data["created_at"],
    )


# ---------------------------------------------------------------------------
# Blockers
# ---------------------------------------------------------------------------


def save_blocker(plan_dir: Path, blocker: WorkflowBlocker) -> None:
    """Write WorkflowBlocker to plan_dir/blockers/{blocker_id}.yaml."""
    blockers_dir = plan_dir / "blockers"
    blockers_dir.mkdir(parents=True, exist_ok=True)
    path = blockers_dir / f"{blocker.blocker_id}.yaml"
    path.write_text(yaml.dump(_blocker_to_dict(blocker), default_flow_style=False, sort_keys=False), encoding="utf-8")


def _blocker_to_dict(blocker: WorkflowBlocker) -> dict[str, Any]:
    """Convert WorkflowBlocker to dict for serialization."""
    return {
        "blocker_id": blocker.blocker_id,
        "task_id": blocker.task_id,
        "reason": blocker.reason,
        "evidence": blocker.evidence,
        "replan_needed": blocker.replan_needed,
        "created_at": blocker.created_at,
    }


def load_blockers(plan_dir: Path) -> list[WorkflowBlocker]:
    """Read all WorkflowBlocker files from plan_dir/blockers/."""
    blockers_dir = plan_dir / "blockers"
    if not blockers_dir.exists():
        return []
    blockers: list[WorkflowBlocker] = []
    for path in sorted(blockers_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        blockers.append(_dict_to_blocker(data))
    return blockers


def _dict_to_blocker(data: dict[str, Any]) -> WorkflowBlocker:
    """Convert dict to WorkflowBlocker."""
    return WorkflowBlocker(
        blocker_id=data["blocker_id"],
        task_id=data.get("task_id"),
        reason=data["reason"],
        evidence=data["evidence"],
        replan_needed=data.get("replan_needed", False),
        created_at=data["created_at"],
    )


# ---------------------------------------------------------------------------
# Directory management
# ---------------------------------------------------------------------------


def init_workflow_dir(base_dir: Path, workflow_id: str) -> Path:
    """Create .hermes/workflows/{workflow_id}/ with subdirs.

    Creates the following structure:
        {base_dir}/.hermes/workflows/{workflow_id}/
        {base_dir}/.hermes/workflows/{workflow_id}/tasks/
        {base_dir}/.hermes/workflows/{workflow_id}/checkpoints/
        {base_dir}/.hermes/workflows/{workflow_id}/blockers/

    Returns the path to the workflow directory.
    """
    workflow_dir = base_dir / ".hermes" / "workflows" / workflow_id
    workflow_dir.mkdir(parents=True, exist_ok=True)
    (workflow_dir / "tasks").mkdir(exist_ok=True)
    (workflow_dir / "checkpoints").mkdir(exist_ok=True)
    (workflow_dir / "blockers").mkdir(exist_ok=True)
    return workflow_dir


def list_workflows(base_dir: Path) -> list[str]:
    """List all workflow_ids in base_dir/.hermes/workflows/."""
    workflows_dir = base_dir / ".hermes" / "workflows"
    if not workflows_dir.exists():
        return []
    return sorted([d.name for d in workflows_dir.iterdir() if d.is_dir()])


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_plan(plan: WorkflowPlan) -> list[str]:
    """Return list of validation errors (empty = valid).

    Validation rules:
    - must have objective (non-empty)
    - must have at least one task
    - must have next_action (non-empty)
    - all task dependencies must reference existing task_ids
    """
    errors: list[str] = []

    # Must have objective
    if not plan.objective:
        errors.append("plan must have a non-empty objective")

    # Must have at least one task
    if not plan.tasks:
        errors.append("plan must have at least one task")

    # Must have next_action
    if not plan.next_action:
        errors.append("plan must have a non-empty next_action")

    # All task dependencies must reference existing task_ids
    task_ids = {t.task_id for t in plan.tasks}
    for task in plan.tasks:
        for dep_id in task.dependencies:
            if dep_id not in task_ids:
                errors.append(f"task '{task.task_id}' has dependency on unknown task_id '{dep_id}'")

    return errors
