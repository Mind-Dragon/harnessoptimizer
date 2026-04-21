# Hermes Optimizer Release 0.8.1

## Status

Completed. v0.8.1 hardened the test suite into a deliberate release gate with explicit layers, domain ownership, and plugin-backed smoke coverage.

## Goal

Turn the existing broad green suite into a deliberate release gate: one that proves core behavior, plugin-backed integrations, installed artifacts, and operator safety boundaries with clear selectors and low-flake layering.

## Why this release exists

v0.8.0 added a meaningful new surface area:
- tool-surface schema and registry
- audit engine and findings model
- presentation-layer rendering contracts
- a narrow read-only command layer
- provider/model recommendation logic

The repo already has wide coverage, but the next risk is not raw test count. The risk is blind spots:
- plugin-backed behavior that only works in one code path
- installed skills/scripts that live outside the repo and are not exercised
- smoke paths that pass unit tests but break at CLI or temp-home boundaries
- domain ownership drift where failures are hard to localize quickly

v0.8.1 fixes that by making the test strategy explicit and versioned.

## Scope

### 1. Freeze and archive v0.8.0
- preserve the completed queue as `VERSION0.8.0.md`
- move the v0.8.0 kickoff/evaluation artifacts under `.hermes/reports/hermesoptimizer/archive/v0.8.0/`
- rewrite `TODO.md` as the active v0.8.1 queue

### 2. Define a layered test model
- L0 static/import/schema checks
- L1 deterministic unit tests
- L2 component integration tests
- L3 plugin and installed-artifact smoke tests
- L4 end-to-end CLI/workflow release gates

### 3. Cover every active domain explicitly
- core discovery, inventory, sources, catalog, diagnosis, routing, validation, reports
- workflow plan/guard/scheduler/executor/CLI behavior
- tool-surface schema/audit/presentation/command/recommendation behavior
- vault discovery, parsing, crypto, validation, write-back planning/execution, rotation hooks
- dreams sidecar logic
- caveman mode
- provider/model/config repair surfaces
- plugin-backed surfaces

### 4. Separate in-repo coverage from installed-artifact coverage
Some important behavior is not fully represented by importable repo modules alone.

v0.8.1 must treat these as separate smoke surfaces:
- `HermesPlugin` — direct Python vault access
- `OpenClawPlugin` — HTTP sidecar path
- `OpenCodePlugin` — read-only config/env generation path
- caveman skill installed under `~/.hermes/skills/...`
- vault workflow skill installed under `~/.hermes/skills/...`
- dreaming scripts and skill files installed under `~/.hermes/scripts/` and `~/.hermes/skills/`

### 5. Keep safety contracts explicit
- never touch production `~/.vault` in tests
- use repo-local temp fixtures for vault data
- use isolated `HERMES_HOME` sandboxes for installed-artifact smoke tests
- keep live-network checks opt-in, not part of the default release gate
- do not restart or mutate live Hermes while testing hermesoptimizer

## Non-goals
- adding new end-user features unrelated to testability
- broad CI/vendor/platform expansion before the local release gate is coherent
- converting every integration into a live network test
- treating doc-only coverage as a substitute for real execution checks

## Release gate

v0.8.1 is done when:
- the v0.8.0 queue and reports are archived cleanly
- `TESTPLAN.md` gives a full domain/layer matrix with real selectors
- plugin-backed surfaces are covered both in temp-fixture tests and isolated smoke tests where needed
- installed skills/scripts have an explicit sandbox smoke story
- the repo-wide default gate stays green
- failures can be localized quickly by layer and domain
## Baseline carried into v0.8.1

- `python3 -m pytest -q` passes
- 1,534 tests collected
- 5 skipped
- 1,528 non-skipped tests currently green
- 76 test files currently present

## Source of truth
- `TODO.md` — active execution queue for v0.8.1
- `TESTPLAN.md` — canonical testing strategy and gate definitions
- `ROADMAP.md` — broader release sequence
- `ARCHITECTURE.md` — system boundaries and data flow
- `GUIDELINE.md` — success rules
- `VERSION0.8.0.md` — archived completed queue for the previous slice
