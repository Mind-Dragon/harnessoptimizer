"""UX formatting for /todo and /devdo command output.

Renders structured, human-readable output for workflow handoff and execution startup.
"""
from __future__ import annotations

from hermesoptimizer.workflow.schema import WorkflowPlan, WorkflowRun, WorkflowTask
from hermesoptimizer.workflow.scheduler import ScheduledPlan


def render_todo_handoff(plan: WorkflowPlan) -> str:
    """Render the /todo plan into a human-readable handoff format.

    Args:
        plan: The workflow plan to render.

    Returns:
        A multi-line string suitable for terminal output.
    """
    lines: list[str] = []

    # Header
    lines.append(f"TODO PLAN — {plan.workflow_id}")
    lines.append("━" * 50)
    lines.append("")

    # Objective and status
    lines.append(f"Objective:  {plan.objective}")
    lines.append(f"Status:     {plan.status}")
    lines.append("")

    # Scope
    lines.append("SCOPE")
    if plan.scope:
        for item in plan.scope:
            lines.append(f"  • {item}")
    else:
        lines.append("  None defined")
    lines.append("")

    # Non-goals
    lines.append("NON-GOALS")
    if plan.non_goals:
        for item in plan.non_goals:
            lines.append(f"  • {item}")
    else:
        lines.append("  None defined")
    lines.append("")

    # Acceptance criteria
    lines.append("ACCEPTANCE CRITERIA")
    if plan.acceptance_criteria:
        for item in plan.acceptance_criteria:
            lines.append(f"  • {item}")
    else:
        lines.append("  None defined")
    lines.append("")

    # Test plan
    lines.append("TEST PLAN")
    lines.append(f"  {plan.test_plan or 'Not yet defined'}")
    lines.append("")

    # Risks
    lines.append("RISKS")
    if plan.risks:
        for item in plan.risks:
            lines.append(f"  • {item}")
    else:
        lines.append("  None identified")
    lines.append("")

    # Tasks
    task_count = len(plan.tasks)
    lines.append(f"TASKS ({task_count} total)")
    for idx, task in enumerate(plan.tasks, start=1):
        deps_str = ", ".join(task.dependencies) if task.dependencies else "none"
        lines.append(f"  {idx}. [{task.status}] {task.role}: {task.description}")
        lines.append(f"     deps: {deps_str}")
    lines.append("")

    # Next action
    lines.append("NEXT ACTION FOR /devdo")
    lines.append(f"  {plan.next_action}")

    return "\n".join(lines)


def render_devdo_startup(
    plan: WorkflowPlan,
    run: WorkflowRun,
    scheduled: ScheduledPlan | None = None,
    progress: dict[str, int] | None = None,
) -> str:
    """Render the /devdo startup output.

    Args:
        plan: The workflow plan being executed.
        run: The live workflow run.
        scheduled: The computed execution schedule, if available.
        progress: Optional progress summary dict with keys: total, completed, in_progress, blocked, pending.

    Returns:
        A multi-line string suitable for terminal output.
    """
    lines: list[str] = []

    # Header
    lines.append("DEVDO — Execution Starting")
    lines.append("━" * 30)
    lines.append("")

    # Plan info
    lines.append(f"Plan:       {plan.objective}")
    lines.append(f"Run ID:     {run.run_id}")
    lines.append(f"Status:     {run.status}")
    lines.append(f"Guard:      {run.guard_state}")
    lines.append("")

    if scheduled is None:
        lines.append("No schedule computed yet.")
        lines.append("")
    else:
        # Execution strategy
        lines.append("EXECUTION STRATEGY")
        lines.append(f"  Total tasks:    {scheduled.total_tasks}")
        lines.append(f"  Max parallel:   {scheduled.max_parallelism}")
        lines.append(f"  Phases:         {scheduled.estimated_phases}")
        lines.append(f"  Batches:        {len(scheduled.batches)}")
        lines.append("")

        # First dispatch wave
        lines.append("FIRST DISPATCH WAVE")
        if scheduled.batches:
            first_batch = scheduled.batches[0]
            # Find task descriptions for this batch
            task_map = {t.task_id: t for t in plan.tasks}
            for task_id in first_batch.task_ids:
                task = task_map.get(task_id)
                if task:
                    lines.append(f"  • {task.description}")
        lines.append("")

        # Checkpoint policy
        lines.append("CHECKPOINT POLICY")
        lines.append("  Checkpoint after each batch completion.")
        lines.append("  Resume from last clean checkpoint on interruption.")
        lines.append("")

    # Progress section (if provided)
    if progress is not None:
        lines.append("PROGRESS")
        lines.append(f"  Total:     {progress.get('total', 0)}")
        lines.append(f"  Done:      {progress.get('completed', 0)}")
        lines.append(f"  In flight: {progress.get('in_progress', 0)}")
        lines.append(f"  Blocked:   {progress.get('blocked', 0)}")
        lines.append(f"  Pending:   {progress.get('pending', 0)}")
        lines.append("")

    return "\n".join(lines)


def render_normal_flow_example() -> str:
    """Return a multi-line string showing an example normal flow."""
    return """NORMAL FLOW
───────────
1. User: /todo Build user authentication
   → Creates plan with objective, scope, tasks
   → Plan is in "draft" status

2. User: /todo freeze <id>
   → Validates plan, sets status to "frozen"
   → Plan is now immutable for /devdo

3. User: /devdo <id>
   → Loads frozen plan
   → Builds task DAG, computes batches
   → Dispatches first wave of subagents
   → Checkpoints after each batch
   → Two-stage review for implementation tasks
   → Marks complete when all tasks done

4. Result: All tasks completed, run resolved."""


def render_blocked_flow_example() -> str:
    """Return a multi-line string showing a blocked flow."""
    return """BLOCKED FLOW
────────────
1. /devdo encounters a blocker on task "implement-auth"
   → Reason: "Missing OAuth credentials in environment"
   → /devdo marks task as blocked
   → Records blocker with evidence
   → Continues unblocked tasks

2. Remaining work continues:
   → Research tasks still run
   → Test tasks wait for implementation
   → /devdo reports progress and blockers

3. User resolves blocker (provides credentials)
   → User: /todo update <id> --next-action "Resume auth"
   → User: /devdo <id>
   → Blocked task is retried"""


def render_resume_flow_example() -> str:
    """Return a multi-line string showing a resume flow."""
    return """RESUME FLOW
───────────
1. /devdo was interrupted (process crashed, timeout, etc.)

2. User: /devdo <id>
   → Loads last clean checkpoint
   → Identifies completed tasks (skip them)
   → Identifies in-progress tasks (re-dispatch)
   → Continues from where it left off
   → Progress preserved, no duplicate work"""


def render_alias_flow_example() -> str:
    """Return a multi-line string describing the /dodev alias."""
    return """ALIAS FLOW
──────────
/dodev is an alias for /devdo

Both commands do exactly the same thing.
Use /devdo going forward. /dodev works during migration."""
