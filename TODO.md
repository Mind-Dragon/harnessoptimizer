# Hermes Optimizer /todo — v0.9.3 clean install + provider registry

Current package version: 0.9.2
Target package version: 0.9.3
Base release proof: VERSION0.9.2.md
Current release contract: VERSION0.9.3.md
Primary target: 100% clean install against current Hermes v0.10.0 / near origin main.

## Scope decisions locked

- Provider registry lives in a separate public repo consumed by both Hermes and HermesOptimizer.
- Hermes modifications stay small. v0.9.3 should extend the current hot-reload patch model, not rewrite Hermes.
- Test target is the local running Hermes here: `/home/agent/hermes-agent` plus `~/.hermes`.
- Dreams and caveman are optional runtime install choices.
- If dreams/caveman are not selected, extension status must say `not selected`, not `missing`.
- If selected, dreams/caveman must install cleanly and pass runtime probes.
- Vault secret files are external runtime state; validate/fingerprint only.
- Both editable and wheel installs need gates.

## Verified baseline

- Caveman source: `src/hermesoptimizer/caveman/__init__.py`
- Caveman CLI: `src/hermesoptimizer/cli/workflow.py`
- Caveman runtime skill: `~/.hermes/skills/software-development/caveman/SKILL.md`
- Caveman config: `~/.hermes/config.yaml` contains `caveman_mode: true`
- Hermes core does not reference `caveman` or `caveman_mode`.
- `provider-list` now reads the packaged/cache provider registry and returns `kilocode`, `nous`, `openai-codex`, `openrouter` with model IDs.
- Provider DB refresh inserted `openai-codex/gpt-5.5`, `kilocode/inclusionai/ling-2.6-flash:free`, `openrouter/inclusionai/ling-2.6-flash:free`, and `nous/moonshotai/kimi-k2.6` into `~/.hermes/provider-db/provider_model.sqlite`.
- `seed_from_config(~/.hermes/config.yaml)` remains a separate live-config source (`kilocode`, `nacrof`, `xai`) until merge policy work lands.
- `ext-doctor` reports 1 missing target group: dreams runtime scripts.
- `ext-sync --dry-run` errors on existing dreams DB and vault file.
- Built wheel does not include provider JSON catalogs or scripts.
- `dodev --help` exits 2.
- Live cron has 2 active jobs: `brain-doctor-hourly`, `copilot-pr-watch`.
- `brain-doctor --dry-run` currently passes but provider request dumps show MiniMax and crof failures.

## Release waves

### Wave 0 — release hygiene

[ ] Create/confirm `dev/0.9.3` from `dev/0.9.2`.
[ ] Add or confirm ignore rules for `.swarm/`, wheel/build/cache artifacts.
[ ] Keep `/home/agent/hermes-agent` dirty state explicit in the release proof.
[ ] Decide whether v0.9.3 will modify Hermes core or only validate against it.
[ ] Update ROADMAP.md with a v0.9.3 milestone.
[ ] Bump package version only after first green implementation wave.
[ ] Update hardcoded release-readiness test version assertions when bumping from 0.9.2 to 0.9.3.
[ ] Archive or explicitly exempt older root VERSION docs so release doc drift remains intentional.

### Wave 1 — provider registry

[x] Fix `provider-list` to load the same seeded truth as the provider registry fallback.
[x] Define the first-pass canonical provider registry schema for separate public repo `Mind-Dragon/Liminal-Registry`.
[x] Add HermesOptimizer support for a packaged fallback/cache copy of the public registry.
[x] Create machine-readable registry seed with active lanes and `openai-codex/gpt-5.5`.
[x] Move first-pass provider registry data under `src/hermesoptimizer/data/` and add `importlib.resources` resolver.
[x] Package provider registry/catalog files into the wheel package-data config.
[x] Add explicit remote registry fetcher/cache path for `Mind-Dragon/Liminal-Registry`.
[ ] Add hash/signature/provenance validation for remote registry fetches.
[ ] Add merge policy: local override > public registry cache > packaged fallback > Hermes provider DB > Hermes config.
[x] Add Hermes provider DB adapter for `~/.hermes/provider-db/provider_model.sqlite`.
[ ] Add registry quarantine behavior for repeated provider failures.
[x] Add provider notes for active lanes: openai-codex, kilocode, openrouter, nous.
[ ] Add tests for alias-map parity or intentional divergence between Hermes and optimizer.
[x] Add `gpt-5.5` registry fixture and test.
[x] Add hot-reload proof helper that updates provider/model metadata in local Hermes DB without restart/update.

### Wave 2 — extension/install cleanup

