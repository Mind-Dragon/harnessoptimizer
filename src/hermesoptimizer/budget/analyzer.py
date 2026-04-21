"""Budget signal extraction from Hermes session logs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BudgetSignal:
    """Immutable signal extracted from a single task session.

    Attributes:
        task_id: Unique identifier for the task.
        role: Role that performed the task (e.g., research, implement).
        turn_utilization: Fraction of available turns used (0.0-1.0).
        retry_count: Number of retries attempted.
        loop_detected: Whether a loop was detected in execution.
        completion_status: How the task completed ('completed'|'incomplete'|'error').
        fix_cycles: Number of fix-iterate cycles used.
        tokens_used: Token count consumed by the task.
        productive_call_ratio: Fraction of calls that were productive (0.0-1.0).
        duration_seconds: Wall-clock duration of the task.
    """

    task_id: str
    role: str
    turn_utilization: float
    retry_count: int
    loop_detected: bool
    completion_status: str
    fix_cycles: int
    tokens_used: int
    productive_call_ratio: float
    duration_seconds: float


# Patterns suggesting error/failure in assistant messages
_ERROR_PATTERNS = re.compile(
    r"(?:error|exception|traceback|failed|failure|crash|fatal)",
    re.IGNORECASE,
)

# Default turn budget when unknown (medium profile)
_DEFAULT_TURNS_BUDGET = 500


def extract_signal(task_data: dict[str, Any]) -> BudgetSignal:
    """Extract a BudgetSignal from a task data dictionary.

    Handles both explicit task dicts (from fixture format) and real
    Hermes session objects (with session_id, messages, etc.).

    Args:
        task_data: Dictionary containing task fields from a session log.

    Returns:
        BudgetSignal instance with extracted data.
    """
    # If this looks like a real Hermes session (has messages, no tasks key at parent),
    # parse it as a whole-session signal.
    if "messages" in task_data and "task_id" not in task_data:
        return _extract_from_real_session(task_data)

    turns_used = task_data.get("turns_used", 0)
    turns_budget = task_data.get("turns_budget", 0)
    total_calls = task_data.get("total_calls", 0)
    productive_calls = task_data.get("productive_calls", 0)

    turn_utilization = _safe_ratio(turns_used, turns_budget)
    productive_call_ratio = _safe_ratio(productive_calls, total_calls)

    return BudgetSignal(
        task_id=str(task_data.get("task_id", "")),
        role=str(task_data.get("role", "")),
        turn_utilization=turn_utilization,
        retry_count=int(task_data.get("retries", 0)),
        loop_detected=bool(task_data.get("loops", False)),
        completion_status=str(task_data.get("status", "incomplete")),
        fix_cycles=int(task_data.get("fix_cycles", 0)),
        tokens_used=int(task_data.get("tokens_used", 0)),
        productive_call_ratio=productive_call_ratio,
        duration_seconds=float(task_data.get("duration_seconds", 0.0)),
    )


def _extract_from_real_session(data: dict[str, Any]) -> BudgetSignal:
    """Extract a BudgetSignal from a real Hermes session dump.

    Real sessions have: session_id, model, platform, messages,
    message_count, session_start, last_updated, tools, system_prompt.
    """
    session_id = data.get("session_id", "unknown")
    message_count = int(data.get("message_count", 0))
    messages = data.get("messages", [])

    # Estimate turns_used: count assistant messages
    assistant_msgs = [m for m in messages if isinstance(m, dict) and m.get("role") == "assistant"]
    turns_used = len(assistant_msgs)
    turn_utilization = _safe_ratio(turns_used, _DEFAULT_TURNS_BUDGET)

    # Detect errors in assistant messages
    error_count = 0
    for msg in assistant_msgs:
        content = msg.get("content", "")
        if isinstance(content, str) and _ERROR_PATTERNS.search(content):
            error_count += 1

    # Detect loops: consecutive identical assistant messages
    loop_detected = False
    prev_content = None
    for msg in assistant_msgs:
        content = msg.get("content", "")
        if isinstance(content, str) and content == prev_content and len(content) > 50:
            loop_detected = True
            break
        prev_content = content

    # Compute duration
    duration_seconds = 0.0
    try:
        start = data.get("session_start", "")
        end = data.get("last_updated", "")
        if start and end:
            t0 = datetime.fromisoformat(start)
            t1 = datetime.fromisoformat(end)
            duration_seconds = max(0.0, (t1 - t0).total_seconds())
    except (ValueError, TypeError):
        pass

    # Productive calls: non-error assistant messages
    productive = max(0, turns_used - error_count)
    productive_call_ratio = _safe_ratio(productive, turns_used)

    # Determine completion status
    if error_count > turns_used * 0.5 and turns_used > 0:
        completion_status = "error"
    elif turn_utilization < 0.01:
        completion_status = "incomplete"
    else:
        completion_status = "completed"

    return BudgetSignal(
        task_id=session_id,
        role=data.get("platform", "cli"),
        turn_utilization=min(turn_utilization, 1.0),
        retry_count=error_count,
        loop_detected=loop_detected,
        completion_status=completion_status,
        fix_cycles=0,  # not available in raw session dumps
        tokens_used=0,  # not tracked in session JSON
        productive_call_ratio=productive_call_ratio,
        duration_seconds=duration_seconds,
    )


def parse_session_file(path: Path) -> list[BudgetSignal]:
    """Parse a single session JSON file and extract all BudgetSignals.

    Handles both fixture format (with 'tasks' key) and real Hermes
    session format (with 'messages' key).

    Args:
        path: Path to the session JSON file.

    Returns:
        List of BudgetSignal instances extracted from the session.
    """
    try:
        raw = path.read_bytes()
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return []

    # Fixture format: has explicit 'tasks' list
    if "tasks" in data:
        signals = []
        for task_data in data["tasks"]:
            signals.append(extract_signal(task_data))
        return signals

    # Real Hermes session format: single session → single signal
    return [extract_signal(data)]


def parse_session_directory(dir_path: Path) -> list[BudgetSignal]:
    """Parse all .json session files in a directory.

    Args:
        dir_path: Path to directory containing session JSON files.

    Returns:
        List of all BudgetSignal instances from all session files.
    """
    signals = []
    for json_file in sorted(dir_path.glob("*.json")):
        signals.extend(parse_session_file(json_file))
    return signals


def _safe_ratio(numerator: int | float, denominator: int | float) -> float:
    """Calculate ratio safely, returning 0.0 when denominator is 0."""
    if denominator == 0:
        return 0.0
    return numerator / denominator
