# Harness Optimizer /todo — v0.9.1 Post-Release Refactor

Previous release: v0.9.1 (Performance Intelligence Suite) — archived.
Current focus: unify CLI surface, make `run` work, wire orphaned modules.

Plan documents:
- `VERSION0.9.1.md` — gap assessment and priority order
- `PRD-0.9.1-RUN-CLI.md` — detailed design for P1 + P2

---

## Phase A: CLI Consolidation (P2)

- [ ] Create `src/hermesoptimizer/cli/` package
  - [ ] `cli/__init__.py` — `build_parser()`, `dispatch()`
  - [ ] `cli/parser.py` — single argparse tree with all subparsers
  - [ ] `cli/legacy.py` — handlers for init-db, add-record, add-finding, export, list-records, list-findings, vault-audit, vault-writeback, budget-review, budget-set
  - [ ] `cli/v091.py` — handlers for token-report, token-check, perf-report, perf-check, tool-report, tool-check, port-reserve, port-list, port-release, ip-list, ip-add, network-scan
  - [ ] `cli/workflow.py` — handlers for todo, devdo, caveman
  - [ ] `cli/orphan.py` — stubs for provider list, provider recommend, verify-endpoints, dreams-sweep
- [ ] Refactor `__main__.py` to import `build_parser` + `dispatch`, remove all hand-rolled if-chains
- [ ] Refactor `run_standalone.py` — move handlers to `cli/legacy.py`, keep thin re-export or delete after verifying no imports
- [ ] Update `setup.py` / `pyproject.toml` entry points if needed
- [ ] Add `tests/test_cli_unified.py` — assert every expected subparser exists
- [ ] Add `tests/test_cli_dispatch.py` — mock handlers, assert correct routing
- [ ] Full test suite passes (1,614+ tests)

## Phase B: `run` Pipeline (P1)

- [ ] Implement `src/hermesoptimizer/discovery.py` — `discover_hermes_surfaces()` scans known Hermes directories
- [ ] Implement `src/hermesoptimizer/cli/run.py` — `handle_run(args)`
  - [ ] Phase 1: discover files
  - [ ] Phase 2: execute analyzers (token, perf, tools, network) in sequence
  - [ ] Phase 3: store findings in catalog DB
  - [ ] Phase 4: emit unified JSON + Markdown report
- [ ] Add `--out-dir` default to `~/.hoptimizer/reports/`
- [ ] Add `--title` for report naming
- [ ] Add `tests/test_run_pipeline.py` — temp dir with fake sessions, assert findings stored and reports written
- [ ] Verify `hermesoptimizer run` produces a report with inspected inputs, findings, and metrics

## Phase C: Auto-Discovery for Analyzers (P3)

- [ ] Update `token-report`, `perf-report`, `tool-report` signatures: `path` becomes `nargs="?"`
- [ ] Add `--auto-discover` flag (default True) to all three report commands
- [ ] If no `path` given, use `discover_hermes_surfaces()`
- [ ] Add tests for auto-discovery path vs explicit path

## Phase D: Catalog Data Lifecycle (P4)

- [ ] Add `db-vacuum` command — `VACUUM` the SQLite DB
- [ ] Add `db-retention --days N` command — prune runs/findings older than N days
- [ ] Add `db-stats` command — print table row counts and DB file size
- [ ] Add tests for each command

## Phase E: Integration Tests (P5)

- [ ] Add `tests/test_cli_integration.py`
  - [ ] Subprocess test for every command (legacy + v0.9.1 + new)
  - [ ] Assert exit code 0 and non-empty output
  - [ ] Run in CI / local pytest

## Phase F: Documentation and Release Prep

- [ ] Update README.md command table
- [ ] Update CHANGELOG.md with refactor notes
- [ ] Verify `python3 -m pytest -q` passes
- [ ] Archive this TODO.md and seed v0.9.2 plan if needed

---

## Acceptance Criteria

- `hermesoptimizer --help` shows a single unified command tree
- `hermesoptimizer run` discovers sessions and produces a report without manual `--path`
- All legacy commands still work with identical arguments
- All v0.9.1 commands still work with identical arguments
- Orphaned modules (`tool_surface`, `verify`, `dreams`) have at least one CLI command each
- Full test suite passes with zero failures
- Integration test runs every command as a subprocess
