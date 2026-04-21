"""CLI commands for budget-review and budget-set subcommands."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from hermesoptimizer.budget.analyzer import parse_session_directory, parse_session_file
from hermesoptimizer.budget.profile import PRESET_ORDER, ProfileLevel, get_profile
from hermesoptimizer.budget.recommender import recommend
from hermesoptimizer.budget.tuner import set_profile


def _expand_path(path: str) -> Path:
    """Expand ~ and environment variables in a path."""
    return Path(os.path.expandvars(os.path.expanduser(path)))


def handle_budget_review(args: argparse.Namespace) -> int:
    """Analyze session files and print a budget recommendation.

    Args:
        args: Parsed argparse.Namespace with:
            - sessions: Number of recent sessions to analyze (default 10)
            - profile: Profile level to compare against (default "medium")
            - session_dir: Path to session directory (default ~/.hermes/sessions/)

    Returns:
        Exit code (0 on success, 1 on error).
    """
    session_dir = _expand_path(args.session_dir)

    if not session_dir.exists():
        print(f"Error: session directory does not exist: {session_dir}", file=sys.stderr)
        return 1

    try:
        current_level: ProfileLevel = args.profile
        get_profile(current_level)  # validate profile exists
    except KeyError:
        valid = ", ".join(PRESET_ORDER)
        print(f"Error: invalid profile '{args.profile}'. Valid levels: {valid}", file=sys.stderr)
        return 1

    # Parse session signals — limit to last N files for performance
    try:
        all_json = sorted(session_dir.glob("*.json"))
        limit = args.sessions if args.sessions and args.sessions > 0 else 10
        recent_files = all_json[-limit:]
        signals = []
        for f in recent_files:
            signals.extend(parse_session_file(f))
    except Exception as e:
        print(f"Error reading session files: {e}", file=sys.stderr)
        return 1

    # Produce recommendation
    recommendation = recommend(signals, current_level)

    # Human-readable output
    print(f"Budget Review")
    print(f"  Profile compared: {current_level}")
    print(f"  Signals analyzed: {recommendation.signals_used}")
    print(f"  Current profile: {recommendation.current_profile}")
    print(f"  Recommended profile: {recommendation.recommended_profile}")
    print(f"  Confidence: {recommendation.confidence:.0%}")
    print()
    print(f"Reasoning:")
    print(f"  {recommendation.reasoning}")
    print()
    print(f"Recommended settings:")
    print(f"  main_turns: {recommendation.main_turns}")
    print(f"  subagent_turns: {recommendation.subagent_turns}")

    if recommendation.axis_overrides:
        print(f"  axis_overrides:")
        for key, value in recommendation.axis_overrides.items():
            print(f"    {key}: {value}")

    return 0


def handle_budget_set(args: argparse.Namespace) -> int:
    """Write a budget profile to the config file.

    Args:
        args: Parsed argparse.Namespace with:
            - profile: Profile level to set (required positional arg)
            - config: Path to config file (default ~/.config/hermes/config.yaml)
            - role: List of (role, turns) tuples for role overrides
            - dry_run: If True, only show what would change (default True)
            - confirm: If True, actually write the config (default False)

    Returns:
        Exit code (0 on success, 1 on error).
    """
    config_path = _expand_path(args.config)

    # Validate profile
    try:
        level: ProfileLevel = args.profile
        get_profile(level)  # validate profile exists
    except KeyError:
        valid = ", ".join(PRESET_ORDER)
        print(f"Error: invalid profile '{args.profile}'. Valid levels: {valid}", file=sys.stderr)
        return 1

    # Build role_overrides dict from --role arguments
    role_overrides = None
    if args.role:
        role_overrides = dict(args.role)

    dry_run = not args.confirm

    result = set_profile(config_path, level, role_overrides=role_overrides, dry_run=dry_run)

    if dry_run:
        print(f"Dry-run: would write profile '{level}' to {config_path}")
    else:
        print(f"Wrote profile '{level}' to {config_path}")

    if result["changes"]:
        print(f"Changes:")
        for key, value in result["changes"].items():
            print(f"  {key}: {value}")
    else:
        print("No changes needed (config already matches).")

    return 0


def add_budget_review_subparser(subparsers) -> argparse.ArgumentParser:
    """Add the budget-review subcommand to an argparse subparsers group."""
    parser = subparsers.add_parser(
        "budget-review",
        help="Analyze recent sessions and print a budget recommendation",
    )
    parser.add_argument(
        "--sessions",
        type=int,
        default=10,
        help="Number of recent sessions to analyze (default: 10)",
    )
    parser.add_argument(
        "--profile",
        default="medium",
        help="Profile level to compare against (default: medium)",
    )
    parser.add_argument(
        "--session-dir",
        default="~/.hermes/sessions/",
        help="Path to session directory (default: ~/.hermes/sessions/)",
    )
    return parser


def add_budget_set_subparser(subparsers) -> argparse.ArgumentParser:
    """Add the budget-set subcommand to an argparse subparsers group."""
    parser = subparsers.add_parser(
        "budget-set",
        help="Write a budget profile to the config file",
    )
    parser.add_argument(
        "profile",
        help="Profile level to set (e.g., low, low-medium, medium, medium-high, high)",
    )
    parser.add_argument(
        "--config",
        default="~/.config/hermes/config.yaml",
        help="Path to config file (default: ~/.config/hermes/config.yaml)",
    )
    parser.add_argument(
        "--role",
        nargs=2,
        action="append",
        metavar=("ROLE", "TURNS"),
        help="Role turn budget override (can repeat), e.g., --role implement 150",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be written without modifying the file (default)",
    )
    group.add_argument(
        "--confirm",
        action="store_true",
        help="Actually write the config file",
    )
    return parser
