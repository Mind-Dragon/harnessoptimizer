from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print("Usage: python -m hermesoptimizer <command> [args]")
        print("Commands: run, todo, devdo, dodev, caveman, budget-review, budget-set,")
        print("          vault-audit, vault-writeback, export, init-db, add-record,")
        print("          add-finding, list-records, list-findings")
        return 1

    command = args[0]
    rest = args[1:]

    if command == "run":
        from hermesoptimizer.run_standalone import main as run_main
        return run_main(rest)

    if command == "caveman":
        from hermesoptimizer.caveman import toggle, is_enabled
        new_state = toggle()
        state_str = "ON" if new_state else "OFF"
        print(f"caveman mode: {state_str}")
        return 0

    if command in ("todo", "devdo", "dodev"):
        if command == "dodev":
            command = "devdo"
        _handle_workflow_command(command, rest)
        return 0

    # Delegate unknown commands (like init-db, add-record, etc.) to run_standalone
    from hermesoptimizer.run_standalone import main as run_main
    return run_main()


def _handle_workflow_command(command: str, args: list[str]) -> None:
    """Handle /todo and /devdo commands with basic CLI arg parsing."""
    base = Path(".")

    if command == "todo":
        from hermesoptimizer.commands.todo_cmd import create_plan, list_plans, freeze_plan
        if not args or args[0] == "list":
            plans = list_plans(base_dir=base)
            for p in plans:
                print(f"  {p.workflow_id}  {p.status:10s}  {p.objective}")
        elif args[0] == "freeze" and len(args) > 1:
            plan = freeze_plan(args[1], base_dir=base)
            print(f"Plan {plan.workflow_id} frozen.")
        else:
            objective = " ".join(args) if args else "Untitled plan"
            plan = create_plan(objective=objective, base_dir=base)
            print(f"Created plan {plan.workflow_id}: {plan.objective}")

    elif command == "devdo":
        from hermesoptimizer.commands.devdo_cmd import start_run, load_run_state
        if not args:
            print("Usage: devdo <workflow_id>")
            return
        wf_id = args[0]
        try:
            run = start_run(wf_id, base_dir=base)
        except ValueError as e:
            print(f"Cannot start: {e}")
            return
        plan, run, tasks = load_run_state(wf_id, base_dir=base)
        print(f"Plan: {plan.objective}")
        print(f"Run:  {run.run_id} ({run.status})")
        print(f"Tasks: {len(tasks)}")
        print(f"Next:  {plan.next_action}")


if __name__ == "__main__":
    raise SystemExit(main())
