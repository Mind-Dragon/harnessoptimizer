# Hermes Optimizer Roadmap

> Goal: keep Hermes accurate first, then extend the same core to other harnesses later.

## Product shape

Hermes Optimizer is a small core with harness-specific adapters.

Core responsibilities:
- initialize and maintain a canonical SQLite catalog
- normalize records and findings into one schema
- export JSON and Markdown reports
- run from CLI or cron
- keep raw source text for auditability

Harness adapters:
- Hermes adapter: local logs, sessions, config, provider hygiene, gateway health, CLI health, runtime drift
- OpenClaw adapter: gateway health, config integrity, provider failures, plugin drift
- OpenCode adapter: agent config, provider routing, worktree/task behavior, logs
- future adapters: same shape, new source readers

## Version plan

### v1.0 — Hermes analysis baseline

Scope:
- ingest Hermes logs and session files
- detect failures, timeouts, auth errors, crashes, and noisy patterns
- read Hermes config and runtime metadata when available
- classify findings into stable categories and lanes
- write SQLite + JSON + Markdown outputs
- provide a CLI and cron-friendly entry point

Primary source targets:
- `~/.hermes/logs/`
- `~/.hermes/sessions/`
- `~/.hermes/config.yaml`
- Hermes-local runtime artifacts, caches, and state files

What v1.0 must answer:
- what failed
- where it failed
- how often it failed
- whether it looks like user error, provider failure, config drift, or infrastructure noise

Acceptance criteria:
- given a Hermes log bundle, the tool produces deterministic findings
- findings are deduplicated and normalized
- exports are generated without manual intervention
- tests cover catalog writes, Hermes source scanning, and report generation

Out of scope for v1.0:
- OpenClaw-specific logic
- OpenCode-specific logic
- remote browser or web scraping beyond the pieces needed for live truth checks
- fancy ML classification

### v1.1 — Hermes runtime hygiene and provider cleanup

Scope:
- normalize provider registry entries
- remove blank providers and collapse duplicate aliases
- strip stale `model.base_url` and `model.api_key` from canonical providers
- ignore or clear stale env overrides that conflict with canonical routing
- validate Hermes gateway health and CLI health before a session is considered ready
- detect invalid new-session bootstrap data
- suppress credential sources that were deliberately removed so they do not re-seed themselves
- keep the report honest about what was actually healthy

Primary source targets:
- `~/.hermes/config.yaml`
- `~/.hermes/logs/`
- `~/.hermes/sessions/`
- gateway health endpoint
- Hermes CLI status output
- auth metadata / credential source tracking

What v1.1 must answer:
- is the gateway alive
- is the CLI healthy
- is the provider registry clean
- which provider entry is blank, duplicate, or stale
- is the bad state in the new session bootstrap path or in the runtime itself
- did a removed credential reappear from a hidden source

Acceptance criteria:
- the Hermes session bootstrap path does not emit blank or duplicate provider entries
- canonical providers do not carry stale embedded endpoint or key fields
- gateway and CLI health are checked explicitly and separately
- invalid new-session data is detected before reuse
- removed credentials do not silently re-seed
- report output clearly distinguishes provider, endpoint, gateway, CLI, and credential-source failures

Out of scope for v1.1:
- mutating config automatically without explicit repair logic
- making provider-side remediation decisions without operator approval
- coupling Hermes parsing to OpenClaw or OpenCode assumptions

### v1.2 — Provider-model catalog, model validation, and agent management

Scope:
- build a canonical provider-model catalog (`ProviderTruthStore`) covering common Hermes providers
- validate configured model names against the known model list
- detect deprecated models and flag them with deprecation notices
- detect RKWE (right-key-wrong-endpoint) errors using canonical endpoint comparison
- add routing-level diagnosis for agent-level failures
- detect broken fallback chains and rank auth failures by position in the chain
- keep all v1.1 hygiene work intact

Provider coverage for v1.2:
- OpenAI (gpt-4o, gpt-4o-mini, gpt-5; deprecated: gpt-4, gpt-3.5)
- Anthropic (claude-3-5-sonnet, claude-3-5-haiku; deprecated: claude-3-opus, claude-3-sonnet)
- Google (gemini-2.0-flash, gemini-2.5-pro)
- Qwen / Alibaba (qwen3.6-plus, plus vision, rerank, embedding, speech, image, video models; note: some Alibaba models are CN-only or have region scope constraints)
- Kimi / Mooncake (kimi-k2, moonshot-v1)
- xAI (grok-3, grok-2)
- Zhipu AI (glm-4, glm-4v)
- MiniMax (abab6, hailuo-ai)
- Others as discovered

Model validation checks:
- STALE_MODEL: configured model not in provider's known model list
- DEPRECATED_MODEL: configured model in provider's deprecated list
- RKWE: correct API key but wrong base URL
- UNKNOWN_PROVIDER: provider not in the truth store
- AUTH_FAILURE: live endpoint returns 401/403 (distinguished from config-only failures)

