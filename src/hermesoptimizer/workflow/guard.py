"""Runtime guard for Hermes Optimizer workflow system.

Validates workflow state before and during /devdo execution.
Hard-blocks on invalid state and can repair safe drift.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from hermesoptimizer.workflow.schema import WorkflowPlan, WorkflowRun, WorkflowTask
from hermesoptimizer.workflow.store import save_run, validate_plan


class GuardDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    REPAIR = "repair"


@dataclass(slots=True)
class GuardLog:
    decision: GuardDecision
    reason: str
    recovery_action: str | None = None
    timestamp: str = ""


@dataclass(slots=True)
class GuardViolation:
    check_name: str
    severity: str  # "error", "warning"
    message: str
    repairable: bool


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def preflight_check(
    plan: WorkflowPlan | None, run: WorkflowRun | None
) -> tuple[list[GuardViolation], list[GuardLog]]:
    """Run all preflight checks.

    Returns (violations, logs). Each check produces a GuardLog entry.
    If a violation is found, the log records the decision (BLOCK for errors,
    REPAIR for warnings). If no violations, decision is ALLOW.
    """
    violations: list[GuardViolation] = []
    logs: list[GuardLog] = []

    # 1. Plan must exist and not be None
    if plan is None:
        violation = GuardViolation(
            check_name="plan_missing",
            severity="error",
            message="Plan is missing or None",
            repairable=False,
        )
        violations.append(violation)
        logs.append(
            GuardLog(
                decision=GuardDecision.BLOCK,
                reason="Plan is missing",
                recovery_action=None,
                timestamp=_now_iso(),
            )
        )
        return violations, logs

    # 2. Plan status must be "frozen"
    if plan.status != "frozen":
        violation = GuardViolation(
            check_name="plan_not_frozen",
            severity="error",
            message=f"Plan status is '{plan.status}', expected 'frozen'",
            repairable=False,
        )
        violations.append(violation)
        logs.append(
            GuardLog(
                decision=GuardDecision.BLOCK,
                reason=f"Plan not frozen (status={plan.status})",
                recovery_action=None,
                timestamp=_now_iso(),
            )
        )

    # 3. Plan must pass validate_plan()
    errors = validate_plan(plan)
    if errors:
        violation = GuardViolation(
            check_name="plan_invalid",
            severity="error",
            message=f"Plan validation failed: {'; '.join(errors)}",
            repairable=False,
        )
        violations.append(violation)
        logs.append(
            GuardLog(
                decision=GuardDecision.BLOCK,
                reason=f"Plan invalid: {'; '.join(errors)}",
                recovery_action=None,
                timestamp=_now_iso(),
            )
        )

    # Only check run-specific items if run exists
    if run is not None:
        # 4. run.workflow_id must match plan.workflow_id
        if run.workflow_id != plan.workflow_id:
            violation = GuardViolation(
                check_name="run_plan_mismatch",
                severity="error",
                message=f"Run workflow_id '{run.workflow_id}' does not match plan workflow_id '{plan.workflow_id}'",
                repairable=False,
            )
            violations.append(violation)
            logs.append(
                GuardLog(
                    decision=GuardDecision.BLOCK,
                    reason=f"Run/plan workflow_id mismatch: {run.workflow_id} != {plan.workflow_id}",
                    recovery_action=None,
                    timestamp=_now_iso(),
                )
            )

        # 5. run.plan_version must match plan.schema_version
        if run.plan_version != plan.schema_version:
            violation = GuardViolation(
                check_name="version_drift",
                severity="warning",
                message=f"Run plan_version '{run.plan_version}' does not match plan schema_version '{plan.schema_version}'",
                repairable=True,
            )
            violations.append(violation)
            logs.append(
                GuardLog(
                    decision=GuardDecision.REPAIR,
                    reason=f"Version drift detected: {run.plan_version} != {plan.schema_version}",
                    recovery_action="Update run.plan_version to match plan.schema_version",
                    timestamp=_now_iso(),
                )
            )

        # 6. run.status must not be "failed"
        if run.status == "failed":
            violation = GuardViolation(
                check_name="run_failed",
                severity="error",
                message=f"Run status is 'failed', cannot proceed",
                repairable=False,
            )
            violations.append(violation)
            logs.append(
                GuardLog(
                    decision=GuardDecision.BLOCK,
                    reason="Run is in failed state",
                    recovery_action=None,
                    timestamp=_now_iso(),
                )
            )

        # 7. run.guard_state must not be "blocked"
        if run.guard_state == "blocked":
            violation = GuardViolation(
                check_name="guard_blocked",
                severity="error",
                message="Run guard_state is 'blocked', cannot proceed",
                repairable=False,
            )
            violations.append(violation)
            logs.append(
                GuardLog(
                    decision=GuardDecision.BLOCK,
                    reason="Guard state is blocked",
                    recovery_action=None,
                    timestamp=_now_iso(),
                )
            )

    # If no violations, log ALLOW
    if not violations:
        logs.append(
            GuardLog(
                decision=GuardDecision.ALLOW,
                reason="All preflight checks passed",
                recovery_action=None,
                timestamp=_now_iso(),
            )
        )

    return violations, logs


def boundary_check(
    plan: WorkflowPlan,
    run: WorkflowRun,
    tasks: list[WorkflowTask],
    action: str,
) -> tuple[list[GuardViolation], list[GuardLog]]:
    """Run boundary checks before specific actions.

    action is one of: "write", "complete_task", "phase_transition", "fan_out".
    """
    violations: list[GuardViolation] = []
    logs: list[GuardLog] = []

    # 1. Run status must be "running" or "initialized"
    if run.status not in ("running", "initialized"):
        violation = GuardViolation(
            check_name="run_not_active",
            severity="error",
            message=f"Run status is '{run.status}', expected 'running' or 'initialized'",
            repairable=False,
        )
        violations.append(violation)
        logs.append(
            GuardLog(
                decision=GuardDecision.BLOCK,
                reason=f"Run not active (status={run.status})",
                recovery_action=None,
                timestamp=_now_iso(),
            )
        )

    # 2. For "write": run.guard_state must be "clean"
    if action == "write":
        if run.guard_state != "clean":
            violation = GuardViolation(
                check_name="guard_state_dirty",
                severity="warning",
                message=f"Run guard_state is '{run.guard_state}', expected 'clean' for write",
                repairable=True,
            )
            violations.append(violation)
            logs.append(
                GuardLog(
                    decision=GuardDecision.REPAIR,
                    reason=f"Guard state dirty for write (state={run.guard_state})",
                    recovery_action="Set guard_state to 'clean'",
                    timestamp=_now_iso(),
                )
            )

    # 3. For "complete_task": the task must exist and be "in_progress"
    if action == "complete_task":
        in_progress_tasks = [t for t in tasks if t.status == "in_progress"]
        if not in_progress_tasks:
            violation = GuardViolation(
                check_name="task_not_in_progress",
                severity="error",
                message="No task is currently in_progress",
                repairable=False,
            )
            violations.append(violation)
            logs.append(
                GuardLog(
                    decision=GuardDecision.BLOCK,
                    reason="No task in progress",
                    recovery_action=None,
                    timestamp=_now_iso(),
                )
            )

    # 4. For "phase_transition": no tasks with status "failed"
    if action == "phase_transition":
        failed_tasks = [t for t in tasks if t.status == "failed"]
        if failed_tasks:
            violation = GuardViolation(
                check_name="failed_tasks_exist",
                severity="error",
                message=f"Cannot transition phase: {len(failed_tasks)} task(s) have failed status",
                repairable=False,
            )
            violations.append(violation)
            logs.append(
                GuardLog(
                    decision=GuardDecision.BLOCK,
                    reason=f"Failed tasks exist: {[t.task_id for t in failed_tasks]}",
                    recovery_action=None,
                    timestamp=_now_iso(),
                )
            )

    # 5. For "fan_out": at least 2 pending tasks available
    if action == "fan_out":
        pending_tasks = [t for t in tasks if t.status == "pending"]
        if len(pending_tasks) < 2:
            violation = GuardViolation(
                check_name="insufficient_pending",
                severity="warning",
                message=f"Only {len(pending_tasks)} pending task(s), need at least 2 for fan_out",
                repairable=False,
            )
            violations.append(violation)
            logs.append(
                GuardLog(
                    decision=GuardDecision.REPAIR,
                    reason=f"Insufficient pending tasks for fan_out ({len(pending_tasks)} < 2)",
                    recovery_action=None,
                    timestamp=_now_iso(),
                )
            )

    # If no violations, log ALLOW
    if not violations:
        logs.append(
            GuardLog(
                decision=GuardDecision.ALLOW,
                reason=f"Boundary check passed for action '{action}'",
                recovery_action=None,
                timestamp=_now_iso(),
            )
        )

    return violations, logs


def repair_drift(
    plan: WorkflowPlan, run: WorkflowRun, base_dir: Path
) -> tuple[WorkflowRun, list[GuardLog]]:
    """Attempt to repair drift when safe.

    1. If run.plan_version doesn't match plan.schema_version, update run.plan_version
       and set run.guard_state to "clean"
    2. If run.guard_state is "drift_detected", set it to "clean"
    3. If run.guard_state is "blocked" or "repairing", return unchanged (not repairable)

    Saves the updated run. Returns (run, logs).
    """
    logs: list[GuardLog] = []
    repaired = False

    # Check if run is in a blocked or repairing state - not repairable
    if run.guard_state in ("blocked", "repairing"):
        logs.append(
            GuardLog(
                decision=GuardDecision.BLOCK,
                reason=f"Guard state is '{run.guard_state}', cannot repair",
                recovery_action=None,
                timestamp=_now_iso(),
            )
        )
        return run, logs

    # Repair version drift
    if run.plan_version != plan.schema_version:
        run.plan_version = plan.schema_version
        run.guard_state = "clean"
        repaired = True
        logs.append(
            GuardLog(
                decision=GuardDecision.REPAIR,
                reason=f"Fixed version drift: updated plan_version to {plan.schema_version}",
                recovery_action="Set run.plan_version = plan.schema_version, guard_state = 'clean'",
                timestamp=_now_iso(),
            )
        )

    # Repair drift_detected state
    if run.guard_state == "drift_detected":
        run.guard_state = "clean"
        repaired = True
        logs.append(
            GuardLog(
                decision=GuardDecision.REPAIR,
                reason="Cleared drift_detected state",
                recovery_action="Set guard_state to 'clean'",
                timestamp=_now_iso(),
            )
        )

    if repaired:
        # Save the updated run
        save_run(base_dir, run)

    if not logs:
        logs.append(
            GuardLog(
                decision=GuardDecision.ALLOW,
                reason="No drift to repair",
                recovery_action=None,
                timestamp=_now_iso(),
            )
        )

    return run, logs


def check_before_write(
    plan: WorkflowPlan, run: WorkflowRun, base_dir: Path
) -> GuardDecision:
    """Convenience function for write operations.

    1. Run boundary_check with action="write"
    2. If any error violations, return BLOCK
    3. If any warning violations, run repair_drift and return REPAIR
    4. Return ALLOW
    """
    violations, logs = boundary_check(plan, run, [], action="write")

    # If any error violations, BLOCK
    error_violations = [v for v in violations if v.severity == "error"]
    if error_violations:
        return GuardDecision.BLOCK

    # If any warning violations, repair and return REPAIR
    warning_violations = [v for v in violations if v.severity == "warning"]
    if warning_violations:
        repair_drift(plan, run, base_dir)
        return GuardDecision.REPAIR

    return GuardDecision.ALLOW


def check_before_complete(
    plan: WorkflowPlan,
    run: WorkflowRun,
    task_id: str,
    tasks: list[WorkflowTask],
) -> GuardDecision:
    """Convenience function for completing tasks.

    1. Run boundary_check with action="complete_task"
    2. Verify the task_id is in tasks and status is "in_progress"
    3. If any error violations, return BLOCK
    4. Return ALLOW
    """
    violations, logs = boundary_check(plan, run, tasks, action="complete_task")

    # If any error violations, BLOCK
    error_violations = [v for v in violations if v.severity == "error"]
    if error_violations:
        return GuardDecision.BLOCK

    # Verify the task exists and is in_progress
    task = next((t for t in tasks if t.task_id == task_id), None)
    if task is None or task.status != "in_progress":
        return GuardDecision.BLOCK

    return GuardDecision.ALLOW
