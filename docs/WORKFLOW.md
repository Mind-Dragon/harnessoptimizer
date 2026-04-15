# /todo + /devdo Workflow Guide

## Overview

The Hermes Optimizer now supports a two-command workflow inspired by oh-my-opencode:
- `/todo` owns planning — it creates, shapes, and freezes plans
- `/devdo` owns execution — it consumes frozen plans and orchestrates subagents

## Quick start

### 1. Create a plan
```
/todo Build user authentication with OAuth2
```

### 2. Freeze it
```
/todo freeze <workflow_id>
```

### 3. Execute it
```
/devdo <workflow_id>
```

## Commands

### /todo

| Action | Description |
|--------|-------------|
| `/todo <objective>` | Create a new draft plan |
| `/todo list` | List all plans |
| `/todo freeze <id>` | Validate and freeze a plan |
| `/todo update <id> --scope ...` | Update plan fields |

/devdo refuses to execute a plan that is not frozen.

### /devdo

| Action | Description |
|--------|-------------|
| `/devdo <workflow_id>` | Start or resume execution |
| `/dodev <workflow_id>` | Alias for /devdo |

/devdo:
- Loads the frozen plan
- Builds a task DAG from dependencies
- Schedules parallel batches
- Dispatches subagents by role
- Runs two-stage review on implementation tasks
- Checkpoints after each batch
- Resumes from the last clean checkpoint on interruption

## Task roles

Tasks are assigned one of these roles:

- **research** — Information gathering, documentation review
- **implement** — Code changes, feature implementation
- **test** — Writing and running tests
- **review** — Spec compliance and code quality review
- **verify** — Smoke tests, live checks, integration verification
- **integrate** — Merge, deploy, or integration work
- **guardrail** — Safety and constraint checking

## Guard behavior

/devdo runs a runtime guard that:
- Blocks execution if the plan is missing, not frozen, or invalid
- Blocks if the run state has a version mismatch with the plan
- Auto-repairs safe drift (version mismatch, stale guard state)
- Hard-blocks on unsafe drift (failed run, blocked guard state)

## Checkpoints and resume

/devdo writes checkpoints after:
- Task graph built
- Each batch dispatched
- Each batch completed
- Tasks blocked
- Phase transitions
- Final audit

If /devdo is interrupted:
1. Restart with `/devdo <workflow_id>`
2. It loads the last clean checkpoint
3. Skips completed tasks
4. Re-dispatches in-progress tasks
5. Continues from where it left off

## File layout

```
.hermes/workflows/<workflow_id>/
  plan.yaml         # Frozen plan from /todo
  run.yaml          # Live execution state
  tasks/
    <task_id>.yaml  # Per-task state
  checkpoints/
    history.yaml    # Append-only checkpoint log
  blockers/
    <blocker_id>.yaml  # Blocker records
  artifacts/        # Task output references
```

## Flow examples

### Normal flow
1. Create plan → freeze → execute → complete

### Blocked flow
1. Execute → task blocked → record blocker → continue unblocked → user resolves blocker → retry

### Resume flow
1. Execute → interrupted → restart → resume from checkpoint → continue

## Parallelism

/devdo can scale to 10+ concurrent subagents when the task graph has many independent tasks at the same depth level. Role pools limit parallelism per role to avoid overwhelming any one type of work.

Example: A plan with 5 independent implementation tasks and 3 independent research tasks can fan out to 4 implementers + 3 researchers = 7 concurrent subagents.

## Anti-patterns

- Do not call /devdo without a frozen plan
- Do not modify plan.yaml directly after freezing
- Do not skip the guard checks
- Do not manually delete checkpoint files
