"""Tests for workflow commands (todo and devdo)."""
from __future__ import annotations

from pathlib import Path

import pytest

from hermesoptimizer.commands import COMMAND_ALIASES
from hermesoptimizer.commands.devdo_cmd import (
    load_run_state,
    record_blocker,
    record_checkpoint,
    resolve_run,
    start_run,
    update_task_status,
)
from hermesoptimizer.commands.todo_cmd import (
    add_task,
    create_plan,
    freeze_plan,
    list_plans,
    update_plan,
)


class TestCreatePlan:
    def test_create_plan(self, tmp_path: Path):
        """Create a plan, verify it's saved and has status 'draft'."""
        plan = create_plan(objective="Test objective", base_dir=tmp_path)
        assert plan.workflow_id is not None
        assert plan.status == "draft"
        assert plan.objective == "Test objective"

        # Verify the plan is saved and can be loaded
        plan_dir = tmp_path / ".hermes" / "workflows" / plan.workflow_id
        assert (plan_dir / "plan.yaml").exists()

    def test_create_plan_with_scope(self, tmp_path: Path):
        """Verify scope and non_goals are saved."""
        plan = create_plan(
            objective="Test with scope",
            scope=["feature A", "feature B"],
            non_goals=["scope creep"],
            base_dir=tmp_path,
        )
        assert plan.scope == ["feature A", "feature B"]
        assert plan.non_goals == ["scope creep"]


class TestUpdatePlan:
    def test_update_plan(self, tmp_path: Path):
        """Create then update, verify fields changed."""
        plan = create_plan(objective="Original objective", base_dir=tmp_path)

        updated = update_plan(
            plan.workflow_id,
            objective="Updated objective",
            next_action="Start working",
            base_dir=tmp_path,
        )

        assert updated.objective == "Updated objective"
        assert updated.next_action == "Start working"
        assert updated.workflow_id == plan.workflow_id


class TestFreezePlan:
    def test_freeze_plan_valid(self, tmp_path: Path):
        """Create with all required fields, freeze, verify status."""
        # Create a plan with all required fields
        plan = create_plan(
            objective="Valid plan to freeze",
            next_action="Start",
            base_dir=tmp_path,
        )
        task = add_task(
            plan.workflow_id,
            description="Test task",
            role="implement",
            base_dir=tmp_path,
        )

        frozen = freeze_plan(plan.workflow_id, base_dir=tmp_path)
        assert frozen.status == "frozen"

    def test_freeze_plan_invalid(self, tmp_path: Path):
        """Freeze a plan with no objective, raises ValueError."""
        # Create a minimal plan that fails validation
        plan = create_plan(objective="", next_action="Start", base_dir=tmp_path)
        add_task(plan.workflow_id, description="Task", role="implement", base_dir=tmp_path)

        with pytest.raises(ValueError) as exc_info:
            freeze_plan(plan.workflow_id, base_dir=tmp_path)
        assert "objective" in str(exc_info.value)


class TestAddTask:
    def test_add_task(self, tmp_path: Path):
        """Add a task to a plan, verify it appears in tasks."""
        plan = create_plan(objective="Test plan", base_dir=tmp_path)
        task = add_task(
            plan.workflow_id,
            description="Implement feature X",
            role="implement",
            base_dir=tmp_path,
        )

        assert task.task_id is not None
        assert task.description == "Implement feature X"
        assert task.role == "implement"
        assert task.status == "pending"

        # Verify task appears in plan
        reloaded_plan = list_plans(base_dir=tmp_path)[0]
        assert len(reloaded_plan.tasks) == 1
        assert reloaded_plan.tasks[0].description == "Implement feature X"

    def test_add_task_with_deps(self, tmp_path: Path):
        """Add a task with dependencies."""
        plan = create_plan(objective="Test plan", base_dir=tmp_path)
        task1 = add_task(plan.workflow_id, description="Task 1", role="research", base_dir=tmp_path)
        task2 = add_task(
            plan.workflow_id,
            description="Task 2",
            role="implement",
            dependencies=[task1.task_id],
            base_dir=tmp_path,
        )

        assert task2.dependencies == [task1.task_id]


class TestListPlans:
    def test_list_plans(self, tmp_path: Path):
        """Create 2 plans, list, get 2."""
        create_plan(objective="Plan 1", base_dir=tmp_path)
        create_plan(objective="Plan 2", base_dir=tmp_path)

        plans = list_plans(base_dir=tmp_path)
        assert len(plans) == 2


class TestStartRun:
    def test_start_run(self, tmp_path: Path):
        """Create and freeze a plan, start a run, verify status 'initialized'."""
        plan = create_plan(
            objective="Frozen plan",
            next_action="Start",
            base_dir=tmp_path,
        )
        add_task(plan.workflow_id, description="Task", role="implement", base_dir=tmp_path)
        freeze_plan(plan.workflow_id, base_dir=tmp_path)

        run = start_run(plan.workflow_id, base_dir=tmp_path)
        assert run.status == "initialized"
        assert run.workflow_id == plan.workflow_id

    def test_start_run_not_frozen(self, tmp_path: Path):
        """Try to start a run on a draft plan, raises ValueError."""
        plan = create_plan(objective="Draft plan", next_action="Start", base_dir=tmp_path)
        add_task(plan.workflow_id, description="Task", role="implement", base_dir=tmp_path)

        with pytest.raises(ValueError) as exc_info:
            start_run(plan.workflow_id, base_dir=tmp_path)
        assert "frozen" in str(exc_info.value)


