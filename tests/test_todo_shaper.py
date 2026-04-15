"""Tests for the plan shaper module."""
from __future__ import annotations

import uuid

import pytest

from hermesoptimizer.workflow.plan_shaper import (
    PlanQualityReport,
    TaskQualityReport,
    check_plan_quality,
    check_task_quality,
    generate_default_tasks,
    handle_blocked_plan,
    shape_plan,
)
from hermesoptimizer.workflow.schema import WorkflowPlan, WorkflowTask


def _make_task(
    task_id: str = "task-1",
    role: str = "implement",
    description: str = "Do something",
    exit_criteria: list[str] | None = None,
    expected_artifact: str | None = "artifact",
    dependencies: list[str] | None = None,
) -> WorkflowTask:
    """Helper to create a task with defaults."""
    return WorkflowTask(
        task_id=task_id,
        parent_id=None,
        dependencies=dependencies if dependencies is not None else [],
        role=role,
        description=description,
        expected_artifact=expected_artifact,
        exit_criteria=exit_criteria if exit_criteria is not None else ["Done"],
    )


def _make_plan(
    objective: str = "Test objective",
    scope: list[str] | None = None,
    acceptance_criteria: list[str] | None = None,
    next_action: str = "Do something",
    tasks: list[WorkflowTask] | None = None,
    risks: list[str] | None = None,
    test_plan: str = "",
) -> WorkflowPlan:
    """Helper to create a plan with defaults."""
    return WorkflowPlan(
        workflow_id=str(uuid.uuid4()),
        schema_version="1.0",
        objective=objective,
        scope=scope if scope is not None else ["scope1"],
        acceptance_criteria=acceptance_criteria if acceptance_criteria is not None else ["criteria1"],
        next_action=next_action,
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
        status="draft",
        tasks=tasks if tasks is not None else [],
        risks=risks if risks is not None else ["risk1"],
        test_plan=test_plan,
    )


# ============================================================================
# check_plan_quality tests
# ============================================================================

def test_check_plan_quality_valid() -> None:
    """Valid plan returns no errors."""
    task = _make_task()
    plan = _make_plan(tasks=[task])
    report = check_plan_quality(plan)
    assert report.is_valid
    assert report.errors == []
    assert report.plan_id == plan.workflow_id


def test_check_plan_quality_missing_objective() -> None:
    """Plan with empty objective has error."""
    plan = _make_plan(objective="")
    report = check_plan_quality(plan)
    assert not report.is_valid
    assert any("objective" in e.lower() for e in report.errors)
    assert "objective" in report.missing_fields


def test_check_plan_quality_no_tasks() -> None:
    """Plan with no tasks has error."""
    plan = _make_plan(tasks=None)
    report = check_plan_quality(plan)
    assert not report.is_valid
    assert any("task" in e.lower() for e in report.errors)


def test_check_plan_quality_no_scope_warning() -> None:
    """Empty scope is a warning."""
    plan = _make_plan(scope=[])
    report = check_plan_quality(plan)
    assert any("scope" in w.lower() for w in report.warnings)


def test_check_plan_quality_no_risks_warning() -> None:
    """Empty risks list is a warning."""
    plan = _make_plan(risks=[])
    report = check_plan_quality(plan)
    assert any("risk" in w.lower() for w in report.warnings)


def test_check_plan_quality_suggests_test_task() -> None:
    """Plan with no test tasks gets suggestion."""
    task = _make_task(role="implement")
    plan = _make_plan(tasks=[task])
    report = check_plan_quality(plan)
    assert any("test" in s.lower() for s in report.suggestions)


def test_check_plan_quality_suggests_review_task() -> None:
    """Plan with no review tasks gets suggestion."""
    task = _make_task(role="implement")
    plan = _make_plan(tasks=[task])
    report = check_plan_quality(plan)
    assert any("review" in s.lower() for s in report.suggestions)


def test_check_plan_quality_large_plan_suggestion() -> None:
    """Plan with 12 tasks gets 'break into sub-plans' suggestion."""
    tasks = [_make_task(task_id=f"task-{i}") for i in range(12)]
    plan = _make_plan(tasks=tasks)
    report = check_plan_quality(plan)
    assert any("sub-plan" in s.lower() for s in report.suggestions)


# ============================================================================
# check_task_quality tests
# ============================================================================

