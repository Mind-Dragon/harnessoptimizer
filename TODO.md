# Hermes Optimizer /todo — v0.9.4 testing + refactor hardening

Current package version: 0.9.4
Target package version: 0.9.4
Base release proof: VERSION0.9.3.md
Current planning contract: VERSION0.9.4.md
Status: closed locally; v0.9.4 testing/refactor hardening complete.
Previous phase status: Status: closed locally; testing preparation complete.
Primary result: deterministic release hardening pass complete; provider lane policy is generic, extension no-sync semantics are explicit, and the final gate is the proof surface.

## Scope decisions preserved

- v0.9.4 is a testing, characterization, and refactor-safety pass, not a new product-surface release.
- v0.9.3 clean-install/provider-registry behavior remains the baseline preserved by v0.9.4.
- Refactors landed only after focused tests or characterization tests locked current behavior.
- Default gates remain offline/deterministic. Live provider checks stay explicit and opt-in unless already dry-run safe.
- Provider/model lane health policy applies to any provider/model tuple. Required release lanes must be `green`; optional, fallback-only, quota-blocked, quarantined, unknown, or absent lanes stay non-blocking when documented.
- Extension `repo_only_no_sync` semantics remain explicit in root and packaged manifests.
- `VERSION0.9.3.md` remains historical closeout proof. `VERSION0.9.4.md` is the current release proof.

## Verified closeout baseline

- 2,065 tests collected across 118 test files: 113 under `tests/` plus 5 brain-script test modules.
- Full suite passes with docling deprecation warnings only.
- `release-readiness --dry-run` passes and includes `governance_doc_drift`.
- `brain-doctor --dry-run` passes with generic provider/model lane policy current.
- `ext-doctor --dry-run` and `ext-sync --dry-run` pass; sync reports `repo_only_no_sync` skip reasons.
- `provider-list` returns `kilocode`, `nacrof`, `nous`, `openai-codex`, and `openrouter`.
- Provider/model dry-run canaries cover configured lanes; non-green lanes are non-blocking unless marked `required_release`.
- Isolated wheel smoke is included in release-readiness.

## Wave closeout

### Wave 0 — freeze v0.9.3 and open v0.9.4 safely

[x] v0.9.3 testing-prep diff sealed in git.
[x] `dev/0.9.4` created from the sealed v0.9.3 state.
[x] `VERSION0.9.4.md` established as active planning contract.
[x] `VERSION0.9.3.md` retained as historical closeout proof.
[x] Fresh baseline outputs recorded before refactor work began.

### Wave 1 — test inventory and selector hardening

[x] Per-file test collection counts regenerated.
[x] `TESTPLAN.md` complete inventory added and machine-checked.
[x] `tests/test_testplan_inventory.py` added as deterministic inventory guard.
[x] Selector cheat sheet added for governance, release, provider, extension, CLI, tool-surface, vault, dreams, budget, workflow, and full-suite gates.
[x] Focused governance/release selectors pass.

### Wave 2 — characterization tests before refactor

[x] Release-readiness behavior characterized for governance/version/doc checks.
[x] Extension sync/install semantics characterized, including repo-owned, optional-unselected, external-runtime, generated-runtime documentation, and `repo_only_no_sync` paths.
[x] Provider registry lane-state behavior characterized for green, fallback-only, quota-blocked, quarantined, and unknown states.
[x] Provider/model canary policy generalized away from provider-specific special cases.
[x] Tool-surface and CLI selectors preserved as release gates.

### Wave 3 — behavior-preserving refactor slices

[x] Generic `LaneState` source added.
[x] Provider registry schema and packaged data accept generic lane states.
[x] Release-readiness canary checks iterate over generic canary metadata instead of hardcoding a provider lane.
[x] Governance tests check canary lane policy generically.
[x] Extension install semantics retain explicit no-sync and runtime ownership contracts.
[x] Refactors stayed behavior-preserving and were verified with focused selectors before broader gates.

### Wave 4 — repeat install, wheel, provider, and brain gates

[x] `ext-doctor --dry-run` passed.
[x] `ext-sync --dry-run` passed and reports `repo_only_no_sync` skip reasons.
[x] Fresh-root extension simulation passed through release-readiness.
[x] Isolated wheel smoke passed through release-readiness.
[x] `provider-list` and provider/model dry-run canaries passed.
[x] `brain-doctor --dry-run` passed with generic provider/model lane policy current.
[x] Docs still describe external vault state as validate/fingerprint unless write-back is explicitly confirmed.

### Wave 5 — close v0.9.4 docs and retarget gates

[x] `TESTPLAN.md` updated with final collection counts and selector map.
[x] `README.md` current release updated to v0.9.4.
[x] `ROADMAP.md` and `CHANGELOG.md` updated for v0.9.4.
[x] `brain/active-work/current.md` updated with final v0.9.4 state.
[x] Governance checks retargeted from v0.9.3 closed-state text to v0.9.4 closeout text.
[x] Package version bumped to 0.9.4 in `pyproject.toml` and `src/hermesoptimizer/__init__.py`.
[x] Final proof block added to `VERSION0.9.4.md`.

## Final exit checks

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

## Acceptance gates

[x] v0.9.3 prep slice is sealed before v0.9.4 implementation begins.
[x] Test inventory matches `TESTPLAN.md` or fails with a clear drift message.
[x] Every refactor has focused before/after proof.
[x] Default tests remain deterministic and network-free.
[x] `release-readiness --dry-run` passes.
[x] `brain-doctor --dry-run` passes with generic provider/model lane policy current.
[x] `ext-doctor --dry-run` passes.
[x] `ext-sync --dry-run` passes and reports `repo_only_no_sync` reasons.
[x] Provider/model dry-run canaries include every configured required lane and preserve fallback-only policy for optional/degraded lanes.
[x] Isolated wheel smoke passes.
[x] Full `PYTHONPATH=src python -m pytest -q` passes.
[x] `VERSION0.9.4.md`, `TODO.md`, `TESTPLAN.md`, `ROADMAP.md`, `CHANGELOG.md`, `README.md`, and `brain/active-work/current.md` agree at closeout.
