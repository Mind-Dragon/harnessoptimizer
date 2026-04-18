# Hermes Optimizer Release 0.6.0

## Status

Complete. Hermes-only provider/model/config repair pass. SSH/tmux workflow, install-skill automation, and all non-Hermes harness adapters deferred to the 1.0 series.

## Goal

Tighten Hermes itself before expanding to other harnesses: make provider truth, model validation, and config repair specific enough that the optimizer can tell a human exactly what is stale, misrouted, deprecated, or safely repairable.

## What v0.6.0 adds

### Provider truth rework
- make canonical providers explicit with endpoint, auth type, region, and transport metadata
- separate canonical providers from stale aliases and user drift
- keep right-key-wrong-endpoint cases first-class
- maintain per-provider known-good endpoint candidates so Hermes can probe the same key against multiple valid endpoints for that provider
- enumerate provider endpoint families and persist them in a repo-local JSON catalog used by the repair engine
- store only configuration-relevant endpoint contract data in the catalog: base URL, API style, auth style, region/scope notes, models-path behavior, and known caveats

### Model validation rework
- tighten model validation for stale aliases, deprecated models, missing capabilities, and wrong-endpoint routing
- distinguish valid alias, stale alias, deprecated model, and wrong-endpoint routing failures
- improve repair notes so the report says which provider/model tuple should replace the bad one
- detect when a provider key is valid but the selected model is not supported by the endpoint contract that key is currently using

### Config-fixing pass
- turn Hermes config drift into specific safe repair recommendations
- distinguish auto-fixable config issues from recommend-only issues
- reconcile evidence across config, sessions, logs, auth store, credential pools, and live endpoint validation
- keep repair suggestions explicit and verifiable, not magical
- for stale or rejected API keys, recommend removal from the active list and provide an insert path for a replacement key
- for expiring OAuth credentials, attempt renewal first; if renewal fails, surface an explicit expiring/expired warning and renewal action
- for bad endpoints, probe known-good endpoints for that provider with the same key and promote the first contract-valid endpoint as the repair candidate

### Report output improvements
- add first-class report sections for provider health, model validity, and config repair priority
- surface the smallest useful fix first
- make the repair path readable without opening raw logs unless needed
- show lane-aware repair tuples: provider alias, endpoint URL, auth type, region, and model

### Provider API documentation catalog
- add a repo-local JSON catalog for provider endpoint documentation used by the repair engine
- safely extract endpoint data from provider docs without triggering anti-bot blocks or brittle scraping failures
- prefer stable sources in this order: official static docs pages, official OpenAPI/Swagger documents, machine-readable SDK/config examples, and manually curated fallback notes
- record blocked or anti-bot provider docs explicitly instead of treating them as transient failures
- for providers that resist live extraction (for example x.ai), keep a manually curated endpoint record with a last-verified timestamp and source note
- restrict the catalog to configuration-relevant endpoint data, not full prose docs
- store per-endpoint fields such as provider slug, endpoint URL, API style, auth header shape, models-list path, region/scope, compatibility notes, and documentation source URLs
- use live extraction only to refresh the JSON catalog; the runtime repair path should read the checked-in JSON instead of scraping docs on demand
- refresh module: `src/hermesoptimizer/catalog_refresh.py`
- verification: `pytest tests/test_catalog_refresh.py -v`
- checked-in files:
  - `src/hermesoptimizer/schemas/provider_endpoint.schema.json`
  - `data/provider_endpoints.json`
  - `src/hermesoptimizer/schemas/provider_endpoint.py`

