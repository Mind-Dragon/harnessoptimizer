# Hermes Optimizer

Current release: v0.4.0.

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
| `hermesoptimizer run` | Discover, parse, diagnose, and report |
| `hermesoptimizer export` | Write JSON and Markdown reports from the catalog |
| `hermesoptimizer todo` | Create, list, and freeze workflow plans |
| `hermesoptimizer devdo` | Execute frozen plans with subagent orchestration |
| `hermesoptimizer dodev` | Alias for `devdo` |

## Architecture

```
src/hermesoptimizer/
  __main__.py             CLI dispatch for run / todo / devdo / dodev
  run_standalone.py       analysis pipeline and catalog export commands
  run_hermes_mode.py      Hermes-specific runtime entry point
  loop.py                 discover -> diagnose -> report loop
  catalog.py              SQLite schema and CRUD
  agent_management.py     agent truth and routing helpers
  sources/                Hermes source readers and provider catalogs
    hermes_*.py           Hermes config, logs, sessions, auth, runtime
    provider_truth.py     ProviderTruthStore and model validation
    model_catalog.py      Provider-model catalog (OpenAI, Anthropic, Google, Qwen, etc.)
  verify/endpoints.py     Live endpoint and model validation
  validate/               normalizer and lane validators
  route/diagnosis.py      routing diagnosis and fallback-chain detection
  report/                 JSON, Markdown, metrics, and issues
  workflow/               /todo and /devdo workflow engine
    schema.py             WorkflowPlan, WorkflowRun, WorkflowTask dataclasses
    store.py              YAML persistence with locking
    guard.py              runtime guard (preflight, boundary, drift-repair)
    scheduler.py          task DAG, role pools, batch computation
    executor.py           execution state machine
    plan_shaper.py        plan quality validation and default task generation
    ux_format.py          terminal-friendly output rendering
  commands/               workflow command implementations
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
- `GUIDELINE.md` -- success rules and release gates
- `ROADMAP.md` -- current version plan from v0.1.0 through v0.8.0+
- `VERSION0.4.md` / `PLAN.md` -- historical transition notes for the current 0.4 release line
- `docs/WORKFLOW.md` -- operator guide for /todo and /devdo
- `TODO.md` -- current execution queue

## What this is not

- not a generic catalog scraper
- not a multi-harness rewrite
- not a place to silently mutate config
- not a system that calls a session healthy when the runtime evidence says otherwise

## License

MIT
