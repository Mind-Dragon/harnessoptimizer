"""Passive budget-watch monitoring for logging budget recommendations."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from hermesoptimizer.budget.analyzer import BudgetSignal, parse_session_directory
from hermesoptimizer.budget.profile import ProfileLevel, get_profile
from hermesoptimizer.budget.recommender import BudgetRecommendation, recommend


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


def budget_watch_entry(
    session_dir: Path | None = None,
    log_path: Path | None = None,
    current_profile: ProfileLevel = "medium",
) -> str | None:
    """Parse session data and append a budget recommendation log entry.

    Args:
        session_dir: Directory containing session JSON files.
                    Defaults to ~/.hermes/sessions/.
        log_path: Path to the log file to append to.
                 Defaults to ~/.hermes/budget-advice.log.
        current_profile: The profile level the agent is currently running.

    Returns:
        The formatted log line string, or None on any failure.
        All failures are silent (exceptions are caught and swallowed).
    """
    try:
        # Resolve defaults
        if session_dir is None:
            session_dir = Path.home() / ".hermes" / "sessions"
        if log_path is None:
            log_path = Path.home() / ".hermes" / "budget-advice.log"

        # Parse session directory for signals
        signals = parse_session_directory(session_dir)

        # Get recommendation
        recommendation = recommend(signals, current_profile)

        # Compute average utilization from signals
        utilization = _compute_avg_utilization(signals)

        # Get session ID from directory name or path
        session_id = session_dir.name if session_dir.name else session_dir.stem

        # Format the log line
        log_line = format_watch_line(recommendation, utilization, session_id)

        # Ensure parent directory exists
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Append to log file
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")

        return log_line

    except Exception:
        # All failures are silent
        return None


def format_watch_line(
    recommendation: BudgetRecommendation,
    utilization: float,
    session_id: str,
    date_str: str | None = None,
) -> str:
    """Format a recommendation into the one-line watch log format.

    Log format:
        YYYY-MM-DD session=<id> profile=<p> utilization=<f> recommend=<p> <notes>

    Args:
        recommendation: BudgetRecommendation from recommend().
        utilization: Average turn utilization (0.0-1.0).
        session_id: Identifier for the session.
        date_str: Date string in YYYY-MM-DD format. Defaults to today.

    Returns:
        Formatted one-line log entry.
    """
    if date_str is None:
        date_str = date.today().isoformat()

    # Format utilization as a simple float (not percentage)
    util_str = f"{utilization:.2f}"

    # Build the recommendation part with any axis overrides as notes
    notes = _format_notes(recommendation)

    return (
        f"{date_str} session={session_id} "
        f"profile={recommendation.current_profile} "
        f"utilization={util_str} "
        f"recommend={recommendation.recommended_profile}"
        + (f" {notes}" if notes else "")
    )


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------


def _compute_avg_utilization(signals: list[BudgetSignal]) -> float:
    """Compute average utilization across signals."""
    if not signals:
        return 0.0
    return sum(s.turn_utilization for s in signals) / len(signals)


def _format_notes(recommendation: BudgetRecommendation) -> str:
    """Format axis overrides and reasoning into a short notes string."""
    parts = []

    # Add axis override hints
    if recommendation.axis_overrides:
        for key in sorted(recommendation.axis_overrides.keys()):
            parts.append(f"implement_{key}_{recommendation.axis_overrides[key]}")

    # Truncate reasoning to first sentence if long
    reasoning = recommendation.reasoning
    if len(reasoning) > 80:
        # Cut at first sentence boundary
        for sep in (". ", "! ", "? "):
            idx = reasoning.find(sep)
            if idx > 0 and idx < 80:
                reasoning = reasoning[: idx + 1]
                break

    if reasoning:
        parts.append(reasoning)

    return " ".join(parts)
