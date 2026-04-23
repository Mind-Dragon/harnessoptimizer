# Hermes Optimizer v0.9.3 — Clean Install + Provider Registry Release Contract

Status: setup
Base: v0.9.2 hardening commit `ab7fef8`
Target: 100% clean install against current Hermes v0.10.0 / near origin main
Prepared: 2026-04-23

## First-pass implementation status — 2026-04-23

Implemented and verified in the v0.9.3 first pass:

- Registry identity: `Mind-Dragon/Liminal-Registry`.
- Packaged fallback registry: `src/hermesoptimizer/data/provider_registry.seed.json`.
- Registry schema: `src/hermesoptimizer/data/provider_registry.schema.json`.
- Registry cache/fetch foundation: `ProviderRegistry.from_cache_or_seed()` and `fetch_remote_registry()`.
- Seed models: `openai-codex/gpt-5.5`, Kilocode/OpenRouter `inclusionai/ling-2.6-flash:free`, Nous `moonshotai/kimi-k2.6`.
- `provider-list` now reads the packaged/cache registry instead of an empty truth store.
- Hermes provider DB adapter: `refresh_provider_db()` upserts providers/models/endpoints into `~/.hermes/provider-db/provider_model.sqlite`.
- Local Hermes `/reload` patch upgraded through `scripts/apply_reload_patch.py` to call `refresh_provider_db()`.

Verified commands:

```bash
PYTHONPATH=src python -m pytest tests/test_provider_registry.py tests/test_package_resources.py tests/test_hot_reload_proof.py tests/test_tool_surface_chain.py -q --tb=short
PYTHONPATH=src python -m hermesoptimizer provider-list
PYTHONPATH=src python - <<'PY'
from hermesoptimizer.verify.hot_reload import refresh_provider_db, inspect_hot_reload_readiness, format_readiness
print(refresh_provider_db())
print(format_readiness(inspect_hot_reload_readiness()))
PY
python3 scripts/apply_reload_patch.py --check
python3 -m py_compile /home/agent/hermes-agent/cli.py
```

Remaining for this wave:

- Add quarantine/health-state behavior for repeated provider failures.
- Add a real CLI command for hot-reload proof if desired; current slice provides the helper and direct Python proof.

Second pass update:

- Remote registry fetch now validates detached SHA-256, detached `sha256:<digest>` signature, and required registry provenance before cache write.
- Failed hash/signature/provenance checks raise `RegistryIntegrityError` and leave cache files untouched.
- Tests cover success, wrong hash, wrong signature, and missing provenance.

Third pass update:

- `ProviderRegistry.from_merged_sources()` implements the declared priority order: Hermes config < Hermes provider DB < packaged fallback < public cache < local override.
- Provider rows with the same ID are replaced by the higher-priority source; unique providers from lower-priority sources remain available.
- `provider-list` now uses the merged source view, so live DB/config-only providers such as `nacrof` appear alongside packaged/cache registry entries.


## Goal

v0.9.3 closes the gap between "optimizer passes its own release gates" and "optimizer installs cleanly against the live Hermes that is actually running." The release is not just another doc cleanup. It must make provider/model truth, extension installation, runtime scripts, and Hermes integration explicit, testable, and hot-reloadable.

Primary user goal:

> A GitHub-maintained provider registry should let a new model like `gpt-5.5` become available and hot-reloaded on all Hermes installs without exiting, restarting, or running `hermes update`.

## Scope decisions locked 2026-04-23

- Provider registry lives in a separate public repository consumed by both Hermes and HermesOptimizer.
- Hermes core modifications stay small. The preferred path is a narrow hot-reload hook/loader patch, not a large Hermes rewrite.
- Hot reload should use the current local-Hermes capability model: small Python patch plus explicit reload/import path, proven against the running Hermes here.
- v0.9.3 tests against the local running Hermes at `/home/agent/hermes-agent` and `~/.hermes`.
- Dreams and caveman are optional runtime install features. They should be installable when selected and absent/disabled cleanly when not selected.
- Caveman default decision: optional installer-managed feature. Do not claim native Hermes behavior unless the small Hermes patch lands and passes a live response-shape probe.
- Dreams default decision: optional installer-managed feature. Install scripts only when selected; otherwise doctor must report "not selected" rather than missing/broken.
- Wheel and editable installs both need gates, because local development uses editable installs but users should not get a broken wheel.
- Vault secret files are external runtime state. Validate/fingerprint them; never sync-overwrite `~/.vault/vault.enc.json`.
- `/home/agent/hermes-agent` dirty state must be resolved, quarantined, or explicitly accepted before v0.9.3 can claim clean local-Hermes compatibility.

