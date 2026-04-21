# Hermes Optimizer Test Plan — v0.9.0

## Status

Active. Canonical test strategy. Updated for v0.9.0 budget-tuning module.

## Baseline (updated 2026-04-19)

|| Metric | Value |
||--------|-------|
|| Repo path | `/home/agent/hermesoptimizer` |
|| Python path | `src` (set in `pyproject.toml`) |
|| Collected tests | 1,534 |
|| Skipped | 5 |
|| Non-skipped green | 1,528 |
|| Test files | 75 |
|| Pytest config | `pyproject.toml [tool.pytest.ini_options]` |
|| Default flags | `-q` |

## Design rules

### 1. Deterministic by default

Default gates run without live network. Fixtures, temp dirs, and checked-in catalogs first. Live lookup is opt-in behind `HERMES_LIVE_TRUTH_ENABLED=1`.

### 2. No live-state mutation

- Never touch production `~/.vault`
- Never depend on live Hermes gateway restart/reconfigure
- Never use the operator's real `HERMES_HOME` for smoke tests
- All vault tests use repo-local `tmp/.vault` fixtures or `tmp_path`

### 3. Isolate installed artifacts

Anything under `~/.hermes/skills/` or `~/.hermes/scripts/` needs its own smoke layer in a temp `HERMES_HOME` sandbox. These are not in-repo unit-testable modules.

### 4. One failure → one layer

If a test fails, the domain + layer is immediately obvious. No ambiguity between schema, business logic, filesystem integration, plugin contract, or CLI behavior.

### 5. Fail-fast policy

Lower-layer failures stop the gate first. Unit failures are not masked by higher-layer smoke passes.

---

## Test layers

| Layer | Purpose | Network | State | Speed |
|-------|---------|---------|-------|-------|
| L0 | Static/import/schema checks | No | No | Fastest |
| L1 | Deterministic unit tests | No | Temp only | Fast |
| L2 | Component integration | No | Temp files/DBs | Medium |
| L3 | Plugin + installed-artifact smoke | Loopback only | Isolated `HERMES_HOME` | Medium |
| L4 | Release-gate CLI/workflow smoke | No | Temp only | Slowest |

### Layer assignments by file

#### L0 — static/import/schema (1 file, 40 tests)

| File | Tests | Domain |
|------|-------|--------|
| `tests/test_tool_surface_schema.py` | 40 | D |

#### L1 — deterministic unit (47 files, 875 tests)

**Domain A — Core analysis**

| File | Tests | Layer |
|------|-------|-------|
| `tests/test_discover.py` | 18 | L1 |
| `tests/test_inventory.py` | 14 | L1 |
| `tests/test_sources.py` | 2 | L1 |
| `tests/test_catalog.py` | 3 | L1 |
| `tests/test_diagnosis.py` | 43 | L1 |
| `tests/test_loop.py` | 40 | L1 |
| `tests/test_validator.py` | 2 | L1 |
| `tests/test_router.py` | 2 | L1 |
| `tests/test_routing_diagnosis.py` | 6 | L1 |
| `tests/test_reports.py` | 18 | L1 |
| `tests/test_run_standalone.py` | 38 | L1 |
| `tests/test_e2e_workflow.py` | 21 | L2 |

**Domain B — Provider/model/config repair**

| File | Tests | Layer |
|------|-------|-------|
| `tests/test_provider_truth.py` | 12 | L1 |
| `tests/test_provider_truth_rework.py` | 20 | L1 |
| `tests/test_provider_catalog.py` | 44 | L1 |
| `tests/test_provider_model_refresh.py` | 35 | L1 |
| `tests/test_catalog_refresh.py` | 33 | L1 |
| `tests/test_model_catalog.py` | 34 | L1 |
| `tests/test_model_validation_rework.py` | 28 | L1 |
| `tests/test_provider_management.py` | 40 | L1 |
| `tests/test_config_fix.py` | 24 | L1 |

**Domain C — Workflow orchestration**