def test_check_task_quality_valid() -> None:
    """Well-formed task is delegatable."""
    task = _make_task(description="Short task description")
    report = check_task_quality(task)
    assert report.is_delegatable
    assert report.has_verification
    assert report.has_artifact
    assert report.issues == []


def test_check_task_quality_no_description() -> None:
    """Empty description → not delegatable."""
    task = _make_task(description="")
    report = check_task_quality(task)
    assert not report.is_delegatable
    assert "Task has no description" in report.issues


def test_check_task_quality_long_description() -> None:
    """Description > 500 chars → not delegatable."""
    task = _make_task(description="x" * 501)
    report = check_task_quality(task)
    assert not report.is_delegatable
    assert "Task description too long for delegation" in report.issues


def test_check_task_quality_no_exit_criteria() -> None:
    """Missing exit_criteria flagged."""
    task = _make_task(exit_criteria=[])
    report = check_task_quality(task)
    assert not report.has_verification
    assert "No exit criteria defined" in report.issues


def test_check_task_quality_no_artifact() -> None:
    """Missing expected_artifact flagged."""
    task = _make_task(expected_artifact=None)
    report = check_task_quality(task)
    assert not report.has_artifact
    assert "No expected artifact defined" in report.issues


def test_check_task_quality_unknown_role() -> None:
    """Unknown role flagged."""
    task = _make_task(role="unknown")
    report = check_task_quality(task)
    assert "Unknown role: unknown" in report.issues


# ============================================================================
# shape_plan tests
# ============================================================================

def test_shape_plan_defaults() -> None:
    """Creates plan with sensible defaults."""
    plan = shape_plan("My objective")
    assert plan.objective == "My objective"
    assert plan.scope == ["implementation"]
    assert plan.non_goals == []
    assert plan.acceptance_criteria == ["All tests pass"]
    assert plan.risks == []
    assert plan.status == "draft"
    assert plan.tasks == []
    assert plan.schema_version == "1.0"
    assert plan.workflow_id  # UUID generated


def test_shape_plan_custom() -> None:
    """Creates plan with custom fields."""
    plan = shape_plan(
        objective="Custom",
        scope=["feature"],
        non_goals=["legacy"],
        acceptance_criteria=["AC1"],
        test_plan="Integration tests",
        risks=["Breaking change"],
    )
    assert plan.objective == "Custom"
    assert plan.scope == ["feature"]
    assert plan.non_goals == ["legacy"]
    assert plan.acceptance_criteria == ["AC1"]
    assert plan.test_plan == "Integration tests"
    assert plan.risks == ["Breaking change"]


def test_shape_plan_has_next_action() -> None:
    """next_action is set."""
    plan = shape_plan("My objective")
    assert plan.next_action == "Review plan, add tasks, then freeze"


# ============================================================================
# generate_default_tasks tests
# ============================================================================

def test_generate_default_tasks_creates_five() -> None:
    """Returns 5 tasks."""
    tasks = generate_default_tasks("Do something")
    assert len(tasks) == 5


def test_generate_default_tasks_chain() -> None:
    """Task 2 depends on task 1, etc."""
    tasks = generate_default_tasks("Do something")
    # Task 0 (research) has no dependencies
    assert tasks[0].dependencies == []
    # Task 1 (implement) depends on task 0
    assert tasks[1].dependencies == [tasks[0].task_id]
    # Task 2 (test) depends on task 1
    assert tasks[2].dependencies == [tasks[1].task_id]
    # Task 3 (review) depends on task 2
    assert tasks[3].dependencies == [tasks[2].task_id]
    # Task 4 (verify) depends on task 3
    assert tasks[4].dependencies == [tasks[3].task_id]


def test_generate_default_tasks_roles() -> None:
    """Roles are research, implement, test, review, verify."""
    tasks = generate_default_tasks("Do something")
    roles = [t.role for t in tasks]
    assert roles == ["research", "implement", "test", "review", "verify"]


# ============================================================================
# handle_blocked_plan tests
# ============================================================================

def test_handle_blocked_plan_sets_blocked() -> None:
    """Status becomes 'blocked'."""
    plan = _make_plan()
    updated = handle_blocked_plan(plan, "Missing API key")
    assert updated.status == "blocked"


def test_handle_blocked_plan_updates_next_action() -> None:
    """next_action includes blocker reason."""
    plan = _make_plan()
    updated = handle_blocked_plan(plan, "Missing API key")
    assert "BLOCKED: Missing API key" in updated.next_action