Routing diagnosis:
- CRITICAL: auth failure on a lane's primary provider
- IMPORTANT: auth failure on a fallback provider; timeouts with fewer than 3 retries
- CRITICAL: timeouts with 3 or more retries
- IMPORTANT: broken fallback chain (some providers in a chain failing, others still up)
- GOOD_IDEA: stale model name in config
- Priority ordering: CRITICAL > IMPORTANT > GOOD_IDEA > NICE_TO_HAVE > WHATEVER

Live truth gate:
- live truth lookups are off by default (HERMES_LIVE_TRUTH_ENABLED env var)
- when enabled, truth records can be refreshed from a source_url
- live truth is merged with local truth, preserving local metadata when the live source omits it

Primary source targets:
- `~/.hermes/config.yaml`
- provider truth store (YAML catalog of known providers and models)
- live provider endpoints and docs (when live truth is enabled)
- Hermes gateway health endpoint
- Hermes CLI status output

What v1.2 must answer:
- which models are valid for each configured provider
- which models are deprecated
- which endpoints match the canonical endpoint for each provider
- which lane or agent routing decision led to a failure
- whether a failure is a primary provider failure or a fallback chain degradation

Acceptance criteria:
- the provider-model catalog can validate any configured model name in use by Hermes
- stale and deprecated models are flagged with clear messages
- RKWE errors show the expected canonical endpoint
- routing diagnosis ranks findings correctly by priority
- broken fallback chains are detected and surfaced
- the live truth gate is off by default and can be enabled without restructuring the core
- Qwen3.6 Plus is explicitly listed in the qwen provider entry
- Alibaba model types (vision, rerank, embedding, speech, image, video) are reflected in capabilities with honest scope constraints
- all v1.1 hygiene criteria still pass

Out of scope for v1.2:
- mutating config automatically
- making repair decisions without operator approval
- OpenClaw or OpenCode adapters (these remain in the backlog)
- claiming global availability for CN-only or region-restricted models

### v1.3 — OpenClaw gateway and config diagnosis

Scope:
- add an OpenClaw adapter that reads gateway health and config
- detect gateway-down, auth-fail, provider-crash, clobbering, plugin drift, and stale config patterns
- pull in gateway logs and health endpoint status
- map findings into the same canonical schema used by Hermes
- add repair-oriented report sections so operators can see what needs fixing

Primary source targets:
- `~/.openclaw/openclaw.json`
- `~/.openclaw/logs/`
- gateway health endpoint and status output
- plugin allowlist / entry config

What v1.3 must answer:
- is the gateway alive
- is the config still the last known good version
- which provider is failing
- what repair action is most likely to work

Acceptance criteria:
- the OpenClaw adapter can classify the common failure matrix
- config drift is detected before repair attempts
- provider-specific failures are separated from gateway failures
- report output clearly distinguishes Hermes findings from OpenClaw findings

### v1.4 — OpenCode agent config and provider routing

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

What v1.4 must answer:
- which model/provider mappings are active
- whether the agent is using valid endpoints
- whether failures are config, provider, or task orchestration problems
- whether the runtime is in a healthy state for coding work

Acceptance criteria:
- the OpenCode adapter emits the same normalized record and finding shapes as Hermes/OpenClaw
- provider and routing issues are separated from task failures
- export files can combine multiple harnesses in one run
- tests cover adapter-specific parsing plus shared normalization

### v1.5+ — additional harnesses

Candidate future integrations:
- other local agent harnesses
- other CLI orchestrators
- CI or cron-driven health monitors
- platform-specific wrappers if they expose useful logs/configs

Future additions should follow one rule:
- if it can be read, normalized, and reported, it can become an adapter

## Architecture direction

The implementation should stay plugin-like even if the first versions are built in-tree.

Recommended layering:
- core catalog and report code stays shared
- each harness gets its own source adapter module
- each adapter returns the same `Finding` / `Record` style objects
- validators and reporters stay harness-agnostic
- versioned behavior is driven by adapter registration, not forks
- provider truth store is harness-agnostic and can be shared across adapters

That keeps Hermes, OpenClaw, and OpenCode from turning into three separate projects.

## Suggested delivery order

1. Finish Hermes v1.0 parsing and reporting
2. Add fixture-driven tests for Hermes sources
3. Add Hermes v1.1 provider cleanup and health checks
4. Add invalid-session bootstrap detection and credential suppression
5. Build provider-model catalog with Qwen3.6 Plus and Alibaba model types
6. Add model validation (stale, deprecated, RKWE) with priority ranking
7. Add routing diagnosis and broken fallback chain detection
8. Add OpenClaw adapter and health/config probes
9. Add OpenClaw failure classification and repair hints
10. Add OpenCode adapter and config/routing parsing
11. Tighten shared normalization and reporting across all harnesses
12. Add a new adapter template so later harnesses are cheap to add

## Definition of done for the roadmap

This roadmap is done when:
- Hermes, OpenClaw, and OpenCode are all first-class adapters
- each harness has source-specific tests and shared integration tests
- the provider-model catalog covers the most common providers and validates model names
- the reports can compare runs across harnesses
- adding a new harness is mostly a new adapter module plus fixtures, not a rewrite