| File | Tests | Layer |
|------|-------|-------|
| `tests/test_workflow_schema.py` | 10 | L1 |
| `tests/test_workflow_store.py` | 10 | L1 |
| `tests/test_todo_shaper.py` | 22 | L1 |
| `tests/test_scheduler.py` | 23 | L1 |
| `tests/test_guard.py` | 21 | L1 |
| `tests/test_devdo_executor.py` | 27 | L1 |
| `tests/test_ux_format.py` | 13 | L1 |
| `tests/test_commands.py` | 18 | L1 |

**Domain D — Tool-surface layer**

| File | Tests | Layer |
|------|-------|-------|
| `tests/test_tool_surface_registry.py` | 15 | L1 |
| `tests/test_tool_surface_audit.py` | 44 | L1 |
| `tests/test_tool_surface_presentation.py` | 97 | L1 |
| `tests/test_tool_surface_commands.py` | 31 | L1 |
| `tests/test_tool_surface_chain.py` | 30 | L1 |
| `tests/test_tool_surface_provider_recommend.py` | 34 | L1 |

**Domain E — Vault core + write-back safety**

| File | Tests | Layer |
|------|-------|-------|
| `tests/test_vault_inventory.py` | 16 | L1 |
| `tests/test_vault_classify.py` | 13 | L1 |
| `tests/test_vault_classify_entries.py` | 8 | L1 |
| `tests/test_vault_fingerprint.py` | 12 | L1 |
| `tests/test_vault_crypto.py` | 10 | L1 |
| `tests/test_vault_validator.py` | 4 | L1 |
| `tests/test_vault_broader_sources.py` | 13 | L1 |
| `tests/test_vault_docling.py` | 13 | L1 |
| `tests/test_vault_audit.py` | 7 | L1 |
| `tests/test_vault_writeback_plan.py` | 9 | L1 |
| `tests/test_vault_writeback_exec.py` | 11 | L1 |
| `tests/test_vault_writeback_cli.py` | 11 | L1 |
| `tests/test_vault_rotation_hooks.py` | 39 | L1 |
| `tests/test_vault_providers.py` | 15 | L1 |
| `tests/test_vault_providers_http.py` | 11 | L1 |
| `tests/test_vault_session.py` | 13 | L1 |
| `tests/test_vault_conversion.py` | 12 | L1 |
| `tests/test_vault_regex_filter.py` | 10 | L1 |

**Domain F — Plugin-backed surfaces**

| File | Tests | Layer |
|------|-------|-------|
| `tests/test_vault_plugins.py` | 16 | L1 |
| `tests/test_vault_integration.py` | 5 | L1 |
| `tests/test_plugin_deep.py` | 29 | L1 |

**Domain G — Dreams sidecar**

| File | Tests | Layer |
|------|-------|-------|
| `tests/test_dreams_memory_meta.py` | 20 | L1 |
| `tests/test_dreams_decay.py` | 20 | L1 |
| `tests/test_dreams_sweep.py` | 22 | L1 |
| `tests/test_dreams_fidelity.py` | 17 | L1 |
| `tests/test_dreams_recall.py` | 29 | L1 |

**Domain H — Caveman mode**

| File | Tests | Layer |
|------|-------|-------|
| `tests/test_caveman.py` | 20 | L1 |
| `tests/test_caveman_config.py` | 12 | L1 |

**Domain I — Agent management**

| File | Tests | Layer |
|------|-------|-------|
| `tests/test_agent_management.py` | 7 | L1 |

**Domain J — Budget tuning**

| File | Tests | Layer |
|------|-------|-------|
| `tests/test_budget_profile.py` | 58 | L1 |
| `tests/test_budget_analyzer.py` | 16 | L1 |
| `tests/test_budget_recommender.py` | 22 | L1 |
| `tests/test_budget_tuner.py` | 18 | L1 |
| `tests/test_budget_cli.py` | 20 | L2 |
| `tests/test_budget_watch.py` | 17 | L1 |

#### L2 — component integration (4 files, 31 tests)

| File | Tests | Domain |
|------|-------|--------|
| `tests/test_caveman_cli.py` | 2 | H |
| `tests/test_smoke_workflow.py` | 8 | C |
| `tests/test_cli_smoke.py` | 1 | C |

#### L3 — plugin + installed-artifact smoke (2 files, 25 tests)

| File | Tests | Domain |
|------|-------|--------|
| `tests/test_installed_artifacts.py` | 12 | F + G |
| `tests/test_lane_a_smoke.py` | 24 | All (integration) |

