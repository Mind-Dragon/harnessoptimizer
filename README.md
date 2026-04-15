# Hermes Optimizer

Hermes Optimizer is a Hermes-focused analysis and hygiene tool. It reads Hermes config, sessions, logs, and runtime health surfaces, then reports what is actually wrong instead of guessing.

## Current focus: v1.1

v1.1 is the runtime hygiene pass:
- no blank providers
- no duplicate providers
- no stale provider aliases
- canonical providers resolve `base_url` and `api_key` from environment variables automatically
- stale `model.base_url` and `model.api_key` fields are stripped before reuse
- gateway and CLI health are checked explicitly
- removed credential sources do not silently re-seed themselves

## What it produces

- grouped findings
- plain-language recommendations
- JSON and Markdown reports
- inspected-inputs visibility
- live health checks where the harness exposes them

## Repository layout

- `src/hermesoptimizer/` — core catalog, reporting, verification, and Hermes adapters
- `VERSION1.1.md` — current working version and cleanup rules
- `ARCHITECTURE.md` — system shape and invariants
- `GUIDELINE.md` — success rules and non-negotiables
- `PHASES.md` — phase-by-phase execution model
- `ROADMAP.md` — version plan
- `TODO.md` — current execution queue
- `PLAN.md` — implementation plan / working notes

## What this repo is not

- not a generic catalog scraper
- not a multi-harness rewrite
- not a place to silently mutate config
- not a system that calls a session healthy when the runtime evidence says otherwise
