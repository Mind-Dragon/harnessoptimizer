# Hermes Optimizer /todo — v0.8.0 Agent-Native Tool Surface Optimization

**Status: Complete.** v0.7.0 is complete; the v0.8.0 tool-surface optimization slice is also complete (tasks 1–7 all verified).

## Source of truth
- `ROADMAP.md` v0.8.0 tool-surface optimization section
- `ARCHITECTURE.md` for system shape and file layout expectations
- `GUIDELINE.md` for release gates and success criteria
- `.hermes/reports/hermesoptimizer/atoolix-hermes-v0.8-evaluation-2026-04-18.md` for the external concept audit that seeded this slice
- `.hermes/reports/hermesoptimizer/v0.8-kickoff-2026-04-18.md` for the concrete kickoff order, file-path suggestions, and verification gates

## v0.8.0 goal
Turn the atoolix/agent-clip interface ideas into a Hermes-grade, agent-native tool-surface optimization layer: auditable tool contracts, a hybrid read-only command layer, and a stronger LLM-facing presentation model without sacrificing Hermes's existing typed safety boundaries.

## Scope
- define a normalized Tool Surface IR for Hermes-native tools and command families
- score tool surfaces for discoverability, composability, safety, observability, token efficiency, and recovery quality
- prototype a read-only hybrid command namespace for provider/report/workflow/memory-or-dreams inspection flows
- support chainable command composition where it helps (`|`, `&&`, `||`, `;`)
- harden output presentation with binary/media routing, overflow handles, stderr retention, and stable result footers
- generate ranked provider/model recommendations from live config + auth + catalog + provenance data instead of static menus
- keep mutation-heavy or high-risk paths on typed tools

## Non-goals
- replacing Hermes's typed browser/filesystem/github/cron tools with a single shell-style supertool
- routing destructive writes or credential mutations through the textual command layer
- broad cross-harness rollout before the Hermes-first proof is stable

## Acceptance criteria
- a Tool Surface IR exists and can describe Hermes-native tool/command surfaces
- audits emit concrete findings for missing help, poor error navigation, missing overflow artifacts, and unsafe untyped mutation patterns
- the hybrid command layer exists for at least a few high-value read-only inspection families
- presentation-layer output preserves raw execution truth while rendering an LLM-friendly contract with status, duration, and truncation cues
- provider/model recommendation output is ranked, provenance-aware, and lane-classified
- focused tests cover the new IR, audits, command-layer parsing, and presentation behavior

## v0.8.0 queue

### 1. Tool Surface IR foundation
- create `src/hermesoptimizer/tool_surface/__init__.py`
- create `src/hermesoptimizer/tool_surface/schema.py`
- define the minimal shared types for agent-facing surfaces:
  - `SurfaceKind` (`typed`, `textual`, `hybrid`)
  - `RiskLevel`
  - `HelpContract`
  - `OutputContract`
  - `ToolSurface`
  - `CommandSurface`
- required minimum fields:
  - `surface_name`
  - `command_name`
  - `kind`
  - `risk_level`
  - `supports_help`
  - `supports_partial_discovery`
  - `supports_overflow_handle`
  - `supports_binary_guard`
  - `read_only`
  - `recommended_for_agent`
  - `notes`
- create `tests/test_tool_surface_schema.py`
- verify the schema layer first before introducing registries or scoring

### 2. Tool Surface registry
- create `src/hermesoptimizer/tool_surface/registry.py`
- map real HermesOptimizer surfaces into the IR instead of inventing toy examples
- first registry targets:
  - provider/config surfaces backed by:
    - `src/hermesoptimizer/sources/provider_truth.py`
    - `src/hermesoptimizer/verify/config_fix.py`
    - `src/hermesoptimizer/verify/provider_management.py`
    - `src/hermesoptimizer/verify/endpoints.py`
  - workflow inspection surfaces backed by:
    - `src/hermesoptimizer/workflow/schema.py`
    - `src/hermesoptimizer/workflow/store.py`
    - `src/hermesoptimizer/commands/todo_cmd.py`
    - `src/hermesoptimizer/commands/devdo_cmd.py`
  - dreams/memory inspection surfaces backed by:
    - `src/hermesoptimizer/dreams/memory_meta.py`
    - `src/hermesoptimizer/dreams/decay.py`
    - `src/hermesoptimizer/dreams/sweep.py`
    - `src/hermesoptimizer/dreams/recall.py`
  - report surfaces backed by:
    - `src/hermesoptimizer/report/markdown.py`
    - `src/hermesoptimizer/report/json_export.py`
    - `src/hermesoptimizer/report/health.py`
    - `src/hermesoptimizer/report/issues.py`