`test_lane_a_smoke.py` — Lane A smoke: copies real `~/.hermes` to sandbox, redacts auth, runs full pipeline against real-shaped data. Catches bugs invisible to fixture tests (e.g., dict-vs-string error fields in session files).

Coverage:
- Installed script artifacts (dreaming_reflection_context.py, supermemory_store.js) — existence + validity
- Installed skill artifacts (dreaming skill) — directory structure + content
- HERMES_HOME sandbox isolation — env resolution, dir creation
- Plugin cross-compatibility — sanity checks for temp-vault fixtures
- Lane A discovery — config, sessions, logs found in sandboxed real HERMES_HOME
- Lane A pipeline — discover→parse→enrich→rank→report completes on real data
- Lane A real config — providers present, auth redacted, session/log sampling
- Lane A CLI — init-db→add-record→export on data derived from real config

#### L4 — release-gate smoke (covered by full-suite gate)

The repo-wide `python3 -m pytest -q` serves as the L4 gate. No separate L4 files needed beyond the L2 smoke files above.

---

## Domain coverage matrix

### A. Core analysis and reporting (139 tests)

Modules: `sources/`, `catalog.py`, `loop.py`, `validate/`, `route/`, `report/`

| File | Tests | Key surfaces |
|------|-------|-------------|
| `test_discover.py` | 18 | Path discovery, config location resolution |
| `test_inventory.py` | 14 | Path inventory normalization, dedup |
| `test_sources.py` | 2 | Source reader dispatch |
| `test_catalog.py` | 3 | SQLite CRUD, schema round-trip |
| `test_diagnosis.py` | 43 | Error extraction, finding grouping, dedup |
| `test_loop.py` | 40 | discover→parse→diagnose→enrich→rank→report pipeline |
| `test_validator.py` | 2 | Input validation |
| `test_router.py` | 2 | Route dispatch |
| `test_routing_diagnosis.py` | 6 | Lane-aware diagnosis ranking |
| `test_reports.py` | 18 | JSON/Markdown export, actionability |
| `test_run_standalone.py` | 38 | CLI entrypoint, internal helpers, vault commands |
| `test_e2e_workflow.py` | 21 | Full pipeline discover→report, multi-source inventories |

**v0.8.1 focus**: Report output must prove actionability, not just serialization. Keep selectors explicit.

Selector:
```
python3 -m pytest tests/test_discover.py tests/test_inventory.py tests/test_sources.py tests/test_catalog.py tests/test_diagnosis.py tests/test_loop.py tests/test_validator.py tests/test_router.py tests/test_routing_diagnosis.py tests/test_reports.py -q
```

### B. Provider/model/config repair (270 tests)

Modules: `sources/provider_truth.py`, `verify/endpoints.py`, `verify/config_fix.py`, `verify/provider_management.py`

| File | Tests | Key surfaces |
|------|-------|-------------|
| `test_provider_truth.py` | 12 | ProviderTruthStore CRUD, canonical names |
| `test_provider_truth_rework.py` | 20 | Reworked truth store, env resolution |
| `test_provider_catalog.py` | 44 | Provider catalog loading, model lists |
| `test_provider_model_refresh.py` | 35 | Live model refresh, merge logic |
| `test_catalog_refresh.py` | 33 | Catalog refresh pipeline |
| `test_model_catalog.py` | 34 | Model catalog CRUD, capabilities |
| `test_model_validation_rework.py` | 28 | RKWE detection, deprecated model flags |
| `test_provider_management.py` | 40 | Dedupe, canonical collapse, fallback hygiene |
| `test_config_fix.py` | 24 | Config repair, stale field stripping |

**v0.8.1 focus**: Deterministic catalogs are the default. Live lookup separated. Recommendation/routing failures attributable by subdomain.

Selector:
```
python3 -m pytest tests/test_provider_truth.py tests/test_provider_truth_rework.py tests/test_provider_catalog.py tests/test_provider_model_refresh.py tests/test_catalog_refresh.py tests/test_model_catalog.py tests/test_model_validation_rework.py tests/test_provider_management.py tests/test_config_fix.py -q
```

### C. Workflow orchestration (153 tests)