## Current verified base

Commands run from `/home/agent/hermesoptimizer` unless noted.

- `PYTHONPATH=src python -m hermesoptimizer release-readiness --dry-run`
  - v0.9.2 gate previously passed.
- `PYTHONPATH=src python -m hermesoptimizer brain-doctor --dry-run`
  - current result: `overall_status=pass`
  - rail loader: `pass`, `mismatch_detected=False`
  - request dump: 49 `max_retries_exhausted`, 1 `non_retryable_client_error`
- `PYTHONPATH=src python -m hermesoptimizer ext-doctor`
  - checked: 7
  - healthy: 3
  - external: 3
  - missing_target: 1
  - verify_passed: 7
  - issue: `dreams` missing `~/.hermes/scripts/dreaming_pre_sweep.py` and `~/.hermes/scripts/probe_memory_meta.py`
- `PYTHONPATH=src python -m hermesoptimizer ext-sync --dry-run`
  - `dreams`: ERROR, existing `~/.hermes/dreams/memory_meta.db`
  - `vault_plugins`: ERROR, existing `~/.vault/vault.enc.json`
  - `scripts`: SKIPPED, no targets
  - `tool_surface`: SKIPPED, no targets
  - `caveman`, `cron`, `skills`: SKIPPED, external runtime ownership
- `PYTHONPATH=src python -m hermesoptimizer provider-list`
  - `No providers found in truth store`
- Controller spot-check:
  - `seed_from_config(~/.hermes/config.yaml)` returns `kilocode`, `nacrof`, `xai`
- Wheel spot-check:
  - provider JSON data is not packaged in the wheel
  - `extensions/data/*.yaml` is packaged
  - `scripts/apply_reload_patch.py` is not packaged
- Caveman tests:
  - `34 passed`
- `dodev --help`
  - exits 2, requires `workflow_id`
- Live cron:
  - `brain-doctor-hourly` active, last run ok
  - `copilot-pr-watch` active
- Local Hermes source:
  - `/home/agent/hermes-agent`: dirty `cli.py`, untracked `internal/`
  - `rg caveman_mode|caveman /home/agent/hermes-agent` returns no code hits

## Subagent audit set

10 requested model-lane agents were launched under `.swarm/093-audit/`:

- z.ai: provider registry, CLI surface, package data
- MiniMax 2.7: installer/extension sync, tests/release gates
- Kimi k2.6: caveman, docs/roadmap, brain/dreams/memory
- GPT-5.4-mini: Hermes integration, vault/security

Two external-lane processes stalled or emitted no report and were stopped. Nine usable reports plus one controller-side timeout were synthesized. A second 10-way Hermes-native audit was run for completion; 9/10 returned, one timed out. Findings below were spot-checked against code and commands before inclusion.

## Top 5 release gaps

### 1. Provider registry/model truth is not a real registry yet

Verified issue:

- `provider-list` instantiates an empty `ProviderTruthStore()` in `src/hermesoptimizer/tool_surface/commands.py`.
- `provider-recommend` and verifier paths seed from `~/.hermes/config.yaml`, so they see some providers.
- Static data files under `data/` are not authoritative, are stale, and are not packaged into wheels.
- No durable checked-in machine-readable provider truth file exists.
- No adapter exists between optimizer truth and Hermes `~/.hermes/provider-db/provider_model.sqlite`.
- `gpt-5.5` is not represented in optimizer data.

Release target:

