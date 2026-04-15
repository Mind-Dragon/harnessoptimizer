"""Execution orchestration scheduler for Hermes Optimizer workflow system."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hermesoptimizer.workflow.schema import (
    WorkflowCheckpoint,
    WorkflowTask,
)


@dataclass(slots=True)
class RolePool:
    """Pool configuration for a given role."""

    role: str
    max_workers: int
    description: str


DEFAULT_ROLE_POOLS: dict[str, RolePool] = {
    "research": RolePool(role="research", max_workers=3, description="Research and information gathering"),
    "implement": RolePool(role="implement", max_workers=4, description="Code implementation"),
    "test": RolePool(role="test", max_workers=2, description="Test writing and execution"),
    "review": RolePool(role="review", max_workers=2, description="Code review and spec compliance"),
    "verify": RolePool(role="verify", max_workers=2, description="Smoke checks and live verification"),
    "integrate": RolePool(role="integrate", max_workers=1, description="Integration and merge"),
    "guardrail": RolePool(role="guardrail", max_workers=1, description="Guardrail and constraint checking"),
}


@dataclass(slots=True)
class ExecutionBatch:
    """A batch of tasks scheduled to run together."""

    batch_id: str
    task_ids: list[str]
    roles: list[str]
    max_parallel: int
    description: str


@dataclass(slots=True)
class ScheduledPlan:
    """A complete scheduled execution plan."""

    batches: list[ExecutionBatch]
    total_tasks: int
    max_parallelism: int
    estimated_phases: int


# Role priority ordering for task selection
ROLE_PRIORITY = [
    "implement",
    "research",
    "test",
    "review",
    "verify",
    "integrate",
    "guardrail",
]


def build_task_graph(tasks: list[WorkflowTask]) -> dict[str, list[str]]:
    """Build an adjacency list from the task list.

    Keys are task_ids, values are lists of task_ids that depend on the key
    (i.e., the dependents/children in the DAG).

    Raises ValueError if a dependency references a task_id not in the list.
    """
    task_ids = {t.task_id for t in tasks}

    # Validate all dependencies exist
    for task in tasks:
        for dep_id in task.dependencies:
            if dep_id not in task_ids:
                raise ValueError(f"Task '{task.task_id}' has dependency on unknown task_id '{dep_id}'")

    # Build adjacency list: task_id -> list of dependents
    graph: dict[str, list[str]] = {t.task_id: [] for t in tasks}

    for task in tasks:
        for dep_id in task.dependencies:
            graph[dep_id].append(task.task_id)

    return graph


def compute_dependency_depth(tasks: list[WorkflowTask]) -> dict[str, int]:
    """Compute the depth of each task (how many dependency layers deep it is).

    Tasks with no dependencies have depth 0.
    A task's depth = 1 + max(depth of its dependencies).

    Returns {task_id: depth}.
    """
    if not tasks:
        return {}

    # Build a lookup map
    task_map = {t.task_id: t for t in tasks}

    # Compute depths recursively with memoization
    depths: dict[str, int] = {}

    def _depth(task_id: str) -> int:
        if task_id in depths:
            return depths[task_id]

        task = task_map[task_id]
        if not task.dependencies:
            depths[task_id] = 0
        else:
            max_dep_depth = max(_depth(dep_id) for dep_id in task.dependencies)
            depths[task_id] = 1 + max_dep_depth

        return depths[task_id]

    for task in tasks:
        _depth(task.task_id)

    return depths


def compute_batches(
    tasks: list[WorkflowTask], role_pools: dict[str, RolePool] | None = None
) -> ScheduledPlan:
    """Compute execution batches from tasks.

    Groups tasks by depth level, then by role within each depth level.
    Each (depth, role) group becomes an ExecutionBatch.
    """
    if role_pools is None:
        role_pools = DEFAULT_ROLE_POOLS

    if not tasks:
        return ScheduledPlan(
            batches=[],
            total_tasks=0,
            max_parallelism=0,
            estimated_phases=0,
        )

    # Compute depths
    depths = compute_dependency_depth(tasks)

    # Group by depth level
    depth_groups: dict[int, list[WorkflowTask]] = {}
    for task in tasks:
        d = depths[task.task_id]
        if d not in depth_groups:
            depth_groups[d] = []
        depth_groups[d].append(task)

    # Within each depth, group by role
    batches: list[ExecutionBatch] = []
    for depth in sorted(depth_groups.keys()):
        tasks_at_depth = depth_groups[depth]
        role_groups: dict[str, list[WorkflowTask]] = {}
        for task in tasks_at_depth:
            if task.role not in role_groups:
                role_groups[task.role] = []
            role_groups[task.role].append(task)

        for role, role_tasks in role_groups.items():
            max_parallel = role_pools.get(role, RolePool(role=role, max_workers=1, description="")).max_workers
            batch = ExecutionBatch(
                batch_id=f"depth-{depth}-{role}",
                task_ids=[t.task_id for t in role_tasks],
                roles=[role],
                max_parallel=max_parallel,
                description=f"Depth {depth}, role {role}",
            )
            batches.append(batch)

    # Compute summary stats
    total_tasks = len(tasks)
    max_parallelism = max((b.max_parallel for b in batches), default=0)
    estimated_phases = len(depth_groups)

    return ScheduledPlan(
        batches=batches,
        total_tasks=total_tasks,
        max_parallelism=max_parallelism,
        estimated_phases=estimated_phases,
    )


def get_ready_tasks(tasks: list[WorkflowTask], completed_task_ids: set[str]) -> list[WorkflowTask]:
    """Return tasks that are ready to execute.

    A task is ready if:
    - status is "pending"
    - all dependencies are in completed_task_ids

    Returns sorted by role priority: implement > research > test > review > verify > integrate > guardrail
    """
    task_map = {t.task_id: t for t in tasks}

    ready: list[WorkflowTask] = []
    for task in tasks:
        if task.status != "pending":
            continue
        # Check all dependencies are completed
        if all(dep_id in completed_task_ids for dep_id in task.dependencies):
            ready.append(task)

    # Sort by role priority
    def role_sort_key(t: WorkflowTask) -> int:
        try:
            return ROLE_PRIORITY.index(t.role)
        except ValueError:
            return len(ROLE_PRIORITY)

    ready.sort(key=role_sort_key)
    return ready


def get_blocked_tasks(tasks: list[WorkflowTask]) -> list[WorkflowTask]:
    """Return tasks that are blocked.

    A task is blocked if:
    - status is "pending" or "in_progress"
    - at least one dependency has status "failed" or "blocked"
    """
    task_map = {t.task_id: t for t in tasks}

    blocked: list[WorkflowTask] = []
    for task in tasks:
        if task.status not in ("pending", "in_progress"):
            continue

        # Check if any dependency is failed or blocked
        for dep_id in task.dependencies:
            dep = task_map.get(dep_id)
            if dep and dep.status in ("failed", "blocked"):
                blocked.append(task)
                break

    return blocked


def compute_resume_point(
    tasks: list[WorkflowTask], checkpoints: list[WorkflowCheckpoint]
) -> str | None:
    """Find the last clean checkpoint to resume from.

    1. Look for checkpoints with milestone "batch_completed" or "phase_completed" in reverse order
    2. For each such checkpoint, verify all its task_ids have status "completed"
    3. Return the first matching checkpoint_id, or None if no clean checkpoint exists
    """
    task_map = {t.task_id: t for t in tasks}

    # Filter to relevant milestones and iterate in reverse
    relevant = [cp for cp in checkpoints if cp.milestone in ("batch_completed", "phase_completed")]
    relevant.reverse()

    for checkpoint in relevant:
        # Verify all task_ids in checkpoint have status "completed"
        all_completed = True
        for task_id in checkpoint.task_ids:
            task = task_map.get(task_id)
            if task is None or task.status != "completed":
                all_completed = False
                break

        if all_completed:
            return checkpoint.checkpoint_id

    return None


def tasks_by_role(tasks: list[WorkflowTask]) -> dict[str, list[WorkflowTask]]:
    """Group tasks by their role field.

    Returns {role: [tasks]}.
    """
    result: dict[str, list[WorkflowTask]] = {}
    for task in tasks:
        if task.role not in result:
            result[task.role] = []
        result[task.role].append(task)
    return result


def estimate_parallelism(
    tasks: list[WorkflowTask], role_pools: dict[str, RolePool] | None = None
) -> int:
    """Estimate maximum parallel workers needed.

    1. Group tasks by role
    2. For each role, min(len(tasks_in_role), role_pool.max_workers)
    3. Sum across roles at the same depth level
    4. Return the maximum sum across all depth levels
    """
    if role_pools is None:
        role_pools = DEFAULT_ROLE_POOLS

    if not tasks:
        return 0

    # Compute depths
    depths = compute_dependency_depth(tasks)

    # Group by depth
    depth_groups: dict[int, dict[str, list[WorkflowTask]]] = {}
    for task in tasks:
        d = depths[task.task_id]
        if d not in depth_groups:
            depth_groups[d] = {}
        if task.role not in depth_groups[d]:
            depth_groups[d][task.role] = []
        depth_groups[d][task.role].append(task)

    # For each depth level, sum the parallelism across roles
    max_parallel = 0
    for depth, role_groups in depth_groups.items():
        depth_parallel = 0
        for role, role_tasks in role_groups.items():
            pool = role_pools.get(role)
            if pool:
                depth_parallel += min(len(role_tasks), pool.max_workers)
            else:
                depth_parallel += min(len(role_tasks), 1)
        max_parallel = max(max_parallel, depth_parallel)

    return max_parallel