Modules: `workflow/schema.py`, `workflow/store.py`, `workflow/guard.py`, `workflow/scheduler.py`, `workflow/executor.py`, `workflow/plan_shaper.py`, `workflow/ux_format.py`, `commands/todo_cmd.py`, `commands/devdo_cmd.py`

| File | Tests | Key surfaces |
|------|-------|-------------|
| `test_workflow_schema.py` | 10 | Dataclass contracts, serialization |
| `test_workflow_store.py` | 10 | YAML persistence, load/save round-trip |
| `test_todo_shaper.py` | 22 | Plan quality validation, default task generation |
| `test_scheduler.py` | 23 | DAG construction, batch computation, role pools |
| `test_guard.py` | 21 | Preflight, boundary, drift-repair checks |
| `test_devdo_executor.py` | 27 | State machine, dispatch, complete, block, resume |
| `test_ux_format.py` | 13 | Terminal output formatting |
| `test_commands.py` | 18 | Command parsing, alias routing (dodev→devdo) |
| `test_smoke_workflow.py` | 8 | End-to-end workflow smoke |
| `test_cli_smoke.py` | 1 | CLI entrypoint smoke |

**v0.8.1 focus**: Frozen-plan contract explicit. Resume/checkpoint and boundary failures separated from unit logic. CLI alias paths covered.

Selector:
```
python3 -m pytest tests/test_workflow_schema.py tests/test_workflow_store.py tests/test_todo_shaper.py tests/test_scheduler.py tests/test_guard.py tests/test_devdo_executor.py tests/test_ux_format.py tests/test_commands.py tests/test_smoke_workflow.py tests/test_cli_smoke.py -q
```

### D. Tool-surface layer (291 tests)

Modules: `tool_surface/schema.py`, `tool_surface/registry.py`, `tool_surface/findings.py`, `tool_surface/audit.py`, `tool_surface/presentation.py`, `tool_surface/commands.py`, `tool_surface/chain.py`, `tool_surface/provider_recommend.py`

| File | Tests | Key surfaces |
|------|-------|-------------|
| `test_tool_surface_schema.py` | 40 | Schema contracts, shape validation |
| `test_tool_surface_registry.py` | 15 | Registry CRUD, read-only vs mutating flags |
| `test_tool_surface_audit.py` | 44 | Audit engine, finding generation |
| `test_tool_surface_presentation.py` | 97 | Rendering contracts, output formatting |
| `test_tool_surface_commands.py` | 31 | Command parsing, help, recovery hints |
| `test_tool_surface_chain.py` | 30 | Chain parsing, multi-step flows |
| `test_tool_surface_provider_recommend.py` | 34 | Provider/model recommendation ranking |

**v0.8.1 focus**: Behavior-first checks over shape-only. Plugin-backed vs read-only distinctions explicit in registry. Transcript-oriented recovery/help/error-path tests.

Selector:
```
python3 -m pytest tests/test_tool_surface_schema.py tests/test_tool_surface_registry.py tests/test_tool_surface_audit.py tests/test_tool_surface_presentation.py tests/test_tool_surface_commands.py tests/test_tool_surface_chain.py tests/test_tool_surface_provider_recommend.py -q
```

### E. Vault core + write-back safety (227 tests)

Modules: `vault/inventory.py`, `vault/classify.py`, `vault/fingerprint.py`, `vault/crypto.py`, `vault/validator.py`, `vault/bridge.py`, `vault/rotation.py`, `vault/providers/`, `vault/session.py`

| File | Tests | Key surfaces |
|------|-------|-------------|
| `test_vault_inventory.py` | 16 | Inventory build, entry discovery |
| `test_vault_classify.py` | 13 | Entry classification, type detection |
| `test_vault_classify_entries.py` | 8 | Per-entry classification edge cases |
| `test_vault_fingerprint.py` | 12 | 20-char fingerprint generation, collision checks |
| `test_vault_crypto.py` | 10 | ChaCha20-Poly1305, Argon2id KDF |
| `test_vault_validator.py` | 4 | Entry validation rules |
| `test_vault_broader_sources.py` | 13 | Non-standard source parsing |
| `test_vault_docling.py` | 13 | OCR/DOCX/PDF credential parsing |
| `test_vault_audit.py` | 7 | Vault audit, health scoring |
| `test_vault_writeback_plan.py` | 9 | Write-back plan generation (planning only) |
| `test_vault_writeback_exec.py` | 11 | Write-back execution against fixtures |
| `test_vault_writeback_cli.py` | 11 | CLI write-back commands |
| `test_vault_rotation_hooks.py` | 39 | Key rotation, credential lifecycle |
| `test_vault_providers.py` | 15 | Provider credential mapping |
| `test_vault_providers_http.py` | 11 | HTTP provider credential flows |
| `test_vault_session.py` | 13 | VaultSession CRUD, atomic writes |
| `test_vault_conversion.py` | 12 | Vault format conversion, dry-run mode |
| `test_vault_regex_filter.py` | 10 | Configurable regex credential detection |

