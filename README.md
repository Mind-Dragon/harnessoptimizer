<p align="center">
  <img src="assets/banner.svg" alt="Harness Optimizer" width="100%">
</p>

<h1 align="center">Harness Optimizer</h1>

<p align="center">
  <strong>Analysis, hygiene, and workflow orchestration for agent environments.</strong>
</p>

<p align="center">
  <a href="#commands">Commands</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#tests">Tests</a> ·
  <a href="#documentation">Docs</a> ·
  <a href="#license">License</a>
</p>

---

Current release: **v0.9.0**

Harness Optimizer reads agent config, sessions, logs, and runtime health surfaces. Detects what is actually wrong, ranks it, and reports it. Also provides a plan-then-execute workflow system (`/todo` + `/devdo`) for multi-agent development orchestration.

## What it does

**Analysis and hygiene:**
- discovers agent config, sessions, logs, databases, and runtime surfaces
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

**Budget tuning:**
- `budget-review` analyzes session utilization and recommends profiles
- `budget-set` applies turn-budget profiles with dry-run safety
- five-step sliding scale (low → high) with per-role overrides
- passive `budget-watch` monitor for post-session advice

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
| `hermesoptimizer budget-review` | Analyze sessions and recommend turn budgets |
| `hermesoptimizer budget-set` | Apply a budget profile to config (dry-run by default) |
| `hermesoptimizer vault-audit` | Audit vault entries, validation, dedup, and rotation state |
| `hermesoptimizer vault-writeback` | Execute write-back to vault files with `--confirm` flow |

## Architecture

```
src/hermesoptimizer/
  __main__.py             CLI dispatch
  run_standalone.py       analysis pipeline and catalog export commands
  run_hermes_mode.py      Hermes-specific runtime entry point
  loop.py                 discover → diagnose → report loop
  catalog.py              SQLite schema and CRUD
  agent_management.py     agent truth and routing helpers
  budget/                 turn-budget tuning sidecar
    profile.py            BudgetProfile presets and per-role defaults
    analyzer.py           session log signal extraction
    recommender.py        sliding-scale recommendation logic
    tuner.py              config writer (dry-run / confirm)
    commands.py           budget-review and budget-set CLI
    watch.py              passive post-session monitor
  sources/                agent source readers and provider catalogs
    hermes_*.py           config, logs, sessions, auth, runtime
    provider_truth.py     ProviderTruthStore and model validation
    model_catalog.py      provider-model catalog (OpenAI, Anthropic, Google, Qwen, etc.)
  verify/endpoints.py     live endpoint and model validation
  dreams/                 dreaming/memory sidecar (memory_meta, decay, sweep, fidelity, recall)
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

1,534 tests collected, 5 skipped. Run with:

```
pytest
```

## Documentation

- `ARCHITECTURE.md` — system shape, data flow, design constraints
- `GUIDELINE.md` — success rules and release gates
- `ROADMAP.md` — release sequence
- `TESTPLAN.md` — canonical layered test matrix, selectors, and release gates
- `CHANGELOG.md` — version history
- `docs/WORKFLOW.md` — operator guide for /todo and /devdo
- `TODO.md` — current execution queue

## What this is not

- not a generic catalog scraper
- not a multi-harness rewrite
- not a place to silently mutate config
- not a system that calls a session healthy when the runtime evidence says otherwise

## License

Apache License 2.0 with Non-Commercial Clause.

This software is licensed under the Apache License, Version 2.0, with the additional restriction that it may not be used for commercial purposes without explicit written permission. See [LICENSE](LICENSE) for full terms.
