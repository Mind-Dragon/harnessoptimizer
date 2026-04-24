# Active Work: v0.9.4 testing/refactor hardening — 2026-04-24

## Objective
Keep the HermesOptimizer v0.9.4 release locally shippable by locking the test inventory, provider lane policy, extension install semantics, and release/governance docs behind deterministic gates.

## Verified state
- Branch: `dev/0.9.4`.
- Package version: `0.9.4` in `pyproject.toml` and `src/hermesoptimizer/__init__.py`.
- v0.9.3 closeout is preserved in `VERSION0.9.3.md`.
- v0.9.4 release proof is `VERSION0.9.4.md`.
- Test collection baseline: 2,065 tests across 118 files: 113 under `tests/` plus 5 brain-script test modules.
- `tests/test_testplan_inventory.py` guards the complete test-file inventory and selector cheat sheet.
- Provider/model lane policy is generic through `LaneState`; required release lanes must be `green`, optional degraded lanes are non-blocking when explicit.
- Extension `repo_only_no_sync` semantics are explicit in root and packaged manifests.
- Read-only v0.9.4 audit artifacts live under ignored `.swarm/094-audit/`; actionable findings were converted into tests/code/docs or left as future optional refactor candidates.

## Current blockers
None for local v0.9.4 release closeout.

## Next deterministic step
run the final v0.9.4 gate before handoff:
- `git diff --check`
- `PYTHONPATH=src python -m pytest --collect-only -q`
- `PYTHONPATH=src python -m pytest tests/test_governance_docs.py tests/test_release_readiness.py tests/test_testplan_inventory.py -q`
- `PYTHONPATH=src python -m hermesoptimizer ext-doctor --dry-run`
- `PYTHONPATH=src python -m hermesoptimizer ext-sync --dry-run`
- `PYTHONPATH=src python -m hermesoptimizer release-readiness --dry-run`
- `PYTHONPATH=src python -m hermesoptimizer brain-doctor --dry-run`
- `python3 brain/scripts/provider_probe.py --config brain/evals/provider-canaries.json --dry-run`
- `PYTHONPATH=src python -m pytest -q`

## Post-release notes
- Keep MiniMax/crof/nacrof as examples of the generic lane-state policy, not special-case code paths.
- Leave OpenClaw/OpenCode adapters and remote workflow automation for the v1.0 series.
- If future closeout work touches release docs, run `release-readiness --dry-run` and the governance/testplan selectors before calling it done.
