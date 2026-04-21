# PRD: Unified CLI and `run` Pipeline (P1 + P2)

## Problem

The CLI is split across two dispatch systems:
1. `__main__.py` — hand-rolled `if command == "..."` for v0.9.1 commands
2. `run_standalone.py` — argparse for legacy commands (init-db, add-record, export, etc.)

The `run` command is a no-op. The Performance Intelligence Suite modules (tokens, perf, tools, network) exist but are not invoked by any unified pipeline. Auto-discovery of Hermes sessions is not implemented.

## Goals

1. **Single CLI tree** — one `argparse.ArgumentParser` with subparsers for every command
2. **Working `run` pipeline** — `hermesoptimizer run` discovers Hermes surfaces, runs all analyzers, stores findings, exports reports
3. **Zero regressions** — all existing commands keep working; all 1,614 tests still pass
4. **Orphaned module wiring** — `tool_surface`, `verify`, `dreams` get CLI exposure

## Non-Goals

- No new analysis algorithms
- No live network probes in default run (keep deterministic)
- No daemon mode
- No config file format changes

---

## Command Inventory

### Legacy commands (move into unified parser)
- `init-db`
- `add-record`
- `add-finding`
- `export`
- `list-records`
- `list-findings`
- `vault-audit`
- `vault-writeback`
- `budget-review`
- `budget-set`

### v0.9.1 commands (already in `__main__.py`, migrate to unified parser)
- `token-report [path]`
- `token-check <path>`
- `perf-report [path]`
- `perf-check <path>`
- `tool-report [path]`
- `tool-check <path>`
- `port-reserve <port>`
- `port-list`
- `port-release <port>`
- `ip-list`
- `ip-add <ip>`
- `network-scan`

### New commands
- `run` — unified analysis pipeline
- `provider list` — from `tool_surface`
- `provider recommend` — from `tool_surface`
- `verify-endpoints` — from `verify/endpoints.py`
- `dreams-sweep` — from `dreams/sweep.py`

### Workflow commands (keep, but wire into unified parser)
- `todo`
- `devdo` / `dodev`
- `caveman`

---

## Architecture

### Before

```
__main__.py
  if command == "run": run_standalone.main(rest)
  if command == "token-report": ...
  ... (15 more if blocks)
  else: run_standalone.main()   # falls through to legacy argparse

run_standalone.py
  argparse with subparsers for init-db, add-record, export, ...
```

### After

```
cli/
  __init__.py
  parser.py        # single argparse tree, all subparsers
  run.py           # run pipeline implementation
  legacy.py        # init-db, add-record, export, list-* handlers
  workflow.py      # todo, devdo, caveman handlers
  v091.py          # token-*, perf-*, tool-*, network-* handlers
  orphan.py        # provider list, verify-endpoints, dreams-sweep handlers

__main__.py
  from cli import build_parser, dispatch
  parser = build_parser()
  args = parser.parse_args()
  dispatch(args)   # single dispatch table, no if-chain
```

---

## `run` Pipeline Design

### Phase 1: Discovery

```python
def discover_hermes_surfaces() -> list[Path]:
    """Return list of inspectable file paths."""
    roots = [
        Path.home() / ".hermes" / "sessions",
        Path.home() / ".hermes" / "logs",
        Path.home() / ".config" / "hermes" / "sessions",
        Path.home() / ".config" / "hermes" / "logs",
    ]
    files: list[Path] = []
    for root in roots:
        if root.exists():
            files.extend(root.rglob("*.json"))
            files.extend(root.rglob("*.yaml"))
            files.extend(root.rglob("*.log"))
    return files
```

### Phase 2: Analysis

```python
def run_analysis(files: list[Path], db_path: Path) -> dict:
    run_id = start_run(db_path, title="auto")
    findings: list[Finding] = []

    # Token analysis
    token_findings = analyze_tokens(files)
    findings.extend(token_findings)

    # Performance analysis
    perf_findings = analyze_perf(files)
    findings.extend(perf_findings)

    # Tool usage analysis
    tool_findings = analyze_tools(files)
    findings.extend(tool_findings)

    # Network validation (from config, not live scan)
    network_findings = validate_network_from_config(files)
    findings.extend(network_findings)

    # Store
    for f in findings:
        upsert_finding(db_path, f)

    finish_run(db_path, run_id, finding_count=len(findings))
    return {"run_id": run_id, "finding_count": len(findings), "files": files}
```

