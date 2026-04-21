# Harness Optimizer /todo — Current Release: v0.9.1

Status: Complete.

Current release: v0.9.1.
- `python3 -m pytest -q` passes
- 1,610 tests collected
- 80 test files

## Completed — v0.9.1 Performance Intelligence Suite

Phase 1: Foundation
- [x] Catalog schema: token_usage, provider_perf, tool_usage, network_inventory tables
- [x] CRUD functions for all new tables
- [x] Network manager core: models, inventory, scanner, validator, enforcer
- [x] Network manager CLI: port-reserve, port-list, port-release, ip-list, ip-add, network-scan

Phase 2: Token Optimizer
- [x] tokens/models.py: TokenUsage, TokenWaste, TokenRecommendation
- [x] tokens/analyzer.py: parse sessions, detect waste (bloat, retries, tool loops, overflow)
- [x] tokens/optimizer.py: generate recommendations (model efficiency, compression, lane tuning)
- [x] tokens/commands.py: token-report, token-check CLI
- [x] 13 tests

Phase 3: Performance Monitor
- [x] perf/models.py: ProviderPerf, ProviderOutage
- [x] perf/analyzer.py: response times, error rates, retry rates, tokens/sec
- [x] perf/reporter.py: health dashboard
- [x] perf/commands.py: perf-report, perf-check CLI
- [x] 7 tests

Phase 4: Tool Optimizer
- [x] tools/models.py: ToolUsage, ToolMiss, ToolRecommendation
- [x] tools/analyzer.py: detect manual workarounds, tool avoidance, repeated failures
- [x] tools/optimizer.py: generate tool usage recommendations
- [x] tools/commands.py: tool-report, tool-check CLI
- [x] 13 tests

Phase 5+6: Integration and Release
- [x] All CLI commands wired into __main__.py
- [x] README.md updated with commands, architecture, test count
- [x] CHANGELOG.md updated with v0.9.1 release notes
- [x] Full test suite passes (1,610 tests, 5 skipped)