[ ] Add installer feature-selection state for optional runtime features.
[ ] Fix dreams/scripts ownership so `dreaming_pre_sweep.py` and `probe_memory_meta.py` install only when dreams is selected.
[ ] Add runtime target checks to `verify_contracts dreams` for selected installs.
[ ] Add caveman selected/unselected install contract for skill/config behavior.
[ ] Reclassify `~/.vault/vault.enc.json` as external runtime data, not a sync overwrite target.
[ ] Make `ext-sync --dry-run` idempotent on existing runtime.
[ ] Add fresh-root install simulation for base, base+caveman, base+dreams, base+caveman+dreams.
[ ] Add generated-runtime-artifact classification.
[ ] Add extension release gate: selected features have 0 missing targets and 0 sync errors; unselected optional features report `not selected`.

### Wave 3 — packaging/wheel install

[ ] Add isolated wheel build inspection to tests/release readiness.
[ ] Add isolated venv wheel install smoke.
[ ] Prove `provider-list`, `provider-recommend`, `ext-list`, `ext-doctor`, `brain-doctor --dry-run`, and `caveman` from wheel install.
[ ] Replace repo-root `parents[3] / data` lookups with packaged resource resolver.
[ ] Package required installer scripts or install them through explicit extension sync.

### Wave 4 — CLI truthfulness

[ ] Fix `dodev --help` to exit 0 and show help.
[ ] Decide whether `dodev/devdo` executes plans or only inspects them.
[ ] If inspect-only, rename or rewrite command help.
[ ] Audit README command list against `hermesoptimizer --help`.
[ ] Remove or mark planned commands that do not exist.
[ ] Add release gate for CLI help smoke across all commands.
[ ] Add README-command drift test.
[ ] Update stale README test-count claim from 1,626 to current collected count, or generate it dynamically.

### Wave 4b — release gate hardening

[ ] Remove undocumented `--ignore=tests/test_channel_management.py` from `check_test_collection`, or document and justify it in code.
[ ] Fix/simplify suspicious `test_channel_management.py` assertion around `sources.isdisjoint(targets) is False` if it is actually redundant or wrong.
[ ] Make `check_provider_truth` fail when provider truth has zero entries.
[ ] Make dry-run `check_extension_doctor` surface REPO_EXTERNAL missing-target drift explicitly instead of hiding the dreams gap as non-critical.
[ ] Replace conditional gate assertion in `test_gate_passes_when_critical_checks_pass` with an unconditional invariant.
[ ] Add `check_installer_canary` or equivalent fresh-install simulation to release readiness.

### Wave 5 — caveman contract

[ ] Normalize `extensions/caveman.yaml` and packaged `extensions/data/caveman.yaml` source paths.
[ ] Implement caveman as an optional runtime install selection.
[ ] If unselected: doctor/status reports `not selected`, not missing/broken.
[ ] If selected: install/verify skill and config behavior against local Hermes runtime.
[ ] Do not claim native Hermes consumption of `caveman_mode` unless a small Hermes patch lands and live response-shape probe passes.
[ ] Add clean config writer test for `caveman_mode` around adjacent comments/free text.
[ ] Keep existing caveman unit/CLI/config tests green.

### Wave 6 — brain/dreams/provider health

[ ] Convert request dump provider failures into provider health status/quarantine input.
[ ] Add non-dry `brain-doctor` canary to release readiness, safely scoped.
[ ] Implement dreams as an optional runtime install selection.
[ ] If unselected: dreams status reports `not selected`, not missing/broken.
[ ] If selected: install dream sweep scripts and verify memory DB/script probes against local Hermes runtime.
[ ] Add brain/provider notes for all active provider lanes.
[ ] Ensure MiniMax and crof failure docs are current and actionable.

### Wave 7 — Hermes integration proof

[ ] Keep Hermes modifications small: registry reload/import hook only, preferably near the existing config hot-reload patch path.
[ ] Resolve or explicitly quarantine `/home/agent/hermes-agent/cli.py` dirty hot-reload patch.
[ ] Resolve or explicitly quarantine `/home/agent/hermes-agent/internal/` untracked files.
[ ] Prove current running local Hermes can ingest provider/model update without restart/update.
[ ] Decide whether optimizer health surfaces in native `hermes status` / `hermes doctor`; prefer a tiny bridge only if low-risk.
[ ] Add a final clean-install proof block to VERSION0.9.3.md.

## Acceptance gates

[ ] `pytest` green.
[ ] `release-readiness --dry-run` green.
[ ] `brain-doctor --dry-run` green.
[ ] non-dry brain canary recorded.
[ ] `ext-doctor` has 0 missing targets.
[ ] `ext-sync --dry-run` exits 0.
[ ] fresh-root install simulation exits 0.
[ ] isolated wheel install smoke exits 0.
[ ] `provider-list` non-empty.
[ ] `gpt-5.5` present in provider registry.
[ ] provider registry hot reload proven without Hermes restart/update.
[ ] README command drift gate passes.
[ ] Hermes integration cleanliness explicitly proven or explicitly scoped out.
