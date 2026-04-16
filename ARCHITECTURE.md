# Hermes Optimizer Architecture

## What this system is

Hermes Optimizer is a small analysis core plus a set of source adapters.

This architecture doc describes the current release line; the numbered sections below track the release path, not the package version.

The core does four things:
- stores normalized records in SQLite
- stores findings in SQLite
- exports reports
- keeps the analysis model shared across harnesses

The adapters do the harness-specific work:
- discover config, session, log, database, and runtime paths
- parse those sources
- extract errors and action items
- enrich provider and model data from live sources
- classify and rank optimizations
- verify runtime health when a harness exposes a live status surface

## The big idea

The project is not a one-off log parser.
It is a harness intelligence layer.

That means every version uses the same rule:
1. find the source of truth on disk or in the runtime
2. compare it to live provider or runtime truth when health and identity matter
3. normalize the evidence
4. rank what should change
5. report it in a way a human can act on

## Versioned scope

### v0.1.0 — Hermes analysis baseline

Hermes v0.1.0 is the first adapter because it is local, structured, and the fastest way to prove the system.

Hermes v0.1.0 reads:
- `~/.hermes/config.yaml`
- `~/.hermes/logs/`
- `~/.hermes/sessions/`
- Hermes-local databases and caches that store recent state

It detects:
- config drift
- stale provider names
- session failures
- auth failures
- retries and stalls
- recurring noise that hides actual problems

It outputs:
- raw evidence
- grouped findings
- prioritized optimizations
- provider/model lookup results when a model name or endpoint needs validation

### v0.2.0 — Hermes runtime hygiene and provider cleanup

v0.2.0 hardens the Hermes adapter so a new session starts cleanly and stays honest.

The adapter must inspect:
- gateway health
- CLI status
- provider registry entries
- session bootstrap data
- config integrity
- logs that show blank providers, duplicate providers, stale aliases, auth failures, or endpoint failures

Canonical providers are env-backed:
- `base_url` comes from config/env resolution, not stale embedded model fields
- `api_key` comes from env resolution, not stale embedded model fields
- any `model.base_url` or `model.api_key` that still appears in config is treated as stale and stripped before reuse
- if a canonical provider is duplicated in a user-defined `providers:` block, the canonical entry wins and the duplicate is collapsed away
- provider-specific env overrides that conflict with canonical routing are treated as stale inputs for the canonical path

The key v0.2.0 problem class is the misleading one:
- the gateway is up, but the CLI state is stale
- or the CLI looks fine, but the gateway is unhealthy
- or the provider key is valid, but the alias list is polluted with duplicates or blanks
- or the session is new, but it inherited invalid data from stale state
- or a removed credential reappears because another source re-seeded it

### v0.3.0 — Provider-model catalog, model validation, and agent management

v0.3.0 adds a canonical provider-model catalog and thorough model validation.

The adapter must:
- maintain a `ProviderTruthStore` with known providers, canonical endpoints, known models, deprecated models, and capabilities
- validate configured model names against the known model list for each provider
- flag deprecated models explicitly
- detect right-key-wrong-endpoint (RKWE) errors by comparing the configured endpoint against the canonical endpoint
- handle auth failures separately from model-not-found errors, with escalation for OAuth providers
- run routing diagnosis to map failures to lanes and rank them by priority

Provider truth record shape:
```
ProviderTruthRecord:
  provider: str                  # canonical provider name
  canonical_endpoint: str         # correct base URL for this provider
  known_models: list[str]        # models confirmed to exist and be supported
  deprecated_models: list[str]   # models confirmed to be deprecated or EOL
  capabilities: list[str]        # e.g. text, vision, embedding, rerank, speech, image, video
  context_window: int             # max context in tokens (0 if unknown)
  source_url: str | None         # URL used to fetch live truth (optional)
  confidence: str                # high, medium, low
  auth_type: str | None          # e.g. oauth, api_key
```

