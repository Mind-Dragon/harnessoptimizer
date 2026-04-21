# Harness Optimizer /todo — v1.0.0 Extension Lifecycle and Plugin Management

Current package version: `0.9.1`
Current focus: turn the repo's plugin-like surfaces into a managed system instead of a pile of code + manual side effects.

This plan treats these as first-class managed extensions:
- Caveman mode config and prompt/output behavior
- Dreams sidecar modules, scripts, and cron-linked reflection flow
- Vault plugins (`HermesPlugin`, `OpenClawPlugin`, `OpenCodePlugin`)
- Tool-surface command layer / provider recommender
- External repo-owned install targets under `~/.hermes/` such as skills, scripts, and future sidecars

Goal: one source of truth for what this repo owns, where it installs, how to validate it, and how to repair drift.

---

## Problem statement

Right now the repo contains several extension-like systems, but there is no single manager for them.

Examples:
- Caveman state lives in `~/.hermes/config.yaml`
- Dreams has repo code plus external scripts/cron surfaces
- Vault plugins exist in code, but their runtime/install state is not centrally audited
- Skills such as caveman live outside the repo install path
- Some extension surfaces are verified only indirectly through tests, not through a repo-level lifecycle command

That makes three things harder than they should be:
- onboarding a fresh machine
- detecting drift between repo truth and installed/runtime truth
- evolving extension surfaces without breaking unrelated commands

---

## Phase A — Extension registry (swarm-structured) ✅ COMPLETE

Design principle: one file per extension, schema-first, waves not linear checklist.

- [x] Wave 1 — Foundation
  - [x] Define registry schema in `src/hermesoptimizer/extensions/schema.py`
    - [x] ExtensionEntry dataclass: id, type, source_path, target_paths, verify_command, ownership, description
    - [x] ExtensionType enum: config, skill, script, cron, vault_plugin, sidecar, command_surface
    - [x] Ownership enum: repo_only, repo_external, external_runtime
  - [x] Define loader in `src/hermesoptimizer/extensions/loader.py`
    - [x] load_extension_file(path) → ExtensionEntry
    - [x] load_registry(directory) → list[ExtensionEntry]
    - [x] validate_registry(entries) → raises on duplicate id / missing required fields
  - [x] Define output directory: `extensions/` (one YAML file per extension)
  - [x] Add validation guards:
    - [x] Duplicate ID guard
    - [x] Missing required field guard
    - [x] Source path existence guard (optional, warn not fail)

- [x] Wave 2 — Parallel registration (one file per extension)
  - [x] Register caveman → `extensions/caveman.yaml`
  - [x] Register dreams → `extensions/dreams.yaml`
  - [x] Register vault plugins → `extensions/vault_plugins.yaml`
  - [x] Register tool-surface → `extensions/tool_surface.yaml`
  - [x] Register scripts → `extensions/scripts.yaml`
  - [x] Register external skills → `extensions/skills.yaml`
  - [x] Register cron surfaces → `extensions/cron.yaml`

- [x] Wave 3 — Integration
  - [x] Load all extension files into combined registry view
  - [x] Add `ext-list` CLI command
  - [x] Verify no duplicate IDs across all files

- [x] Wave 4 — Dry-run and checkpoint
  - [x] Add `ext-doctor --dry-run` that validates registry without touching runtime
  - [x] Add checkpoint persistence for registry state

Verification:
- [x] `PYTHONPATH=src python -m pytest tests/test_extensions_schema.py tests/test_extensions_loader.py -q`
- [x] `PYTHONPATH=src python -m hermesoptimizer ext-list`
- [x] Registry loads with all 7 current extension surfaces

## Phase B — Add extension management commands

- [ ] Add unified CLI group or top-level commands for extension lifecycle
  - [ ] `hermesoptimizer ext-list`
  - [ ] `hermesoptimizer ext-status`
  - [ ] `hermesoptimizer ext-verify <id|all>`
  - [ ] `hermesoptimizer ext-sync <id|all>`
  - [ ] `hermesoptimizer ext-doctor`
- [ ] `ext-list`
  - [ ] prints registry entries with type and ownership
- [ ] `ext-status`
  - [ ] compares repo source vs installed/runtime target
  - [ ] shows `ok`, `missing`, `drifted`, `external`, `blocked`
- [ ] `ext-verify`
  - [ ] runs the verification contract for one or more extensions
