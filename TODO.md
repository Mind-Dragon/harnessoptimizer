# Hermes Optimizer /todo — v0.9.4 testing + refactor hardening

Current package version: 0.9.3
Target package version: 0.9.4
Base release proof: VERSION0.9.3.md
Current planning contract: VERSION0.9.4.md
Status: planned; do not implement until v0.9.3 testing-prep diff is sealed.
Previous phase status: Status: closed locally; testing preparation complete.
Primary target: one more deterministic testing pass with behavior-preserving refactors where tests justify them.

## Scope decisions locked

- v0.9.4 is not a new feature release. It is a testing, characterization, and refactor-safety pass.
- v0.9.3 clean-install/provider-registry behavior remains the baseline to preserve.
- Refactors are allowed only after focused tests or characterization tests lock current behavior.
- Default gates remain offline/deterministic. Live provider checks stay explicit and opt-in unless already dry-run safe.
- Provider/model lane health policy applies to any provider/model tuple. Red, absent, quota-blocked, quarantined, or fallback-only canaries are non-blocking unless that lane is declared required; required lanes must be green. MiniMax and crof/nacrof are current examples, not special cases.
- Extension `repo_only_no_sync` semantics must remain explicit in root and packaged manifests.
- Do not retarget governance checks away from the v0.9.3 closed marker until v0.9.4 is actually ready to close.
- Do not mix v0.9.4 implementation changes into the uncommitted v0.9.3 testing-prep slice.

## Verified baseline to preserve

- 2,033 tests collected across 117 test files.
- Full v0.9.3 suite previously passed with docling deprecation warnings only.
- `release-readiness --dry-run` previously passed and includes `governance_doc_drift`.
- `brain-doctor --dry-run` previously passed with provider/model lane health evidence recorded as policy. MiniMax/crof are current examples only.
- `ext-doctor --dry-run`, `ext-sync --dry-run`, and provider dry-run canaries previously passed.
- `provider-list` returns `kilocode`, `nacrof`, `nous`, `openai-codex`, and `openrouter`.
- Largest refactor candidates from live inventory:
  - `src/hermesoptimizer/sources/model_catalog.py` — 1,291 lines
  - `src/hermesoptimizer/verify/provider_management.py` — 1,109 lines
  - `src/hermesoptimizer/release/readiness.py` — 766 lines
  - `src/hermesoptimizer/verify/endpoints.py` — 720 lines
  - `src/hermesoptimizer/schemas/provider_model_refresh.py` — 635 lines
  - `src/hermesoptimizer/route/diagnosis.py` — 592 lines
  - `src/hermesoptimizer/tool_surface/provider_recommend.py` — 586 lines
  - `src/hermesoptimizer/extensions/install_integrity.py` — 478 lines

## Wave 0 — freeze v0.9.3 and open v0.9.4 safely

[ ] Commit or otherwise freeze the current v0.9.3 testing-prep diff.
[ ] Create `dev/0.9.4` from the sealed v0.9.3 state.
[ ] Confirm `VERSION0.9.4.md` is the active planning contract.
[ ] Keep `VERSION0.9.3.md` as historical closeout proof.
[ ] Record fresh baseline outputs in `VERSION0.9.4.md` before code refactors begin.

Exit checks:

```bash
git status --short
git diff --check
PYTHONPATH=src python -m pytest --collect-only -q
PYTHONPATH=src python -m hermesoptimizer release-readiness --dry-run
```

## Wave 1 — test inventory and selector hardening

[ ] Regenerate per-file test collection counts.
[ ] Compare collection counts against `TESTPLAN.md`.
[ ] Add or update a deterministic test inventory guard for undocumented test files.
[ ] Ensure every test file belongs to exactly one layer and one domain.
[ ] Add copy-paste selectors for release, provider, extension, CLI, tool-surface, vault, dreams, budget, workflow, and governance domains.
[ ] Decide whether inventory enforcement belongs in `tests/test_governance_docs.py`, a new `tests/test_testplan_inventory.py`, or release-readiness.
[ ] Run the focused governance/release selector before broader suite work.

Exit checks:

```bash
PYTHONPATH=src python -m pytest --collect-only -q
PYTHONPATH=src python -m pytest tests/test_governance_docs.py tests/test_release_readiness.py -q
PYTHONPATH=src python -m pytest -q
```

## Wave 2 — characterization tests before refactor

[ ] Add characterization coverage for `release/readiness.py` check order, criticality, evidence shape, dry-run JSON shape, and CLI output markers.
[ ] Add characterization coverage for extension sync/install semantics: repo-owned, external runtime, generated runtime, optional unselected, and `repo_only_no_sync`.
[ ] Add characterization coverage for CLI parser behavior: command names, help exit codes, report-only wording, and README command drift.
[ ] Add characterization coverage for provider registry merge priority, quarantine visibility, fallback-only policy, lane-state classification, and provider/model canary fixture integration.
[ ] Add characterization coverage for tool-surface provider recommendation ordering and output contract.
[ ] Run each characterization test before refactoring and record whether it locks existing behavior or exposes a real bug.

