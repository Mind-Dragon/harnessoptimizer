# Hermes Optimizer — v1.1 Working Plan

**Status:** Active working plan for the Hermes runtime hygiene pass.

---

## Goal

Make Hermes sessions start cleanly and stay honest:
- no blank providers
- no duplicate providers
- no stale aliases
- no stale embedded endpoint/key fields on canonical providers
- no hidden re-seeding of removed credentials
- no false claim that Hermes is healthy when gateway or CLI health is broken

---

## Current scope

Hermes Optimizer v1.1 focuses on four things:

1. provider registry cleanup
2. explicit gateway and CLI health checks
3. invalid new-session data detection
4. suppression of removed credential sources so they do not come back through a hidden auto-seed path

This version is Hermes-only. OpenClaw and OpenCode remain later work.

---

## Canonical provider rule

Canonical providers are env-backed.

For canonical providers:
- `base_url` comes from env/config resolution, not stale embedded model fields
- `api_key` comes from env/config resolution, not stale embedded model fields
- `model.base_url` and `model.api_key` are stripped if they still appear in config
- duplicate canonical entries in a user-defined `providers:` block are collapsed away
- conflicting provider-specific env overrides are treated as stale inputs for the canonical path

---

## Credential suppression rule

When a credential source is deliberately removed:
- mark it as suppressed
- do not re-import it from the same source until explicitly re-enabled
- keep suppression state in auth metadata
- do not silently resurrect it because another tool still has a token

This specifically protects removed copilot credentials from being re-seeded by `gh auth token`.

---

## Repository map

- `src/hermesoptimizer/catalog.py` — SQLite schema and CRUD
- `src/hermesoptimizer/report/` — JSON and Markdown output
- `src/hermesoptimizer/sources/` — Hermes-specific source readers
- `src/hermesoptimizer/verify/` — live health / endpoint verification helpers
- `src/hermesoptimizer/run_standalone.py` — CLI entry point
- `src/hermesoptimizer/sources/hermes_runtime.py` — runtime scanning and canary handling
- `tests/` — regression and smoke tests
- `VERSION1.1.md` — version-specific rules and acceptance criteria
- `TODO.md` — execution queue

---

## Implementation tracks

### Track A: provider registry cleanup

- locate every source of provider aliases
- identify duplicates, blanks, and stale aliases
- collapse canonical providers to one entry each
- remove stale embedded endpoint/key fields from canonical providers

### Track B: health gating

- verify gateway health live
- verify Hermes CLI health live
- treat gateway and CLI as separate signals
- fail loudly if either is unhealthy

### Track C: invalid session data

- detect malformed bootstrap data
- classify it separately from auth or endpoint failures
- prevent bad state from being reused in the next session

### Track D: regression tests

- add tests for provider cleanup
- add tests for gateway/CLI checks
- add tests for credential suppression
- add a live smoke check for a fresh clean session

---

## Verification rule

A change is not done until:
- the relevant tests pass
- a fresh Hermes session looks clean
- the report explains what was inspected
- the runtime evidence matches the docs
