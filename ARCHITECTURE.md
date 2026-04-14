# Hermes Optimizer Architecture

## What this system is

Hermes Optimizer is a small analysis core plus a set of source adapters.

The core does four things:
- stores normalized records in SQLite
- stores findings in SQLite
- exports reports
- keeps the analysis model shared across harnesses

The adapters do the harness-specific work:
- discover config/session/log/database paths
- parse those sources
- extract errors and action items
- enrich provider/model data from live sources
- classify and rank optimizations

## The big idea

The project is not a one-off log parser.
It is a harness intelligence layer.

That means every version uses the same rule:
1. find the source of truth on disk or in the runtime
2. compare it to live provider truth when provider details matter
3. normalize the evidence
4. rank what should change
5. report it in a way a human can act on

## Versioned scope

### v1.0 — Hermes

Hermes is the first adapter because it is local, structured, and the fastest way to prove the system.

Hermes v1.0 should read:
- `~/.hermes/config.yaml`
- `~/.hermes/logs/`
- `~/.hermes/sessions/`
- any Hermes-related databases or caches that store recent state

It should detect:
- config drift
- stale provider names
- session failures
- auth failures
- retries and stalls
- recurring noise that hides actual problems

It should output:
- raw evidence
- grouped findings
- prioritized optimizations
- provider/model lookup results when a model name or endpoint needs validation

### v1.1 — OpenClaw

OpenClaw adds a gateway and more direct provider plumbing.

That means the adapter must inspect:
- gateway health
- config integrity
- provider profiles
- plugin allowlists and entries
- logs that show auth or endpoint failures

The key OpenClaw problem class is the misleading one:
- the key is right, but the endpoint is wrong
- or the endpoint is right, but the model name is stale

### v1.2 — OpenCode

OpenCode adds another layer of agent config and provider mapping.

The adapter must understand:
- provider registry entries
- model aliases
- auth file locations
- worktree or runtime metadata
- task/agent failures that are not actually provider failures

### Later versions

Future harnesses should only need:
- a new adapter
- a path inventory
- parsers
- a provider truth check if applicable
- the shared ranking and reporting pipeline

## Data flow

1. Discover files and runtime sources.
2. Read config, session, log, cache, and database files.
3. Extract errors and action items.
4. Deduplicate repeated signals.
5. Enrich model and endpoint details from live sources.
6. Assign a priority bucket.
7. Save normalized records and findings.
8. Export reports.

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

For model names and endpoint details, prefer live truth over local memory.

Use this hierarchy:
1. provider website / docs
2. provider endpoint or model list
3. local config and runtime files
4. cloned docs or cached text

If the website and endpoint disagree, that is not a contradiction to ignore.
That is a versioning signal.

## Why browser-based lookup matters

Some providers block or distort bot scraping.
Some provider pages lag behind their APIs.
Some API surfaces know about a model before the public docs do.

So the architecture allows multiple lookup methods:
- standard search engines
- live browser sessions
- provider docs
- provider API/model listings

The system should treat those as evidence sources, not as interchangeable copies.

## Repository structure

- `src/hermesoptimizer/catalog.py` — SQLite schema and CRUD
- `src/hermesoptimizer/sources/` — harness-specific source readers
- `src/hermesoptimizer/scrape/` — external enrichment collectors
- `src/hermesoptimizer/route/` — lightweight classification and routing
- `src/hermesoptimizer/validate/` — normalization and lane assignment
- `src/hermesoptimizer/report/` — JSON and Markdown export
- `src/hermesoptimizer/run_hermes_mode.py` — Hermes entry point
- `src/hermesoptimizer/run_standalone.py` — CLI entry point

## Design constraints

- never mutate config silently
- keep raw evidence alongside normalized findings
- keep harness adapters independent
- keep the report format stable across versions
- make it easy to add new adapters without rewriting the core

## Practical interpretation

What you mean by this project is:

"Build a system that watches the harnesses we use to run Hermes work, learns where their real files and real endpoints live, detects when they are misconfigured or stale, and recommends the smallest useful fix in priority order."

That is the clean version.
The slightly more operational version is:

"Stop guessing at where the config lives, stop trusting stale model names, stop treating endpoint mistakes like auth problems, and make the tool tell us what to change first."
