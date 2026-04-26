"""Budget recommendation engine: analyzes session signals and suggests profile adjustments."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hermesoptimizer.budget.analyzer import BudgetSignal
from hermesoptimizer.budget.profile import (
    PRESET_ORDER,
    BudgetProfile,
    ProfileLevel,
    get_profile,
    get_role_defaults,
)


@dataclass(frozen=True)
class BudgetRecommendation:
    """Immutable recommendation produced by the budget recommender.

    Attributes:
        current_profile: Name of the profile the agent is currently running.
        recommended_profile: Name of the profile the recommender suggests.
        confidence: Confidence score between 0.0 and 1.0.
        reasoning: Plain-language explanation of the recommendation.
        main_turns: Recommended main_turns for the new profile.
        subagent_turns: Recommended subagent_turns for the new profile.
        role_overrides: Role -> turn count overrides to apply.
        axis_overrides: Axis name -> value overrides to apply.
        signals_used: Number of signals that contributed to this recommendation.
    """

    current_profile: str
    recommended_profile: str
    confidence: float
    reasoning: str
    main_turns: int
    subagent_turns: int
    role_overrides: dict[str, int] = field(default_factory=dict)
    axis_overrides: dict[str, Any] = field(default_factory=dict)
    signals_used: int = 0


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------


def _compute_aggregate_metrics(signals: list[BudgetSignal]) -> dict[str, Any]:
    """Compute aggregate metrics from a list of BudgetSignal instances.

    Returns:
        Dictionary with keys:
            avg_utilization (float): Mean turn_utilization across signals.
            completion_rate (float): Fraction of signals with "completed" status.
            avg_retry_count (float): Mean retry_count across signals.
            loop_rate (float): Fraction of signals where loop_detected is True.
            avg_fix_cycles (float): Mean fix_cycles across signals.
            total_signals (int): Count of input signals.
    """
    if not signals:
        return {
            "avg_utilization": 0.0,
            "completion_rate": 0.0,
            "avg_retry_count": 0.0,
            "loop_rate": 0.0,
            "avg_fix_cycles": 0.0,
            "total_signals": 0,
        }

    n = len(signals)
    avg_utilization = sum(s.turn_utilization for s in signals) / n
    completion_rate = sum(1 for s in signals if s.completion_status == "completed") / n
    avg_retry_count = sum(s.retry_count for s in signals) / n
    loop_rate = sum(1 for s in signals if s.loop_detected) / n
    avg_fix_cycles = sum(s.fix_cycles for s in signals) / n

    return {
        "avg_utilization": avg_utilization,
        "completion_rate": completion_rate,
        "avg_retry_count": avg_retry_count,
        "loop_rate": loop_rate,
        "avg_fix_cycles": avg_fix_cycles,
        "total_signals": n,
    }


def _determine_step(metrics: dict[str, Any], current: BudgetProfile) -> tuple[ProfileLevel, str]:
    """Determine the recommended profile level and produce reasoning.

    Args:
        metrics: Aggregate metrics from _compute_aggregate_metrics.
        current: The current BudgetProfile.

    Returns:
        Tuple of (recommended ProfileLevel, reasoning string).
    """
    n = metrics["total_signals"]

    # Empty signals: stay with the current profile
    if n == 0:
        return current.name, (
            f"No signal data available. Staying at {current.name}."
        )

    util = metrics["avg_utilization"]
    comp = metrics["completion_rate"]
    loop_rate = metrics["loop_rate"]
    fix_cycles = metrics["avg_fix_cycles"]

    # Rule 1: Low utilization + high completion → step down
    if util < 0.3 and comp > 0.8:
        step = current.step_down()
        if step is not None:
            return step.name, (
                f"Turn utilization is very low ({util:.0%}) with high completion rate ({comp:.0%}). "
                f"Consider stepping down from {current.name} to {step.name} to conserve resources."
            )
        else:
            return current.name, (
                f"Turn utilization is low ({util:.0%}) but already at the lowest profile; "
                f"recommend tightening axis overrides instead."
            )

    # Rule 2: High utilization OR low completion → step up
    if util > 0.7 or comp < 0.7:
        step = current.step_up()
        if step is not None:
            reasons = []
            if util > 0.7:
                reasons.append(f"high turn utilization ({util:.0%})")
            if comp < 0.7:
                reasons.append(f"low completion rate ({comp:.0%})")
            return step.name, (
                f"Signals indicate {' and '.join(reasons)}. "
                f"Stepping up from {current.name} to {step.name}."
            )
        else:
            return current.name, (
                f"Already at the highest profile ({current.name}) with "
                f"utilization={util:.0%}, completion={comp:.0%}; recommend axis overrides to constrain."
            )

    # Rule 3: Medium utilization (0.3-0.7) + decent completion (>0.8) → stay or step up
    if 0.3 <= util <= 0.7 and comp > 0.8:
        # Check if approaching boundary (within 0.1 of 0.7)
        if util > 0.6:
            step = current.step_up()
            if step is not None:
                return step.name, (
                    f"Turn utilization ({util:.0%}) is approaching the high boundary with "
                    f"strong completion ({comp:.0%}). Stepping up from {current.name} to {step.name}."
                )
        return current.name, (
            f"Turn utilization ({util:.0%}) and completion rate ({comp:.0%}) are healthy. "
            f"Staying at {current.name}."
        )

    # Default: mixed signals — stay with reasoning
    return current.name, (
        f"Mixed signals across {n} sessions: utilization={util:.0%}, completion={comp:.0%}. "
        f"Staying at {current.name}."
    )


def _compute_role_overrides(
    signals: list[BudgetSignal], current: BudgetProfile
) -> dict[str, int]:
    """Compute per-role turn budget overrides based on signal patterns.

    Role overrides only tighten (reduce) budgets, never expand them.
    Research and review stay conservative even on high profiles.

    Returns:
        Dict mapping role names to recommended turn counts.
    """
    if not signals:
        return {}

    # Group signals by role
    by_role: dict[str, list[BudgetSignal]] = {}
    for s in signals:
        by_role.setdefault(s.role, []).append(s)

    overrides: dict[str, int] = {}
    role_defaults = get_role_defaults(current.name)

    # Map role names to their default turn counts
    defaults_map = {
        "research": role_defaults.research,
        "implement": role_defaults.implement,
        "test": role_defaults.test,
        "review": role_defaults.review,
        "verify": role_defaults.verify,
        "integrate": role_defaults.integrate,
    }

    for role, role_signals in by_role.items():
        if len(role_signals) < 2:
            # Need at least 2 signals to make role-level adjustments
            continue

        avg_util = sum(s.turn_utilization for s in role_signals) / len(role_signals)
        completion_rate = sum(
            1 for s in role_signals if s.completion_status == "completed"
        ) / len(role_signals)

        default_turns = defaults_map.get(role)
        if default_turns is None:
            continue

        # Tighten if utilization is consistently low
        if avg_util < 0.3 and completion_rate > 0.9:
            # Very efficient - can tighten significantly
            new_turns = int(default_turns * 0.75)
            if new_turns < default_turns:
                overrides[role] = max(new_turns, 50)  # Never go below 50

        # Tighten if completion rate is poor (role is struggling)
        elif completion_rate < 0.5:
            # Role is failing often - give it more budget within the profile cap
            # This is actually an expansion, so we skip for "tighten only" rule
            pass

        # Research and review: cap at low-medium levels per guidelines
        if role in ("research", "review") and default_turns > 100:
            overrides[role] = min(overrides.get(role, default_turns), 100)

    return overrides


def recommend(signals: list[BudgetSignal], current_level: ProfileLevel) -> BudgetRecommendation:
    """Produce a BudgetRecommendation from a list of BudgetSignal instances.

    Args:
        signals: List of BudgetSignal instances from session analysis.
        current_level: The profile level the agent is currently running.

    Returns:
        BudgetRecommendation with suggested profile and overrides.
    """
    metrics = _compute_aggregate_metrics(signals)
    current = get_profile(current_level)

    # Determine base profile step
    recommended_level, reasoning = _determine_step(metrics, current)

    # Build axis overrides based on specific conditions
    axis_overrides: dict[str, Any] = {}
    loop_rate = metrics["loop_rate"]
    fix_cycles = metrics["avg_fix_cycles"]

    if loop_rate > 0.2:
        # Increase retry_limit in axis_overrides
        new_retry = current.retry_limit + 2
        axis_overrides["retry_limit"] = new_retry
        reasoning += (
            f" Loop detected in {loop_rate:.0%} of signals; "
            f"increasing retry_limit to {new_retry}."
        )

    if fix_cycles > 3:
        new_fix_cycles = current.fix_iterate_cycles + 2 if current.fix_iterate_cycles is not None else 10
        axis_overrides["fix_iterate_cycles"] = new_fix_cycles
        reasoning += (
            f" Average fix_cycles ({fix_cycles:.1f}) exceeds threshold; "
            f"increasing fix_iterate_cycles to {new_fix_cycles}."
        )

    # Compute confidence based on signal count and agreement
    n = metrics["total_signals"]
    if n == 0:
        confidence = 0.0
    elif n == 1:
        confidence = 0.4  # Single signal is noisy
    elif n < 5:
        confidence = 0.6
    else:
        # More signals = higher confidence, capped at 0.9
        confidence = min(0.5 + (n - 5) * 0.05, 0.9)

    # Compute role overrides
    role_overrides = _compute_role_overrides(signals, current)

    recommended = get_profile(recommended_level)

    return BudgetRecommendation(
        current_profile=current_level,
        recommended_profile=recommended_level,
        confidence=confidence,
        reasoning=reasoning.strip(),
        main_turns=recommended.main_turns,
        subagent_turns=recommended.subagent_turns,
        role_overrides=role_overrides,
        axis_overrides=axis_overrides,
        signals_used=n,
    )
