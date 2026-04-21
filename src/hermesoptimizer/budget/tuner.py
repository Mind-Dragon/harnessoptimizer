from __future__ import annotations

from pathlib import Path

import yaml

from hermesoptimizer.budget.profile import BudgetProfile, ProfileLevel, get_profile
from hermesoptimizer.budget.recommender import BudgetRecommendation


def write_budget_section(
    level: ProfileLevel,
    role_overrides: dict[str, int] | None = None,
) -> dict:
    """Build the budget section dict without any file I/O.

    Args:
        level: Profile level to use.
        role_overrides: Optional per-role turn budget overrides.

    Returns:
        Dict suitable for the 'turn_budget:' section of a config file.
    """
    profile = get_profile(level)
    section: dict = {
        "profile": profile.name,
        "main_turns": profile.main_turns,
        "subagent_turns": profile.subagent_turns,
        "retry_limit": profile.retry_limit,
        "fix_iterate_cycles": profile.fix_iterate_cycles,
        "max_parallel_workers": profile.max_parallel_workers,
        "token_budget_per_task": profile.token_budget_per_task,
        "verification_depth": profile.verification_depth.value,
    }
    if role_overrides:
        section["role_overrides"] = role_overrides
    return section


def apply_recommendation(
    config_path: Path,
    recommendation: BudgetRecommendation,
    dry_run: bool = True,
) -> dict:
    """Apply a budget recommendation to a config file.

    Args:
        config_path: Path to the YAML config file.
        recommendation: BudgetRecommendation to apply.
        dry_run: If True, return what would change without writing.

    Returns:
        Dict with keys: 'changes' (dict of changed fields), 'dry_run' (bool), 'path' (str)
    """
    role_overrides = recommendation.role_overrides if recommendation.role_overrides else None

    budget_section = write_budget_section(
        recommendation.recommended_profile,
        role_overrides=role_overrides,
    )

    # Read existing config or create empty
    if config_path.exists():
        with config_path.open() as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {}

    # Ensure turn_budget key exists
    if "turn_budget" not in config:
        config["turn_budget"] = {}

    # Compute changes
    changes = {}
    for key, value in budget_section.items():
        if config.get("turn_budget", {}).get(key) != value:
            changes[key] = value

    result: dict = {
        "changes": changes,
        "dry_run": dry_run,
        "path": str(config_path),
    }

    if dry_run:
        return result

    # Write updated config
    config["turn_budget"] = budget_section
    with config_path.open("w") as f:
        yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)

    return result


def set_profile(
    config_path: Path,
    level: ProfileLevel,
    role_overrides: dict[str, int] | None = None,
    dry_run: bool = True,
) -> dict:
    """Set a profile level directly in a config file.

    Args:
        config_path: Path to the YAML config file.
        level: Profile level to set.
        role_overrides: Optional per-role turn budget overrides.
        dry_run: If True, return what would change without writing.

    Returns:
        Dict with keys: 'changes' (dict of changed fields), 'dry_run' (bool), 'path' (str)
    """
    budget_section = write_budget_section(level, role_overrides=role_overrides)

    # Read existing config or create empty
    if config_path.exists():
        with config_path.open() as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {}

    # Compute changes
    changes = {}
    for key, value in budget_section.items():
        if config.get("turn_budget", {}).get(key) != value:
            changes[key] = value

    result: dict = {
        "changes": changes,
        "dry_run": dry_run,
        "path": str(config_path),
    }

    if dry_run:
        return result

    # Write updated config
    config["turn_budget"] = budget_section
    with config_path.open("w") as f:
        yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)

    return result
