# Hermes Optimizer v0.9.4 — Testing + Refactor Hardening Release Contract

Status: closed locally; v0.9.4 testing/refactor hardening complete
Base: v0.9.3 testing-prep state on `dev/0.9.3`
Prepared: 2026-04-24 11:16 Central time
Current package version: 0.9.4
Target package version: 0.9.4

## Goal

v0.9.4 is the last Hermes-only hardening pass before the v1.0 adapter/remote-workflow series. The point is not new product surface. The point is to run one more deliberate testing round, identify fragile seams, and refactor only where characterization tests prove behavior can stay stable.

Primary outcome:

- the existing 2,065-test / 118-file suite is machine-inventoried and easier to reason about
- release-readiness and docs drift gates remain deterministic
- refactors land only behind tests that fail first or characterization tests that lock current behavior
- wheel, fresh-root, extension, provider, brain, and governance gates stay green before and after each refactor

## Closeout baseline

Commands were run from `/home/agent/hermesoptimizer` on 2026-04-24.

- Branch: `dev/0.9.4`.
- Package version: `0.9.4`.
- Base proof: `VERSION0.9.3.md` at `08df8a7 docs: close v0.9.3 phase`.
- v0.9.4 head includes test inventory hardening, extension semantics characterization, generic provider lane policy, and release-governance retargeting.
- Test collection: 2,065 tests across 118 files (113 under `tests/`, 5 under `brain/scripts/`).
- Full suite passes with docling deprecation warnings only.
- `release-readiness --dry-run` passes and includes `governance_doc_drift`, wheel smoke, extension simulation, provider truth, and brain canary checks.
- `brain-doctor --dry-run` passes while recording provider/model lane health evidence. MiniMax/crof/nacrof remain examples of generic lane-state policy, not special cases.
- `ext-sync --dry-run` reports `repo_only_no_sync` skips for repo-only extensions.
- `provider-list` includes `kilocode`, `nacrof`, `nous`, `openai-codex`, and `openrouter`.

Large-file inventory from the v0.9.4 planning check:

| File | Lines | Why it matters |
|------|-------|----------------|
| `src/hermesoptimizer/sources/model_catalog.py` | 1,291 | model catalog logic may need characterization before later adapter expansion |
| `src/hermesoptimizer/verify/provider_management.py` | 1,109 | provider health/quarantine/management behavior is broad and release-sensitive |
| `src/hermesoptimizer/release/readiness.py` | 766 | release gate has many independent checks in one module |
| `src/hermesoptimizer/verify/endpoints.py` | 720 | endpoint verification is provider-sensitive and should stay deterministic by default |
| `src/hermesoptimizer/schemas/provider_model_refresh.py` | 635 | provider-model refresh has schema and live-fetch edges |
| `src/hermesoptimizer/route/diagnosis.py` | 592 | routing diagnosis is behavior-heavy and good refactor candidate only after tests |
| `src/hermesoptimizer/tool_surface/provider_recommend.py` | 586 | recommendation behavior must remain stable for agent-facing output |
| `src/hermesoptimizer/extensions/install_integrity.py` | 478 | install/wheel/fresh-root gates depend on this staying exact |

Largest tests by source lines include `tests/test_tool_surface_presentation.py`, `tests/test_provider_model_refresh.py`, `tests/test_tool_surface_audit.py`, `tests/test_vault_rotation_hooks.py`, and `tests/test_catalog_refresh.py`. v0.9.4 should prefer helper extraction and domain selectors over rewriting these tests wholesale.

## Non-goals

- Do not add remote workflow automation in v0.9.4.
- Do not broaden Hermes core patches beyond the already-scoped hot-reload proof unless explicitly approved.
- Do not make any provider/model lane required for release while its canary is red, absent, quota-blocked, or fallback-only. MiniMax and crof/nacrof are current examples, not special cases.
- Do not refactor by taste. Refactor only after a test locks the behavior.

## Provider/model lane policy

The policy is generic. Any provider/model tuple can be registered, probed, classified, and routed by the same health machinery.

Lane states:

- `green`: canary passes and the lane may be used for required release work.
- `fallback_only`: configured and useful for opportunistic work, but not eligible for required release gates.
- `quota_blocked`: credentials work but the account cannot currently serve the model.
- `quarantined`: repeated failures or request-dump evidence show the lane is unsafe for autonomous required work.
- `unknown`: no recent canary evidence; not eligible for required work.

Release rule:

- Required release lanes must be green.
- Optional lanes can be red, quota-blocked, fallback-only, or quarantined without blocking the release if the status is explicit and documented.
- New providers/models should enter through the registry + canary path, not provider-specific code.

## Refactor rule

Every possible refactor follows this order:

1. write or identify a focused test that captures current behavior
2. run it and record the baseline
3. make the smallest structural change
4. run the focused selector
5. run the owning domain selector
6. run release-readiness when the change touches install, provider, extension, CLI, or docs gates
7. run full pytest before closeout

If the behavior cannot be described in a test, the refactor waits.

## Release waves

### Wave 0 — seal and freeze the v0.9.3 base — complete

Objective: prevent v0.9.4 work from contaminating the v0.9.3 testing-prep closeout.

Tasks:

- Commit or otherwise freeze the current v0.9.3 testing-prep diff.
- Create `dev/0.9.4` only after the v0.9.3 prep state is recoverable.
- Record the baseline collection and gate outputs in this file.
- Preserve the v0.9.3 closed-state marker until governance tests are deliberately retargeted.

Exit checks:

```bash
git status --short
git diff --check
PYTHONPATH=src python -m pytest --collect-only -q
PYTHONPATH=src python -m hermesoptimizer release-readiness --dry-run
```

### Wave 1 — test inventory and selector hardening — complete

Objective: make the suite navigable before refactoring.

Tasks:

- Regenerate per-file collection counts and compare them with `TESTPLAN.md`.
- Add or update a deterministic inventory check so undocumented test files are visible.
- Assign every test file to exactly one layer and one domain.
- Add selector commands for release, provider, extension, CLI, tool-surface, vault, dreams, budget, and workflow domains.
- Decide whether the inventory check should live in `tests/test_governance_docs.py`, a new `tests/test_testplan_inventory.py`, or release-readiness.

Exit checks:

```bash
PYTHONPATH=src python -m pytest --collect-only -q
PYTHONPATH=src python -m pytest tests/test_governance_docs.py tests/test_release_readiness.py -q
PYTHONPATH=src python -m pytest -q
```

### Wave 2 — characterization tests for refactor seams — complete

Objective: lock current behavior before moving code.

Candidate seams:

- `release/readiness.py`: check order, criticality, evidence shape, dry-run JSON shape, CLI output markers.
- `extensions/sync.py` + `extensions/install_integrity.py`: repo-owned vs external-runtime vs generated-runtime vs `repo_only_no_sync` behavior.
- `cli/` command registry: parser command names, help exit codes, README command drift, report-only vs active command wording.
- `sources/provider_registry.py` + `verify/provider_management.py`: merge priority, quarantine visibility, fallback-only policy, provider/model canary integration.
- `tool_surface/provider_recommend.py`: recommendation ordering and output contract.

Exit checks:

```bash
PYTHONPATH=src python -m pytest tests/test_release_readiness.py tests/test_extensions_sync.py tests/test_extensions_status.py -q
PYTHONPATH=src python -m pytest tests/test_cli_dispatch.py tests/test_cli_unified.py tests/test_commands.py tests/test_tool_surface_commands.py -q
PYTHONPATH=src python -m pytest tests/test_provider_registry.py tests/test_provider_management.py tests/test_tool_surface_provider_recommend.py -q
```

### Wave 3 — low-risk refactors, only where tests justify them — complete

Objective: reduce drift risk without changing product behavior.

Allowed refactor candidates:

1. Split release-readiness checks into small modules or a typed registry if characterization proves the public output remains identical.
2. Extract extension manifest parity helpers so root `extensions/*.yaml` and packaged `src/hermesoptimizer/extensions/data/*.yaml` cannot drift silently.
3. Centralize CLI command metadata if it reduces README/help drift without changing parser behavior.
4. Separate provider registry merge logic from provider health/quarantine state if tests already lock priority and policy.
5. Extract repeated test fixture builders from the largest tests when it improves clarity and keeps assertions behavior-first.

Not allowed without a new explicit plan:

- broad CLI rewrite
- provider registry schema redesign
- native Hermes caveman implementation
- live-network dependency in default tests
- test deletion to make refactors easier

Exit checks after each refactor slice:

```bash
git diff --check
PYTHONPATH=src python -m pytest <focused test selector> -q
PYTHONPATH=src python -m hermesoptimizer release-readiness --dry-run
```

### Wave 4 — install, wheel, provider, and brain repeat gates — complete

Objective: prove that refactors did not break the v0.9.3 release surface.

Tasks:

- Re-run extension doctor and sync dry-run against the real local runtime.
- Re-run fresh-root extension simulation.
- Re-run wheel smoke through release-readiness.
- Re-run provider-list and provider/model dry-run canaries.
- Re-run brain-doctor dry-run and keep provider/model lane status documented as policy, not a mystery failure. MiniMax and crof/nacrof are current examples only.

Exit checks:

```bash
PYTHONPATH=src python -m hermesoptimizer ext-doctor --dry-run
PYTHONPATH=src python -m hermesoptimizer ext-sync --dry-run
PYTHONPATH=src python -m hermesoptimizer release-readiness --dry-run
PYTHONPATH=src python -m hermesoptimizer brain-doctor --dry-run
python3 brain/scripts/provider_probe.py --config brain/evals/provider-canaries.json --dry-run
```

### Wave 5 — v0.9.4 closeout docs and gate retarget — complete

Objective: close the planning loop only after the testing/refactor pass is proven.

Tasks:

- Update `TESTPLAN.md` with final collection counts and selector map.
- Update `README.md` current release only when v0.9.4 is actually closed.
- Update `ROADMAP.md` and `CHANGELOG.md` after green gates.
- Update `brain/active-work/current.md` to the final v0.9.4 state.
- Retarget governance checks from v0.9.3 closed-state text to v0.9.4 closed-state text only after v0.9.4 is ready to close.
- Bump package version to 0.9.4 atomically with tests that assert the version.

Final exit checks:

```bash
git diff --check
PYTHONPATH=src python -m pytest --collect-only -q
PYTHONPATH=src python -m pytest tests/test_governance_docs.py tests/test_release_readiness.py -q
PYTHONPATH=src python -m hermesoptimizer release-readiness --dry-run
PYTHONPATH=src python -m pytest -q
```

## Final proof

Final closeout gate for v0.9.4:

```bash
git diff --check
PYTHONPATH=src python -m pytest --collect-only -q
PYTHONPATH=src python -m pytest tests/test_governance_docs.py tests/test_release_readiness.py tests/test_testplan_inventory.py -q
PYTHONPATH=src python -m hermesoptimizer ext-doctor --dry-run
PYTHONPATH=src python -m hermesoptimizer ext-sync --dry-run
PYTHONPATH=src python -m hermesoptimizer release-readiness --dry-run
PYTHONPATH=src python -m hermesoptimizer brain-doctor --dry-run
python3 brain/scripts/provider_probe.py --config brain/evals/provider-canaries.json --dry-run
PYTHONPATH=src python -m pytest -q
```

Verified result: all commands pass; full pytest exits 0 with only upstream docling deprecation warnings and 4 expected skips.

## Definition of done

v0.9.4 is done when:

- v0.9.3 testing-prep state is sealed before v0.9.4 implementation begins
- every changed behavior has a failing or characterization test first
- every accepted refactor has before/after focused proof
- all default tests remain deterministic and network-free
- `release-readiness --dry-run` passes
- full `pytest -q` passes
- provider/model canary policy is current for every configured lane; MiniMax and crof/nacrof remain examples, not hardcoded exceptions
- extension repo-only/no-sync semantics stay explicit
- docs, TODO, active-work, roadmap, changelog, and version constants agree