- model vault plugin surfaces only if the registry cleanly distinguishes read-only vs mutating paths
- create `tests/test_tool_surface_registry.py`
- success condition: registry emits at least 8-12 normalized entries from current HermesOptimizer surfaces

### 3. Tool audit engine
- create `src/hermesoptimizer/tool_surface/audit.py`
- create `src/hermesoptimizer/tool_surface/findings.py`
- add scoring buckets:
  - discoverability
  - composability
  - safety
  - observability
  - token_efficiency
  - recovery_quality
- emit concrete finding kinds rather than prose-only judgments, starting with:
  - `tool-help-missing-subcommand-usage`
  - `tool-error-missing-next-step`
  - `tool-output-no-overflow-path`
  - `tool-binary-routing-weak`
  - `tool-surface-high-risk-untyped-mutation`
- create `tests/test_tool_surface_audit.py`
- keep the first audit engine fixture-driven and deterministic

### 4. Presentation-layer hardening
- create `src/hermesoptimizer/tool_surface/presentation.py`
- separate raw execution truth from LLM-facing rendering
- add explicit support for:
  - stable footer with status, duration, and truncation metadata
  - overflow artifact handles for large output
  - stderr retention on failure
  - next-step navigation hints for large/failing output
  - binary/media routing based on content, not just file extension
- create `tests/test_tool_surface_presentation.py`
- keep this module reusable by later command-layer and audit outputs

### 5. Hybrid read-only command layer
- create `src/hermesoptimizer/tool_surface/commands.py`
- create `src/hermesoptimizer/tool_surface/chain.py`
- create `tests/test_tool_surface_commands.py`
- create `tests/test_tool_surface_chain.py`
- keep the first command namespace deliberately narrow and read-only
- initial command families should come from the current source of truth:
  - `provider list`
  - `provider recommend`
  - `workflow list`
  - `dreams inspect`
  - `report latest`
- support composition operators only where deterministic and testable:
  - `|`
  - `&&`
  - `||`
  - `;`
- do not route destructive or credential-mutating actions through this layer
- help behavior must be progressive:
  - top-level list
  - command usage
  - subcommand-specific usage

### 6. Provider/model recommender
- create `src/hermesoptimizer/tool_surface/provider_recommend.py`
- create `tests/test_tool_surface_provider_recommend.py`
- replace atoolix-style static picker ergonomics with a Hermes-grade recommender using:
  - live config evidence
  - known auth presence
  - checked-in provider endpoint/model catalogs
  - provenance information
  - safety lane logic
- output contract should include:
  - ranked recommendations
  - reason strings
  - lane classification
  - config snippet generation only after validation
- reuse existing provider fixtures where possible instead of creating parallel truth sets

### 7. Evaluation and proof
- add focused tests for every new contract before broad integration
- add transcript-oriented checks that show the new contracts reduce dead-end retries or improve recovery hints
- prove at least one real audit output against current HermesOptimizer surfaces
- prove at least one real command/help/error path from the hybrid read-only namespace
- keep the slice measurable rather than purely architectural

### 8. Verification gates
- per sub-slice:
  - targeted tests for the touched files
  - `git diff --check`
- after slices 1-3:
  - one auditable report or fixture output showing the registry + audit engine scoring real HermesOptimizer surfaces
- after slices 4-5:
  - one read-only command flow with working progressive help and deterministic chained behavior
- after slice 6:
  - one provider/model recommendation example grounded in existing provider truth data
- global gate throughout:
  - `python3 -m pytest -q` stays green

### 9. Execution order
- implement in this order:
  1. Tool Surface IR foundation
  2. Tool Surface registry
  3. Tool audit engine
  4. Presentation-layer hardening
  5. Hybrid read-only command layer
  6. Provider/model recommender
  7. Evaluation and proof
- preserve small commits with one verification story each
- do not start broad non-Hermes rollout before the Hermes-first proof is stable

## Execution note
- v0.7.0 dreaming sidecar is already complete and should be treated as foundation, not reopened scope
- the atoolix audit is research input; implementation should improve on it rather than mirror it

## Historical note
The sections below are preserved as release history for v0.5.x through v0.7.0 and should not be treated as the active execution queue.

## What closed in v0.5.0
- vault package skeleton exists under `src/hermesoptimizer/vault/`
- inventory, fingerprinting, validation, dedup, rotation hints, and bridge planning exist
- tests cover the current read-only contract
- `tmp/.vault` is the repo-local fixture area and `~/.vault` remains off-limits

