# Hermes Optimizer v0.9.1 Post-Release Plan

v0.9.1 landed the Performance Intelligence Suite (tokens, perf, tools, network) as individually-testable modules with CLI wiring. The modules work, but the tool does not yet function as a unified harness intelligence layer.

This document enumerates the gaps and sets priority order for closing them.

---

## Gap Assessment

| Module Count | ~100 Python files across 15+ packages |
| Test Count | 1,614 unit tests (good coverage) |
| CLI Surface | Split between `__main__.py` ad-hoc dispatch and `run_standalone.py` argparse |
| Orphaned Modules | `tool_surface/`, `verify/`, `dreams/`, `scrape/`, `sources/`, `catalog_refresh`, `agent_management` exist but have no CLI path |
| `run` Command | Prints help. Does not discover, parse, diagnose, or report. |
| Auto-Discovery | Token/perf/tool analyzers require manual `--path`. No Hermes session auto-discovery. |
| Data Lifecycle | Catalog DB grows forever. No vacuum, retention, or stats commands. |
| Integration Tests | None. CLI wiring is untested at the subprocess level. |

---

## Priority Order

### P1 — Make `hermesoptimizer run` actually run
The README promises "Discover, parse, diagnose, and report." The `run` command currently re-enters `main()` with no args and prints usage. It should:
- Discover Hermes config (`~/.hermes/config.yaml`, `~/.config/hermes/`)
- Discover session/log files from known locations
- Execute all analyzers (token, perf, tools, network) in sequence
- Store findings in the catalog DB
- Emit a unified JSON + Markdown report

**Acceptance:** `hermesoptimizer run` produces a report with inspected inputs, findings, and metrics without requiring manual `--path` arguments.

### P2 — Consolidate CLI into a single argparse tree
`__main__.py` uses hand-rolled `if command == "..."` dispatch for v0.9.1 commands, then falls through to `run_standalone.py` for legacy commands. Merge into one parser. Wire orphaned modules:
- `tool_surface/commands.py` → `provider list`, `provider recommend`, `workflow list`, `dreams inspect`, `report latest`
- `verify/endpoints.py` → `verify-endpoints`
- `dreams/sweep.py` → `dreams-sweep`

**Acceptance:** All commands live in one parser. `--help` shows the full command tree. No hand-rolled dispatch in `__main__.py`.

### P3 — Session auto-discovery for analyzers
Token/perf/tool analyzers take a `path` argument. Add `--auto-discover` (or make it the default) that scans `~/.hermes/sessions/`, `~/.hermes/logs/` for `.json`, `.yaml`, `.log` files and feeds them to analyzers.

**Acceptance:** `hermesoptimizer token-report` with no `--path` discovers and analyzes sessions automatically.

### P4 — Catalog data lifecycle
The SQLite DB at `~/.hoptimizer/db/catalog.db` grows unbounded. Add:
- `db-vacuum` — reclaim space
- `db-retention --days N` — prune old runs/findings
- `db-stats` — show table sizes, record counts

**Acceptance:** Commands exist, are tested, and actually modify/prune the DB.

### P5 — CLI integration tests
Add `tests/test_cli_integration.py` that runs `python -m hermesoptimizer <command>` as a subprocess for every command, verifying exit code 0 and sensible output.

**Acceptance:** Integration test runs in CI and catches import errors, missing subparsers, and broken dispatch.

---

## What is NOT in scope

- New analysis modules (no v0.9.2 features)
- Live network health probes in the default run (keep it file-based for determinism)
- GUI or web dashboard
- Daemon/watch mode (one-shot only for this pass)

---

## Definition of Done for this Plan

- `VERSION0.9.1.md` and `PRD-0.9.1-RUN-CLI.md` are archived
- `TODO.md` is updated with active checkboxes
- P1 and P2 are implemented, tested, and passing
- P3 is at least stubbed with a scanner that finds files
- P4 commands exist and have tests
- P5 integration test exists and passes
- Full test suite passes
- README updated with new command tree
