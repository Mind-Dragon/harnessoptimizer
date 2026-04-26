"""Budget profile definitions and presets for Hermes agent run tiers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


# Five-step profile levels
ProfileLevel = Literal["low", "low-medium", "medium", "medium-high", "high"]

PRESET_ORDER: list[ProfileLevel] = ["low", "low-medium", "medium", "medium-high", "high"]


class VerificationDepth(str, Enum):
    SMOKE = "smoke"
    UNIT_INTEGRATION = "unit+integration"
    FULL_GATE = "full_gate"


@dataclass(frozen=True)
class BudgetProfile:
    """Immutable budget profile for an agent run tier."""

    name: ProfileLevel
    main_turns: int
    subagent_turns: int
    retry_limit: int
    fix_iterate_cycles: int | None  # None = unlimited
    max_parallel_workers: int
    token_budget_per_task: int
    verification_depth: VerificationDepth

    def step_index(self) -> int:
        """Return ordinal position in PRESET_ORDER."""
        return PRESET_ORDER.index(self.name)

    def step_up(self) -> BudgetProfile | None:
        """Return next higher profile, or None if already at high."""
        idx = self.step_index()
        if idx >= len(PRESET_ORDER) - 1:
            return None
        return PRESETS[PRESET_ORDER[idx + 1]]

    def step_down(self) -> BudgetProfile | None:
        """Return next lower profile, or None if already at low."""
        idx = self.step_index()
        if idx <= 0:
            return None
        return PRESETS[PRESET_ORDER[idx - 1]]


@dataclass(frozen=True)
class RoleBudgetDefaults:
    """Per-role turn budget range within a profile."""

    research: int
    implement: int
    test: int
    review: int
    verify: int
    integrate: int


# Per-role defaults keyed by profile level.
# Research and review stay low-medium even on high profiles.
# Implement and integrate scale with the profile.
ROLE_DEFAULTS: dict[ProfileLevel, RoleBudgetDefaults] = {
    "low": RoleBudgetDefaults(50, 90, 75, 50, 50, 90),
    "low-medium": RoleBudgetDefaults(75, 150, 100, 75, 75, 150),
    "medium": RoleBudgetDefaults(100, 200, 125, 100, 100, 200),
    "medium-high": RoleBudgetDefaults(100, 300, 150, 100, 100, 300),
    "high": RoleBudgetDefaults(100, 400, 150, 100, 100, 400),
}

PRESETS: dict[ProfileLevel, BudgetProfile] = {
    "low": BudgetProfile(
        name="low",
        main_turns=90,
        subagent_turns=50,
        retry_limit=2,
        fix_iterate_cycles=1,
        max_parallel_workers=3,
        token_budget_per_task=50_000,
        verification_depth=VerificationDepth.SMOKE,
    ),
    "low-medium": BudgetProfile(
        name="low-medium",
        main_turns=200,
        subagent_turns=75,
        retry_limit=3,
        fix_iterate_cycles=2,
        max_parallel_workers=4,
        token_budget_per_task=100_000,
        verification_depth=VerificationDepth.UNIT_INTEGRATION,
    ),
    "medium": BudgetProfile(
        name="medium",
        main_turns=500,
        subagent_turns=100,
        retry_limit=4,
        fix_iterate_cycles=3,
        max_parallel_workers=5,
        token_budget_per_task=200_000,
        verification_depth=VerificationDepth.UNIT_INTEGRATION,
    ),
    "medium-high": BudgetProfile(
        name="medium-high",
        main_turns=750,
        subagent_turns=150,
        retry_limit=6,
        fix_iterate_cycles=5,
        max_parallel_workers=8,
        token_budget_per_task=350_000,
        verification_depth=VerificationDepth.UNIT_INTEGRATION,
    ),
    "high": BudgetProfile(
        name="high",
        main_turns=1000,
        subagent_turns=200,
        retry_limit=8,
        fix_iterate_cycles=None,
        max_parallel_workers=10,
        token_budget_per_task=500_000,
        verification_depth=VerificationDepth.FULL_GATE,
    ),
}


def get_profile(level: ProfileLevel) -> BudgetProfile:
    """Look up a preset profile by name. Raises KeyError if invalid."""
    return PRESETS[level]


def get_role_defaults(level: ProfileLevel) -> RoleBudgetDefaults:
    """Look up per-role defaults for a profile level."""
    return ROLE_DEFAULTS[level]
