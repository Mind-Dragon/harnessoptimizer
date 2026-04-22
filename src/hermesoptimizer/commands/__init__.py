"""Commands package for Hermes Optimizer workflow CLI."""
from hermesoptimizer.commands.devdo_cmd import (
    start_run,
    load_run_state,
    update_task_status,
    record_checkpoint,
    record_blocker,
    resolve_run,
)

COMMAND_ALIASES = {"dodev": "devdo"}
