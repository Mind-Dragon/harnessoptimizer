"""Tests for workflow schema."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from hermesoptimizer.workflow.schema import (
    WorkflowBlocker,
    WorkflowCheckpoint,
    WorkflowPlan,
    WorkflowRun,
    WorkflowTask,
)
from hermesoptimizer.workflow.store import validate_plan


def test_workflow_plan_creation() -> None:
    """Create a plan with all fields, verify defaults."""
    workflow_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    task = WorkflowTask(
        task_id="task-1",
        parent_id=None,
        dependencies=[],
        role="research",
        description="Research something",
        expected_artifact="research.md",
        exit_criteria=["criteria1"],
    )

    plan = WorkflowPlan(
        workflow_id=workflow_id,
        schema_version="1.0",
        objective="Test objective",
        scope=["scope1"],
        non_goals=["non-goal1"],
        acceptance_criteria=["criteria1"],
        test_plan="Test plan",
        risks=["risk1"],
        execution_hints={"hint": "value"},
        next_action="first action",
        created_at=now,
        updated_at=now,
        status="frozen",
        tasks=[task],
    )

    assert plan.workflow_id == workflow_id
    assert plan.schema_version == "1.0"
    assert plan.objective == "Test objective"
    assert plan.status == "frozen"
    assert len(plan.tasks) == 1
    assert plan.tasks[0].task_id == "task-1"


def test_workflow_task_defaults() -> None:
    """Verify retry_policy and budget_hints defaults."""
    task = WorkflowTask(
        task_id="task-1",
        parent_id=None,
        dependencies=[],
        role="implement",
        description="Implement something",
        expected_artifact=None,
        exit_criteria=[],
    )

    assert task.retry_policy == {"max_retries": 0}
    assert task.budget_hints == {}
    assert task.status == "pending"
    assert task.assigned_to is None
    assert task.artifact_path is None


def test_workflow_run_creation() -> None:
    """Verify run status defaults to 'initialized'."""
    run = WorkflowRun(
        run_id=str(uuid.uuid4()),
        workflow_id=str(uuid.uuid4()),
        plan_version="1.0",
    )

    assert run.status == "initialized"
    assert run.active_tasks == []
    assert run.owner == "devdo"
    assert run.guard_state == "clean"
    assert run.last_checkpoint_id is None


def test_workflow_checkpoint_creation() -> None:
    """Verify all fields."""
    now = datetime.now(timezone.utc).isoformat()
    checkpoint = WorkflowCheckpoint(
        checkpoint_id="cp-1",
        run_id="run-1",
        milestone="task_completed",
        task_ids=["task-1", "task-2"],
        message="All tasks completed",
        created_at=now,
    )

    assert checkpoint.checkpoint_id == "cp-1"
    assert checkpoint.run_id == "run-1"
    assert checkpoint.milestone == "task_completed"
    assert checkpoint.task_ids == ["task-1", "task-2"]
    assert checkpoint.message == "All tasks completed"
    assert checkpoint.created_at == now


def test_workflow_blocker_creation() -> None:
    """Verify all fields."""
    now = datetime.now(timezone.utc).isoformat()
    blocker = WorkflowBlocker(
        blocker_id="blk-1",
        task_id="task-1",
        reason="Missing dependency",
        evidence="File not found",
        replan_needed=True,
        created_at=now,
    )

    assert blocker.blocker_id == "blk-1"
    assert blocker.task_id == "task-1"
    assert blocker.reason == "Missing dependency"
    assert blocker.evidence == "File not found"
    assert blocker.replan_needed is True
    assert blocker.created_at == now


def test_plan_validation_valid() -> None:
    """Valid plan returns empty errors."""
    task = WorkflowTask(
        task_id="task-1",
        parent_id=None,
        dependencies=[],
        role="research",
        description="Research something",
        expected_artifact=None,
        exit_criteria=[],
    )
    plan = WorkflowPlan(
        workflow_id="wf-1",
        objective="Test objective",
        next_action="Do something",
        tasks=[task],
    )

    errors = validate_plan(plan)
    assert errors == []


def test_plan_validation_missing_objective() -> None:
    """Returns error about objective."""
    task = WorkflowTask(
        task_id="task-1",
        parent_id=None,
        dependencies=[],
        role="research",
        description="Research something",
        expected_artifact=None,
        exit_criteria=[],
    )
    plan = WorkflowPlan(
        workflow_id="wf-1",
        objective="",
        next_action="Do something",
        tasks=[task],
    )

    errors = validate_plan(plan)
    assert any("objective" in e for e in errors)


def test_plan_validation_no_tasks() -> None:
    """Returns error about tasks."""
    plan = WorkflowPlan(
        workflow_id="wf-1",
        objective="Test objective",
        next_action="Do something",
        tasks=[],
    )

    errors = validate_plan(plan)
    assert any("task" in e.lower() for e in errors)


def test_plan_validation_missing_next_action() -> None:
    """Returns error about next_action."""
    task = WorkflowTask(
        task_id="task-1",
        parent_id=None,
        dependencies=[],
        role="research",
        description="Research something",
        expected_artifact=None,
        exit_criteria=[],
    )
    plan = WorkflowPlan(
        workflow_id="wf-1",
        objective="Test objective",
        next_action="",
        tasks=[task],
    )

    errors = validate_plan(plan)
    assert any("next_action" in e for e in errors)


def test_plan_validation_dangling_dependency() -> None:
    """Returns error about missing task_id."""
    task = WorkflowTask(
        task_id="task-1",
        parent_id=None,
        dependencies=["task-99"],  # does not exist
        role="research",
        description="Research something",
        expected_artifact=None,
        exit_criteria=[],
    )
    plan = WorkflowPlan(
        workflow_id="wf-1",
        objective="Test objective",
        next_action="Do something",
        tasks=[task],
    )

    errors = validate_plan(plan)
    assert any("task-99" in e for e in errors)
