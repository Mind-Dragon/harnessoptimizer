"""Tests for workflow store."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hermesoptimizer.workflow.schema import (
    WorkflowBlocker,
    WorkflowCheckpoint,
    WorkflowPlan,
    WorkflowRun,
    WorkflowTask,
)
from hermesoptimizer.workflow.store import (
    append_checkpoint,
    init_workflow_dir,
    list_workflows,
    load_all_tasks,
    load_blockers,
    load_checkpoints,
    load_plan,
    load_run,
    load_task,
    save_blocker,
    save_plan,
    save_run,
    save_task,
    validate_plan,
)


def test_init_workflow_dir_creates_structure(tmp_path: Path) -> None:
    """Verify directory layout."""
    workflow_id = "wf-123"
    workflow_dir = init_workflow_dir(tmp_path, workflow_id)

    expected = (
        tmp_path
        / ".hermes"
        / "workflows"
        / workflow_id
    )
    assert workflow_dir == expected
    assert (workflow_dir / "tasks").is_dir()
    assert (workflow_dir / "checkpoints").is_dir()
    assert (workflow_dir / "blockers").is_dir()


def test_save_load_plan_roundtrip(tmp_path: Path) -> None:
    """Save plan, load it, assert equality."""
    workflow_dir = init_workflow_dir(tmp_path, "wf-1")
    now = datetime.now(timezone.utc).isoformat()

    task = WorkflowTask(
        task_id="task-1",
        parent_id=None,
        dependencies=[],
        role="research",
        description="Research something",
        expected_artifact="research.md",
        exit_criteria=["criteria1"],
        retry_policy={"max_retries": 2},
        budget_hints={"tokens": 1000},
    )
    plan = WorkflowPlan(
        workflow_id="wf-1",
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

    save_plan(workflow_dir, plan)
    loaded = load_plan(workflow_dir)

    assert loaded.workflow_id == plan.workflow_id
    assert loaded.schema_version == plan.schema_version
    assert loaded.objective == plan.objective
    assert loaded.status == plan.status
    assert len(loaded.tasks) == 1
    assert loaded.tasks[0].task_id == "task-1"
    assert loaded.tasks[0].retry_policy == {"max_retries": 2}


def test_save_load_run_roundtrip(tmp_path: Path) -> None:
    """Save run, load it, assert equality."""
    workflow_dir = init_workflow_dir(tmp_path, "wf-1")
    now = datetime.now(timezone.utc).isoformat()

    run = WorkflowRun(
        run_id="run-1",
        workflow_id="wf-1",
        plan_version="1.0",
        status="running",
        active_tasks=["task-1", "task-2"],
        owner="devdo",
        guard_state="clean",
        last_checkpoint_id="cp-1",
        created_at=now,
        updated_at=now,
    )

    save_run(workflow_dir, run)
    loaded = load_run(workflow_dir)

    assert loaded.run_id == run.run_id
    assert loaded.workflow_id == run.workflow_id
    assert loaded.plan_version == run.plan_version
    assert loaded.status == run.status
    assert loaded.active_tasks == ["task-1", "task-2"]


def test_save_load_task_roundtrip(tmp_path: Path) -> None:
    """Save task, load it, assert equality."""
    workflow_dir = init_workflow_dir(tmp_path, "wf-1")

    task = WorkflowTask(
        task_id="task-1",
        parent_id=None,
        dependencies=["task-0"],
        role="implement",
        description="Implement something",
        expected_artifact="impl.py",
        exit_criteria=["works"],
        retry_policy={"max_retries": 3},
        budget_hints={"hours": 2},
        status="in_progress",
        assigned_to="agent-1",
        artifact_path="/tmp/impl.py",
    )

    save_task(workflow_dir, task)
    loaded = load_task(workflow_dir, "task-1")

    assert loaded.task_id == task.task_id
    assert loaded.dependencies == ["task-0"]
    assert loaded.retry_policy == {"max_retries": 3}
    assert loaded.assigned_to == "agent-1"


def test_load_all_tasks(tmp_path: Path) -> None:
    """Save 3 tasks, load all, get 3 back."""
    workflow_dir = init_workflow_dir(tmp_path, "wf-1")

    for i in range(3):
        task = WorkflowTask(
            task_id=f"task-{i}",
            parent_id=None,
            dependencies=[],
            role="research",
            description=f"Task {i}",
            expected_artifact=None,
            exit_criteria=[],
        )
        save_task(workflow_dir, task)

    loaded = load_all_tasks(workflow_dir)
    assert len(loaded) == 3
    assert {t.task_id for t in loaded} == {"task-0", "task-1", "task-2"}


def test_append_checkpoint_accumulates(tmp_path: Path) -> None:
    """Append 3 checkpoints, load, get 3 in order."""
    workflow_dir = init_workflow_dir(tmp_path, "wf-1")
    now = datetime.now(timezone.utc).isoformat()

    for i in range(3):
        checkpoint = WorkflowCheckpoint(
            checkpoint_id=f"cp-{i}",
            run_id="run-1",
            milestone="task_completed",
            task_ids=[f"task-{i}"],
            message=f"Checkpoint {i}",
            created_at=now,
        )
        append_checkpoint(workflow_dir, checkpoint)

    loaded = load_checkpoints(workflow_dir)
    assert len(loaded) == 3
    assert [c.checkpoint_id for c in loaded] == ["cp-0", "cp-1", "cp-2"]


def test_save_load_blocker(tmp_path: Path) -> None:
    """Save and load a blocker."""
    workflow_dir = init_workflow_dir(tmp_path, "wf-1")
    now = datetime.now(timezone.utc).isoformat()

    blocker = WorkflowBlocker(
        blocker_id="blk-1",
        task_id="task-1",
        reason="Missing dependency",
        evidence="file.txt not found",
        replan_needed=True,
        created_at=now,
    )

    save_blocker(workflow_dir, blocker)
    loaded = load_blockers(workflow_dir)

    assert len(loaded) == 1
    assert loaded[0].blocker_id == "blk-1"
    assert loaded[0].task_id == "task-1"
    assert loaded[0].reason == "Missing dependency"
    assert loaded[0].replan_needed is True


def test_load_plan_missing_raises(tmp_path: Path) -> None:
    """FileNotFoundError when no plan.yaml."""
    workflow_dir = init_workflow_dir(tmp_path, "wf-1")

    with pytest.raises(FileNotFoundError):
        load_plan(workflow_dir)


def test_validate_plan_via_store(tmp_path: Path) -> None:
    """Validate a plan with known error."""
    workflow_dir = init_workflow_dir(tmp_path, "wf-1")

    # Plan with no objective - should fail validation
    task = WorkflowTask(
        task_id="task-1",
        parent_id=None,
        dependencies=[],
        role="research",
        description="Research",
        expected_artifact=None,
        exit_criteria=[],
    )
    plan = WorkflowPlan(
        workflow_id="wf-1",
        objective="",  # empty - validation error
        next_action="Do it",
        tasks=[task],
    )

    errors = validate_plan(plan)
    assert len(errors) > 0
    assert any("objective" in e for e in errors)


def test_list_workflows(tmp_path: Path) -> None:
    """Init 2 workflows, list, get 2 IDs."""
    init_workflow_dir(tmp_path, "wf-a")
    init_workflow_dir(tmp_path, "wf-b")

    workflows = list_workflows(tmp_path)
    assert len(workflows) == 2
    assert set(workflows) == {"wf-a", "wf-b"}
