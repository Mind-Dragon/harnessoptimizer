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

## Phase B — Add extension management commands ✅ COMPLETE

- [x] Add unified CLI group or top-level commands for extension lifecycle
  - [x] `hermesoptimizer ext-list`
  - [x] `hermesoptimizer ext-status`
  - [x] `hermesoptimizer ext-verify <id|all>`
  - [x] `hermesoptimizer ext-sync <id|all>`
  - [x] `hermesoptimizer ext-doctor`
- [x] `ext-list`
  - [x] prints registry entries with type and ownership
- [x] `ext-status`
  - [x] compares repo source vs installed/runtime target
  - [x] shows `ok`, `missing`, `drifted`, `external`, `blocked`
- [x] `ext-verify`
  - [x] runs the verification contract for one or more extensions
- [x] `ext-sync`
  - [x] copies or renders repo-managed artifacts to their install targets
  - [x] supports dry-run first
  - [x] fail-closed for destructive or external-only targets
- [x] `ext-doctor`
  - [x] summarizes missing deps, broken links, stale install paths, and config drift

Verification:
- [x] `PYTHONPATH=src python -m hermesoptimizer ext-list`
- [x] `PYTHONPATH=src python -m hermesoptimizer ext-status`
- [x] `PYTHONPATH=src python -m hermesoptimizer ext-doctor`

## Phase C — Caveman as a managed extension ✅ COMPLETE

- [x] Register caveman in the extension registry
- [x] Define caveman verification contract
  - [x] config key exists / is readable
  - [x] CLI toggle still works
  - [x] compression guardrails still hold
- [x] Add caveman drift checks
  - [x] config key present but module missing
  - [x] module present but config invalid
  - [x] skill/install references stale
- [x] Decide whether the caveman skill should be synced from repo truth or explicitly marked external/manual
  - Decision: skill is marked external_runtime in `extensions/skills.yaml`; caveman config is repo_external. The skill is generated at runtime and not synced from repo canonical copies.

Verification:
- [x] `PYTHONPATH=src python -m hermesoptimizer caveman`
- [x] focused caveman tests still pass
- [x] extension status reports caveman cleanly

## Phase D — Dreams sidecar and cron-linked artifacts ✅ COMPLETE

- [x] Register dreams repo module plus external scripts as one managed extension family
- [x] Add status checks for:
  - [x] `~/.hermes/dreams/memory_meta.db` presence/readability
  - [x] expected external scripts under `~/.hermes/scripts/`
  - [x] known cron-linked reflection surfaces
- [x] Decide safe sync policy
  - [x] repo code syncable
  - [x] external scripts syncable if repo owns canonical copies
  - [x] cron entries verify-only unless explicitly updated
- [x] Add a report for "repo owns this but machine is missing it"

Verification:
- [x] `PYTHONPATH=src python -m hermesoptimizer dreams-sweep --help`
- [x] extension doctor reports dreams family accurately on a machine with and without the external artifacts

## Phase E — Vault plugins and sidecar health ✅ COMPLETE

- [x] Register `HermesPlugin`, `OpenClawPlugin`, and `OpenCodePlugin`
- [x] Add verification for each plugin class
  - [x] importability
  - [x] status shape
  - [x] read-only/read-write contract
- [x] Add sidecar-specific checks for `OpenClawPlugin`
  - [x] startup health
  - [x] auth token expectations
  - [x] port binding/status behavior
- [x] Add config-generation checks for `OpenCodePlugin`

Verification:
- [x] vault plugin tests pass
- [x] extension doctor shows per-plugin health and capability type

## Phase F — Tool-surface and recommendation surface governance ✅ COMPLETE

- [x] Register tool-surface command layer as a managed extension family
- [x] Verify command/help contracts stay aligned with the registry
- [x] Add drift detection for repo help text vs actual command availability
- [x] Add a check that placeholder text does not reappear on shipped command surfaces

Verification:
- [x] `provider-recommend`, `report-latest`, `dreams-inspect`, `workflow-list` all verify through the extension manager

## Phase G — Tests, docs, and release surface ✅ COMPLETE

- [x] Add focused tests
  - [x] `tests/test_extensions_registry.py` (covered by test_extensions_integration.py)
  - [x] `tests/test_extensions_commands.py`
  - [x] `tests/test_extensions_sync.py`
  - [x] `tests/test_extensions_verify_contracts.py`
  - [x] `tests/test_extensions_drift.py`
- [x] Update docs
  - [x] `README.md` extension-management section
  - [x] `ARCHITECTURE.md` extension registry / lifecycle section
  - [x] `ROADMAP.md` next-version wording
- [x] Add an operator recipe for fresh-machine sync and drift repair
  - [x] `docs/EXTENSIONS.md`

Verification:
- [x] focused extension tests pass
- [x] full suite passes
- [x] `git diff --check` clean

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
