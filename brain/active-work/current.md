# Active Work: v0.9.3 testing preparation — 2026-04-24

## Objective
Keep the closed v0.9.3 clean-install/provider-registry release ready for human and automated testing by preventing governance, provider-canary, extension-contract, and active-work drift from reopening completed work.

## Verified state
- Branch: `dev/0.9.3`.
- v0.9.3 waves 0-7 and acceptance gates are complete in `TODO.md`.
- Post-closeout audit artifacts exist under ignored `.swarm/` logs; their actionable findings are now represented as deterministic tests and doc updates instead of active swarm work.
- `ProviderRegistry.from_merged_sources()` is the canonical provider view; live config adapters remain low-priority sources for config-only providers.
- MiniMax remains a quarantine candidate from request-dump evidence; nacrof/crof is fallback-only until its canary is green.

## Current blockers
None for local testing prep.

## Next deterministic step
run the testing-prep gate before handing off:
- `PYTHONPATH=src python -m pytest tests/test_governance_docs.py tests/test_release_readiness.py -q`
- `PYTHONPATH=src python -m hermesoptimizer release-readiness --dry-run`
- `PYTHONPATH=src python -m pytest -q`

## Verification commands
- `git diff --check`
- `PYTHONPATH=src python -m pytest tests/test_governance_docs.py tests/test_release_readiness.py -q`
- `PYTHONPATH=src python -m hermesoptimizer release-readiness --dry-run`
- `PYTHONPATH=src python -m pytest -q`
