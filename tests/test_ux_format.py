"""Tests for the UX format module."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hermesoptimizer.workflow.schema import (
    WorkflowPlan,
    WorkflowRun,
    WorkflowTask,
)
from hermesoptimizer.workflow.scheduler import (
    ExecutionBatch,
    ScheduledPlan,
)
from hermesoptimizer.workflow.ux_format import (
    render_alias_flow_example,
    render_blocked_flow_example,
    render_devdo_startup,
    render_normal_flow_example,
    render_resume_flow_example,
    render_todo_handoff,
)


def _make_task(
    task_id: str,
    role: str = "implement",
    dependencies: list[str] | None = None,
    status: str = "pending",
    description: str = "Test task",
) -> WorkflowTask:
    """Helper to create a WorkflowTask with sensible defaults."""
    return WorkflowTask(
        task_id=task_id,
        parent_id=None,
        dependencies=dependencies or [],
        role=role,
        description=description,
        expected_artifact=None,
        exit_criteria=[],
        status=status,
    )


def _make_plan(
    workflow_id: str = "plan-001",
    objective: str = "Build user authentication",
    status: str = "draft",
    scope: list[str] | None = None,
    non_goals: list[str] | None = None,
    acceptance_criteria: list[str] | None = None,
    test_plan: str = "Run unit and integration tests",
    risks: list[str] | None = None,
    next_action: str = "Run /devdo plan-001",
    tasks: list[WorkflowTask] | None = None,
) -> WorkflowPlan:
    """Helper to create a WorkflowPlan with sensible defaults."""
    return WorkflowPlan(
        workflow_id=workflow_id,
        objective=objective,
        status=status,
        scope=["User login", "User logout", "Password reset"] if scope is None else scope,
        non_goals=["OAuth integration"] if non_goals is None else non_goals,
        acceptance_criteria=["Users can log in", "Sessions persist"] if acceptance_criteria is None else acceptance_criteria,
        test_plan=test_plan,
        risks=["Third-party auth provider downtime"] if risks is None else risks,
        next_action=next_action,
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        tasks=tasks if tasks is not None else [],
    )


def _make_run(
    run_id: str = "run-001",
    workflow_id: str = "plan-001",
    status: str = "initialized",
    guard_state: str = "clean",
) -> WorkflowRun:
    """Helper to create a WorkflowRun with sensible defaults."""
    return WorkflowRun(
        run_id=run_id,
        workflow_id=workflow_id,
        plan_version="1.0",
        status=status,
        guard_state=guard_state,
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
    )


def _make_scheduled_plan(tasks: list[WorkflowTask]) -> ScheduledPlan:
    """Helper to create a ScheduledPlan from tasks."""
    batch = ExecutionBatch(
        batch_id="depth-0-implement",
        task_ids=[t.task_id for t in tasks],
        roles=[t.role for t in tasks],
        max_parallel=4,
        description="Depth 0, role implement",
    )
    return ScheduledPlan(
        batches=[batch],
        total_tasks=len(tasks),
        max_parallelism=4,
        estimated_phases=1,
    )


class TestRenderTodoHandoff:
    def test_render_todo_handoff_complete(self) -> None:
        """Render a full plan, verify all sections present."""
        tasks = [
            _make_task("task-1", role="implement", description="Implement login"),
            _make_task("task-2", role="test", dependencies=["task-1"], description="Test login"),
        ]
        plan = _make_plan(tasks=tasks)

        output = render_todo_handoff(plan)

        # Verify all sections are present
        assert plan.workflow_id in output
        assert plan.objective in output
        assert plan.status in output
        assert "SCOPE" in output
        assert "NON-GOALS" in output
        assert "ACCEPTANCE CRITERIA" in output
        assert "TEST PLAN" in output
        assert "RISKS" in output
        assert "TASKS" in output
        assert "NEXT ACTION FOR /devdo" in output

    def test_render_todo_handoff_empty_fields(self) -> None:
        """Plan with empty scope/risks shows fallback text."""
        plan = _make_plan(
            scope=[],
            non_goals=[],
            risks=[],
            test_plan="",
        )

        output = render_todo_handoff(plan)

        assert "None defined" in output
        assert "None identified" in output
        assert "Not yet defined" in output

    def test_render_todo_handoff_tasks(self) -> None:
        """Verify tasks are listed with status and role."""
        tasks = [
            _make_task("task-1", role="research", status="completed", description="Research auth"),
            _make_task("task-2", role="implement", status="pending", description="Implement auth"),
        ]
        plan = _make_plan(tasks=tasks)

        output = render_todo_handoff(plan)

        # Check task info appears
        assert "Research auth" in output
        assert "Implement auth" in output
        assert "research" in output
        assert "implement" in output
        assert "completed" in output
        assert "pending" in output
        # Tasks are numbered
        assert "1." in output
        assert "2." in output

    def test_render_todo_handoff_next_action(self) -> None:
        """Verify next action section present."""
        plan = _make_plan(next_action="Run /devdo plan-001")

        output = render_todo_handoff(plan)

        assert "NEXT ACTION FOR /devdo" in output
        assert "Run /devdo plan-001" in output


class TestRenderDevdoStartup:
    def test_render_devdo_startup_with_schedule(self) -> None:
        """Render with scheduled plan, verify all sections."""
        tasks = [
            _make_task("task-1", description="Implement login"),
            _make_task("task-2", description="Test login"),
        ]
        plan = _make_plan(tasks=tasks)
        run = _make_run()
        scheduled = _make_scheduled_plan(tasks)

        output = render_devdo_startup(plan, run, scheduled)

        assert "DEVDO — Execution Starting" in output
        assert plan.objective in output
        assert run.run_id in output
        assert run.status in output
        assert run.guard_state in output
        assert "EXECUTION STRATEGY" in output
        assert "Total tasks:" in output
        assert "Max parallel:" in output
        assert "Phases:" in output
        assert "Batches:" in output
        assert "FIRST DISPATCH WAVE" in output
        assert "CHECKPOINT POLICY" in output

    def test_render_devdo_startup_without_schedule(self) -> None:
        """Render without schedule, shows 'not computed'."""
        plan = _make_plan()
        run = _make_run()

        output = render_devdo_startup(plan, run, scheduled=None)

        assert "No schedule computed yet" in output

    def test_render_devdo_startup_with_progress(self) -> None:
        """Verify progress section appears when progress is provided."""
        plan = _make_plan()
        run = _make_run()
        progress = {
            "total": 10,
            "completed": 3,
            "in_progress": 2,
            "blocked": 1,
            "pending": 4,
        }

        output = render_devdo_startup(plan, run, progress=progress)

        assert "PROGRESS" in output
        assert "Total:" in output
        assert "Done:" in output
        assert "In flight:" in output
        assert "Blocked:" in output
        assert "Pending:" in output
        assert "10" in output
        assert "3" in output
        assert "2" in output
        assert "1" in output
        assert "4" in output

    def test_render_devdo_startup_first_wave(self) -> None:
        """Verify first dispatch wave shows task descriptions."""
        tasks = [
            _make_task("task-1", description="Implement login form"),
            _make_task("task-2", description="Implement session handling"),
        ]
        plan = _make_plan(tasks=tasks)
        run = _make_run()
        scheduled = _make_scheduled_plan(tasks)

        output = render_devdo_startup(plan, run, scheduled)

        assert "FIRST DISPATCH WAVE" in output
        assert "Implement login form" in output
        assert "Implement session handling" in output


class TestRenderFlowExamples:
    def test_render_normal_flow_not_empty(self) -> None:
        """Example is non-empty string."""
        output = render_normal_flow_example()
        assert output
        assert len(output) > 0

    def test_render_blocked_flow_not_empty(self) -> None:
        """Example is non-empty string."""
        output = render_blocked_flow_example()
        assert output
        assert len(output) > 0

    def test_render_resume_flow_not_empty(self) -> None:
        """Example is non-empty string."""
        output = render_resume_flow_example()
        assert output
        assert len(output) > 0

    def test_render_alias_flow_not_empty(self) -> None:
        """Example is non-empty string."""
        output = render_alias_flow_example()
        assert output
        assert len(output) > 0

    def test_render_alias_flow_mentions_both(self) -> None:
        """Mentions both /devdo and /dodev."""
        output = render_alias_flow_example()
        assert "/devdo" in output
        assert "/dodev" in output
