"""Execution engine for Hermes Optimizer workflow system.

Coordinates subagent dispatch, tracks progress, and manages execution lifecycle
for /devdo autonomous operations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from hermesoptimizer.workflow.schema import WorkflowPlan, WorkflowRun, WorkflowTask


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

TWO_STAGE_REVIEW_ROLES = {"implement", "integrate", "guardrail"}


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class ProgressEvent:
    """Records a significant event during workflow execution."""

    event_type: str  # "started", "completed", "blocked", "checkpoint", "dispatched", "reviewed"
    task_id: str | None
    message: str
    timestamp: str


@dataclass(slots=True)
class ReviewResult:
    """Result from a spec or quality review of a task."""

    task_id: str
    spec_compliant: bool
    code_quality_pass: bool
    issues: list[str]
    reviewer: str  # "spec_reviewer" or "quality_reviewer"


@dataclass(slots=True)
class ExecutionState:
    """Live execution state for a workflow run."""

    plan: WorkflowPlan
    run: WorkflowRun
    tasks: list[WorkflowTask]
    completed_ids: set[str]
    blocked_ids: set[str]
    progress_log: list[ProgressEvent] = field(default_factory=list)
    review_results: list[ReviewResult] = field(default_factory=list)


def init_execution(
    plan: WorkflowPlan, run: WorkflowRun, tasks: list[WorkflowTask]
) -> ExecutionState:
    """Initialize execution state from loaded workflow components.

    - Set all tasks with status "completed" into completed_ids
    - Set all tasks with status "failed" or "blocked" into blocked_ids
    - Return ExecutionState with empty progress_log and review_results
    """
    completed_ids: set[str] = set()
    blocked_ids: set[str] = set()

    for task in tasks:
        if task.status == "completed":
            completed_ids.add(task.task_id)
        elif task.status in ("failed", "blocked"):
            blocked_ids.add(task.task_id)

    return ExecutionState(
        plan=plan,
        run=run,
        tasks=tasks,
        completed_ids=completed_ids,
        blocked_ids=blocked_ids,
        progress_log=[],
        review_results=[],
    )


def get_dispatchable_tasks(state: ExecutionState) -> list[WorkflowTask]:
    """Get tasks that can be dispatched right now.

    - Status must be "pending"
    - All dependencies must be in completed_ids
    - Not in blocked_ids
    - Sort by role priority: implement > research > test > review > verify > integrate > guardrail
    - Return the list
    """
    task_map = {t.task_id: t for t in state.tasks}

    dispatchable: list[WorkflowTask] = []
    for task in state.tasks:
        if task.status != "pending":
            continue
        if task.task_id in state.blocked_ids:
            continue
        # Check all dependencies are completed
        if all(dep_id in state.completed_ids for dep_id in task.dependencies):
            dispatchable.append(task)

    # Sort by role priority
    def role_sort_key(t: WorkflowTask) -> int:
        try:
            return ROLE_PRIORITY.index(t.role)
        except ValueError:
            return len(ROLE_PRIORITY)

    dispatchable.sort(key=role_sort_key)
    return dispatchable


def mark_dispatched(
    state: ExecutionState, task_ids: list[str]
) -> ExecutionState:
    """Mark tasks as dispatched (in_progress).

    - For each task_id, update the task status to "in_progress"
    - Add a ProgressEvent with event_type="dispatched" for each
    - Return new ExecutionState (immutable pattern: create new, don't mutate)
    """
    # Create new tasks list with updated statuses
    new_tasks: list[WorkflowTask] = []
    new_events: list[ProgressEvent] = []

    task_id_set = set(task_ids)
    now = _now_iso()

    for task in state.tasks:
        if task.task_id in task_id_set:
            # Create a new task with updated status
            new_task = WorkflowTask(
                task_id=task.task_id,
                parent_id=task.parent_id,
                dependencies=task.dependencies,
                role=task.role,
                description=task.description,
                expected_artifact=task.expected_artifact,
                exit_criteria=task.exit_criteria,
                retry_policy=task.retry_policy,
                budget_hints=task.budget_hints,
                status="in_progress",
                assigned_to=task.assigned_to,
                artifact_path=task.artifact_path,
            )
            new_tasks.append(new_task)
            new_events.append(
                ProgressEvent(
                    event_type="dispatched",
                    task_id=task.task_id,
                    message=f"Task {task.task_id} dispatched",
                    timestamp=now,
                )
            )
        else:
            new_tasks.append(task)

    return ExecutionState(
        plan=state.plan,
        run=state.run,
        tasks=new_tasks,
        completed_ids=state.completed_ids,
        blocked_ids=state.blocked_ids,
        progress_log=state.progress_log + new_events,
        review_results=state.review_results,
    )


def mark_completed(
    state: ExecutionState, task_id: str, artifact_path: str | None = None
) -> ExecutionState:
    """Mark a task as completed.

    - Update task status to "completed"
    - Set artifact_path if provided
    - Add task_id to completed_ids
    - Add ProgressEvent with event_type="completed"
    - Return new ExecutionState
    """
    now = _now_iso()

    # Create new tasks list with updated statuses
    new_tasks: list[WorkflowTask] = []
    for task in state.tasks:
        if task.task_id == task_id:
            new_task = WorkflowTask(
                task_id=task.task_id,
                parent_id=task.parent_id,
                dependencies=task.dependencies,
                role=task.role,
                description=task.description,
                expected_artifact=task.expected_artifact,
                exit_criteria=task.exit_criteria,
                retry_policy=task.retry_policy,
                budget_hints=task.budget_hints,
                status="completed",
                assigned_to=task.assigned_to,
                artifact_path=artifact_path if artifact_path is not None else task.artifact_path,
            )
            new_tasks.append(new_task)
        else:
            new_tasks.append(task)

    new_completed_ids = state.completed_ids | {task_id}
    new_event = ProgressEvent(
        event_type="completed",
        task_id=task_id,
        message=f"Task {task_id} completed" + (f", artifact: {artifact_path}" if artifact_path else ""),
        timestamp=now,
    )

    return ExecutionState(
        plan=state.plan,
        run=state.run,
        tasks=new_tasks,
        completed_ids=new_completed_ids,
        blocked_ids=state.blocked_ids,
        progress_log=state.progress_log + [new_event],
        review_results=state.review_results,
    )


def mark_blocked(
    state: ExecutionState, task_id: str, reason: str
) -> ExecutionState:
    """Mark a task as blocked.

    - Update task status to "blocked"
    - Add task_id to blocked_ids
    - Add ProgressEvent with event_type="blocked"
    - Return new ExecutionState
    """
    now = _now_iso()

    # Create new tasks list with updated statuses
    new_tasks: list[WorkflowTask] = []
    for task in state.tasks:
        if task.task_id == task_id:
            new_task = WorkflowTask(
                task_id=task.task_id,
                parent_id=task.parent_id,
                dependencies=task.dependencies,
                role=task.role,
                description=task.description,
                expected_artifact=task.expected_artifact,
                exit_criteria=task.exit_criteria,
                retry_policy=task.retry_policy,
                budget_hints=task.budget_hints,
                status="blocked",
                assigned_to=task.assigned_to,
                artifact_path=task.artifact_path,
            )
            new_tasks.append(new_task)
        else:
            new_tasks.append(task)

    new_blocked_ids = state.blocked_ids | {task_id}
    new_event = ProgressEvent(
        event_type="blocked",
        task_id=task_id,
        message=f"Task {task_id} blocked: {reason}",
        timestamp=now,
    )

    return ExecutionState(
        plan=state.plan,
        run=state.run,
        tasks=new_tasks,
        completed_ids=state.completed_ids,
        blocked_ids=new_blocked_ids,
        progress_log=state.progress_log + [new_event],
        review_results=state.review_results,
    )


def should_two_stage_review(task: WorkflowTask) -> bool:
    """Determine if a task needs two-stage review.

    - Tasks with role "implement", "integrate", or "guardrail" need review
    - Tasks with other roles don't
    """
    return task.role in TWO_STAGE_REVIEW_ROLES


def create_review(
    task_id: str,
    spec_compliant: bool,
    code_quality_pass: bool,
    issues: list[str],
    reviewer: str,
) -> ReviewResult:
    """Create a review result. Simple factory."""
    return ReviewResult(
        task_id=task_id,
        spec_compliant=spec_compliant,
        code_quality_pass=code_quality_pass,
        issues=issues,
        reviewer=reviewer,
    )


def apply_review(state: ExecutionState, review: ReviewResult) -> ExecutionState:
    """Apply a review result.

    - Add to review_results
    - If spec_compliant is False, mark task as blocked with reason "Spec review failed: {issues}"
    - If code_quality_pass is False, add a ProgressEvent noting quality issues but don't block
    - Return new ExecutionState
    """
    now = _now_iso()
    new_events: list[ProgressEvent] = []
    new_blocked_ids = set(state.blocked_ids)
    new_tasks = list(state.tasks)

    # Always add the review result
    new_review_results = state.review_results + [review]

    # If spec not compliant, block the task
    if not review.spec_compliant:
        issues_str = "; ".join(review.issues) if review.issues else "unspecified"
        new_events.append(
            ProgressEvent(
                event_type="blocked",
                task_id=review.task_id,
                message=f"Task {review.task_id} blocked: Spec review failed: {issues_str}",
                timestamp=now,
            )
        )
        new_blocked_ids = new_blocked_ids | {review.task_id}

        # Update task status to blocked
        updated_tasks: list[WorkflowTask] = []
        for task in new_tasks:
            if task.task_id == review.task_id:
                updated_tasks.append(
                    WorkflowTask(
                        task_id=task.task_id,
                        parent_id=task.parent_id,
                        dependencies=task.dependencies,
                        role=task.role,
                        description=task.description,
                        expected_artifact=task.expected_artifact,
                        exit_criteria=task.exit_criteria,
                        retry_policy=task.retry_policy,
                        budget_hints=task.budget_hints,
                        status="blocked",
                        assigned_to=task.assigned_to,
                        artifact_path=task.artifact_path,
                    )
                )
            else:
                updated_tasks.append(task)
        new_tasks = updated_tasks

    # If code quality fails (but spec passed), just log an event, don't block
    if not review.code_quality_pass and review.spec_compliant:
        issues_str = "; ".join(review.issues) if review.issues else "unspecified"
        new_events.append(
            ProgressEvent(
                event_type="reviewed",
                task_id=review.task_id,
                message=f"Task {review.task_id} code quality issues: {issues_str}",
                timestamp=now,
            )
        )

    return ExecutionState(
        plan=state.plan,
        run=state.run,
        tasks=new_tasks,
        completed_ids=state.completed_ids,
        blocked_ids=new_blocked_ids,
        progress_log=state.progress_log + new_events,
        review_results=new_review_results,
    )


def compute_progress_summary(state: ExecutionState) -> dict[str, int]:
    """Return a summary dict:

    {
        "total": len(tasks),
        "completed": len(completed_ids),
        "blocked": len(blocked_ids),
        "in_progress": count of tasks with status "in_progress",
        "pending": count of tasks with status "pending",
    }
    """
    in_progress_count = sum(1 for t in state.tasks if t.status == "in_progress")
    pending_count = sum(1 for t in state.tasks if t.status == "pending")

    return {
        "total": len(state.tasks),
        "completed": len(state.completed_ids),
        "blocked": len(state.blocked_ids),
        "in_progress": in_progress_count,
        "pending": pending_count,
    }


def resume_from_state(
    plan: WorkflowPlan, run: WorkflowRun, tasks: list[WorkflowTask]
) -> ExecutionState:
    """Resume execution from saved state.

    - Same as init_execution but also add a ProgressEvent with event_type="started" and message="Resuming execution"
    - Return ExecutionState
    """
    state = init_execution(plan, run, tasks)
    now = _now_iso()
    resume_event = ProgressEvent(
        event_type="started",
        task_id=None,
        message="Resuming execution",
        timestamp=now,
    )
    return ExecutionState(
        plan=state.plan,
        run=state.run,
        tasks=state.tasks,
        completed_ids=state.completed_ids,
        blocked_ids=state.blocked_ids,
        progress_log=[resume_event],
        review_results=state.review_results,
    )
