# Hermes Optimizer Roadmap

> Goal: keep Hermes accurate first, then extend to credential lifecycle management and multi-harness coverage.

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

## Next version

### v0.5.0 -- Vault management and credential lifecycle

The optimizer currently reads configs and detects stale credentials. The next step is managing the credential lifecycle itself -- without forcing users to abandon their existing vault setups.

#### The concept

Most Hermes operators store credentials in one or more of these places:
- `.env` files in project directories
- `~/.hermes/config.yaml` with embedded keys
- shell profile exports
- dedicated vault files (`~/.vault/`, `~/.env/`, etc.)
- platform-specific secret stores (1Password CLI, pass, etc.)

The problem: there is no single source of truth for which credentials exist, which are active, which are expired, and which are duplicated across locations. Operators find out a key is stale when a request fails, not before.

Vault management adds a credential inventory and lifecycle layer on top of whatever storage the operator already uses. It does not replace existing vaults. It watches them.

#### How it works

1. **Discovery**: The optimizer scans configured credential locations (default paths plus user-specified paths) and builds a credential inventory. Each entry records:
   - source location (file path, env var name, config key)
   - provider it belongs to
   - key prefix (first 8 chars, for fingerprinting without exposing the full secret)
   - last-seen timestamp
   - last-validated timestamp (when the optimizer last confirmed the key works against the provider endpoint)
   - status: active, expired, unknown, duplicate

2. **Validation**: On each run, the optimizer validates credentials against their provider endpoints. A key that returns 401/403 is marked expired. A key that works is marked active with a fresh timestamp.

3. **Deduplication**: If the same key prefix appears in multiple locations, the optimizer flags the duplicates and identifies which location is canonical. The operator chooses which one wins.

4. **Rotation tracking**: When a key changes (different prefix at the same location), the optimizer logs the rotation event. This creates an audit trail: when was this credential last rotated, how often does it rotate, has it been silent for too long.

5. **Staleness detection**: Credentials that have not been validated in N days (configurable, default 30) are flagged as stale-even-if-not-expired. Providers that have been unused for the same period get a "dormant provider" notice.

6. **Vault bridge**: For operators who want the optimizer to write back to their vault format, a vault bridge module handles the serialization. Supported formats:
   - `.env` files (key=VALUE lines)
   - YAML config files (nested key resolution)
   - JSON config files
   - Shell export statements

   The bridge is opt-in. The default mode is read-only analysis with recommendations.

#### What it does not do

- Does not store plaintext secrets in the catalog (only fingerprints and metadata)
- Does not force a specific vault format
- Does not auto-rotate credentials (it detects and recommends, the operator rotates)
- Does not replace 1Password, pass, or any dedicated secret manager
- Does not send credentials to any external service

#### File layout

```
src/hermesoptimizer/
  vault/
    __init__.py
    inventory.py        Credential discovery and indexing
    validator.py        Live credential validation against provider endpoints
    dedup.py            Duplicate detection and canonical source identification
    rotation.py         Rotation event tracking and staleness detection
    bridge.py           Write-back bridge for supported vault formats
    fingerprint.py      Key fingerprinting (prefix-based, no full secret storage)
```

#### Primary source targets

- `~/.hermes/config.yaml` -- embedded provider keys
- `~/.vault/` -- vault directory convention
- `.env` files in project directories
- `~/.bashrc`, `~/.zshrc`, `~/.profile` -- exported env vars
- user-specified additional paths (configurable in `config.yaml` under `vault.sources`)

#### What v0.5.0 must answer

- which credentials exist across all configured vault locations
- which are active, which are expired, which are stale
- which are duplicated across locations
- when each credential was last rotated
- which vault location is canonical for each provider
- whether a dormant provider should be cleaned up

#### Acceptance criteria

- credential inventory is complete across all configured sources
- live validation marks keys correctly as active or expired
- duplicate detection identifies same-key different-location entries
- rotation tracking records change events without storing plaintext
- vault bridge writes back to at least .env and YAML formats
- all credential metadata uses fingerprints, not full secrets
- existing vault files are never modified unless the operator explicitly enables write-back
- tests cover discovery, validation, dedup, rotation, and bridge without requiring real API keys

#### Out of scope

- auto-rotation of credentials
- replacing dedicated secret managers
- encrypting vault files (the vault itself handles this)
- managing credentials for providers the optimizer does not know about

### v0.6.0 -- OpenClaw gateway and config diagnosis

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