### Phase 3: Report

```python
def emit_report(run_result: dict, db_path: Path, out_dir: Path) -> None:
    records = [Record(**row) for row in get_records(db_path)]
    findings = [Finding(**row) for row in get_findings(db_path)]
    inspected = [{"type": "file", "path": str(p)} for p in run_result["files"]]
    metrics = compute_report_metrics(records, findings, inspected)
    write_json_report(out_dir / "report.json", ...)
    write_markdown_report(out_dir / "report.md", ...)
```

---

## Auto-Discovery for Analyzer Commands

Change the signature of `token-report`, `perf-report`, `tool-report`:

```python
# Before
parser.add_argument("path", help="Path to session file or directory")

# After
parser.add_argument("path", nargs="?", help="Path to session file or directory")
parser.add_argument("--auto-discover", action="store_true", default=True,
                    help="Scan known Hermes directories for sessions (default: True)")
```

If `path` is omitted and `--auto-discover` is set, call `discover_hermes_surfaces()` and use those files.

---

## CLI Implementation Plan

### Phase A: Create `cli/` package
1. `src/hermesoptimizer/cli/__init__.py` — `build_parser()` and `dispatch()`
2. `src/hermesoptimizer/cli/parser.py` — unified argparse tree
3. `src/hermesoptimizer/cli/legacy.py` — handlers moved from `run_standalone.py`
4. `src/hermesoptimizer/cli/v091.py` — handlers moved from `__main__.py`
5. `src/hermesoptimizer/cli/run.py` — new run pipeline
6. `src/hermesoptimizer/cli/orphan.py` — stubs for provider list, verify-endpoints, dreams-sweep

### Phase B: Refactor `__main__.py`
Replace the entire body with:
```python
from hermesoptimizer.cli import build_parser, dispatch
from hermesoptimizer.paths import ensure_dirs

ensure_dirs()

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return dispatch(args)

if __name__ == "__main__":
    raise SystemExit(main())
```

### Phase C: Refactor `run_standalone.py`
- Move handler functions into `cli/legacy.py`
- Keep `run_standalone.py` as a thin re-export for backward compatibility, or delete it after verifying nothing imports it

### Phase D: Wire orphaned modules
- `tool_surface/commands.py` → `cli/orphan.py:handle_provider_list`, `handle_provider_recommend`
- `verify/endpoints.py` → `cli/orphan.py:handle_verify_endpoints`
- `dreams/sweep.py` → `cli/orphan.py:handle_dreams_sweep`

### Phase E: Add tests
- `tests/test_cli_unified.py` — test `build_parser()` produces all subparsers
- `tests/test_cli_dispatch.py` — test `dispatch()` routes correctly (mocked handlers)
- `tests/test_run_pipeline.py` — test run pipeline with temp files
- `tests/test_cli_integration.py` — subprocess tests for every command

---

## Test Plan

| Test | Scope | Method |
|------|-------|--------|
| Parser construction | Unit | Assert every expected subparser exists |
| Dispatch routing | Unit | Mock handlers, assert correct one called per command |
| Run pipeline | Unit | Temp dir with fake session files, assert findings stored |
| Auto-discovery | Unit | Temp dir with `.json` files, assert discovered |
| Legacy commands | Integration | Subprocess `init-db`, `add-record`, `export` |
| v0.9.1 commands | Integration | Subprocess `token-report`, `perf-check`, etc. |
| Full suite | Regression | `pytest -q` passes with 0 failures |

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking existing CLI contracts | Keep all argument names and defaults identical |
| Import cycles from moving code | `cli/` imports from sibling modules, not vice versa |
| Orphaned modules are stubs | Wire them as thin passthroughs; do not expand their logic |
| `run` pipeline is slow | Make analysis lazy — skip empty files, short-circuit on zero findings |
| Test count drops from refactoring | Only move code, do not delete tests. Add new ones. |

---

## Rollback Plan

If the refactor breaks CI or user workflows:
1. `git revert` the merge commit
2. `run_standalone.py` and `__main__.py` are restored intact
3. No DB schema changes means no data migration needed
