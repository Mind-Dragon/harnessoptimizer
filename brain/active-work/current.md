# Active Work: v0.9.3 closeout and governance audit — 2026-04-24

## Objective
Close the v0.9.3 clean-install/provider-registry phase, align docs, commit locally, then run a full codebase audit against governing documents with parallel subagents.

## Verified state
- Branch: `dev/0.9.3`.
- v0.9.3 waves 1-7 and acceptance gates are marked complete in `TODO.md`.
- `openai-codex/gpt-5.5` is present in provider registry tests and hot-reload proof paths.
- Local Hermes integration scope is explicit: small hot-reload patch in `/home/agent/hermes-agent/cli.py`; unrelated `/home/agent/hermes-agent/internal/` is excluded.

## Current blockers
None for local closeout. Future audit findings may create follow-up work.

## Next deterministic step
Run verification gates, commit local docs/closeout changes, then dispatch parallel whole-codebase governance audit agents.

## Verification commands
- `PYTHONPATH=src python -m pytest -q`
- `PYTHONPATH=src python -m hermesoptimizer release-readiness --dry-run`
- `PYTHONPATH=src python -m hermesoptimizer provider-list`
- `python3 scripts/apply_reload_patch.py --check`
