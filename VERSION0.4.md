# Hermes Optimizer Release 0.4

## Current reality

This is the archived v0.4.0 release note:
- `pyproject.toml` pins the package at `0.4.0`
- `src/hermesoptimizer/__init__.py` exposes `__version__ = "0.4.0"`
- `CHANGELOG.md` records v0.4.0 as the workflow-engine release
- the full test suite passes (`332` tests)

The old hygiene story in this repo is already shipped. It is represented by the v0.2.0 and v0.3.0 work, and the `/todo` + `/devdo` workflow engine is already shipped in v0.4.0.

This document is therefore not a promise of unfinished work. It is the transition note that says what is actually true now and what the next path should be.

## What the codebase actually has today

### Shipped
- canonical SQLite catalog and report export
- Hermes runtime hygiene and provider cleanup
- provider-model catalog and routing diagnosis
- `/todo` planning workflow
- `/devdo` execution workflow
- `/dodev` alias
- workflow schema, store, guard, scheduler, executor, and UX formatting
- checkpoint/resume and two-stage review plumbing
- working tests for the shipped workflow stack

### Not shipped yet
- credential inventory and vault lifecycle management
- OpenClaw adapter work
- OpenCode adapter work
- cross-harness correlation
- real subagent dispatch/fan-out beyond the current workflow state machinery
- the v0.5.0+ roadmap items below

## The clear path forward

The next real implementation path from the current codebase is:

1. v0.5.0 — vault management and credential lifecycle
2. v0.6.0 — OpenClaw gateway and config diagnosis
3. v0.7.0 — OpenCode agent config and provider routing
4. v0.8.0+ — cross-harness correlation and adapter template

That is the path the codebase is actually on. The old 0.4 hygiene label should not be reused for work that is already complete.

## v0.5.0 target slice

If the repo is moving forward from the current shipped state, the next concrete slice is v0.5.0.

### v0.5.0 must answer
- which credentials exist across configured vault locations
- which are active, expired, stale, or duplicated
- when each credential was last rotated
- which location is canonical for each provider
- whether a dormant provider should be cleaned up

### v0.5.0 acceptance criteria
- credential inventory is complete across all configured sources
- live validation marks keys correctly as active or expired
- duplicate detection identifies same-key different-location entries
- rotation tracking records change events without storing plaintext
- vault bridge writes back to at least `.env` and YAML formats when explicitly enabled
- all credential metadata uses fingerprints, not full secrets
- existing vault files are never modified unless write-back is explicitly enabled
- tests cover discovery, validation, dedup, rotation, and bridge without real API keys

## Non-goals
- do not relabel shipped v0.4.0 workflow work as unfinished 0.4.0 work
- do not pretend the current repository still needs the `/todo` + `/devdo` engine
- do not treat this archived note as the active release line; use `VERSION0.5.md` for the vault-prep release line
- do not skip directly to adapter work before the vault layer is cleanly defined

## Decision log

- Historical release line: `0.4.0`
- Historical workflow engine status: shipped
- Historical 0.4 hygiene status: already satisfied by shipped work
- Next build target: `v0.5.0` vault management
