"""Comprehensive smoke tests for the full workflow cycle.

Exercises the complete /todo -> freeze -> /devdo -> checkpoint -> resume -> complete cycle.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from hermesoptimizer.commands.devdo_cmd import (
    load_run_state,
    record_blocker,
    record_checkpoint,
    resolve_run,
    start_run,
    update_task_status,
)
from hermesoptimizer.commands.todo_cmd import add_task, freeze_plan
from hermesoptimizer.workflow.executor import (
    apply_review,
    compute_progress_summary,
    create_review,
    get_dispatchable_tasks,
    init_execution,
    mark_blocked,
    mark_completed,
    mark_dispatched,
    resume_from_state,
)
from hermesoptimizer.workflow.plan_shaper import (
    check_plan_quality,
    generate_default_tasks,
    shape_plan,
)
from hermesoptimizer.workflow.scheduler import (
    build_task_graph,
    compute_batches,
    compute_dependency_depth,
    get_blocked_tasks,
)
from hermesoptimizer.workflow.store import (
    load_all_tasks,
    load_blockers,
    load_plan,
    save_plan,
    save_task,
)
from hermesoptimizer.workflow.ux_format import render_devdo_startup, render_todo_handoff
from hermesoptimizer.workflow.schema import WorkflowTask


# ---------------------------------------------------------------------------
# Test 1: Full todo -> devdo cycle
# ---------------------------------------------------------------------------

def test_full_todo_devdo_cycle(tmp_path: Path) -> None:
    """Test the complete end-to-end workflow: todo -> freeze -> devdo -> complete."""
    base_dir = tmp_path

    # 1. Create a plan using shape_plan
    plan = shape_plan(
        objective="Build user authentication system",
        scope=["implementation", "testing"],
        acceptance_criteria=["All tests pass", "No security vulnerabilities"],
    )

    # 2. Generate 5 default tasks
    tasks = generate_default_tasks("Build user authentication system")
    plan.tasks = tasks

    # Save plan and tasks to disk
    plan_dir = base_dir / ".hermes" / "workflows" / plan.workflow_id
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "tasks").mkdir(exist_ok=True)
    save_plan(plan_dir, plan)
    for task in tasks:
        save_task(plan_dir, task)

    # 4. Freeze the plan
    frozen = freeze_plan(plan.workflow_id, base_dir=base_dir)
    assert frozen.status == "frozen"

    # 5. Start run
    run = start_run(plan.workflow_id, base_dir=base_dir)
    assert run.status == "initialized"

    # 6. Load run state
    loaded_plan, loaded_run, loaded_tasks = load_run_state(plan.workflow_id, base_dir=base_dir)
    assert loaded_plan.workflow_id == plan.workflow_id
    assert loaded_run.run_id == run.run_id
    assert len(loaded_tasks) == 5

    # 7. Init execution state
    state = init_execution(loaded_plan, loaded_run, loaded_tasks)
    assert len(state.completed_ids) == 0

    # 8. Get first wave - should be the research task (depth 0)
    dispatchable = get_dispatchable_tasks(state)
    assert len(dispatchable) == 1
    assert dispatchable[0].role == "research"

    research_task = dispatchable[0]

    # 9. Mark research as dispatched
    state = mark_dispatched(state, [research_task.task_id])
    assert any(t.task_id == research_task.task_id and t.status == "in_progress" for t in state.tasks)

    # 10. Mark research as completed
    state = mark_completed(state, research_task.task_id)

    # Persist task status to disk
    update_task_status(plan.workflow_id, research_task.task_id, "completed", base_dir=base_dir)

    # 11. Get next wave - should be implement task
    dispatchable = get_dispatchable_tasks(state)
    assert len(dispatchable) == 1
    assert dispatchable[0].role == "implement"
    implement_task = dispatchable[0]

    # 12. Mark implement dispatched + completed
    state = mark_dispatched(state, [implement_task.task_id])
    state = mark_completed(state, implement_task.task_id)
    update_task_status(plan.workflow_id, implement_task.task_id, "completed", base_dir=base_dir)

    # 13. Continue for test -> review -> verify
    dispatchable = get_dispatchable_tasks(state)
    assert len(dispatchable) == 1
    assert dispatchable[0].role == "test"
    test_task = dispatchable[0]

    state = mark_dispatched(state, [test_task.task_id])
    state = mark_completed(state, test_task.task_id)
    update_task_status(plan.workflow_id, test_task.task_id, "completed", base_dir=base_dir)

    dispatchable = get_dispatchable_tasks(state)
    assert len(dispatchable) == 1
    assert dispatchable[0].role == "review"
    review_task = dispatchable[0]

    state = mark_dispatched(state, [review_task.task_id])
    state = mark_completed(state, review_task.task_id)
    update_task_status(plan.workflow_id, review_task.task_id, "completed", base_dir=base_dir)

    dispatchable = get_dispatchable_tasks(state)
    assert len(dispatchable) == 1
    assert dispatchable[0].role == "verify"
    verify_task = dispatchable[0]

    state = mark_dispatched(state, [verify_task.task_id])
    state = mark_completed(state, verify_task.task_id)
    update_task_status(plan.workflow_id, verify_task.task_id, "completed", base_dir=base_dir)

    # 14. Verify all 5 completed
    summary = compute_progress_summary(state)
    assert summary["total"] == 5
    assert summary["completed"] == 5
    assert summary["pending"] == 0

    # 15. Record checkpoint with milestone "final_audit"
    checkpoint = record_checkpoint(
        plan.workflow_id,
        milestone="final_audit",
        task_ids=[t.task_id for t in tasks],
        message="All tasks completed",
        base_dir=base_dir,
    )
    assert checkpoint.milestone == "final_audit"
    assert len(checkpoint.task_ids) == 5

    # 16. Resolve run as completed
    resolved_run = resolve_run(plan.workflow_id, status="completed", base_dir=base_dir)
    assert resolved_run.status == "completed"

    # 17 & 18. Verify run status and all tasks completed on disk
    final_plan, final_run, final_tasks = load_run_state(plan.workflow_id, base_dir=base_dir)
    assert final_run.status == "completed"
    # Verify tasks are completed on disk
    assert all(t.status == "completed" for t in final_tasks)


# ---------------------------------------------------------------------------
# Test 2: Guard blocks unfrozen plan
# ---------------------------------------------------------------------------

def test_guard_blocks_unfrozen_plan(tmp_path: Path) -> None:
    """Verify that start_run raises ValueError when plan is not frozen."""
    from hermesoptimizer.workflow.guard import preflight_check

    base_dir = tmp_path

    # 1. Create a plan but don't freeze it
    plan = shape_plan(objective="Test plan")
    plan_dir = base_dir / ".hermes" / "workflows" / plan.workflow_id
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "tasks").mkdir(exist_ok=True)
    save_plan(plan_dir, plan)

    # Attempt to start run should fail because plan is not frozen
    with pytest.raises(ValueError, match="Plan must be frozen"):
        start_run(plan.workflow_id, base_dir=base_dir)

    # Also verify the guard preflight check detects this
    run = None
    violations, _ = preflight_check(plan, run)
    assert len(violations) > 0
    assert any(v.check_name == "plan_not_frozen" for v in violations)


# ---------------------------------------------------------------------------
# Test 3: Scheduler parallel batch
# ---------------------------------------------------------------------------

def test_scheduler_parallel_batch(tmp_path: Path) -> None:
    """Test that independent tasks at depth 0 are batched by role with max_parallelism > 1."""
    base_dir = tmp_path

    # 1. Create a plan with 6 independent tasks (no dependencies) with different roles
    plan = shape_plan(objective="Test parallel scheduling")

    # Create 6 tasks with no dependencies, different roles
    task_defs = [
        {"role": "research", "desc": "Research task 1"},
        {"role": "research", "desc": "Research task 2"},
        {"role": "implement", "desc": "Implement task 1"},
        {"role": "implement", "desc": "Implement task 2"},
        {"role": "test", "desc": "Test task 1"},
        {"role": "verify", "desc": "Verify task 1"},
    ]

    tasks = []
    for i, td in enumerate(task_defs):
        task_id = f"task-{i}"
        task = WorkflowTask(
            task_id=task_id,
            parent_id=None,
            dependencies=[],
            role=td["role"],
            description=td["desc"],
            expected_artifact=f"Artifact for {td['desc']}",
            exit_criteria=["Completed"],
            status="pending",
        )
        tasks.append(task)

    plan.tasks = tasks
    plan_dir = base_dir / ".hermes" / "workflows" / plan.workflow_id
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "tasks").mkdir(exist_ok=True)
    save_plan(plan_dir, plan)
    for task in tasks:
        save_task(plan_dir, task)

    # 2. Build task graph
    graph = build_task_graph(tasks)
    assert len(graph) == 6

    # 3. Compute batches
    scheduled = compute_batches(tasks)
    assert scheduled.total_tasks == 6

    # 4. Verify tasks at depth 0 are grouped into batches by role
    depths = compute_dependency_depth(tasks)
    depth_0_tasks = [t for t in tasks if depths[t.task_id] == 0]
    assert len(depth_0_tasks) == 6  # all 6 are depth 0 (no deps)

    # Group by role to verify batching
    by_role: dict[str, list[str]] = {}
    for t in depth_0_tasks:
        by_role.setdefault(t.role, []).append(t.task_id)

    # 5. Verify max_parallelism > 1 (we have multiple roles that can run in parallel)
    assert scheduled.max_parallelism > 1

    # Verify we have batches for different roles
    role_batches = [b for b in scheduled.batches if "research" in b.roles]
    assert len(role_batches) >= 1


# ---------------------------------------------------------------------------
# Test 4: Checkpoint resume cycle
# ---------------------------------------------------------------------------

def test_checkpoint_resume_cycle(tmp_path: Path) -> None:
    """Test that checkpoint/resume preserves completed task state."""
    base_dir = tmp_path

    # 1. Create plan, freeze, start run
    plan = shape_plan(objective="Resume test")
    tasks = generate_default_tasks("Resume test")
    plan.tasks = tasks

    plan_dir = base_dir / ".hermes" / "workflows" / plan.workflow_id
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "tasks").mkdir(exist_ok=True)
    save_plan(plan_dir, plan)
    for task in tasks:
        save_task(plan_dir, task)

    freeze_plan(plan.workflow_id, base_dir=base_dir)
    start_run(plan.workflow_id, base_dir=base_dir)

    # 2. Init execution
    loaded_plan, loaded_run, loaded_tasks = load_run_state(plan.workflow_id, base_dir=base_dir)
    state = init_execution(loaded_plan, loaded_run, loaded_tasks)

    # 3. Dispatch and complete first 2 tasks in dependency order (research then implement)
    # Use get_dispatchable_tasks to find the correct next task, not array index
    dispatchable = get_dispatchable_tasks(state)
    assert len(dispatchable) >= 1
    task1 = dispatchable[0]  # should be research (depth 0, highest priority role)
    state = mark_dispatched(state, [task1.task_id])
    state = mark_completed(state, task1.task_id)
    update_task_status(plan.workflow_id, task1.task_id, "completed", base_dir=base_dir)

    # Now implement should be dispatchable
    dispatchable = get_dispatchable_tasks(state)
    assert len(dispatchable) >= 1
    task2 = dispatchable[0]  # should be implement
    state = mark_dispatched(state, [task2.task_id])
    state = mark_completed(state, task2.task_id)
    update_task_status(plan.workflow_id, task2.task_id, "completed", base_dir=base_dir)

    assert len(state.completed_ids) == 2
    assert task1.task_id in state.completed_ids
    assert task2.task_id in state.completed_ids

    # 4. Record a checkpoint with milestone "batch_completed" and those task IDs
    checkpoint = record_checkpoint(
        plan.workflow_id,
        milestone="batch_completed",
        task_ids=[task1.task_id, task2.task_id],
        message="First batch completed",
        base_dir=base_dir,
    )
    assert checkpoint.milestone == "batch_completed"
    assert set(checkpoint.task_ids) == {task1.task_id, task2.task_id}

    # 5. Simulate a "crash" by reloading from disk (tasks now have completed status persisted)
    fresh_plan, fresh_run, fresh_tasks = load_run_state(plan.workflow_id, base_dir=base_dir)

    # Verify tasks were persisted as completed
    completed_on_disk = [t for t in fresh_tasks if t.status == "completed"]
    assert len(completed_on_disk) == 2

    # 6. Use resume_from_state to resume
    resumed_state = resume_from_state(fresh_plan, fresh_run, fresh_tasks)

    # 7. Verify completed_ids still has the 2 completed tasks
    assert task1.task_id in resumed_state.completed_ids
    assert task2.task_id in resumed_state.completed_ids

    # 8. Verify progress_log has a "Resuming execution" event
    resuming_events = [e for e in resumed_state.progress_log if "Resuming" in e.message]
    assert len(resuming_events) == 1

    # 9. Continue and complete remaining tasks
    # With linear deps (research->implement->test->review->verify), after completing
    # research+implement, only test is dispatchable. Complete them one by one.
    remaining_tasks = get_dispatchable_tasks(resumed_state)
    assert len(remaining_tasks) == 1
    assert remaining_tasks[0].role == "test"
    state = mark_dispatched(state, [remaining_tasks[0].task_id])
    state = mark_completed(state, remaining_tasks[0].task_id)

    remaining_tasks = get_dispatchable_tasks(state)
    assert len(remaining_tasks) == 1
    assert remaining_tasks[0].role == "review"
    state = mark_dispatched(state, [remaining_tasks[0].task_id])
    state = mark_completed(state, remaining_tasks[0].task_id)

    remaining_tasks = get_dispatchable_tasks(state)
    assert len(remaining_tasks) == 1
    assert remaining_tasks[0].role == "verify"
    state = mark_dispatched(state, [remaining_tasks[0].task_id])
    state = mark_completed(state, remaining_tasks[0].task_id)

    summary = compute_progress_summary(state)
    assert summary["completed"] == 5


# ---------------------------------------------------------------------------
# Test 5: Blocked task flow
# ---------------------------------------------------------------------------

def test_blocked_task_flow(tmp_path: Path) -> None:
    """Test that blocked tasks are properly identified and recorded."""
    base_dir = tmp_path

    # 1. Create plan with 3 tasks: A (research), B (implement, depends on A), C (test, depends on B)
    plan = shape_plan(objective="Blocked task test")

    task_a = WorkflowTask(
        task_id="task-a",
        parent_id=None,
        dependencies=[],
        role="research",
        description="Research task",
        expected_artifact="Research doc",
        exit_criteria=["Done"],
        status="pending",
    )
    task_b = WorkflowTask(
        task_id="task-b",
        parent_id=None,
        dependencies=["task-a"],
        role="implement",
        description="Implement task",
        expected_artifact="Code",
        exit_criteria=["Done"],
        status="pending",
    )
    task_c = WorkflowTask(
        task_id="task-c",
        parent_id=None,
        dependencies=["task-b"],
        role="test",
        description="Test task",
        expected_artifact="Tests",
        exit_criteria=["Done"],
        status="pending",
    )

    plan.tasks = [task_a, task_b, task_c]
    plan_dir = base_dir / ".hermes" / "workflows" / plan.workflow_id
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "tasks").mkdir(exist_ok=True)
    save_plan(plan_dir, plan)
    for task in plan.tasks:
        save_task(plan_dir, task)

    freeze_plan(plan.workflow_id, base_dir=base_dir)
    start_run(plan.workflow_id, base_dir=base_dir)

    # 2. Init execution
    loaded_plan, loaded_run, loaded_tasks = load_run_state(plan.workflow_id, base_dir=base_dir)
    state = init_execution(loaded_plan, loaded_run, loaded_tasks)

    # 3. Dispatch A
    dispatchable = get_dispatchable_tasks(state)
    assert len(dispatchable) == 1
    assert dispatchable[0].task_id == "task-a"

    state = mark_dispatched(state, ["task-a"])

    # 4. Mark A as blocked (reason: "missing docs")
    state = mark_blocked(state, "task-a", reason="missing docs")
    assert "task-a" in state.blocked_ids

    # 5. Verify get_blocked_tasks returns tasks that depend on the blocked task
    # get_blocked_tasks returns tasks (pending/in_progress) whose dependencies are blocked/failed
    # task-a IS blocked, so task-b (which depends on task-a) should appear as blocked
    blocked = get_blocked_tasks(state.tasks)
    assert any(t.task_id == "task-b" for t in blocked), "task-b should be blocked because it depends on blocked task-a"

    # 6. Verify get_dispatchable_tasks returns nothing (B depends on blocked A)
    still_dispatchable = get_dispatchable_tasks(state)
    assert len(still_dispatchable) == 0

    # 7. Record blocker
    blocker = record_blocker(
        plan.workflow_id,
        reason="missing docs",
        task_id="task-a",
        evidence="No documentation found in repository",
        replan_needed=True,
        base_dir=base_dir,
    )
    assert blocker.task_id == "task-a"
    assert blocker.reason == "missing docs"

    # 8. Verify blocker loads from disk
    blockers = load_blockers(plan_dir)
    assert len(blockers) >= 1
    disk_blocker = next((b for b in blockers if b.task_id == "task-a"), None)
    assert disk_blocker is not None
    assert disk_blocker.reason == "missing docs"


# ---------------------------------------------------------------------------
# Test 6: Two-stage review flow
# ---------------------------------------------------------------------------

def test_two_stage_review_flow(tmp_path: Path) -> None:
    """Test two-stage review: spec compliance and code quality gates."""
    base_dir = tmp_path

    # 1. Create plan with an implement task
    plan = shape_plan(objective="Two-stage review test")

    implement_task = WorkflowTask(
        task_id="implement-1",
        parent_id=None,
        dependencies=[],
        role="implement",
        description="Implement feature X",
        expected_artifact="Feature X code",
        exit_criteria=["Done"],
        status="pending",
    )

    plan.tasks = [implement_task]
    plan_dir = base_dir / ".hermes" / "workflows" / plan.workflow_id
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "tasks").mkdir(exist_ok=True)
    save_plan(plan_dir, plan)
    save_task(plan_dir, implement_task)

    freeze_plan(plan.workflow_id, base_dir=base_dir)
    start_run(plan.workflow_id, base_dir=base_dir)

    # 2. Init execution
    loaded_plan, loaded_run, loaded_tasks = load_run_state(plan.workflow_id, base_dir=base_dir)
    state = init_execution(loaded_plan, loaded_run, loaded_tasks)

    # 3. Dispatch the implement task
    dispatchable = get_dispatchable_tasks(state)
    assert len(dispatchable) == 1

    state = mark_dispatched(state, ["implement-1"])

    # 4. Create a review with spec_compliant=True, code_quality_pass=True
    review_pass = create_review(
        task_id="implement-1",
        spec_compliant=True,
        code_quality_pass=True,
        issues=[],
        reviewer="spec_reviewer",
    )

    # 5. Apply review -> verify task is NOT blocked
    state = apply_review(state, review_pass)
    implement_in_state = next(t for t in state.tasks if t.task_id == "implement-1")
    assert implement_in_state.status != "blocked"

    # 6. Create another review with spec_compliant=False
    review_fail = create_review(
        task_id="implement-1",
        spec_compliant=False,
        code_quality_pass=True,
        issues=["API endpoint does not match spec"],
        reviewer="spec_reviewer",
    )

    # 7. Apply review -> verify task IS blocked
    state = apply_review(state, review_fail)
    implement_after_fail = next(t for t in state.tasks if t.task_id == "implement-1")
    assert implement_after_fail.status == "blocked"
    assert "implement-1" in state.blocked_ids


# ---------------------------------------------------------------------------
# Test 7: Plan quality check
# ---------------------------------------------------------------------------

def test_plan_quality_check(tmp_path: Path) -> None:
    """Test plan quality validation."""
    base_dir = tmp_path

    # 1. Use shape_plan to create a plan, generate default tasks, add them
    plan = shape_plan(
        objective="Quality test plan",
        scope=["implementation"],
        acceptance_criteria=["All tests pass"],
    )
    tasks = generate_default_tasks("Quality test plan")
    plan.tasks = tasks
    plan.next_action = "Freeze and execute"

    plan_dir = base_dir / ".hermes" / "workflows" / plan.workflow_id
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "tasks").mkdir(exist_ok=True)
    save_plan(plan_dir, plan)
    for task in tasks:
        save_task(plan_dir, task)

    # 2. Run check_plan_quality -> verify is_valid is True
    report = check_plan_quality(plan)
    assert report.is_valid is True
    assert len(report.errors) == 0

    # 3. Create a plan with empty objective -> verify is_valid is False
    bad_plan = shape_plan(objective="")
    bad_plan.tasks = [
        WorkflowTask(
            task_id="bad-task",
            parent_id=None,
            dependencies=[],
            role="research",
            description="Some task",
            expected_artifact="Artifact",
            exit_criteria=["Done"],
            status="pending",
        )
    ]
    bad_plan.next_action = "Do something"

    bad_report = check_plan_quality(bad_plan)
    assert bad_report.is_valid is False
    assert any("no objective" in e.lower() for e in bad_report.errors)


# ---------------------------------------------------------------------------
# Test 8: UX format rendering
# ---------------------------------------------------------------------------

def test_ux_format_rendering(tmp_path: Path) -> None:
    """Test that UX rendering functions produce expected output."""
    base_dir = tmp_path

    # 1. Create a full plan with tasks
    plan = shape_plan(
        objective="UX rendering test",
        scope=["implementation"],
        acceptance_criteria=["Tests pass"],
    )
    tasks = generate_default_tasks("UX rendering test")
    plan.tasks = tasks
    plan.next_action = "Freeze and start devdo"

    plan_dir = base_dir / ".hermes" / "workflows" / plan.workflow_id
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "tasks").mkdir(exist_ok=True)
    save_plan(plan_dir, plan)
    for task in tasks:
        save_task(plan_dir, task)

    # 2. Freeze it
    freeze_plan(plan.workflow_id, base_dir=base_dir)

    # 3. Render with render_todo_handoff -> verify "Objective" appears
    output = render_todo_handoff(plan)
    assert "Objective" in output
    assert plan.objective in output

    # 4. Start run
    run = start_run(plan.workflow_id, base_dir=base_dir)

    # 5. Compute batches
    scheduled = compute_batches(tasks)

    # 6. Render with render_devdo_startup -> verify "Execution Starting" appears
    startup_output = render_devdo_startup(plan, run, scheduled=scheduled)
    assert "Execution Starting" in startup_output
    assert plan.objective in startup_output
