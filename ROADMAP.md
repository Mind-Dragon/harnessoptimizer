# Hermes Optimizer Roadmap

> Goal: turn the current scaffold into a multi-harness analysis tool that starts with Hermes, then adds OpenClaw, then OpenCode, and keeps the extension point open for more harnesses later.

## Product shape

Hermes Optimizer is not one monolithic parser. It is a small core with harness-specific adapters.

Core responsibilities:
- initialize and maintain a canonical SQLite catalog
- normalize records and findings into one schema
- export JSON and Markdown reports
- run from CLI or cron
- keep raw source text for auditability

Harness adapters:
- Hermes adapter: local logs, sessions, config, runtime drift
- OpenClaw adapter: gateway health, config integrity, provider failures, plugin drift
- OpenCode adapter: agent config, provider routing, worktree/task behavior, logs
- future adapters: same shape, new source readers

## Version plan

### v1.0 — Hermes

Scope:
- ingest Hermes logs and session files
- detect failures, timeouts, auth errors, crashes, and noisy patterns
- read Hermes config and runtime metadata when available
- classify findings into stable categories and lanes
- write SQLite + JSON + Markdown outputs
- provide a CLI and cron-friendly entry point

Primary source targets:
- `~/.hermes/logs/`
- `~/.hermes/sessions/`
- `~/.hermes/config.yaml`
- any repo-local or worktree-local Hermes runtime artifacts

What v1.0 must answer:
- what failed
- where it failed
- how often it failed
- whether it looks like user error, provider failure, config drift, or infrastructure noise

Acceptance criteria:
- given a Hermes log bundle, the tool produces deterministic findings
- findings are deduplicated and normalized
- exports are generated without manual intervention
- tests cover catalog writes, Hermes source scanning, and report generation

Out of scope for v1.0:
- OpenClaw-specific logic
- OpenCode-specific logic
- remote browser or web scraping of public catalogs beyond stub interfaces
- fancy ML classification

### v1.1 — OpenClaw

Scope:
- add an OpenClaw adapter that reads gateway health and config
- detect gateway-down, auth-fail, provider-crash, clobbering, plugin drift, and stale config patterns
- pull in gateway logs and health endpoint status
- map findings into the same canonical schema used by Hermes
- add repair-oriented report sections so operators can see what needs fixing

Primary source targets:
- `~/.openclaw/openclaw.json`
- `~/.openclaw/logs/`
- gateway health endpoint and status output
- plugin allowlist / entry config

What v1.1 must answer:
- is the gateway alive
- is the config still the last known good version
- which provider is failing
- what repair action is most likely to work

Acceptance criteria:
- the OpenClaw adapter can classify the common failure matrix
- config drift is detected before repair attempts
- provider-specific failures are separated from gateway failures
- report output clearly distinguishes Hermes findings from OpenClaw findings

Out of scope for v1.1:
- mutating OpenClaw config automatically
- making provider-side remediation decisions without operator approval
- coupling OpenClaw parsing to Hermes-only assumptions

### v1.2 — OpenCode

Scope:
- add an OpenCode adapter for agent config, provider routing, and runtime behavior
- detect broken model mappings, invalid provider endpoints, and agent-level execution problems
- ingest worktree/task metadata when present
- track config drift and missing plugin or skill references
- keep the same catalog and reporting pipeline

Primary source targets:
- OpenCode config files
- OpenCode logs and task traces
- provider routing metadata
- worktree-aware runtime files

What v1.2 must answer:
- which model/provider mappings are active
- whether the agent is using valid endpoints
- whether failures are config, provider, or task orchestration problems
- whether the runtime is in a healthy state for coding work

Acceptance criteria:
- the OpenCode adapter emits the same normalized record and finding shapes as Hermes/OpenClaw
- provider and routing issues are separated from task failures
- export files can combine multiple harnesses in one run
- tests cover adapter-specific parsing plus shared normalization

Out of scope for v1.2:
- building a new agent runtime
- replacing OpenCode’s own UI or execution engine
- adding unsupported provider-specific behavior

### v1.3+ — Additional harnesses

Candidate future integrations:
- other local agent harnesses
- other CLI orchestrators
- CI or cron-driven health monitors
- platform-specific wrappers if they expose useful logs/configs

Future additions should follow one rule:
- if it can be read, normalized, and reported, it can become an adapter

## Architecture direction

The implementation should stay plugin-like even if the first versions are built in-tree.

Recommended layering:
- core catalog and report code stays shared
- each harness gets its own source adapter module
- each adapter returns the same `Finding` / `Record` style objects
- validators and reporters stay harness-agnostic
- versioned behavior is driven by adapter registration, not forks

That keeps Hermes, OpenClaw, and OpenCode from turning into three separate projects.

## Suggested delivery order

1. Finish Hermes v1.0 parsing and reporting
2. Add fixture-driven tests for Hermes sources
3. Add OpenClaw adapter and health/config probes
4. Add OpenClaw failure classification and repair hints
5. Add OpenCode adapter and config/routing parsing
6. Tighten shared normalization and reporting across all harnesses
7. Add a new adapter template so later harnesses are cheap to add

## Definition of done for the roadmap

This roadmap is done when:
- Hermes, OpenClaw, and OpenCode are all first-class adapters
- each harness has source-specific tests and shared integration tests
- the reports can compare runs across harnesses
- adding a new harness is mostly a new adapter module plus fixtures, not a rewrite
