# Changelog

All notable changes to Hermes Optimizer.

## v0.9.0 -- Agent Turn Budget Tuning

### Added

- `budget/profile.py`: BudgetProfile dataclass with five-step presets (low, low-medium, medium, medium-high, high)
- `budget/analyzer.py`: BudgetSignal extraction from Hermes session JSON logs
- `budget/recommender.py`: Sliding-scale recommendation logic based on turn utilization and completion rates
- `budget/tuner.py`: Config writer with dry-run and --confirm safety flow
- `budget/commands.py`: CLI subcommands `budget-review` and `budget-set`
- `budget/watch.py`: Passive post-session monitor appending to `~/.hermes/budget-advice.log`
- Domain J in TESTPLAN.md with 151 tests across 6 test files
- Per-role budget defaults (research, implement, test, review, verify, integrate)

### Changed

- ARCHITECTURE.md updated with v0.9.0 budget module section
- README.md updated with budget command references

### Tests

- 1,534 tests passing (151 new), 0 failures
- 76 test files covering budget, workflow, vault, dreaming, tool-surface domains

## v0.8.1 -- Test Strategy and Validation Hardening

### Added

- Layered test model (L0-L4) with explicit domain ownership
- L0: Static/import/schema checks (40 tests)
- L1: Deterministic unit tests (875 tests)
- L2: Component integration tests (31 tests)
- L3: Plugin and installed-artifact smoke tests (25 tests)
- L4: Release-gate CLI/workflow smoke tests
- `scripts/validate_testplan.py`: Testplan alignment validator
- Isolated `HERMES_HOME` sandbox strategy for installed-artifact tests

### Changed

- TESTPLAN.md: Canonical test matrix with real selectors, layer assignments, and domain breakdown
- No live-network tests in default gate (opt-in behind `HERMES_LIVE_TRUTH_ENABLED=1`)
- Production vault access explicitly prohibited in test suite

### Tests

- 1,383 tests passing at start of v0.8.1
- 1,534 tests passing at completion (151 new)
- Test files: 65 → 76
- 5 skipped (mostly docling deprecation warnings)

## v0.7.0 -- Vault encryption overhaul and agent plugins

### Added

- `vault/crypto.py`: ChaCha20-Poly1305 encryption with Argon2id KDF for secrets at rest
- `vault/session.py`: VaultSession context manager with get/set/delete/list_entries, real-value write-back, and atomic writes (temp+rename)
- `vault/plugins/base.py`: VaultPlugin ABC with abstract CRUD methods, status helper, and context manager protocol
- `vault/plugins/hermes_plugin.py`: HermesPlugin — direct Python VaultSession wrapper for Hermes Agent
- `vault/plugins/openclaw_plugin.py`: OpenClawPlugin — HTTP bridge sidecar (http.server, port 8599) with bearer token auth
- `vault/plugins/opencode_plugin.py`: OpenCodePlugin — read-only plugin with generate_config() and inject_env()
- `scripts/convert_vault.py`: Conversion script with --dry-run mode; creates backup, encrypts secrets, writes vault.enc.json
- Dual-type VaultEntry: is_encrypted, encrypted_value, plaintext_value fields with auto-classification
- 20-char hex fingerprints (80 bits) with migrate_fingerprint() for legacy 12-char support
- Hermes and OpenClaw provider status providers
- TOML parser (tomllib) and pyyaml-based YAML parser

### Changed

- Fingerprint length: 12 chars (48 bits) -> 20 chars (80 bits) throughout vault module
- AWS STS and Azure AD providers: stubbed with NotImplementedError (broken auth logic removed)
- `discover_vault_files()`: added skip_dirs parameter (default excludes .venv, .git, __pycache__, etc.)
- CSV parser: filters entries by secret-pattern key names to reduce noise
- JSON parser: guards against list-root files that caused crashes
- VaultSession now reads/writes vault.enc.json as single source of truth (no individual YAML files)
- argon2-cffi made a lazy import in crypto.py to avoid CLI subprocess failures

### Fixed

- Salt mismatch in convert_vault.py: now stores actual derivation salt in vault.enc.json (not random)
- EnvFileRotationAdapter non-atomic writes replaced with temp+rename pattern
- Inventory scan: 809 entries (mostly CSV noise) -> 330 entries after filter fixes

### Tests

- 955 tests passing (113 new), 0 failures
- 16 plugin unit tests + 5 cross-plugin integration tests
- 12 conversion round-trip tests
- Real ~/.vault converted: 19 secrets encrypted, 311 metadata plaintext, 19/19 round-trip decrypt verified

## v0.4.0 -- Workflow engine and multi-agent orchestration

### Added

- `/todo` command: create, update, freeze, add tasks, validate plan quality
- `/devdo` command: start runs, build task DAGs, dispatch parallel subagent batches
- `/dodev` backward-compatible alias for `/devdo`
- `workflow/schema.py`: WorkflowPlan, WorkflowRun, WorkflowTask, WorkflowCheckpoint, WorkflowBlocker dataclasses (current schema)
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
