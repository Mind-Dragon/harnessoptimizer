"""Tests for the scheduler module."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hermesoptimizer.workflow.schema import WorkflowCheckpoint, WorkflowTask
from hermesoptimizer.workflow.scheduler import (
    DEFAULT_ROLE_POOLS,
    ExecutionBatch,
    RolePool,
    ScheduledPlan,
    build_task_graph,
    compute_batches,
    compute_dependency_depth,
    compute_resume_point,
    estimate_parallelism,
    get_blocked_tasks,
    get_ready_tasks,
    tasks_by_role,
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


def _make_checkpoint(
    checkpoint_id: str,
    milestone: str,
    task_ids: list[str],
) -> WorkflowCheckpoint:
    """Helper to create a WorkflowCheckpoint."""
    return WorkflowCheckpoint(
        checkpoint_id=checkpoint_id,
        run_id="run-1",
        milestone=milestone,
        task_ids=task_ids,
        message="test checkpoint",
        created_at=datetime.now(timezone.utc).isoformat(),
    )


class TestBuildTaskGraph:
    def test_build_task_graph_linear(self) -> None:
        """A→B→C, verify adjacency."""
        tasks = [
            _make_task("A", dependencies=[]),
            _make_task("B", dependencies=["A"]),
            _make_task("C", dependencies=["B"]),
        ]
        graph = build_task_graph(tasks)
        assert graph == {
            "A": ["B"],
            "B": ["C"],
            "C": [],
        }

    def test_build_task_graph_diamond(self) -> None:
        """A→B, A→C, B→D, C→D, verify adjacency."""
        tasks = [
            _make_task("A", dependencies=[]),
            _make_task("B", dependencies=["A"]),
            _make_task("C", dependencies=["A"]),
            _make_task("D", dependencies=["B", "C"]),
        ]
        graph = build_task_graph(tasks)
        assert graph == {
            "A": ["B", "C"],
            "B": ["D"],
            "C": ["D"],
            "D": [],
        }

    def test_build_task_graph_independent(self) -> None:
        """3 tasks no deps, all empty lists."""
        tasks = [
            _make_task("A"),
            _make_task("B"),
            _make_task("C"),
        ]
        graph = build_task_graph(tasks)
        assert graph == {
            "A": [],
            "B": [],
            "C": [],
        }

    def test_build_task_graph_dangling_dep(self) -> None:
        """Dependency on non-existent task_id, raises ValueError."""
        tasks = [
            _make_task("A", dependencies=["X"]),  # X doesn't exist
        ]
        with pytest.raises(ValueError, match="dependency on unknown task_id"):
            build_task_graph(tasks)


class TestComputeDependencyDepth:
    def test_compute_dependency_depth_linear(self) -> None:
        """A(0)→B(1)→C(2)."""
        tasks = [
            _make_task("A", dependencies=[]),
            _make_task("B", dependencies=["A"]),
            _make_task("C", dependencies=["B"]),
        ]
        depths = compute_dependency_depth(tasks)
        assert depths == {"A": 0, "B": 1, "C": 2}

    def test_compute_dependency_depth_diamond(self) -> None:
        """A(0), B(1), C(1), D(2)."""
        tasks = [
            _make_task("A", dependencies=[]),
            _make_task("B", dependencies=["A"]),
            _make_task("C", dependencies=["A"]),
            _make_task("D", dependencies=["B", "C"]),
        ]
        depths = compute_dependency_depth(tasks)
        assert depths == {"A": 0, "B": 1, "C": 1, "D": 2}

    def test_compute_dependency_depth_independent(self) -> None:
        """All 0."""
        tasks = [
            _make_task("A"),
            _make_task("B"),
            _make_task("C"),
        ]
        depths = compute_dependency_depth(tasks)
        assert depths == {"A": 0, "B": 0, "C": 0}


class TestComputeBatches:
    def test_compute_batches_groups_by_depth(self) -> None:
        """4 tasks at depth 0, 2 at depth 1 → 2+ batches."""
        tasks = [
            _make_task("A"),  # depth 0
            _make_task("B"),  # depth 0
            _make_task("C"),  # depth 0
            _make_task("D"),  # depth 0
            _make_task("E", dependencies=["A"]),  # depth 1
            _make_task("F", dependencies=["B"]),  # depth 1
        ]
        plan = compute_batches(tasks)
        assert plan.total_tasks == 6
        assert plan.estimated_phases == 2  # depth 0 and depth 1
        # At least 2 batches: one for depth 0, one for depth 1
        assert len(plan.batches) >= 2

    def test_compute_batches_respects_role_pools(self) -> None:
        """Tasks at same depth but different roles get separate batches."""
        tasks = [
            _make_task("A", role="research"),  # depth 0
            _make_task("B", role="implement"),  # depth 0
            _make_task("C", role="test"),  # depth 0
        ]
        plan = compute_batches(tasks)
        # Should have 3 batches, one per role
        assert len(plan.batches) == 3
        batch_roles = {b.roles[0] for b in plan.batches}
        assert batch_roles == {"research", "implement", "test"}

    def test_compute_batches_max_parallelism(self) -> None:
        """Multiple roles at same depth, max_parallelism is max across batches."""
        tasks = [
            _make_task("A", role="research"),
            _make_task("B", role="research"),
            _make_task("C", role="implement"),
        ]
        plan = compute_batches(tasks)
        # research has max_workers=3, implement has max_workers=4
        # max_parallelism = max of batch max_parallel values = max(3, 4) = 4
        assert plan.max_parallelism == 4

    def test_compute_batches_custom_role_pools(self) -> None:
        """Pass custom role_pools, verify used."""
        custom_pools: dict[str, RolePool] = {
            "research": RolePool(role="research", max_workers=1, description="Custom"),
            "implement": RolePool(role="implement", max_workers=1, description="Custom"),
        }
        tasks = [
            _make_task("A", role="research"),
            _make_task("B", role="research"),
            _make_task("C", role="implement"),
        ]
        plan = compute_batches(tasks, role_pools=custom_pools)
        # Custom pools have max_workers=1 for both
        # max_parallelism = max of batch max_parallel values = max(1, 1) = 1
        assert plan.max_parallelism == 1


class TestGetReadyTasks:
    def test_get_ready_tasks_no_deps(self) -> None:
        """All pending, no completed, returns all sorted by role priority."""
        tasks = [
            _make_task("A", role="test"),
            _make_task("B", role="implement"),
            _make_task("C", role="research"),
        ]
        ready = get_ready_tasks(tasks, completed_task_ids=set())
        assert len(ready) == 3
        # implement > research > test in priority order
        assert ready[0].role == "implement"
        assert ready[1].role == "research"
        assert ready[2].role == "test"

    def test_get_ready_tasks_with_deps(self) -> None:
        """A completed, B depends on A → B is ready."""
        tasks = [
            _make_task("A", status="completed"),
            _make_task("B", dependencies=["A"]),
        ]
        ready = get_ready_tasks(tasks, completed_task_ids={"A"})
        assert len(ready) == 1
        assert ready[0].task_id == "B"

    def test_get_ready_tasks_partial_deps(self) -> None:
        """A,B completed, C depends on A and D (D not done) → C not ready, D is ready."""
        tasks = [
            _make_task("A", status="completed"),
            _make_task("B", status="completed"),
            _make_task("C", dependencies=["A", "D"]),
            _make_task("D"),
        ]
        ready = get_ready_tasks(tasks, completed_task_ids={"A", "B"})
        # C is not ready because D is not done
        # D is ready because it has no dependencies
        task_ids = {t.task_id for t in ready}
        assert "C" not in task_ids
        assert "D" in task_ids

    def test_get_ready_tasks_excludes_non_pending(self) -> None:
        """Tasks with in_progress or completed status are excluded."""
        tasks = [
            _make_task("A", status="completed"),
            _make_task("B", status="in_progress"),
            _make_task("C"),
        ]
        ready = get_ready_tasks(tasks, completed_task_ids=set())
        assert len(ready) == 1
        assert ready[0].task_id == "C"


class TestGetBlockedTasks:
    def test_get_blocked_tasks_with_failed_dep(self) -> None:
        """Dependency failed → task is blocked."""
        tasks = [
            _make_task("A", status="failed"),
            _make_task("B", dependencies=["A"]),
        ]
        blocked = get_blocked_tasks(tasks)
        assert len(blocked) == 1
        assert blocked[0].task_id == "B"

    def test_get_blocked_tasks_all_healthy(self) -> None:
        """No blocked tasks."""
        tasks = [
            _make_task("A", status="completed"),
            _make_task("B", dependencies=["A"], status="pending"),
        ]
        blocked = get_blocked_tasks(tasks)
        assert len(blocked) == 0

    def test_get_blocked_tasks_blocked_chain(self) -> None:
        """A blocked → B (depends on A) also blocked."""
        tasks = [
            _make_task("A", status="blocked"),
            _make_task("B", dependencies=["A"]),
        ]
        blocked = get_blocked_tasks(tasks)
        assert len(blocked) == 1
        assert blocked[0].task_id == "B"


class TestComputeResumePoint:
    def test_compute_resume_point_finds_clean(self) -> None:
        """batch_completed checkpoint with all tasks done."""
        tasks = [
            _make_task("A", status="completed"),
            _make_task("B", status="completed"),
        ]
        checkpoints = [
            _make_checkpoint("cp-1", "graph_built", ["A"]),
            _make_checkpoint("cp-2", "batch_completed", ["A", "B"]),
        ]
        result = compute_resume_point(tasks, checkpoints)
        assert result == "cp-2"

    def test_compute_resume_point_skips_dirty(self) -> None:
        """Checkpoint exists but one task not completed → skip."""
        tasks = [
            _make_task("A", status="completed"),
            _make_task("B", status="pending"),  # Not done
        ]
        checkpoints = [
            _make_checkpoint("cp-1", "batch_completed", ["A", "B"]),
            _make_checkpoint("cp-2", "phase_completed", ["A"]),
        ]
        result = compute_resume_point(tasks, checkpoints)
        # cp-1 is dirty (B not completed), cp-2 is clean (A is completed)
        assert result == "cp-2"

    def test_compute_resume_point_no_checkpoints(self) -> None:
        """Returns None."""
        tasks = [
            _make_task("A"),
        ]
        checkpoints: list[WorkflowCheckpoint] = []
        result = compute_resume_point(tasks, checkpoints)
        assert result is None


class TestTasksByRole:
    def test_tasks_by_role_groups_correctly(self) -> None:
        """3 implement, 2 test tasks → {implement: [3], test: [2]}."""
        tasks = [
            _make_task("A", role="implement"),
            _make_task("B", role="implement"),
            _make_task("C", role="implement"),
            _make_task("D", role="test"),
            _make_task("E", role="test"),
        ]
        by_role = tasks_by_role(tasks)
        assert len(by_role["implement"]) == 3
        assert len(by_role["test"]) == 2


class TestEstimateParallelism:
    def test_estimate_parallelism_wide_graph(self) -> None:
        """5 implement + 3 test at same depth, max(5,4)*4 + min(3,2)*2 = 4+2 = 6."""
        tasks = [
            _make_task("A1", role="implement"),
            _make_task("A2", role="implement"),
            _make_task("A3", role="implement"),
            _make_task("A4", role="implement"),
            _make_task("A5", role="implement"),
            _make_task("B1", role="test"),
            _make_task("B2", role="test"),
            _make_task("B3", role="test"),
        ]
        # All at depth 0
        parallelism = estimate_parallelism(tasks)
        # implement: min(5, 4) = 4, test: min(3, 2) = 2, total = 6
        assert parallelism == 6