Model validation result statuses:
- OK: endpoint and model both verified
- RKWE: correct key, wrong endpoint (shows canonical endpoint)
- STALE_MODEL: model not in known list
- DEPRECATED_MODEL: model in deprecated list
- UNKNOWN_PROVIDER: provider not in truth store
- AUTH_FAILURE: live endpoint returned 401/403 (escalates to human for OAuth)
- NETWORK_ERROR: endpoint unreachable
- FAILED: general failure

Routing diagnosis priority order:
- CRITICAL: auth failure on a lane's primary provider; timeouts with 3+ retries
- IMPORTANT: auth failure on a fallback provider; timeouts with fewer than 3 retries
- GOOD_IDEA: stale model name or deprecated model in config
- NICE_TO_HAVE: minor configuration improvements
- WHATEVER: low-confidence or speculative findings

Special provider notes for v0.3.0:
- Qwen / Alibaba: qwen3.6-plus is the current recommended model for the qwen family
- Alibaba has vision, rerank, embedding, speech, image, and video capabilities (some with CN or region scope constraints)
- Kimi (moonshot-v1 family) is aliased from kimi, kimi-for-coding, kimi-coding, kimi-coding-cn
- OpenAI codex aliases to openai

Live truth gate:
- `HERMES_LIVE_TRUTH_ENABLED=1` enables live lookups from `source_url` in truth records
- live truth is merged with local truth, preserving local metadata when the live source omits fields
- the gate is off by default so tests and CI runs are deterministic

### v0.6.0 — OpenClaw gateway and config diagnosis

OpenClaw adds a gateway and more direct provider plumbing.

That means the adapter must inspect:
- gateway health
- config integrity
- provider profiles
- plugin allowlists and entries
- logs that show auth or endpoint failures

### v0.7.0 — OpenCode provider routing and worktree behavior

OpenCode adds another layer of agent config and provider mapping.

The adapter must understand:
- provider registry entries
- model aliases
- auth file locations
- worktree or runtime metadata
- task or agent failures that are not actually provider failures

### Later versions

Future harnesses should only need:
- a new adapter
- a path inventory
- parsers
- a live truth check if applicable
- the shared ranking and reporting pipeline

## Data flow

1. Discover files and runtime sources.
2. Read config, session, log, cache, and database files.
3. Check gateway and CLI status when the harness exposes them.
4. Extract errors and action items.
5. Normalize provider aliases and deduplicate repeated signals.
6. Enrich model, endpoint, and runtime details from live sources and the provider truth store.
7. Run routing diagnosis to map findings to lanes and rank by priority.
8. Assign a priority bucket.
9. Save normalized records and findings.
10. Export reports.
11. Re-check health after a repair or config change.

## Priority model

Use five buckets:
- critical: broken or dangerous
- important: likely to cause real problems soon
- good ideas: worthwhile improvements
- nice to have: polish
- whatever: low confidence or speculative

This matters because not every issue should be fixed immediately.
The goal is to separate fire from friction.

## Source-of-truth rules

For provider names, runtime health, and endpoint details, prefer live truth over local memory.

Use this hierarchy:
1. live gateway or CLI status
2. provider website, docs, or endpoint list
3. local config and runtime files
4. cloned docs or cached text

If the live status and local config disagree, that is not a contradiction to ignore.
That is the failure signal.

## Why live lookup matters

Some provider pages lag behind runtime reality.
Some aliases exist in old configs but are invalid in the current registry.
Some endpoints are reachable but point at stale or unsupported routes.

So the architecture allows multiple lookup methods:
- standard search engines
- live browser sessions
- provider docs
- provider API or model listings
- Hermes CLI and gateway status commands
- the provider truth store (canonical, versioned, testable)

The system should treat those as evidence sources, not as interchangeable copies.

## Repository structure

