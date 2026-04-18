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

### v0.6.0 -- Provider/model/config repair pass

Done. Hermes-only provider truth rework: explicit canonical providers with endpoint/auth/region/transport metadata, stale alias detection, endpoint candidate probing, and model-specific endpoint routing. Config-fixing pass with safe repair recommendations and auto-fix vs recommend-and-confirm vs human-only classification. Report output improvements: provider health, model validity, and config-repair priority as first-class sections with lane-aware repair tuples. Provider endpoint documentation catalog (`src/hermesoptimizer/schemas/provider_endpoint.schema.json`, `data/provider_endpoints.json`, `src/hermesoptimizer/schemas/provider_endpoint.py`) with safe extraction workflow and blocked-doc state tracking. Provider model catalog refresh (`src/hermesoptimizer/schemas/provider_model.schema.json`, `data/provider_models.json`, `src/hermesoptimizer/schemas/provider_model.py`) with live `/models` API preference and explicit blocked-source states. Provider management controls: endpoint health memory with decay, credential-source provenance, fallback-order hygiene, model pinning, endpoint quarantine TTL. Tests: `pytest tests/test_catalog_refresh.py`, `pytest tests/test_provider_model_refresh.py`, `pytest tests/test_config_fix.py`, `pytest tests/test_provider_management.py`.

## Next version

### v1.0 series -- Other harnesses and remote workflow

Scope:
- SSH bootstrap and tmux session reuse for remote workflows
- private/VPN IP defaults and port-range conventions
- install-skill bundles for common environments
- OpenClaw adapter and health/config probes
- OpenCode adapter and config/routing parsing
- later multi-harness correlation after Hermes-side repair flow is mature

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
9. ~~Add vault management: credential inventory, validation, dedup, rotation tracking~~
10. ~~Add vault bridge: write-back for .env and YAML formats~~
11. ~~Rework Hermes provider truth, model validation, and config repair surfaces~~
12. ~~Tighten Hermes-first normalization and reporting for provider/model/config repair~~
13. Defer non-Hermes adapters and remote workflow automation to the v1.0 series
14. Add adapter template for new harness onboarding once the Hermes repair path is stable

## Definition of done for the roadmap

This roadmap is done when:
- Hermes has a mature provider/model/config repair path with explicit safe recommendations
- vault management provides credential lifecycle visibility across Hermes and future adapters
- the provider-model catalog covers the most common providers and validates model names
- the reports can compare runs across repair passes and later across adapters
- adding a new harness in the v1.0 series is mostly a new adapter module plus fixtures, not a rewrite
