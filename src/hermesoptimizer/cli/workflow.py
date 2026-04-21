"""Workflow command handlers extracted from __main__.py."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable


HANDLERS: dict[str, Callable[[argparse.Namespace], int]] = {}


def add_subparsers(subparsers) -> None:
    """Add subparsers for workflow commands: todo, devdo, dodev, caveman."""
    # todo command
    todo_parser = subparsers.add_parser("todo", help="Create/list/freeze plans")
    todo_parser.add_argument(
        "objective",
        nargs="*",
        help="Plan objective, or 'list' or 'freeze <id>'"
    )
    HANDLERS["todo"] = handle_todo

    # devdo command
    devdo_parser = subparsers.add_parser("devdo", help="Execute a plan")
    devdo_parser.add_argument("workflow_id", help="Workflow ID to execute")
    HANDLERS["devdo"] = handle_devdo

    # dodev is an alias for devdo
    dodev_parser = subparsers.add_parser("dodev", help="Alias for devdo", add_help=False)
    dodev_parser.add_argument("workflow_id", help="Workflow ID to execute")
    HANDLERS["dodev"] = handle_devdo

    # caveman command
    caveman_parser = subparsers.add_parser("caveman", help="Toggle caveman mode")
    HANDLERS["caveman"] = handle_caveman


def handle_todo(args: argparse.Namespace) -> int:
    """Handle todo command: create/list/freeze plans."""
    from hermesoptimizer.commands.todo_cmd import create_plan, list_plans, freeze_plan

    base = Path(".")
    objective_parts = args.objective or []

    if not objective_parts or objective_parts[0] == "list":
        plans = list_plans(base_dir=base)
        for p in plans:
            print(f"  {p.workflow_id}  {p.status:10s}  {p.objective}")
        return 0
    elif objective_parts[0] == "freeze" and len(objective_parts) > 1:
        plan = freeze_plan(objective_parts[1], base_dir=base)
        print(f"Plan {plan.workflow_id} frozen.")
        return 0
    else:
        objective = " ".join(objective_parts) if objective_parts else "Untitled plan"
        plan = create_plan(objective=objective, base_dir=base)
        print(f"Created plan {plan.workflow_id}: {plan.objective}")
        return 0


def handle_devdo(args: argparse.Namespace) -> int:
    """Handle devdo/dodev command: execute a plan."""
    from hermesoptimizer.commands.devdo_cmd import start_run, load_run_state

    base = Path(".")
    wf_id = args.workflow_id

    try:
        run = start_run(wf_id, base_dir=base)
    except ValueError as e:
        print(f"Cannot start: {e}")
        return 1

    plan, run, tasks = load_run_state(wf_id, base_dir=base)
    print(f"Plan: {plan.objective}")
    print(f"Run:  {run.run_id} ({run.status})")
    print(f"Tasks: {len(tasks)}")
    print(f"Next:  {plan.next_action}")
    return 0


def handle_caveman(args: argparse.Namespace) -> int:
    """Handle caveman command: toggle caveman mode."""
    from hermesoptimizer.caveman import toggle

    new_state = toggle()
    state_str = "ON" if new_state else "OFF"
    print(f"caveman mode: {state_str}")
    return 0
