# Hermes Optimizer /todo — Current Release: v0.9.0

Status: Active.

Current release: v0.9.0.
- `python3 -m pytest -q` passes
- 1,534 tests collected
- 69 test files

## Completed — v0.8.1 Test Strategy and Validation Hardening

- [x] Freeze and archive v0.8.0 artifacts
- [x] Define layered test model (L0-L4)
- [x] Cover all active domains with explicit selectors
- [x] Separate in-repo coverage from installed-artifact smoke
- [x] Keep safety contracts explicit (no production vault mutation)
- [x] TESTPLAN.md canonical with 76 test files aligned
- [x] `scripts/validate_testplan.py` passing

## Completed — v0.9.0 Budget Tuning Module

- [x] BudgetProfile data model and presets (low/low-medium/medium/medium-high/high)
- [x] Session log analyzer (BudgetSignal extraction from Hermes sessions)
- [x] Budget recommender with sliding scale logic
- [x] Budget tuner with dry-run/config writer
- [x] CLI commands (`budget-review`, `budget-set`)
- [x] Budget-watch passive monitor
- [x] ARCHITECTURE.md updated with v0.9.0 section
- [x] TESTPLAN.md updated with Domain J (Budget tuning)

## Active — v0.9.0 Released

Current focus: multi-harness support and remote workflow automation (v1.0 series).

## Next Release (v1.0 series)

Scope:
- SSH bootstrap and tmux session reuse for remote workflows
- Private/VPN IP defaults and port-range conventions
- Install-skill bundles for common environments
- OpenClaw adapter and health/config probes
- OpenCode adapter and config/routing parsing
- Multi-harness correlation after Hermes-side repair flow is mature

## Completed — Documentation Unification and Cleanup

- [x] Finalize CHANGELOG.md with v0.8.1 and v0.9.0 entries
- [x] Unify version references across docs (README, GUIDELINE, ROADMAP, pyproject.toml, __init__.py)
- [x] Archive old VERSION*.md files to docs/archive/
- [x] Workflow path hygiene verified (base_dir = project root)
- [x] CLI usage string lists all commands
