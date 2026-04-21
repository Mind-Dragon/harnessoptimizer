# Harness Optimizer /todo — Current Release: v0.9.1

Status: Active.

Current release: v0.9.1.
- `python3 -m pytest -q` passes
- 1,534 tests collected (baseline)
- 69 test files

## Active — v0.9.1 Performance Intelligence Suite

### Phase 1: Foundation
- [x] Version bump to 0.9.1 (pyproject.toml, README.md)
- [x] Create plan documents (PRD, ARCHITECTURE, TECHSPEC, TESTPLAN, BUILDPLAN)
- [ ] Add catalog schema migrations (token_usage, provider_perf, tool_usage, network_inventory)
- [ ] Network manager core (models, inventory, scanner, validator, enforcer)
- [ ] Network manager CLI (port-reserve, port-list, ip-list, ip-add, network-scan)

### Phase 2: Token Optimizer
- [ ] Token models + extractor
- [ ] Token analyzer + recommender
- [ ] Token CLI (token-review, token-report)

### Phase 3: Performance Monitor
- [ ] Perf models + collector
- [ ] Perf aggregator + reporter
- [ ] Perf CLI (perf-report, perf-check)

### Phase 4: Tool Optimizer
- [ ] Tool models + detector
- [ ] Tool analyzer + recommender
- [ ] Tool CLI (tool-review, tool-report)

### Phase 5: Loop Integration
- [ ] Wire tokens, perf, tools, network into loop.py
- [ ] Config-gated enablement
- [ ] Integration tests

### Phase 6: Documentation
- [ ] Update ARCHITECTURE.md
- [ ] Update README.md
- [ ] Update CHANGELOG.md
- [ ] Final test count verification
- [ ] Commit and push

## Completed — v0.9.0 Budget Tuning Module

- [x] BudgetProfile data model and presets
- [x] Session log analyzer
- [x] Budget recommender with sliding scale logic
- [x] Budget tuner with dry-run/config writer
- [x] CLI commands (`budget-review`, `budget-set`)
- [x] Budget-watch passive monitor

## Next Release (v1.0 series)

Scope:
- SSH bootstrap and tmux session reuse for remote workflows
- Private/VPN IP defaults and port-range conventions
- Install-skill bundles for common environments
- OpenClaw adapter and health/config probes
- OpenCode adapter and config/routing parsing
- Multi-harness correlation after Hermes-side repair flow is mature