- [ ] `ext-sync`
  - [ ] copies or renders repo-managed artifacts to their install targets
  - [ ] supports dry-run first
  - [ ] fail-closed for destructive or external-only targets
- [ ] `ext-doctor`
  - [ ] summarizes missing deps, broken links, stale install paths, and config drift

Verification:
- [ ] `PYTHONPATH=src python -m hermesoptimizer ext-list`
- [ ] `PYTHONPATH=src python -m hermesoptimizer ext-status`
- [ ] `PYTHONPATH=src python -m hermesoptimizer ext-doctor`

## Phase C — Caveman as a managed extension

- [ ] Register caveman in the extension registry
- [ ] Define caveman verification contract
  - [ ] config key exists / is readable
  - [ ] CLI toggle still works
  - [ ] compression guardrails still hold
- [ ] Add caveman drift checks
  - [ ] config key present but module missing
  - [ ] module present but config invalid
  - [ ] skill/install references stale
- [ ] Decide whether the caveman skill should be synced from repo truth or explicitly marked external/manual

Verification:
- [ ] `PYTHONPATH=src python -m hermesoptimizer caveman`
- [ ] focused caveman tests still pass
- [ ] extension status reports caveman cleanly

## Phase D — Dreams sidecar and cron-linked artifacts

- [ ] Register dreams repo module plus external scripts as one managed extension family
- [ ] Add status checks for:
  - [ ] `~/.hermes/dreams/memory_meta.db` presence/readability
  - [ ] expected external scripts under `~/.hermes/scripts/`
  - [ ] known cron-linked reflection surfaces
- [ ] Decide safe sync policy
  - [ ] repo code syncable
  - [ ] external scripts syncable if repo owns canonical copies
  - [ ] cron entries verify-only unless explicitly updated
- [ ] Add a report for "repo owns this but machine is missing it"

Verification:
- [ ] `PYTHONPATH=src python -m hermesoptimizer dreams-sweep --help`
- [ ] extension doctor reports dreams family accurately on a machine with and without the external artifacts

## Phase E — Vault plugins and sidecar health

- [ ] Register `HermesPlugin`, `OpenClawPlugin`, and `OpenCodePlugin`
- [ ] Add verification for each plugin class
  - [ ] importability
  - [ ] status shape
  - [ ] read-only/read-write contract
- [ ] Add sidecar-specific checks for `OpenClawPlugin`
  - [ ] startup health
  - [ ] auth token expectations
  - [ ] port binding/status behavior
- [ ] Add config-generation checks for `OpenCodePlugin`

Verification:
- [ ] vault plugin tests pass
- [ ] extension doctor shows per-plugin health and capability type

## Phase F — Tool-surface and recommendation surface governance

- [ ] Register tool-surface command layer as a managed extension family
- [ ] Verify command/help contracts stay aligned with the registry
- [ ] Add drift detection for repo help text vs actual command availability
- [ ] Add a check that placeholder text does not reappear on shipped command surfaces

Verification:
- [ ] `provider-recommend`, `report-latest`, `dreams-inspect`, `workflow-list` all verify through the extension manager

## Phase G — Tests, docs, and release surface

- [ ] Add focused tests
  - [ ] `tests/test_extensions_registry.py`
  - [ ] `tests/test_extensions_commands.py`
  - [ ] `tests/test_extensions_sync.py`
- [ ] Update docs
  - [ ] `README.md` extension-management section
  - [ ] `ARCHITECTURE.md` extension registry / lifecycle section
  - [ ] `ROADMAP.md` next-version wording
- [ ] Add an operator recipe for fresh-machine sync and drift repair

Verification:
- [ ] focused extension tests pass
- [ ] full suite passes
- [ ] `git diff --check` clean

---

## Acceptance criteria

- `hermesoptimizer` can list, verify, and doctor all repo-owned extension surfaces
- Caveman, dreams, vault plugins, and tool-surface commands are all represented in one registry
- repo truth vs installed/runtime truth can be compared without manual grep
- sync behavior is explicit, dry-runnable, and safe for external targets
- docs explain what is repo-managed versus external-runtime-managed

## Non-goals for this slice

- rewriting Hermes core plugin architecture
- silently mutating cron jobs or user config without explicit action
- forcing every external artifact to become repo-synced if it is intentionally machine-local
