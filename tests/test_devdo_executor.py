"""Tests for the executor module."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hermesoptimizer.workflow.executor import (
    ExecutionState,
    ProgressEvent,
    ReviewResult,
    apply_review,
    compute_progress_summary,
    create_review,
    get_dispatchable_tasks,
    init_execution,
    mark_blocked,
    mark_completed,
    mark_dispatched,
    resume_from_state,
    should_two_stage_review,
)
from hermesoptimizer.workflow.schema import WorkflowPlan, WorkflowRun, WorkflowTask


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


def _make_plan(workflow_id: str = "wf-1") -> WorkflowPlan:
    """Helper to create a WorkflowPlan with sensible defaults."""
    return WorkflowPlan(
        workflow_id=workflow_id,
        schema_version="1.0",
        objective="Test workflow",
        scope=[],
        non_goals=[],
        acceptance_criteria=[],
        test_plan="",
        risks=[],
        execution_hints={},
        next_action="Start",
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        status="frozen",
        tasks=[],
    )


def _make_run(workflow_id: str = "wf-1") -> WorkflowRun:
    """Helper to create a WorkflowRun with sensible defaults."""
    return WorkflowRun(
        run_id="run-1",
        workflow_id=workflow_id,
        plan_version="1.0",
        status="running",
        active_tasks=[],
        owner="devdo",
        guard_state="clean",
        last_checkpoint_id=None,
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
    )


class TestInitExecution:
    def test_init_execution_identifies_completed(self) -> None:
        """2 completed tasks, 3 pending → completed_ids has 2."""
        tasks = [
            _make_task("A", status="completed"),
            _make_task("B", status="completed"),
            _make_task("C", status="pending"),
            _make_task("D", status="pending"),
            _make_task("E", status="pending"),
        ]
        plan = _make_plan()
        run = _make_run()

        state = init_execution(plan, run, tasks)
        assert len(state.completed_ids) == 2
        assert "A" in state.completed_ids
        assert "B" in state.completed_ids

    def test_init_execution_identifies_blocked(self) -> None:
        """1 blocked task → blocked_ids has 1."""
        tasks = [
            _make_task("A", status="blocked"),
            _make_task("B", status="pending"),
        ]
        plan = _make_plan()
        run = _make_run()

        state = init_execution(plan, run, tasks)
        assert len(state.blocked_ids) == 1
        assert "A" in state.blocked_ids

    def test_init_execution_empty_progress(self) -> None:
        """progress_log starts empty."""
        tasks = [_make_task("A")]
        plan = _make_plan()
        run = _make_run()

        state = init_execution(plan, run, tasks)
        assert state.progress_log == []
        assert state.review_results == []


class TestGetDispatchableTasks:
    def test_get_dispatchable_no_deps(self) -> None:
        """3 pending tasks, no deps → all 3 returned."""
        tasks = [
            _make_task("A"),
            _make_task("B"),
            _make_task("C"),
        ]
        plan = _make_plan()
        run = _make_run()
        state = init_execution(plan, run, tasks)

        dispatchable = get_dispatchable_tasks(state)
        assert len(dispatchable) == 3

    def test_get_dispatchable_with_deps(self) -> None:
        """A completed, B depends on A, C depends on B → only B dispatched."""
        tasks = [
            _make_task("A", status="completed"),
            _make_task("B", dependencies=["A"]),
            _make_task("C", dependencies=["B"]),
        ]
        plan = _make_plan()
        run = _make_run()
        state = init_execution(plan, run, tasks)

        dispatchable = get_dispatchable_tasks(state)
        assert len(dispatchable) == 1
        assert dispatchable[0].task_id == "B"

    def test_get_dispatchable_blocked_excluded(self) -> None:
        """Blocked task not returned."""
        tasks = [
            _make_task("A", status="blocked"),
            _make_task("B"),
        ]
        plan = _make_plan()
        run = _make_run()
        state = init_execution(plan, run, tasks)

        dispatchable = get_dispatchable_tasks(state)
        assert len(dispatchable) == 1
        assert dispatchable[0].task_id == "B"
        assert "A" not in [t.task_id for t in dispatchable]

    def test_get_dispatchable_sorted_by_role(self) -> None:
        """Tasks in random role order, result sorted by priority."""
        tasks = [
            _make_task("A", role="guardrail"),
            _make_task("B", role="research"),
            _make_task("C", role="implement"),
            _make_task("D", role="test"),
        ]
        plan = _make_plan()
        run = _make_run()
        state = init_execution(plan, run, tasks)

        dispatchable = get_dispatchable_tasks(state)
        assert len(dispatchable) == 4
        # implement > research > test > review > verify > integrate > guardrail
        assert dispatchable[0].role == "implement"
        assert dispatchable[1].role == "research"
        assert dispatchable[2].role == "test"
        assert dispatchable[3].role == "guardrail"


class TestMarkDispatched:
    def test_mark_dispatched_updates_status(self) -> None:
        """3 pending → mark dispatched → all in_progress."""
        tasks = [
            _make_task("A"),
            _make_task("B"),
            _make_task("C"),
        ]
        plan = _make_plan()
        run = _make_run()
        state = init_execution(plan, run, tasks)

        new_state = mark_dispatched(state, ["A", "B", "C"])

        for task_id in ["A", "B", "C"]:
            task = next(t for t in new_state.tasks if t.task_id == task_id)
            assert task.status == "in_progress"

    def test_mark_dispatched_creates_events(self) -> None:
        """3 tasks → 3 dispatched events in log."""
        tasks = [
            _make_task("A"),
            _make_task("B"),
            _make_task("C"),
        ]
        plan = _make_plan()
        run = _make_run()
        state = init_execution(plan, run, tasks)

        new_state = mark_dispatched(state, ["A", "B", "C"])

        dispatched_events = [e for e in new_state.progress_log if e.event_type == "dispatched"]
        assert len(dispatched_events) == 3


class TestMarkCompleted:
    def test_mark_completed_updates_state(self) -> None:
        """Task moved to completed, in completed_ids."""
        tasks = [_make_task("A")]
        plan = _make_plan()
        run = _make_run()
        state = init_execution(plan, run, tasks)

        new_state = mark_completed(state, "A")

        task = next(t for t in new_state.tasks if t.task_id == "A")
        assert task.status == "completed"
        assert "A" in new_state.completed_ids

    def test_mark_completed_sets_artifact(self) -> None:
        """artifact_path is recorded."""
        tasks = [_make_task("A")]
        plan = _make_plan()
        run = _make_run()
        state = init_execution(plan, run, tasks)

        new_state = mark_completed(state, "A", artifact_path="/path/to/artifact")

        task = next(t for t in new_state.tasks if t.task_id == "A")
        assert task.artifact_path == "/path/to/artifact"

    def test_mark_completed_creates_event(self) -> None:
        """Completed event in log."""
        tasks = [_make_task("A")]
        plan = _make_plan()
        run = _make_run()
        state = init_execution(plan, run, tasks)

        new_state = mark_completed(state, "A", artifact_path="/path")

        completed_events = [e for e in new_state.progress_log if e.event_type == "completed"]
        assert len(completed_events) == 1
        assert completed_events[0].task_id == "A"


class TestMarkBlocked:
    def test_mark_blocked_updates_state(self) -> None:
        """Task moved to blocked, in blocked_ids."""
        tasks = [_make_task("A")]
        plan = _make_plan()
        run = _make_run()
        state = init_execution(plan, run, tasks)

        new_state = mark_blocked(state, "A", "test reason")

        task = next(t for t in new_state.tasks if t.task_id == "A")
        assert task.status == "blocked"
        assert "A" in new_state.blocked_ids

    def test_mark_blocked_creates_event(self) -> None:
        """Blocked event in log."""
        tasks = [_make_task("A")]
        plan = _make_plan()
        run = _make_run()
        state = init_execution(plan, run, tasks)

        new_state = mark_blocked(state, "A", "test reason")

        blocked_events = [e for e in new_state.progress_log if e.event_type == "blocked"]
        assert len(blocked_events) == 1
        assert blocked_events[0].task_id == "A"
        assert "test reason" in blocked_events[0].message


class TestShouldTwoStageReview:
    def test_should_two_stage_review_implement(self) -> None:
        """True for implement."""
        task = _make_task("A", role="implement")
        assert should_two_stage_review(task) is True

    def test_should_two_stage_review_research(self) -> None:
        """False for research."""
        task = _make_task("A", role="research")
        assert should_two_stage_review(task) is False

    def test_should_two_stage_review_test(self) -> None:
        """False for test."""
        task = _make_task("A", role="test")
        assert should_two_stage_review(task) is False

    def test_should_two_stage_review_integrate(self) -> None:
        """True for integrate."""
        task = _make_task("A", role="integrate")
        assert should_two_stage_review(task) is True

    def test_should_two_stage_review_guardrail(self) -> None:
        """True for guardrail."""
        task = _make_task("A", role="guardrail")
        assert should_two_stage_review(task) is True


class TestCreateReview:
    def test_create_review_fields(self) -> None:
        """Verify all fields set correctly."""
        review = create_review(
            task_id="A",
            spec_compliant=True,
            code_quality_pass=False,
            issues=["Issue 1", "Issue 2"],
            reviewer="quality_reviewer",
        )
        assert review.task_id == "A"
        assert review.spec_compliant is True
        assert review.code_quality_pass is False
        assert review.issues == ["Issue 1", "Issue 2"]
        assert review.reviewer == "quality_reviewer"


class TestApplyReview:
    def test_apply_review_spec_pass(self) -> None:
        """Spec compliant, no blocking."""
        tasks = [_make_task("A")]
        plan = _make_plan()
        run = _make_run()
        state = init_execution(plan, run, tasks)

        review = create_review(
            task_id="A",
            spec_compliant=True,
            code_quality_pass=True,
            issues=[],
            reviewer="spec_reviewer",
        )
        new_state = apply_review(state, review)

        assert len(new_state.review_results) == 1
        # Task should NOT be blocked
        task = next(t for t in new_state.tasks if t.task_id == "A")
        assert task.status == "pending"

    def test_apply_review_spec_fail(self) -> None:
        """Spec not compliant, task gets blocked."""
        tasks = [_make_task("A")]
        plan = _make_plan()
        run = _make_run()
        state = init_execution(plan, run, tasks)

        review = create_review(
            task_id="A",
            spec_compliant=False,
            code_quality_pass=True,
            issues=["Missing spec"],
            reviewer="spec_reviewer",
        )
        new_state = apply_review(state, review)

        assert len(new_state.review_results) == 1
        # Task should be blocked
        task = next(t for t in new_state.tasks if t.task_id == "A")
        assert task.status == "blocked"
        assert "A" in new_state.blocked_ids

    def test_apply_review_quality_fail(self) -> None:
        """Quality fails, event logged but not blocked."""
        tasks = [_make_task("A")]
        plan = _make_plan()
        run = _make_run()
        state = init_execution(plan, run, tasks)

        review = create_review(
            task_id="A",
            spec_compliant=True,
            code_quality_pass=False,
            issues=["Style issues"],
            reviewer="quality_reviewer",
        )
        new_state = apply_review(state, review)

        assert len(new_state.review_results) == 1
        # Task should NOT be blocked (spec passed)
        task = next(t for t in new_state.tasks if t.task_id == "A")
        assert task.status == "pending"
        # But there should be a "reviewed" event noting quality issues
        reviewed_events = [e for e in new_state.progress_log if e.event_type == "reviewed"]
        assert len(reviewed_events) == 1


class TestComputeProgressSummary:
    def test_compute_progress_summary_all_pending(self) -> None:
        """5 pending, 0 others."""
        tasks = [
            _make_task("A"),
            _make_task("B"),
            _make_task("C"),
            _make_task("D"),
            _make_task("E"),
        ]
        plan = _make_plan()
        run = _make_run()
        state = init_execution(plan, run, tasks)

        summary = compute_progress_summary(state)
        assert summary["total"] == 5
        assert summary["completed"] == 0
        assert summary["blocked"] == 0
        assert summary["in_progress"] == 0
        assert summary["pending"] == 5

    def test_compute_progress_summary_mixed(self) -> None:
        """2 completed, 1 blocked, 1 in_progress, 1 pending."""
        tasks = [
            _make_task("A", status="completed"),
            _make_task("B", status="completed"),
            _make_task("C", status="blocked"),
            _make_task("D", status="in_progress"),
            _make_task("E", status="pending"),
        ]
        plan = _make_plan()
        run = _make_run()
        state = init_execution(plan, run, tasks)

        summary = compute_progress_summary(state)
        assert summary["total"] == 5
        assert summary["completed"] == 2
        assert summary["blocked"] == 1
        assert summary["in_progress"] == 1
        assert summary["pending"] == 1


class TestResumeFromState:
    def test_resume_from_state_adds_event(self) -> None:
        """Resume event in progress_log."""
        tasks = [_make_task("A")]
        plan = _make_plan()
        run = _make_run()
        tasks[0].status = "in_progress"

        state = resume_from_state(plan, run, tasks)

        assert len(state.progress_log) == 1
        assert state.progress_log[0].event_type == "started"
        assert state.progress_log[0].message == "Resuming execution"

    def test_resume_from_state_preserves_completed(self) -> None:
        """completed_ids preserved from tasks."""
        tasks = [
            _make_task("A", status="completed"),
            _make_task("B", status="pending"),
        ]
        plan = _make_plan()
        run = _make_run()

        state = resume_from_state(plan, run, tasks)

        assert "A" in state.completed_ids
        assert len(state.completed_ids) == 1
