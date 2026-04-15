# Changelog

All notable changes to Hermes Optimizer.

## v0.4.0 -- Workflow engine and multi-agent orchestration

### Added

- `/todo` command: create, update, freeze, add tasks, validate plan quality
- `/devdo` command: start runs, build task DAGs, dispatch parallel subagent batches
- `/dodev` backward-compatible alias for `/devdo`
- `workflow/schema.py`: WorkflowPlan, WorkflowRun, WorkflowTask, WorkflowCheckpoint, WorkflowBlocker dataclasses (schema version 1.0)
- `workflow/store.py`: YAML persistence with file locking and round-trip validation
- `workflow/guard.py`: Runtime guard with preflight checks, boundary validation, phase transitions, batch limits, write consistency, plan version alignment, safe drift auto-repair
- `workflow/scheduler.py`: Task DAG construction, dependency depth levels, role pools (research=3, implement=4, test=2, review=2, verify=2, integrate=1, guardrail=1), batch computation with max_parallelism=10
- `workflow/executor.py`: Execution state machine with dispatch, complete, block, review, resume; checkpoint emission; blocker routing
- `workflow/plan_shaper.py`: Plan quality validation, default task chain generation, scope/non-goals extraction, exit criteria setting
- `workflow/ux_format.py`: Terminal-friendly formatted output for /todo handoff and /devdo startup screens
- `commands/todo_cmd.py`: /todo slash command with create, show, add_task, freeze, list, status subcommands
- `commands/devdo_cmd.py`: /devdo slash command with start_run, load_state, update_task, checkpoint, blocker, resolve subcommands
- `commands/__init__.py`: Command registry with alias routing
- `docs/WORKFLOW.md`: Standalone operator guide with quickstart, command reference, flow examples
- 93 new tests across 8 test files covering workflow engine, commands, and smoke validation

### Changed

- `__main__.py` updated with /todo and /devdo entry points plus /dodev alias
- `ARCHITECTURE.md` updated with workflow state system section
- `GUIDELINE.md` updated with /todo and /devdo workflow rules

### Tests

- 332 tests passing (93 new), 0 failures

## v0.3.0 -- Provider-model catalog and routing diagnosis

### Added

- `ProviderTruthStore`: canonical provider catalog covering OpenAI, Anthropic, Google, Qwen/Alibaba, Kimi/Mooncake, xAI, Zhipu AI, MiniMax
- Model validation: STALE_MODEL, DEPRECATED_MODEL, RKWE (right-key-wrong-endpoint), UNKNOWN_PROVIDER detection
- `route/diagnosis.py`: routing diagnosis with CRITICAL/IMPORTANT/GOOD_IDEA/NICE_TO_HAVE/WHATEVER priority ranking
- Broken fallback chain detection
- Live truth gate (`HERMES_LIVE_TRUTH_ENABLED=1`)
- Agent management module

### Changed

- Endpoint verification enriched with provider truth lookups
- Report sections now show routing-level diagnosis alongside config-level findings

## v0.2.0 -- Runtime hygiene and provider cleanup

### Added

- Gateway health and CLI health validation
- Provider registry cleanup: blank provider removal, duplicate collapse, stale alias stripping
- Canonical provider env resolution (base_url and api_key from environment, not embedded model fields)
- Invalid new-session bootstrap detection
- Credential re-seeding suppression
- Report metrics module
- Run history persistence

### Changed

- Session analysis now distinguishes provider, endpoint, gateway, CLI, and credential-source failures
- Reports show inspected inputs and exact health evidence

## v0.1.0 -- Initial analysis baseline

### Added

- Hermes config discovery and parsing
- Session file analysis with failure classification
- Log file scanning for auth errors, timeouts, crashes
- SQLite catalog with normalized records and findings
- JSON and Markdown report export
- Phase 0/1 discover-parse-diagnose-report loop
- CLI entry point with run and report commands
- Web scraping adapters (Exa, Firecrawl) for live truth lookups