**v0.8.1 focus**: No production vault mutation. Docling-dependent tests isolated when OCR missing. Write-back planning separated from execution. Conversion and regex filter tests as first-class surfaces.

Selector:
```
python3 -m pytest tests/test_vault_inventory.py tests/test_vault_classify.py tests/test_vault_classify_entries.py tests/test_vault_fingerprint.py tests/test_vault_crypto.py tests/test_vault_validator.py tests/test_vault_broader_sources.py tests/test_vault_docling.py tests/test_vault_audit.py tests/test_vault_writeback_plan.py tests/test_vault_writeback_exec.py tests/test_vault_writeback_cli.py tests/test_vault_rotation_hooks.py tests/test_vault_providers.py tests/test_vault_providers_http.py tests/test_vault_session.py tests/test_vault_conversion.py tests/test_vault_regex_filter.py -q
```

### F. Plugin-backed surfaces (21 tests)

Modules: `vault/plugins/base.py`, `vault/plugins/hermes_plugin.py`, `vault/plugins/openclaw_plugin.py`, `vault/plugins/opencode_plugin.py`

| File | Tests | Key surfaces |
|------|-------|-------------|
| `test_vault_plugins.py` | 16 | Per-plugin contract, cross-plugin consistency |
| `test_vault_integration.py` | 5 | Integration flows, shared temp vault |
| `test_plugin_deep.py` | 29 | Deep plugin contract, cross-plugin edge cases |
| `test_installed_artifacts.py` | 12 | Installed script/skill smoke, sandbox isolation, plugin fixture sanity |

**v0.8.1 focus**: This is its own matrix, not a vault footnote. Verify: (1) per-plugin contract, (2) cross-plugin consistency on shared temp vault, (3) read-only vs mutating boundaries, (4) installed-artifact presence and structure in sandbox. HTTP auth for OpenClaw sidecar.

Selector:
```
python3 -m pytest tests/test_vault_plugins.py tests/test_vault_integration.py -q
```

### G. Dreams sidecar (108 tests)

Modules: `dreams/memory_meta.py`, `dreams/decay.py`, `dreams/sweep.py`, `dreams/fidelity.py`, `dreams/recall.py`

| File | Tests | Key surfaces |
|------|-------|-------------|
| `test_dreams_memory_meta.py` | 20 | Sidecar SQLite, metadata CRUD |
| `test_dreams_decay.py` | 20 | Exponential decay scoring, tier classification |
| `test_dreams_sweep.py` | 22 | Sweep logic, keep/demote/prune decisions |
| `test_dreams_fidelity.py` | 17 | Structured tier storage, best_representation |
| `test_dreams_recall.py` | 29 | Session parsing, recall_log fallback, reheating |

**v0.8.1 focus**: Sidecar-only guarantees. Installed-script/skill smoke tests separate from in-repo unit logic.

Selector:
```
python3 -m pytest tests/test_dreams_memory_meta.py tests/test_dreams_decay.py tests/test_dreams_sweep.py tests/test_dreams_fidelity.py tests/test_dreams_recall.py -q
```

### H. Caveman mode (34 tests)

Modules: `caveman/`

| File | Tests | Key surfaces |
|------|-------|-------------|
| `test_caveman.py` | 20 | Compression logic, safety guardrails |
| `test_caveman_cli.py` | 2 | CLI toggle entrypoint |
| `test_caveman_config.py` | 12 | Persistent config, enable/disable |