- `src/hermesoptimizer/catalog.py` — SQLite schema and CRUD
- `src/hermesoptimizer/sources/` — harness-specific source readers
- `src/hermesoptimizer/verify/endpoints.py` — live status and endpoint verification helpers, model validation, RKWE detection
- `src/hermesoptimizer/sources/provider_truth.py` — ProviderTruthStore, canonical provider names, model validation helpers
- `src/hermesoptimizer/route/diagnosis.py` — RoutingDiagnosis, Recommendation, priority ranking, broken fallback chain detection
- `src/hermesoptimizer/report/` — JSON and Markdown export
- `src/hermesoptimizer/run_hermes_mode.py` — Hermes entry point
- `src/hermesoptimizer/run_standalone.py` — CLI entry point
- `src/hermesoptimizer/loop.py` — Phase 0/1 loop with discover -> parse -> diagnose -> enrich -> rank -> report -> verify -> repeat

## Design constraints

- never mutate config silently
- keep raw evidence alongside normalized findings
- keep harness adapters independent
- keep the report format stable across versions
- make it easy to add new adapters without rewriting the core
- keep health checks explicit, named, and verifiable
- keep the live truth gate off by default for deterministic test behavior
- do not claim global availability for CN-only or region-restricted models

## Practical interpretation

What you mean by this project is:

"Build a system that watches the harnesses we use to run Hermes work, learns where their real files and real health surfaces live, validates that the configured models are actually supported by the provider, detects when they are misconfigured or stale, and recommends the smallest useful fix in priority order."

The slightly more operational version is:

"Stop guessing at where the config lives, stop trusting stale provider aliases, stop treating endpoint mistakes like auth problems, stop using models that are deprecated or not in the provider's catalog, and make the tool tell us what to change first."

## Workflow state system

### Workflow modules

- `workflow/schema.py` — Dataclasses for WorkflowPlan, WorkflowRun, WorkflowTask, WorkflowCheckpoint, WorkflowBlocker
- `workflow/store.py` — YAML persistence with load/save/validate round-trips
- `workflow/guard.py` — Runtime guard with preflight, boundary, and drift-repair checks
- `workflow/scheduler.py` — Task DAG construction, dependency depth, batch computation, role pools
- `workflow/executor.py` — Execution state machine with dispatch, complete, block, review, resume
- `workflow/plan_shaper.py` — Plan quality validation, default task generation, blocked-plan handling
- `workflow/ux_format.py` — Terminal-friendly formatted output for /todo handoff and /devdo startup

### Command modules

- `commands/todo_cmd.py` — /todo: create, update, freeze plans, add tasks
- `commands/devdo_cmd.py` — /devdo: start runs, update tasks, record checkpoints/blockers, resolve runs
- `commands/__init__.py` — Alias routing (dodev → devdo)

### Data flow (workflow)

1. /todo creates a WorkflowPlan with status "draft"
2. /todo adds tasks and validates quality
3. /todo freezes the plan (status "frozen")
4. /devdo loads the frozen plan and creates a WorkflowRun
5. /devdo builds the task DAG and computes execution batches
6. /devdo dispatches tasks by role, respecting dependency order
7. Guard validates state before each write or phase transition
8. Checkpoints are appended after each meaningful milestone
9. Two-stage review runs on implementation tasks
10. Run is resolved as "completed" or "failed"

### Role pools

| Role | Max Workers | Purpose |
|------|-------------|---------|
| research | 3 | Information gathering |
| implement | 4 | Code implementation |
| test | 2 | Test writing and execution |
| review | 2 | Code review and spec compliance |
| verify | 2 | Smoke checks and live verification |
| integrate | 1 | Integration and merge |
| guardrail | 1 | Constraint and safety checking |

### Migration path

- /dodev is aliased to /devdo and will be supported until the next major version
- All existing optimizer functionality (run, report, verify) continues unchanged
- Workflow state is stored in .hermes/workflows/ and does not interfere with existing reports/
