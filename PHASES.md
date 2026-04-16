# Hermes Optimizer Phase 0-4 Plan

This is the Hermes-only path for the current 0.4.0 release line.
It deliberately includes discovery, parsing, canonical provider cleanup, gateway checks, CLI checks, credential suppression, and closed-loop verification.

The rule is simple:
- do not trust local config alone
- do not trust cloned docs alone
- do not trust a key without checking the endpoint
- do not trust a gateway status without looking at the runtime evidence behind it
- do not trust a removed credential unless the suppression state says it may return

## Phase 0 — Discovery and loop skeleton

Goal: establish the inventory of Hermes truth sources and the outer run loop that will keep collecting evidence.

What this phase does:
- discover every Hermes config file, session file, log file, cache directory, and database that matters
- identify the Hermes gateway, CLI, and runtime entry points
- record where the tool will look on every run
- define the collection loop: discover -> parse -> enrich -> rank -> report -> verify -> repeat

Inputs:
- `~/.hermes/config.yaml`
- `~/.hermes/logs/`
- `~/.hermes/sessions/`
- Hermes gateway and CLI status surfaces
- any Hermes-local database or cache files
- auth metadata that tracks suppressed credential sources

Outputs:
- a source inventory
- a path map
- a first-pass runtime topology
- a repeatable loop contract

Acceptance criteria:
- we can name every Hermes source of truth we care about
- the run loop is explicit and repeatable
- the repo has a canonical place to store discovered Hermes paths
- gateway, CLI, and credential-source surfaces are part of the inventory

## Phase 1 — Parse Hermes config, sessions, logs, and runtime state

Goal: turn Hermes local artifacts into structured findings.

What this phase does:
- parse config for missing fields, stale values, bad endpoints, and invalid model/provider settings
- parse sessions for exceptions, timeouts, stalls, retries, and task failures
- parse logs for auth failures, provider failures, crash signatures, and congestion
- parse any Hermes database or state file that records recent runs
- parse runtime diagnosis signals such as stuck state, missing services, or broken startup paths
- parse credential metadata for suppressed or re-seeded sources

Inputs:
- config files
- session files
- logs
- local databases and caches
- runtime status outputs

Outputs:
- raw findings
- grouped findings
- runtime diagnosis records

Acceptance criteria:
- a real Hermes run can be reduced to structured findings
- repeated signals are deduplicated
- raw evidence is preserved
- runtime failures are distinguishable from config drift

## Phase 2 — Canonical provider truth and endpoint verification

Goal: stop guessing about provider names, canonical provider routing, and endpoints.

What this phase does:
- use search engines and live browser access where needed
- look up model/provider details from provider docs and endpoint listings
- verify the provider website and the provider endpoint itself
- confirm model IDs, versions, context limits, and auth style from live truth
- detect the specific failure mode where a canonical provider is duplicated in a user-defined block
- detect stale embedded `model.base_url` and `model.api_key` fields
- detect stale env overrides that force the wrong canonical route

Inputs:
- provider docs and websites
- live provider API endpoints
- model catalog pages
- search engine results
- browser-accessible docs when scraping is blocked
- local config showing canonical providers and user-defined provider blocks

Outputs:
- provider truth records
- model truth records
- endpoint mismatch findings
- version mismatch findings
- canonical-vs-duplicate routing findings

Acceptance criteria:
- the tool can tell the difference between auth failure and endpoint mismatch
- the tool can identify stale model names even when the key is valid
- the tool can identify duplicate canonical providers hiding in a user-defined block
- live provider truth beats local repo text when they disagree
- lookup results are stored in the same canonical format as Hermes findings

## Phase 3 — Routing diagnosis, credential suppression, and prioritized proposals

Goal: explain what should change first, and why.

What this phase does:
- infer agent routing decisions from Hermes config and runtime behavior
- map providers/models to the intended lane or use case
- detect bad routing, stale defaults, and broken fallback chains
- detect removed credentials that have been re-seeded by another source
- rank fixes into priority buckets:
  - critical
  - important
  - good ideas
  - nice to have
  - whatever
- propose concrete optimization actions without silently applying them

Inputs:
- normalized findings
- provider truth records
- routing metadata
- runtime diagnosis records
- credential suppression metadata

Outputs:
- prioritized recommendations
- config change proposals
- routing fixes
- a human-readable action list
- credential-source remediation notes

Acceptance criteria:
- every major issue lands in a sensible priority bucket
- routing problems are separated from provider problems
- suppressed credentials remain suppressed until explicitly restored
- the report explains why something is critical versus merely useful
- proposed changes are specific enough to apply later

## Phase 4 — Closed loop verification and 0.4.0 hardening

Goal: turn the analysis into a stable, repeatable Hermes 0.4.0 system.

What this phase does:
- rerun the scan after changes
- confirm that fixes actually reduced the target failure signals
- add tests for the discovered paths, parser behavior, provider lookup, and routing diagnosis
- add smoke checks for a clean new session
- keep the loop stable across repeated runs
- define 0.4.0 readiness

Inputs:
- previous phase outputs
- updated config or runtime state
- regression test fixtures

Outputs:
- verified reports
- regression tests
- a 0.4.0 readiness signal
- a stable Hermes-only optimizer loop

Acceptance criteria:
- a Hermes scan can run end to end without manual cleanup
- the optimizer can show before/after improvement
- the system can explain its own recommendations
- 0.4.0 is ready when Hermes-only discovery, parsing, enrichment, routing diagnosis, provider cleanup, and reporting all work together

## What 0.4.0 means here

0.4.0 is complete when Hermes only can do all of this:
- discover its own runtime truth sources
- parse config, session, log, database, and gateway/runtime state
- normalize canonical providers and strip stale embedded fields
- detect duplicate providers, blank providers, and stale env overrides
- suppress removed credentials instead of letting them reappear
- propose ranked optimizations
- generate reproducible reports
- verify that the loop still works after changes

## The short version

Phase 0 finds the truth sources.
Phase 1 reads them.
Phase 2 checks live provider truth and canonical cleanup.
Phase 3 ranks the fixes and keeps removed credentials removed.
Phase 4 proves the loop is stable enough to call 0.4.0.
