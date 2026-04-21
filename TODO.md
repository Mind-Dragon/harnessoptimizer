# Harness Optimizer /todo — v0.9.1 Closeout Complete

Current package version: `0.9.1`
Repo state for this plan: closeout queue completed and verified.

This file now serves as the completion record for the `0.9.1` closeout pass.
If new work starts, seed a fresh plan instead of reopening the completed checklist below.

Plan references:
- `VERSION0.9.1.md` — preserved as historical gap assessment
- `PRD-0.9.1-RUN-CLI.md` — preserved as historical design doc

---

## Completion status

### Implemented in code and verified

- [x] Unified CLI package exists under `src/hermesoptimizer/cli/`
- [x] `src/hermesoptimizer/__main__.py` uses `build_parser()` + `dispatch()`
- [x] `src/hermesoptimizer/run_standalone.py` is a backward-compatible shim
- [x] `src/hermesoptimizer/discovery.py` exists and discovers Hermes surfaces
- [x] `src/hermesoptimizer/cli/run.py` performs the real run pipeline and writes JSON + Markdown reports
- [x] Auto-discovery landed for `token-report`, `perf-report`, and `tool-report`
- [x] DB lifecycle commands exist: `db-vacuum`, `db-retention`, `db-stats`
- [x] `verify-endpoints` is a real CLI surface with parser/help/output
- [x] `dreams-sweep` is a real CLI surface with parser/help/output
- [x] `provider-recommend` is a real CLI surface with ranked output
- [x] `report-latest` reads from the runtime report directory via `get_report_dir()`
- [x] Focused CLI/run test files exist:
  - [x] `tests/test_cli_unified.py`
  - [x] `tests/test_cli_dispatch.py`
  - [x] `tests/test_run_pipeline.py`
  - [x] `tests/test_cli_integration.py`
- [x] Release docs reconciled:
  - [x] `README.md`
  - [x] `GUIDELINE.md`
  - [x] `ROADMAP.md`
  - [x] `CHANGELOG.md`
  - [x] `VERSION0.9.1.md` historical note added
  - [x] `PRD-0.9.1-RUN-CLI.md` historical note added

---

## Verification evidence

### Focused closeout command/tests

- [x] `PYTHONPATH=src python -m pytest tests/test_cli_unified.py tests/test_cli_dispatch.py tests/test_run_pipeline.py tests/test_cli_integration.py -q`
- [x] `PYTHONPATH=src python -m pytest tests/test_tool_surface_commands.py tests/test_tool_surface_provider_recommend.py tests/test_provider_truth.py tests/test_dreams_sweep.py -q`
- [x] `PYTHONPATH=src python -m pytest tests/test_caveman_config.py::TestCavemanCLISmoke tests/test_vault_audit.py::test_vault_audit_default_vault_root -q`

### Full-suite and live CLI probes

- [x] `PYTHONPATH=src python -m pytest -q`
- [x] `PYTHONPATH=src pytest --collect-only`
- [x] `PYTHONPATH=src python -m hermesoptimizer --help`
- [x] `PYTHONPATH=src python -m hermesoptimizer run --help`
- [x] `PYTHONPATH=src python -m hermesoptimizer verify-endpoints --help`
- [x] `PYTHONPATH=src python -m hermesoptimizer provider-recommend --help`
- [x] `PYTHONPATH=src python -m hermesoptimizer dreams-sweep --help`
- [ ] Installed entrypoint check: `hermesoptimizer --help`
  - [ ] Not available in the current shell (`command not found`), so src-layout verification remained the reliable gate for this session.
- [x] `git diff --check`

---

## Outcome

- [x] Shipped commands are real, or explicitly grounded in current runtime behavior
- [x] Focused parser/dispatch/run/integration tests exist and pass
- [x] `README.md`, `GUIDELINE.md`, `ROADMAP.md`, `CHANGELOG.md`, and `TODO.md` are aligned with live code
- [x] Full suite passes on the unified CLI branch state

## Next action

No active `0.9.1` closeout items remain.
Next work should start from a fresh TODO seeded from the next requested feature or release slice.
