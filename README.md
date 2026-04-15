# Hermes Optimizer

Analysis, hygiene, and workflow orchestration for Hermes Agent environments.

Reads Hermes config, sessions, logs, and runtime health surfaces. Detects what is actually wrong, ranks it, and reports it. Also provides a plan-then-execute workflow system (`/todo` + `/devdo`) for multi-agent development orchestration.

## What it does

**Analysis and hygiene:**
- discovers Hermes config, sessions, logs, databases, and runtime surfaces
- detects failures, auth errors, timeouts, crashes, and config drift
- validates provider endpoints and model names against live truth
- detects stale, deprecated, and misconfigured models
- diagnoses routing failures and broken fallback chains
- checks gateway health, CLI health, and provider registry integrity
- removes blank providers, collapses duplicates, strips stale embedded credentials

**Workflow orchestration:**
- `/todo` creates and freezes execution plans
- `/devdo` runs plans through parallel subagent batches
- task DAGs with dependency resolution and role pools
- two-stage review, checkpoint/resume, blocker routing
- scales to 10+ concurrent subagents

**Reports:**
- grouped findings with plain-language recommendations
- JSON and Markdown export
- inspected-inputs visibility and live health checks

## Quick start

```
pip install -e .
hermesoptimizer                    # run analysis
hermesoptimizer --help             # CLI options
```

## Commands

| Command | Purpose |
|---------|---------|
| `hermesoptimizer` | Run full analysis pipeline |
| `hermesoptimizer run` | Discover, parse, diagnose, report |
| `hermesoptimizer report` | Generate reports from catalog |
| `/todo` | Create and freeze workflow plans |
| `/devdo` | Execute frozen plans with subagent orchestration |

## Architecture

```
src/hermesoptimizer/
  catalog.py              SQLite schema and CRUD
  loop.py                 Phase 0/1 discover-report loop
  run_standalone.py       CLI entry point
  run_hermes_mode.py      Hermes entry point
  sources/                Harness-specific source readers
    hermes_*.py           Hermes config, logs, sessions, auth, runtime
    provider_truth.py     ProviderTruthStore and model validation
    model_catalog.py      Provider-model catalog (OpenAI, Anthropic, Google, Qwen, etc.)
  verify/endpoints.py     Live endpoint and model validation
  validate/               Normalizer and lane validators
  route/diagnosis.py      Routing diagnosis and fallback chain detection
  report/                 JSON, Markdown, metrics, issues
  workflow/               /todo and /devdo workflow engine
    schema.py             WorkflowPlan, WorkflowRun, WorkflowTask dataclasses
    store.py              YAML persistence with locking
    guard.py              Runtime guard (preflight, boundary, drift-repair)
    scheduler.py          Task DAG, role pools, batch computation
    executor.py           Execution state machine
    plan_shaper.py        Plan quality validation and default task generation
    ux_format.py          Terminal-friendly output rendering
  commands/               Slash command implementations
    todo_cmd.py           /todo: create, update, freeze plans
    devdo_cmd.py          /devdo: start runs, update tasks, checkpoint, resume
```

## Tests

332 tests, 0 failures. Run with:

```
pytest
```

## Documentation

- `ARCHITECTURE.md` -- system shape, data flow, design constraints
- `GUIDELINE.md` -- success rules and version gates
- `ROADMAP.md` -- version plan from v1.0 through vault management
- `docs/WORKFLOW.md` -- operator guide for /todo and /devdo
- `TODO.md` -- current execution queue

## What this is not

- not a generic catalog scraper
- not a multi-harness rewrite
- not a place to silently mutate config
- not a system that calls a session healthy when the runtime evidence says otherwise

## License

MIT