Exit checks:

```bash
PYTHONPATH=src python -m pytest tests/test_release_readiness.py tests/test_extensions_sync.py tests/test_extensions_status.py -q
PYTHONPATH=src python -m pytest tests/test_cli_dispatch.py tests/test_cli_unified.py tests/test_commands.py tests/test_tool_surface_commands.py -q
PYTHONPATH=src python -m pytest tests/test_provider_registry.py tests/test_provider_management.py tests/test_tool_surface_provider_recommend.py -q
```

## Wave 3 — behavior-preserving refactor slices

[ ] Refactor `release/readiness.py` into smaller check modules or a typed check registry only if Wave 2 locks output shape.
[ ] Extract extension manifest parity helpers so root manifests and packaged manifests cannot drift silently.
[ ] Centralize CLI command metadata only if parser behavior and README drift checks stay unchanged.
[ ] Separate provider registry merge logic from provider health/quarantine state only if priority and policy tests are green.
[ ] Extract repeated test fixture builders from the largest tests without weakening assertions.
[ ] Keep each refactor as a small slice with focused selector proof before moving to the next slice.
[ ] Revert any refactor that requires changing product behavior without an explicit bug test.

Required after each refactor slice:

```bash
git diff --check
PYTHONPATH=src python -m pytest <focused test selector> -q
PYTHONPATH=src python -m hermesoptimizer release-readiness --dry-run
```

## Wave 4 — repeat install, wheel, provider, and brain gates

[ ] Re-run `ext-doctor --dry-run` against the real local runtime.
[ ] Re-run `ext-sync --dry-run` and verify `repo_only_no_sync` reasons remain visible.
[ ] Re-run fresh-root extension simulation through release-readiness.
[ ] Re-run isolated wheel smoke through release-readiness.
[ ] Re-run `provider-list` and provider/model dry-run canaries.
[ ] Re-run `brain-doctor --dry-run` and keep generic provider/model lane policy current. MiniMax/crof are examples, not hardcoded exceptions.
[ ] Verify docs still describe external vault state as validate/fingerprint only.

Exit checks:

```bash
PYTHONPATH=src python -m hermesoptimizer ext-doctor --dry-run
PYTHONPATH=src python -m hermesoptimizer ext-sync --dry-run
PYTHONPATH=src python -m hermesoptimizer release-readiness --dry-run
PYTHONPATH=src python -m hermesoptimizer brain-doctor --dry-run
python3 brain/scripts/provider_probe.py --config brain/evals/provider-canaries.json --dry-run
```

## Wave 5 — close v0.9.4 docs and retarget gates

[ ] Update `TESTPLAN.md` with final collection counts and selector map.
[ ] Update `README.md` current release only after v0.9.4 is actually closed.
[ ] Update `ROADMAP.md` and `CHANGELOG.md` after green gates.
[ ] Update `brain/active-work/current.md` with final v0.9.4 state.
[ ] Retarget governance checks from v0.9.3 closed-state text to v0.9.4 closed-state text after v0.9.4 is ready to close.
[ ] Bump package version to 0.9.4 atomically with version tests.
[ ] Add final proof block to `VERSION0.9.4.md`.

Final exit checks:

```bash
git diff --check
PYTHONPATH=src python -m pytest --collect-only -q
PYTHONPATH=src python -m pytest tests/test_governance_docs.py tests/test_release_readiness.py -q
PYTHONPATH=src python -m hermesoptimizer release-readiness --dry-run
PYTHONPATH=src python -m pytest -q
```

## Acceptance gates

[ ] v0.9.3 prep slice is sealed before v0.9.4 implementation begins.
[ ] Test inventory matches `TESTPLAN.md` or fails with a clear drift message.
[ ] Every refactor has focused before/after proof.
[ ] Default tests remain deterministic and network-free.
[ ] `release-readiness --dry-run` passes.
[ ] `brain-doctor --dry-run` passes with generic provider/model lane policy current.
[ ] `ext-doctor --dry-run` passes.
[ ] `ext-sync --dry-run` passes and reports `repo_only_no_sync` reasons.
[ ] Provider/model dry-run canaries include every configured required lane, preserve fallback-only policy for optional/degraded lanes, and keep `nacrof-crof` as one current example unless green.
[ ] Isolated wheel smoke passes.
[ ] Full `PYTHONPATH=src python -m pytest -q` passes.
[ ] `VERSION0.9.4.md`, `TODO.md`, `TESTPLAN.md`, `ROADMAP.md`, `CHANGELOG.md`, `README.md`, and `brain/active-work/current.md` agree at closeout.