class TestLoadRunState:
    def test_load_run_state(self, tmp_path: Path):
        """Start a run, load state, verify all three components."""
        plan = create_plan(
            objective="State test plan",
            next_action="Begin",
            base_dir=tmp_path,
        )
        add_task(plan.workflow_id, description="Task 1", role="implement", base_dir=tmp_path)
        freeze_plan(plan.workflow_id, base_dir=tmp_path)
        start_run(plan.workflow_id, base_dir=tmp_path)

        loaded_plan, loaded_run, loaded_tasks = load_run_state(plan.workflow_id, base_dir=tmp_path)

        assert loaded_plan.objective == "State test plan"
        assert loaded_run.status == "initialized"
        assert len(loaded_tasks) == 1


class TestUpdateTaskStatus:
    def test_update_task_status(self, tmp_path: Path):
        """Add task, update status, verify."""
        plan = create_plan(objective="Update status test", base_dir=tmp_path)
        task = add_task(plan.workflow_id, description="Task", role="implement", base_dir=tmp_path)

        updated = update_task_status(
            plan.workflow_id,
            task.task_id,
            status="in_progress",
            assigned_to="agent-1",
            base_dir=tmp_path,
        )

        assert updated.status == "in_progress"
        assert updated.assigned_to == "agent-1"


class TestRecordCheckpoint:
    def test_record_checkpoint(self, tmp_path: Path):
        """Start run, record checkpoint, verify it loads."""
        plan = create_plan(
            objective="Checkpoint test",
            next_action="Go",
            base_dir=tmp_path,
        )
        add_task(plan.workflow_id, description="Task", role="implement", base_dir=tmp_path)
        freeze_plan(plan.workflow_id, base_dir=tmp_path)
        start_run(plan.workflow_id, base_dir=tmp_path)

        checkpoint = record_checkpoint(
            plan.workflow_id,
            milestone="task_completed",
            task_ids=["test-task-id"],
            message="Task finished successfully",
            base_dir=tmp_path,
        )

        assert checkpoint.milestone == "task_completed"
        assert checkpoint.message == "Task finished successfully"


class TestRecordBlocker:
    def test_record_blocker(self, tmp_path: Path):
        """Record a blocker, verify it loads."""
        plan = create_plan(objective="Blocker test", next_action="Start", base_dir=tmp_path)
        add_task(plan.workflow_id, description="Task", role="implement", base_dir=tmp_path)
        freeze_plan(plan.workflow_id, base_dir=tmp_path)
        start_run(plan.workflow_id, base_dir=tmp_path)

        blocker = record_blocker(
            plan.workflow_id,
            reason="Missing dependency",
            task_id="some-task-id",
            evidence="Package X not found",
            replan_needed=True,
            base_dir=tmp_path,
        )

        assert blocker.reason == "Missing dependency"
        assert blocker.replan_needed is True


class TestResolveRun:
    def test_resolve_run(self, tmp_path: Path):
        """Start run, resolve as completed, verify."""
        plan = create_plan(
            objective="Resolve test",
            next_action="Finish",
            base_dir=tmp_path,
        )
        add_task(plan.workflow_id, description="Task", role="implement", base_dir=tmp_path)
        freeze_plan(plan.workflow_id, base_dir=tmp_path)
        start_run(plan.workflow_id, base_dir=tmp_path)

        resolved = resolve_run(plan.workflow_id, status="completed", base_dir=tmp_path)
        assert resolved.status == "completed"


class TestCliAlias:
    def test_cli_alias_dodev(self):
        """Verify the COMMAND_ALIASES constant maps dodev to devdo."""
        assert COMMAND_ALIASES == {"dodev": "devdo"}


class TestCliMain:
    def test_cli_main_no_args(self):
        """Call main() with no args, get return code 1."""
        from hermesoptimizer.__main__ import main

        # Simulate no args by calling with empty list behavior
        import sys
        original_argv = sys.argv
        sys.argv = ["hermesoptimizer"]
        try:
            result = main()
        finally:
            sys.argv = original_argv
        assert result == 1

    def test_cli_main_todo_create(self, tmp_path: Path):
        """Call main(['todo', 'Test', 'objective']), get return code 0."""
        from hermesoptimizer.__main__ import main

        import sys
        original_argv = sys.argv
        sys.argv = ["hermesoptimizer", "todo", "Test", "objective"]

        # Patch base_dir to use tmp_path
        import hermesoptimizer.commands.todo_cmd as todo_cmd
        original_create_plan = todo_cmd.create_plan

        def patched_create_plan(objective, **kwargs):
            kwargs["base_dir"] = tmp_path
            return original_create_plan(objective, **kwargs)

        todo_cmd.create_plan = patched_create_plan

        try:
            result = main()
        finally:
            sys.argv = original_argv
            todo_cmd.create_plan = original_create_plan

        assert result == 0
