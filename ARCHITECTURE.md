# Hermes Optimizer Architecture

## What this system is

Hermes Optimizer is a small analysis core plus a set of source adapters.

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

### v1.0 — Hermes analysis baseline

Hermes v1.0 is the first adapter because it is local, structured, and the fastest way to prove the system.

Hermes v1.0 reads:
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

### v1.1 — Hermes runtime hygiene and provider cleanup

v1.1 hardens the Hermes adapter so a new session starts cleanly and stays honest.

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

The key v1.1 problem class is the misleading one:
- the gateway is up, but the CLI state is stale
- or the CLI looks fine, but the gateway is unhealthy
- or the provider key is valid, but the alias list is polluted with duplicates or blanks
- or the session is new, but it inherited invalid data from stale state
- or a removed credential reappears because another source re-seeded it

### v1.2 — OpenClaw gateway and config diagnosis

OpenClaw adds a gateway and more direct provider plumbing.

That means the adapter must inspect:
- gateway health
- config integrity
- provider profiles
- plugin allowlists and entries
- logs that show auth or endpoint failures

### v1.3 — OpenCode provider routing and worktree behavior

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
6. Enrich model, endpoint, and runtime details from live sources.
7. Assign a priority bucket.
8. Save normalized records and findings.
9. Export reports.
10. Re-check health after a repair or config change.

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

The system should treat those as evidence sources, not as interchangeable copies.

## Repository structure

- `src/hermesoptimizer/catalog.py` — SQLite schema and CRUD
- `src/hermesoptimizer/sources/` — harness-specific source readers
- `src/hermesoptimizer/verify/` — live status and endpoint verification helpers
- `src/hermesoptimizer/report/` — JSON and Markdown export
- `src/hermesoptimizer/run_hermes_mode.py` — Hermes entry point
- `src/hermesoptimizer/run_standalone.py` — CLI entry point

## Design constraints

- never mutate config silently
- keep raw evidence alongside normalized findings
- keep harness adapters independent
- keep the report format stable across versions
- make it easy to add new adapters without rewriting the core
- keep health checks explicit, named, and verifiable

## Practical interpretation

What you mean by this project is:

"Build a system that watches the harnesses we use to run Hermes work, learns where their real files and real health surfaces live, detects when they are misconfigured or stale, and recommends the smallest useful fix in priority order."

The slightly more operational version is:

"Stop guessing at where the config lives, stop trusting stale provider aliases, stop treating endpoint mistakes like auth problems, and make the tool tell us what to change first."