### Provider model catalog refresh
- refresh the model list for each provider using the provider's current website/docs data and persist the normalized result in the checked-in catalog
- when a provider supports a live `/models` or equivalent model-list API, treat that API as the highest-confidence source for enumerating current models
- merge provider website/docs data into the model catalog for metadata the live API does not expose, such as deprecation notes, capability hints, regional restrictions, and alias guidance
- record blocked API or blocked-doc states explicitly per provider instead of silently dropping model refresh coverage
- store model-source provenance for each provider/model record: live API, official docs, SDK/example, or manual fallback
- keep the runtime repair path reading the checked-in model catalog rather than live-scraping providers during a repair run
- refresh module: `src/hermesoptimizer/schemas/provider_model_refresh.py`
- verification: `pytest tests/test_provider_model_refresh.py -v`
- checked-in files:
  - `src/hermesoptimizer/schemas/provider_model.schema.json`
  - `data/provider_models.json`
  - `src/hermesoptimizer/schemas/provider_model.py`

### Provider management suggestions
- recommend removing providers that have no valid credentials and no successful recent probe history
- recommend collapsing duplicate provider aliases onto a single canonical provider entry
- recommend demoting providers with repeatedly failing probes out of the active fallback order
- recommend provider-specific rotation or re-auth only when the credential source supports it
- recommend pinning a known-good model per provider instead of keeping an invalid default that re-breaks on restart
- recommend endpoint quarantine when a key is good but one endpoint repeatedly returns contract errors
- keep short-lived endpoint health memory with decay so one transient failure does not reorder or quarantine a provider permanently
- record credential-source provenance for every provider decision: `.env`, `auth.json`, credential pool, OAuth store, or runtime-only source
- classify every repair action as one of: auto-fix now, recommend-and-confirm, or human-only
- support fallback-order hygiene by recommending reorder when a provider repeatedly fails and a healthy fallback proves better
- prefer concrete last-known-good model pins when aliases drift or deprecate repeatedly
- apply endpoint quarantine with a TTL so bad endpoints are retried later instead of blacklisted forever
- add provider-repair report sections for broken now, auto-repaired, needs new key, needs OAuth renewal, endpoint candidates tested, and recommended fallback order
## Safety contract

- v0.6.0 is Hermes-only
- no new non-Hermes harness adapters land in this release
- no SSH/tmux remote execution automation lands in this release
- config repair must stay explicit, auditable, and safe by default
- live provider/model truth still needs deterministic test coverage and safe fallback behavior

## v0.6.0 focus

1. rework provider truth so canonical providers, endpoints, auth types, and regions are explicit and repairable
2. tighten model validation for stale aliases, deprecated models, missing capabilities, and wrong-endpoint routing
3. add a config-fixing pass that produces specific safe repair recommendations for Hermes config drift
4. reconcile provider/model/config evidence across config, sessions, logs, and live validation results
5. add stronger report sections for provider health, model validity, and config repair priority
6. build and maintain a repo-local JSON catalog of provider endpoint documentation for configuration/repair use
7. validate the provider/model/config repair path with deterministic fixture-driven smoke coverage

## Provider documentation extraction strategy

- extract endpoint data with a low-friction, non-brittle workflow rather than aggressive scraping
- prefer, in order:
  1. official static docs pages
  2. official OpenAPI / Swagger / machine-readable specs
  3. official SDK/config examples and setup guides
  4. manual curated fallback records when providers block automated extraction
- treat anti-bot blocks, JavaScript walls, and auth-gated docs as explicit catalog states
- do not keep hammering blocked providers; record the block and fall back to manual curation
- use live extraction only in the catalog refresh workflow; runtime repair should consume the checked-in JSON catalog
- keep catalog scope narrow: endpoint URLs, API style, auth header shape, models endpoint path, region/scope notes, compatibility caveats, source URLs, and last-verified timestamps

## Deferred to v1.0 series

- SSH bootstrap/session reuse for remote runs
- tmux session management for persistent remote workflows
- private/VPN IP defaults and port-range conventions
- default install skills for common environments
- OpenClaw adapter and health/config diagnosis
- OpenCode adapter and provider-routing diagnosis
- later multi-harness correlation once the Hermes repair path is mature

## Source of truth

- `TODO.md` for the active execution queue
- `ROADMAP.md` for the release sequence
- `ARCHITECTURE.md` and `GUIDELINE.md` for system shape and gates
