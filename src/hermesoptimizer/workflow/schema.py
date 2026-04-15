"""Schema definitions for Hermes Optimizer workflow system."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class WorkflowTask:
    """A node in the task DAG."""

    task_id: str
    parent_id: str | None
    dependencies: list[str]
    role: str  # "research", "implement", "test", "review", "verify", "integrate", "guardrail"
    description: str
    expected_artifact: str | None
    exit_criteria: list[str]
    retry_policy: dict[str, Any] = field(default_factory=lambda: {"max_retries": 0})
    budget_hints: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # "pending", "in_progress", "completed", "blocked", "failed"
    assigned_to: str | None = None
    artifact_path: str | None = None


@dataclass(slots=True)
class WorkflowPlan:
    """The frozen plan produced by /todo."""

    workflow_id: str  # UUID
    schema_version: str = "1.0"
    objective: str = ""
    scope: list[str] = field(default_factory=list)
    non_goals: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    test_plan: str = ""
    risks: list[str] = field(default_factory=list)
    execution_hints: dict[str, Any] = field(default_factory=dict)
    next_action: str = ""
    created_at: str = ""  # ISO 8601
    updated_at: str = ""  # ISO 8601
    status: str = "draft"  # "draft", "frozen", "blocked", "completed"
    tasks: list[WorkflowTask] = field(default_factory=list)


@dataclass(slots=True)
class WorkflowRun:
    """Live execution state produced by /devdo."""

    run_id: str  # UUID
    workflow_id: str  # matches plan
    plan_version: str  # matches plan schema_version
    status: str = "initialized"  # "initialized", "running", "paused", "completed", "failed"
    active_tasks: list[str] = field(default_factory=list)  # task_ids currently running
    owner: str = "devdo"  # "devdo" or "todo"
    guard_state: str = "clean"  # "clean", "drift_detected", "blocked", "repairing"
    last_checkpoint_id: str | None = None
    created_at: str = ""  # ISO 8601
    updated_at: str = ""  # ISO 8601


@dataclass(slots=True)
class WorkflowCheckpoint:
    """Append-only progress record."""

    checkpoint_id: str
    run_id: str
    milestone: str  # "graph_built", "batch_dispatched", "task_completed", "task_blocked", "phase_completed", "final_audit"
    task_ids: list[str]  # tasks involved
    message: str
    created_at: str  # ISO 8601


@dataclass(slots=True)
class WorkflowBlocker:
    """Records why something stopped."""

    blocker_id: str
    task_id: str | None
    reason: str
    evidence: str
    replan_needed: bool
    created_at: str  # ISO 8601
