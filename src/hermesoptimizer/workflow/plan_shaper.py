"""Plan shaper module - adds intelligence to the /todo planning process.

This module validates, shapes, and improves plans before they are frozen.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from hermesoptimizer.workflow.schema import WorkflowPlan, WorkflowTask

# Known task roles
KNOWN_ROLES = {"research", "implement", "test", "review", "verify", "integrate", "guardrail"}


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class TaskQualityReport:
    """Quality report for a single task."""
    task_id: str
    is_delegatable: bool
    has_verification: bool
    has_artifact: bool
    issues: list[str]


@dataclass(slots=True)
class PlanQualityReport:
    """Quality report for a workflow plan."""
    plan_id: str
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    suggestions: list[str]
    missing_fields: list[str]
    task_quality: list[TaskQualityReport]


def check_task_quality(task: WorkflowTask) -> TaskQualityReport:
    """Check a single task for quality issues.

    Args:
        task: The task to check.

    Returns:
        TaskQualityReport with quality metrics and issues.
    """
    issues: list[str] = []
    description = task.description or ""

    # is_delegatable: description is non-empty and less than 500 chars
    is_delegatable = bool(description and len(description) <= 500)

    # has_verification: exit_criteria is non-empty
    has_verification = bool(task.exit_criteria)

    # has_artifact: expected_artifact is non-empty
    has_artifact = bool(task.expected_artifact)

    # Check issues
    if not description:
        issues.append("Task has no description")
    elif len(description) > 500:
        issues.append("Task description too long for delegation")

    if not task.exit_criteria:
        issues.append("No exit criteria defined")

    if not task.expected_artifact:
        issues.append("No expected artifact defined")

    if task.role and task.role not in KNOWN_ROLES:
        issues.append(f"Unknown role: {task.role}")

    return TaskQualityReport(
        task_id=task.task_id,
        is_delegatable=is_delegatable,
        has_verification=has_verification,
        has_artifact=has_artifact,
        issues=issues,
    )


def check_plan_quality(plan: WorkflowPlan) -> PlanQualityReport:
    """Run comprehensive quality checks on a plan.

    Args:
        plan: The workflow plan to check.

    Returns:
        PlanQualityReport with validation results.
    """
    errors: list[str] = []
    warnings: list[str] = []
    suggestions: list[str] = []
    missing_fields: list[str] = []

    # Check required fields
    if not plan.objective:
        errors.append("Plan has no objective")
        missing_fields.append("objective")

    if not plan.scope:
        warnings.append("Plan has no scope defined")

    if not plan.acceptance_criteria:
        warnings.append("Plan has no acceptance criteria")
        missing_fields.append("acceptance_criteria")

    if not plan.next_action:
        errors.append("Plan has no next_action")
        missing_fields.append("next_action")

    # Check plan has at least 1 task
    if not plan.tasks:
        errors.append("Plan has no tasks")

    # Check each task with check_task_quality
    task_quality_reports = [check_task_quality(task) for task in plan.tasks]

    # Check risks is populated
    if not plan.risks:
        warnings.append("Plan has no risks defined")

    # Check test_plan is non-empty
    if not plan.test_plan:
        warnings.append("Plan has no test_plan defined")

    # Suggest: if tasks > 10, suggest breaking into sub-plans
    if len(plan.tasks) > 10:
        suggestions.append("Consider breaking this plan into sub-plans (>10 tasks)")

    # Suggest: if any task has no exit_criteria, suggest adding them
    tasks_without_exit_criteria = [
        task.task_id for task in plan.tasks if not task.exit_criteria
    ]
    if tasks_without_exit_criteria:
        suggestions.append("Some tasks lack exit criteria: " + ", ".join(tasks_without_exit_criteria))

    # Suggest: if no task has role="test", suggest adding a test task
    task_roles = {task.role for task in plan.tasks if task.role}
    if "test" not in task_roles:
        suggestions.append("Consider adding a test task (role='test')")

    # Suggest: if no task has role="review", suggest adding a review task
    if "review" not in task_roles:
        suggestions.append("Consider adding a review task (role='review')")

    # Set is_valid = no errors
    is_valid = len(errors) == 0

    return PlanQualityReport(
        plan_id=plan.workflow_id,
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        suggestions=suggestions,
        missing_fields=missing_fields,
        task_quality=task_quality_reports,
    )


def shape_plan(
    objective: str,
    scope: list[str] | None = None,
    non_goals: list[str] | None = None,
    acceptance_criteria: list[str] | None = None,
    test_plan: str = "",
    risks: list[str] | None = None,
) -> WorkflowPlan:
    """Create a shaped plan with sensible defaults.

    Args:
        objective: The plan objective.
        scope: List of scope items (default: ["implementation"]).
        non_goals: List of non-goals (default: []).
        acceptance_criteria: List of acceptance criteria (default: ["All tests pass"]).
        test_plan: Test plan description (default: "").
        risks: List of risks (default: []).

    Returns:
        A new WorkflowPlan with defaults applied.
    """
    now = _now_iso()
    return WorkflowPlan(
        workflow_id=str(uuid.uuid4()),
        schema_version="1.0",
        objective=objective,
        scope=scope if scope is not None else ["implementation"],
        non_goals=non_goals if non_goals is not None else [],
        acceptance_criteria=acceptance_criteria if acceptance_criteria is not None else ["All tests pass"],
        test_plan=test_plan,
        risks=risks if risks is not None else [],
        next_action="Review plan, add tasks, then freeze",
        created_at=now,
        updated_at=now,
        status="draft",
        tasks=[],
    )


def generate_default_tasks(objective: str) -> list[WorkflowTask]:
    """Generate a sensible default task structure for an objective.

    Creates a chain of tasks: research -> implement -> test -> review -> verify

    Args:
        objective: The plan objective to create tasks for.

    Returns:
        List of 5 WorkflowTask objects in dependency order.
    """
    now = _now_iso()

    # Research task
    research_task = WorkflowTask(
        task_id=str(uuid.uuid4())[:8],
        parent_id=None,
        dependencies=[],
        role="research",
        description=f"Research requirements and gather context for: {objective}",
        expected_artifact="Requirements document",
        exit_criteria=["Task completed successfully"],
        retry_policy={"max_retries": 0},
        budget_hints={},
        status="pending",
    )

    # Implement task (depends on research)
    implement_task = WorkflowTask(
        task_id=str(uuid.uuid4())[:8],
        parent_id=None,
        dependencies=[research_task.task_id],
        role="implement",
        description=f"Implement: {objective}",
        expected_artifact="Implementation complete",
        exit_criteria=["Task completed successfully"],
        retry_policy={"max_retries": 0},
        budget_hints={},
        status="pending",
    )

    # Test task (depends on implement)
    test_task = WorkflowTask(
        task_id=str(uuid.uuid4())[:8],
        parent_id=None,
        dependencies=[implement_task.task_id],
        role="test",
        description=f"Write tests for: {objective}",
        expected_artifact="Test suite written",
        exit_criteria=["Task completed successfully"],
        retry_policy={"max_retries": 0},
        budget_hints={},
        status="pending",
    )

    # Review task (depends on test)
    review_task = WorkflowTask(
        task_id=str(uuid.uuid4())[:8],
        parent_id=None,
        dependencies=[test_task.task_id],
        role="review",
        description=f"Review implementation of: {objective}",
        expected_artifact="Code review complete",
        exit_criteria=["Task completed successfully"],
        retry_policy={"max_retries": 0},
        budget_hints={},
        status="pending",
    )

    # Verify task (depends on review)
    verify_task = WorkflowTask(
        task_id=str(uuid.uuid4())[:8],
        parent_id=None,
        dependencies=[review_task.task_id],
        role="verify",
        description=f"Verify and smoke-test: {objective}",
        expected_artifact="Verification complete",
        exit_criteria=["Task completed successfully"],
        retry_policy={"max_retries": 0},
        budget_hints={},
        status="pending",
    )

    return [research_task, implement_task, test_task, review_task, verify_task]


def handle_blocked_plan(plan: WorkflowPlan, missing_input: str) -> WorkflowPlan:
    """Mark a plan as blocked due to missing input.

    Args:
        plan: The workflow plan to block.
        missing_input: Description of the missing input causing the block.

    Returns:
        The updated plan with blocked status.
    """
    plan.status = "blocked"
    plan.next_action = f"BLOCKED: {missing_input}"
    plan.updated_at = _now_iso()
    return plan