- Add a canonical provider registry format under the repo, with provenance and schema validation.
- Make GitHub the update channel for the registry.
- Package the registry in the wheel.
- Add a Hermes provider DB adapter.
- Add hot-reload path: registry update -> local cache/SQLite -> running Hermes reload signal.
- Make `provider-list`, `provider-recommend`, `verify-endpoints`, and release gates consume the same source.

Exit checks:

- `provider-list` returns active providers from current Hermes plus registry entries.
- `gpt-5.5` is present with endpoint/provenance in the registry.
- Wheel contains provider registry data.
- A fresh install can update provider metadata without `hermes update`.
- Hot-reload proof records timestamp, model slug, provider, before/after config/db state.

### 2. Clean install is blocked by extension ownership and missing runtime scripts

Verified issue:

- `dreams` declares runtime targets in `~/.hermes/scripts/`, but the scripts only exist in repo `scripts/`.
- `scripts` extension has no target paths.
- `ext-doctor` reports `dreams` missing targets.
- `ext-sync --dry-run` errors on pre-existing runtime files instead of giving a clean idempotent plan.
- `vault_plugins` points at `~/.vault/vault.enc.json`; this should be external runtime data, not an overwrite target.

Release target:

- Define idempotent extension sync semantics:
  - repo-owned files are installable and checksum-verified
  - external runtime data is detected, never overwritten by default
  - sidecar generated files are classified separately
- Install or explicitly de-scope `dreaming_pre_sweep.py` and `probe_memory_meta.py`.
- Make `ext-sync --dry-run` a clean install plan, not a mixed error report.

Exit checks:

- `ext-doctor` reports 0 missing targets.
- `ext-sync --dry-run` exits 0 on an existing install.
- `ext-sync --fresh-root /tmp/... --dry-run` proves fresh install targets.
- `verify_contracts dreams` checks runtime script targets, not only repo scripts.

### 3. Caveman exists in optimizer but Hermes does not natively consume it

Verified issue:

- Caveman source: `src/hermesoptimizer/caveman/__init__.py`
- CLI toggle: `src/hermesoptimizer/cli/workflow.py`
- Runtime skill exists: `~/.hermes/skills/software-development/caveman/SKILL.md`
- Config contains `caveman_mode: true`
- `/home/agent/hermes-agent` has no `caveman` or `caveman_mode` code references.
- Packaged extension YAML and repo YAML have source_path drift.

Release target:

Choose one explicit product contract:

A. Optimizer-only caveman: keep as external runtime, document exactly what it affects, and remove any implication that Hermes core reads `caveman_mode`.

B. Native Hermes caveman: patch Hermes to read `caveman_mode` and apply the compression/response-shape behavior in the agent loop, then make optimizer verify it.

Exit checks:

- `ext-doctor` reports no caveman drift.
- YAML source paths match.
- If native: Hermes source has `caveman_mode` tests and a live response-shape probe.
- If optimizer-only: docs and CLI say so plainly.

### 4. Packaging/install path is editable-install biased

Verified issue:

- Built wheel `hermesoptimizer-0.9.2-py3-none-any.whl` does not include:
  - `provider_models.json`
  - `provider_endpoints.json`
  - `scripts/apply_reload_patch.py`
- Code uses repo-root paths such as `Path(__file__).resolve().parents[3] / "data" / ...`.
- This works in editable installs and breaks in wheel installs.

Release target:

- Move package data under `src/hermesoptimizer/data/` or add a robust resource resolver using `importlib.resources`.
- Package provider registry, endpoint catalog, schema files, and required install scripts.
- Add wheel smoke tests in release-readiness.

Exit checks:

- Build wheel, inspect contents, and run CLI from installed wheel in isolated venv.
- Provider list/recommend works from wheel install.
- Extension data resolves from package resources.

### 5. CLI surface has advertised but stubbed or misleading commands

Verified issue:

- `dodev --help` exits 2 because the parser disables help and requires `workflow_id`.
- `dodev/devdo` creates/loads a run and prints metadata; it does not execute a plan.
- README mentions commands not implemented as CLI choices, including service/config/auxiliary/yolo surfaces.
- Several commands are dry-run/report-only while phrasing suggests active repair.

Release target:

- Split command classes clearly:
  - implemented active commands
  - report-only commands
  - planned commands hidden from README until shipped
- Fix `dodev --help`.
- Either implement `devdo` execution loop or rename it to `dodev-plan` / `workflow-inspect`.
- Add CLI doc drift gate.

Exit checks:

- Every command in README exists or is marked planned.
- Every command supports `--help` cleanly.
- Release gate runs command help smoke across the whole CLI.

## Additional gaps found

### Provider registry/hot reload

- No remote registry fetcher exists.
- No registry signature/hash validation exists.
- No registry merge policy exists for local overrides vs GitHub registry vs models.dev cache.
- No rollback path exists for bad registry updates.
- No versioned provider schema migration exists.
- Alias maps diverge between optimizer and Hermes.
- `brain/providers/*.md` are narrative notes, not machine-readable truth.
- Provider notes are missing for active lanes: openai-codex, kilocode, xai, z.ai.
- MiniMax failure evidence exists in request dumps but is not turned into provider quarantine or routing policy.

### Extensions/install

- `scripts` and `tool_surface` extensions are registered but have no install targets.
- `vault_plugins` target semantics confuse external secrets with repo-owned artifacts.
- `dreams` status passes verify_contracts while runtime script targets are missing.
- No clean fresh-root installer simulation exists.
- No formal classification for generated runtime artifacts vs installable repo artifacts.

### Hermes integration

- Optimizer checks are external; native `hermes status` / `hermes doctor` do not surface optimizer health.
- Hot-reload patch is in dirty Hermes `cli.py`; not a clean upstreamed integration.
- Running Hermes is close to origin main but not clean enough for a release proof.
- Messaging gateway runs but platform configs are empty; decide whether this matters for v0.9.3 scope.
- Current provider DB exists independently of optimizer registry.

### Brain/dreams/memory

- `brain-doctor --dry-run` passes now, but request dump digest still indicates 49 MiniMax failures and 1 crof client error.
- Dreaming memory DB exists but has zero entries.
- Dream sweep scripts are not installed in runtime path.
- Full non-dry run behavior needs a release canary, not just dry-run.

### Vault/security

- AWS SigV4 and Azure JWKS providers intentionally raise `NotImplementedError`; keep documented or hide from active claims.
- OpenCode plugin is read-only by design; keep documented.
- StubRotationAdapter is test/demo; keep outside production surfaces.
- Writeback fingerprint placeholder behavior needs product decision: safe references vs actual secret writes. Do not silently write misleading placeholders as deployable configs.

### Docs/release gates

- No v0.9.3 milestone existed before this file.
- TODO.md was still v0.9.2-focused before v0.9.3 setup.
- README command list is ahead of implementation.
- Release readiness does not yet include isolated wheel install, fresh-root install simulation, provider registry freshness, or CLI doc drift.
- Release readiness tests hardcode `0.9.2`, so a version bump will false-fail until those assertions are updated or derived from `hermesoptimizer.__version__`.
- `check_test_collection` ignores `tests/test_channel_management.py` without documented release-gate rationale.
- `check_provider_truth` passes with an empty `ProviderTruthStore`, so provider registry absence is invisible to the gate.
- Dry-run extension doctor suppresses REPO_EXTERNAL missing-target drift, which masks the current dreams install gap.
- README test-count claim is stale: it says 1,626, current collection is 1,961.

## v0.9.3 release waves

### Wave 0 — Baseline and release branch hygiene

- Create/confirm `dev/0.9.3` from `dev/0.9.2`.
- Keep Hermes source dirty state explicit; do not claim clean integration until resolved.
- Add `.swarm/` to ignored audit artifacts or relocate audits outside repo.
- Preserve this file as release contract.

### Wave 1 — Provider registry productization

- Define machine-readable provider registry schema in a separate public registry repo consumed by both Hermes and HermesOptimizer.
- In HermesOptimizer, add a packaged fallback copy/cache of that public registry for offline and wheel-install operation.
- Add a remote registry fetcher with hash/signature/provenance checks.
- Add local checked-in/cache registry data with `gpt-5.5` and current Hermes providers.
- Add resolver order:
  1. pinned local overrides
  2. public registry cache
  3. packaged registry fallback
  4. models.dev cache
  5. live Hermes config
