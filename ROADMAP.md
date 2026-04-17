# Hermes Optimizer Roadmap

> Goal: keep Hermes accurate first, then extend to credential lifecycle management and multi-harness coverage.
>
> Current package version: 0.5.3. The milestones below are release/capability labels, not the installed package version.

## Product shape

Hermes Optimizer is a small core with harness-specific adapters plus a workflow orchestration layer.

Core responsibilities:
- initialize and maintain a canonical SQLite catalog
- normalize records and findings into one schema
- export JSON and Markdown reports
- run from CLI or cron
- keep raw source text for auditability

Workflow layer:
- `/todo` plans work, `/devdo` executes it
- task DAGs with role pools scale to 10+ concurrent subagents
- checkpoints, resume, two-stage review

Harness adapters:
- Hermes adapter: local logs, sessions, config, provider hygiene, gateway health, CLI health, runtime drift
- OpenClaw adapter: gateway health, config integrity, provider failures, plugin drift
- OpenCode adapter: agent config, provider routing, worktree/task behavior, logs
- future adapters: same shape, new source readers

## Completed versions

### v0.1.0 -- Hermes analysis baseline

Done. Ingests Hermes logs, sessions, config. Detects failures, auth errors, timeouts, crashes. SQLite + JSON + Markdown outputs. CLI entry point.

### v0.2.0 -- Runtime hygiene and provider cleanup

Done. Gateway/CLI health validation. Provider registry cleanup (blanks, duplicates, stale aliases). Canonical env resolution. Credential re-seeding suppression.

### v0.3.0 -- Provider-model catalog and routing diagnosis

Done. ProviderTruthStore with model validation. RKWE detection. Routing diagnosis with priority ranking. Broken fallback chain detection. Agent management.

### v0.4.0 -- Workflow engine and multi-agent orchestration

Done. `/todo` + `/devdo` two-command workflow. Task DAGs, role pools, scheduler, guard, executor, checkpoints, resume, two-stage review, UX rendering. 332 tests passing.

### v0.5.0 -- Vault management and credential lifecycle

Done. Vault package under `src/hermesoptimizer/vault/` with read-only primitives: inventory discovery, fingerprinting, validation, deduplication, rotation hints, and bridge planning. Tests use repo-local `tmp/.vault` fixtures. Production installs read from `~/.vault`. Write-back is opt-in and non-destructive by default.

### v0.5.1 -- Vault harness integration and CLI surface

Done. Hermes vault skill added, CLI audit/report path added, provider-validation adapter hook added, target-format-aware write-back planning added, and vault tests expanded. The non-destructive contract remains in place: read from `~/.vault`, test with repo-local `tmp/.vault`, and never mutate without explicit opt-in.

### v0.5.2 -- Vault operational iteration

Done. Live provider validation backends, broader source parsing (YAML/JSON/shell profiles/CSV/TXT/DOCX/PDF/images via Docling), actual write-back execution with confirmation, rotation automation hooks, and Docling OCR integration for screenshot-based credentials.

### v0.5.3 -- Caveman mode for token-efficient output

Done. Caveman-style output compression added as an opt-in feature for Hermes-wide work. Reduces output tokens ~75% while preserving technical accuracy. Safety-critical paths (vault write-back, config mutations, destructive operations, auth/credential handling, setup/onboarding) stay in full mode regardless of setting. Persistent config via `~/.hermes/config.yaml` with `caveman_mode` key. CLI toggle via `python -m hermesoptimizer caveman`. Hermes skill created at `~/.hermes/skills/software-development/caveman/SKILL.md`. 34 tests passing.

## Next version

### v0.6.0 -- OpenClaw gateway and config diagnosis

Scope:
- add an OpenClaw adapter that reads gateway health and config
- detect gateway-down, auth-fail, provider-crash, clobbering, plugin drift, and stale config patterns
- add SSH bootstrap/session reuse for remote runs so the agent does not SSH for every command
- add tmux session management for persistent remote workflows
- establish private/VPN IP defaults instead of localhost
- establish port range conventions for dev servers (not just 8000/3000)
- add default install skills for common dev environments
- pull in gateway logs and health endpoint status
- map findings into the same canonical schema used by Hermes
- add repair-oriented report sections so operators can see what needs fixing

Primary source targets:
- `~/.openclaw/openclaw.json`
- `~/.openclaw/logs/`
- gateway health endpoint and status output
- plugin allowlist / entry config

What v0.6.0 must answer:
- is the gateway alive
- is the config still the last known good version
- which provider is failing
- what repair action is most likely to work

### v0.7.0 -- OpenCode agent config and provider routing

Scope:
- add an OpenCode adapter for agent config, provider routing, and runtime behavior
- detect broken model mappings, invalid provider endpoints, and agent-level execution problems
- ingest worktree/task metadata when present
- track config drift and missing plugin or skill references
- keep the same catalog and reporting pipeline

Primary source targets:
- OpenCode config files
- OpenCode logs and task traces
- provider routing metadata
- worktree-aware runtime files

### v0.8.0+ -- Cross-harness correlation and adapter template

Scope:
- reports that combine findings from multiple harnesses in a single run
- cross-harness correlation (same provider failing in Hermes and OpenClaw)
- adapter template module so new harnesses are cheap to add
- cron-driven continuous monitoring mode

Future additions should follow one rule:
- if it can be read, normalized, and reported, it can become an adapter

## Architecture direction

The implementation stays plugin-like even if the first versions are built in-tree.

Layering:
- core catalog and report code stays shared
- each harness gets its own source adapter module
- each adapter returns the same Finding / Record style objects
- validators and reporters stay harness-agnostic
- versioned behavior is driven by adapter registration, not forks
- provider truth store is harness-agnostic and can be shared across adapters
- vault management is harness-agnostic (credentials span all adapters)
- workflow engine is harness-agnostic (plans and runs are generic)

That keeps Hermes, OpenClaw, OpenCode, and vault management from turning into separate projects.

## Suggested delivery order

1. ~~Finish Hermes v0.1.0 parsing and reporting~~
2. ~~Add fixture-driven tests for Hermes sources~~
3. ~~Add v0.2.0 provider cleanup and health checks~~
4. ~~Add invalid-session bootstrap detection and credential suppression~~
5. ~~Build provider-model catalog with Qwen3.6 Plus and Alibaba model types~~
6. ~~Add model validation (stale, deprecated, RKWE) with priority ranking~~
7. ~~Add routing diagnosis and broken fallback chain detection~~
8. ~~Build /todo + /devdo workflow engine with scheduler, guard, executor~~
9. Add vault management: credential inventory, validation, dedup, rotation tracking
10. Add vault bridge: write-back for .env and YAML formats
11. Add OpenClaw adapter and health/config probes
12. Add OpenCode adapter and config/routing parsing
13. Tighten shared normalization and reporting across all harnesses
14. Add adapter template for new harness onboarding

## Definition of done for the roadmap

This roadmap is done when:
- Hermes, OpenClaw, and OpenCode are all first-class adapters
- vault management provides credential lifecycle visibility across all adapters
- each harness has source-specific tests and shared integration tests
- the provider-model catalog covers the most common providers and validates model names
- the reports can compare runs across harnesses
- adding a new harness is mostly a new adapter module plus fixtures, not a rewrite