## v0.5.1 goal
Turn the existing vault primitives into a harness-usable workflow with clearer docs, a dedicated skill, and a usable CLI surface while preserving the non-destructive contract.

## Scope
- document how the vault works end to end
- explain how Hermes loads and uses a vault skill
- add a user-facing vault audit/report path
- harden validation and bridge planning boundaries
- keep the real vault read-only by default

## Vault safety contract
- production installs read from `~/.vault`
- tests and prototype work use repo-local `tmp/.vault` or temp fixtures
- the code must never delete the user's `~/.vault`
- any write-back path must be opt-in and preserve existing files by default

## Acceptance criteria
- v0.5.0 is explicitly closed out in the release docs
- v0.5.1 docs explain inventory, fingerprinting, validation, dedup, rotation, and bridge planning
- a Hermes skill exists for vault workflows and says when to load it
- the CLI exposes a vault audit/report path that does not require importing internals by hand
- provider validation points are clearly named and remain non-destructive
- write-back planning stays opt-in and format-specific
- tests cover the no-touch `~/.vault` contract and the supported source shapes

## Non-goals
- auto-rotation
- mutating vault files without explicit operator opt-in
- replacing dedicated secret managers
- storing plaintext secrets in the catalog

## Completed tasks
1. archive the v0.5.0 release note and point the active queue at v0.5.1
2. write the v0.5.1 vault contract docs
3. create the Hermes vault skill
4. add CLI wiring for vault audit/report flows
5. tighten provider-validation and write-back boundaries
6. expand tests around source shapes and the no-touch contract
7. run `pytest -q` and keep `git diff --check` clean

All seven items are now complete and verified.

## v0.5.2 completion status

### Completed
- live provider validation backends (HTTP-based, mockable)
- broader source parsing (YAML, JSON, shell profiles, CSV, TXT, DOCX, PDF, images via Docling)
- rotation automation hooks (adapter interface, executor, rollback support)
- **concrete rotation adapters: StubRotationAdapter (testing/demonstration) and EnvFileRotationAdapter (env file rotation)**
- regex filtering for credential detection
- expanded test coverage (33 test files)
- write-back execution with fingerprint placeholders (security: no plaintext written)

### Known gaps
- 2 tests skipped (docling OCR/PDF fixture limitations; tests are correctly marked skip):
  - `test_parse_pdf_file_skips_non_key_lines` (PDF fixture does not produce OCR-keyed content)
  - `test_parse_image_file_skips_non_key_content` (image fixture does not produce OCR-keyed content)

## v0.5.2 + v0.5.3 queue

### v0.5.2 (planned)
- live provider validation backends (AWS, GCP, Azure, or HTTP checks)
- broader source parsing (YAML, JSON, shell profiles, CSV, TXT, DOCX, PDF, images via Docling)
- actual write-back execution with --confirm flow
- rotation automation hooks (not just detection)
- expanded tests for all new surfaces
- Docling integration for document/image-based credential extraction

### v0.5.3 (done)
- add `caveman_mode` config support with safe default OFF
- add `python -m hermesoptimizer caveman` toggle path
- keep safety-critical responses in full mode for mutations, credentials, and destructive ops
- wire caveman skill/rules into Hermes-wide workflow as optional add-on
- document caveman behavior, non-goals, and safety guardrails

## v0.6.0 queue