**v0.8.1 focus**: In-repo logic stays as-is. Add installed-skill smoke in temp `HERMES_HOME` for the shipped skill that lives outside the repo.

Selector:
```
python3 -m pytest tests/test_caveman.py tests/test_caveman_cli.py tests/test_caveman_config.py -q
```

### I. Agent management (7 tests)

Modules: `agent_management.py`

| File | Tests | Key surfaces |
|------|-------|-------------|
| `test_agent_management.py` | 7 | AgentProfile, HermesAgentRegistry, role→model mapping |

Selector:
```
python3 -m pytest tests/test_agent_management.py -q
```

---

## Domain totals

| Domain | Description | Files | Tests |
|--------|-------------|-------|-------|
| A | Core analysis + reporting | 10 | 139 |
| B | Provider/model/config repair | 9 | 270 |
| C | Workflow orchestration | 10 | 153 |
| D | Tool-surface layer | 7 | 291 |
| E | Vault core + write-back | 18 | 227 |
| F | Plugin-backed surfaces | 4 | 46 |
| G | Dreams sidecar | 5 | 108 |
| H | Caveman mode | 3 | 34 |
| I | Agent management | 1 | 7 |
| **Total** | | **67** | **1,275** |

---

## Installed-artifact smoke strategy

These artifacts are operationally important but live outside the repo:

| Artifact | Installed path | Smoke approach |
|----------|---------------|----------------|
| Caveman skill | `~/.hermes/skills/caveman/` | Temp `HERMES_HOME`, assert file exists + trigger text |
| Vault workflow skill | `~/.hermes/skills/vault-workflow/` | Temp `HERMES_HOME`, assert entrypoint runs `--help` |
| Dreaming scripts | `~/.hermes/scripts/dreaming_*.py` | Temp `HERMES_HOME`, assert importable |
| Dreaming skill | `~/.hermes/skills/dreaming/` | Temp `HERMES_HOME`, assert file exists |

Pattern:
1. Create temp `HERMES_HOME`
2. Seed minimum files for the target smoke
3. Assert artifact exists or skip clearly if absent
4. Run narrowest possible check
5. Never touch operator's real `~/.hermes`

---

## Release gates

### Fast gate (local iteration)

```
git diff --check
python3 -m pytest <touched-domain-selector> -q
```

Pick the selector for the domain you touched.

### Medium gate (before merging a workstream)

```
git diff --check
python3 -m pytest <touched-domain-selector> -q
python3 -m pytest tests/test_vault_plugins.py tests/test_vault_integration.py -q   # if touching vault/plugins
python3 -m pytest tests/test_smoke_workflow.py tests/test_cli_smoke.py -q          # if touching workflow/CLI
```

### Full gate (before closing v0.8.1)

```
git diff --check
python3 -m pytest -q
test -f VERSION0.8.0.md
test -f .hermes/reports/hermesoptimizer/archive/v0.8.0/v0.8-tool-surface-evaluation-2026-04-19.md
test -f .hermes/reports/hermesoptimizer/archive/v0.8.0/v0.8-kickoff-2026-04-18.md
test -f .hermes/reports/hermesoptimizer/archive/v0.8.0/atoolix-hermes-v0.8-evaluation-2026-04-18.md
git status --short
```

---

## Failure policy

| Failure type | Action |
|-------------|--------|
| L0/L1 deterministic test | Stop there. Fix before proceeding. Do not mask with higher-layer passes. |
| L2 integration test | Check if it's a contract mismatch between modules or a fixture regression. |
| L3 plugin test | Identify: direct Python path? HTTP sidecar? Cross-plugin consistency? |
| L3 installed-artifact | Report as environment/setup issue, not core regression. Skip clearly if absent. |
| L4 smoke | Full gate blocked. Trace back through layers. |

---

## v0.8.1 planned additions

1. **Dedicated installed-artifact smoke tests** under temp `HERMES_HOME` for caveman skill, vault workflow skill, dreaming scripts/skills
2. **Transcript-oriented tool-surface tests** — prove recovery/help/error-path behavior, not just shapes
3. **Explicit pytest markers** for `@pytest.mark.plugin`, `@pytest.mark.smoke`, `@pytest.mark.installed_artifact` to enable selector-based gating
4. **Clearer skip policy** for optional dependencies (docling/OCR) — xfail when deps missing, skip when env absent
5. **Plugin matrix expansion** — per-plugin deep tests and cross-plugin consistency on shared fixtures