- Add SQLite adapter for `~/.hermes/provider-db/provider_model.sqlite`.
- Add hot-reload integration proof against the local running Hermes.

### Wave 2 — Installer and extension clean install

- Add installer feature-selection state for optional runtime features.
- Fix dreams/scripts ownership so dreams scripts install only when the dreams feature is selected.
- Fix caveman install contract so the skill/config pieces install only when the caveman feature is selected.
- Reclassify vault runtime secret file.
- Make `ext-sync --dry-run` idempotent on existing installs.
- Add fresh-root install simulator with feature matrix:
  - base only
  - base + caveman
  - base + dreams
  - base + caveman + dreams
- Add release gate: extension status must have 0 missing targets and 0 sync errors for selected features; unselected optional features must report `not selected`, not `missing`.

### Wave 3 — Wheel/resource correctness

- Package registry JSON/YAML, schemas, and required scripts.
- Replace repo-root resource lookup with package resource resolver.
- Add isolated wheel smoke test.
- Add `hermesoptimizer doctor --install-root` or equivalent to verify clean installs.

### Wave 4 — CLI truthfulness

- Fix `dodev --help`.
- Rename or implement stubby commands.
- Remove/mark README commands that do not exist.
- Add command help smoke and README command drift checks to release readiness.
- Update or generate README test-count claims from live collection.

### Wave 4b — release gate hardening

- Make release-readiness version tests derive from `hermesoptimizer.__version__` or update them atomically with the v0.9.3 bump.
- Include `tests/test_channel_management.py` in collection or document why it is excluded.
- Make `check_provider_truth` require non-empty provider truth.
- Make dry-run extension doctor expose REPO_EXTERNAL missing-target drift in a way that blocks clean-install claims.
- Add a fresh-install canary to release readiness.

### Wave 5 — Hermes integration proof

- Use the smallest practical Hermes patch: a narrow provider-registry reload/import hook, preferably adjacent to the existing config hot-reload patch path.
- Avoid large Hermes rewrites or broad provider subsystem replacement in v0.9.3.
- Caveman is optional installer-managed behavior unless/until the small Hermes patch explicitly supports it.
- Resolve dirty Hermes tree before final proof, or document exactly which local patch is the tested compatibility target.
- Surface optimizer checks through Hermes only if it can be done with a small bridge; otherwise document optimizer checks as external.
- Prove hot reload against live running Hermes without restart.

## Scope decisions

1. Provider registry ownership: separate public registry repo consumed by both Hermes and HermesOptimizer.
2. Hot reload mechanism: use the existing small-Hermes-patch model. Optimizer writes/updates a registry artifact or provider DB cache, then the small Hermes reload/import hook ingests it without restart/update.
3. Caveman contract: optional runtime install feature. Do not claim native Hermes behavior unless a small Hermes patch lands and a live probe proves it.
4. Clean install target: support both editable and wheel installs, with wheel smoke mandatory before release.
5. Dreams scope: optional runtime install feature. If selected, scripts and DB checks must pass; if not selected, status must say `not selected`.
6. External secrets: validate/fingerprint external vault state only; never sync-overwrite `~/.vault/vault.enc.json`.
7. Hermes dirty tree: test against the local Hermes here, but final proof must resolve, quarantine, or explicitly document the exact small patch under test.

## Release exit criteria

v0.9.3 is releasable only when all of these are true:

- `pytest` green.
- `release-readiness --dry-run` green.
- `brain-doctor --dry-run` green and non-dry canary recorded.
- `ext-doctor` reports 0 missing targets.
- `ext-sync --dry-run` exits 0 on existing runtime.
- Fresh-root install simulation exits 0.
- Isolated wheel install smoke exits 0.
- `provider-list` returns non-empty providers.
- Registry contains `gpt-5.5` and current Hermes active providers.
- Hot-reload proof shows no Hermes restart/update required.
- README command drift check passes.
- `/home/agent/hermes-agent` cleanliness/integration state is explicitly handled.