### v0.6.0 (done)
- rework provider truth so canonical providers, auth types, endpoints, regions, and transports are explicit and repairable
- tighten model validation for stale aliases, deprecated models, missing capabilities, and wrong-endpoint routing
- add a config-fixing pass that produces specific safe repair recommendations for Hermes config drift
- reconcile provider/model/config evidence across config, sessions, logs, auth store, credential pools, and live validation results
- track provider provenance for every displayed/provider-list row: top-level model, `providers:` block, `fallback_providers`, auxiliary/tool assignment, env discovery, auth store / credential pool, and external auto-detect
- collapse duplicate provider rows by canonical provider identity plus endpoint contract, not just display name
- explain duplicate rows as provenance collisions in reports and repair output instead of leaving them as silent picker noise
- auto-repair stale API-key providers by recommending removal from the active list and offering a replacement-key insert path
- auto-repair expiring OAuth providers by attempting renewal first and surfacing an explicit expiring/expired action if renewal fails
- auto-repair bad endpoints by testing the same key against known-good endpoints for that provider and promoting the first contract-valid endpoint
- add stronger report sections for provider health, model validity, and config repair priority
- emit lane-aware repair tuples: provider alias, endpoint URL, auth type, region, and model
- recommend provider-management actions: dedupe aliases, demote repeatedly failing providers, quarantine bad endpoints, pin known-good models, keep endpoint health memory with decay, record credential-source provenance, classify repair actions by safety level, and reorder fallback providers when healthier options consistently win
- build and maintain a repo-local JSON catalog of provider endpoint documentation for configuration/repair use (`src/hermesoptimizer/schemas/provider_endpoint.schema.json`, `data/provider_endpoints.json`, `src/hermesoptimizer/schemas/provider_endpoint.py`)
- define a checked-in JSON schema for endpoint and provenance catalog data used by the repair engine and picker dedup logic
- refresh the provider endpoint catalog with a safe extraction workflow that records blocked-doc states instead of hammering anti-bot providers
- refresh the model list for each provider using current provider website/docs data and keep the checked-in catalog in sync (`src/hermesoptimizer/schemas/provider_model.schema.json`, `data/provider_models.json`, `src/hermesoptimizer/schemas/provider_model.py`)
- for providers that support it, prefer live `/models` API results as the highest-confidence source for model enumeration and merge website/docs data only for missing metadata or blocked APIs
- track per-provider model-source provenance in the catalog: live API, official docs, SDK/examples, or manual fallback
- validate the schemas/catalogs with `tests/test_catalog_refresh.py` and `tests/test_provider_model_refresh.py`
- keep SSH/tmux/session-reuse, install-skill automation, and all non-Hermes harness adapters out of v0.6.0
- verify the provider/model/config repair path with deterministic fixture-driven smoke coverage

## v1.0 series

### v1.0.0+ (deferred)
- SSH bootstrap and tmux session reuse for remote workflows
- private/VPN IP defaults and port-range conventions for remote/dev hosts
- install-skill bundles for common remote environments
- OpenClaw adapter and health/config probes
- OpenCode adapter and config/routing parsing
- later multi-harness correlation after the Hermes repair path is mature

## v0.7.0 completion status

**Status: Complete.** Phases 0–4 fully implemented and tested. Acceptance verified.

### What completed (v0.7.0)

v0.7.0 delivers a TEMM1E-inspired dreaming and memory-consolidation sidecar for Hermes, implemented entirely within `src/hermesoptimizer/dreams/` and `scripts/` without modifying the Hermes core.

#### Phase 0 — Sidecar DB bootstrap
- `src/hermesoptimizer/dreams/memory_meta.py` — SQLite sidecar at `~/.hermes/dreams/memory_meta.db`
- Tracks per-entry: `supermemory_id`, `content_hash`, `importance`, `created_at`, `last_recalled`, `recall_count`, `fidelity_tier`
- `init_db`, `upsert`, `query_by_score`, `set_fidelity`, `update_recall`, `bootstrap_from_entries`, `apply_recall_reheat`

#### Phase 1 — Decay and Sweep
- `src/hermesoptimizer/dreams/decay.py` — exponential decay scoring, `classify_tier` (`full` / `summary` / `essence` / `gone`), adaptive thresholds
- `src/hermesoptimizer/dreams/sweep.py` — `run_sweep`, `sweep_entry_score`, keep/demote/prune decisions
- `scripts/dreaming_pre_sweep.py` — pre-sweep script entry point

#### Phase 2 — Fidelity tiers
- `src/hermesoptimizer/dreams/fidelity.py` — structured fidelity storage (`full` / `summary` / `essence` JSON payloads), `best_representation`, `get_active_content`, `make_fidelity_payload` / `parse_fidelity_payload`, downgrade path

#### Phase 3 — Recall and reheating
- `src/hermesoptimizer/dreams/recall.py` — transcript parsing, recall_log fallback, `reheat_recalled_ids`, `scan_sessions_directory`

#### Phase 4 — Reflection (outside repo)
- `~/.hermes/scripts/dreaming_reflection_context.py` — reflection context builder
- `~/.hermes/scripts/supermemory_store.js` — supermemory store integration
- Skills: `dreaming`, `memory-decay`, `dreaming-reflection`
- Cron job: `30b51a980bc4`

#### Test coverage
- `tests/test_dreams_memory_meta.py`, `tests/test_dreams_decay.py`, `tests/test_dreams_sweep.py`, `tests/test_dreams_fidelity.py`, `tests/test_dreams_recall.py`
- All 938 repo tests pass; 4 skipped (docling OCR/PDF fixture limitations)