---

## Selector cheat sheet

Full copy-paste selectors by domain:

**All domains (full gate):**
```
python3 -m pytest -q
```

**Domain A — Core analysis (10 files, 139 tests):**
```
python3 -m pytest tests/test_discover.py tests/test_inventory.py tests/test_sources.py tests/test_catalog.py tests/test_diagnosis.py tests/test_loop.py tests/test_validator.py tests/test_router.py tests/test_routing_diagnosis.py tests/test_reports.py -q
```

**Domain B — Provider/model/config (9 files, 270 tests):**
```
python3 -m pytest tests/test_provider_truth.py tests/test_provider_truth_rework.py tests/test_provider_catalog.py tests/test_provider_model_refresh.py tests/test_catalog_refresh.py tests/test_model_catalog.py tests/test_model_validation_rework.py tests/test_provider_management.py tests/test_config_fix.py -q
```

**Domain C — Workflow (10 files, 153 tests):**
```
python3 -m pytest tests/test_workflow_schema.py tests/test_workflow_store.py tests/test_todo_shaper.py tests/test_scheduler.py tests/test_guard.py tests/test_devdo_executor.py tests/test_ux_format.py tests/test_commands.py tests/test_smoke_workflow.py tests/test_cli_smoke.py -q
```

**Domain D — Tool-surface (7 files, 291 tests):**
```
python3 -m pytest tests/test_tool_surface_schema.py tests/test_tool_surface_registry.py tests/test_tool_surface_audit.py tests/test_tool_surface_presentation.py tests/test_tool_surface_commands.py tests/test_tool_surface_chain.py tests/test_tool_surface_provider_recommend.py -q
```

**Domain E — Vault (18 files, 227 tests):**
```
python3 -m pytest tests/test_vault_inventory.py tests/test_vault_classify.py tests/test_vault_classify_entries.py tests/test_vault_fingerprint.py tests/test_vault_crypto.py tests/test_vault_validator.py tests/test_vault_broader_sources.py tests/test_vault_docling.py tests/test_vault_audit.py tests/test_vault_writeback_plan.py tests/test_vault_writeback_exec.py tests/test_vault_writeback_cli.py tests/test_vault_rotation_hooks.py tests/test_vault_providers.py tests/test_vault_providers_http.py tests/test_vault_session.py tests/test_vault_conversion.py tests/test_vault_regex_filter.py -q
```

**Domain F — Plugins (4 files, 46 tests):**
```
python3 -m pytest tests/test_vault_plugins.py tests/test_vault_integration.py tests/test_installed_artifacts.py tests/test_lane_a_smoke.py -q
```

**Domain G — Dreams (5 files, 108 tests):**
```
python3 -m pytest tests/test_dreams_memory_meta.py tests/test_dreams_decay.py tests/test_dreams_sweep.py tests/test_dreams_fidelity.py tests/test_dreams_recall.py -q
```

**Domain H — Caveman (3 files, 34 tests):**
```
python3 -m pytest tests/test_caveman.py tests/test_caveman_cli.py tests/test_caveman_config.py -q
```

**Domain I — Agent management (1 file, 7 tests):**
```
python3 -m pytest tests/test_agent_management.py -q
```

**Domain J — Budget tuning (6 files, 151 tests):**
```
python3 -m pytest tests/test_budget_profile.py tests/test_budget_analyzer.py tests/test_budget_recommender.py tests/test_budget_tuner.py tests/test_budget_cli.py tests/test_budget_watch.py -q
```

---

## Source of truth

| Document | Role |
|----------|------|
| `TESTPLAN.md` | This file. Canonical test strategy, layers, selectors, coverage matrix |
| `TODO.md` | Active execution queue for v0.8.1 |
| `VERSION0.8.1.md` | Version goal, scope, release gate |
| `VERSION0.8.0.md` | Archived v0.8.0 completed queue |
| `GUIDELINE.md` | Success rules, release gates, workflow contracts |
| `ARCHITECTURE.md` | System shape, module boundaries, data flow |
| `ROADMAP.md` | Broader release sequence |
