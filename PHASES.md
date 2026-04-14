# Hermes Optimizer Phase 0-4 Plan

This is the Hermes-only path to v1.0.
It deliberately includes the feedback loop, gateway checks, config discovery, provider truth lookup, routing diagnosis, and runtime diagnosis.

The rule is simple:
- do not trust local config alone
- do not trust cloned docs alone
- do not trust a key without checking the endpoint
- do not trust a gateway status without looking at the runtime evidence behind it

## Phase 0 — Discovery and loop skeleton

Goal: establish the inventory of Hermes truth sources and the outer run loop that will keep collecting evidence.

What this phase does:
- discover every Hermes config file, session file, log file, cache directory, and database that matters
- identify the Hermes gateway / runtime entry points
- record where the tool will look on every run
- define the collection loop: discover -> parse -> enrich -> rank -> report -> verify -> repeat

Inputs:
- `~/.hermes/config.yaml`
- `~/.hermes/logs/`
- `~/.hermes/sessions/`
- Hermes cron/gateway status surfaces
- any Hermes-local database or cache files

Outputs:
- a source inventory
- a path map
- a first-pass runtime topology
- a repeatable loop contract

Acceptance criteria:
- we can name every Hermes source of truth we care about
- the run loop is explicit and repeatable
- the repo has a canonical place to store discovered Hermes paths
- gateway and runtime surfaces are part of the inventory, not an afterthought

## Phase 1 — Parse Hermes config, sessions, logs, and runtime state

Goal: turn Hermes local artifacts into structured findings.

What this phase does:
- parse config for missing fields, stale values, bad endpoints, and invalid model/provider settings
- parse sessions for exceptions, timeouts, stalls, retries, and task failures
- parse logs for auth failures, provider failures, crash signatures, and congestion
- parse any Hermes database or state file that records recent runs
- parse runtime diagnosis signals such as stuck state, missing services, or broken startup paths

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

## Phase 2 — Provider truth and endpoint verification

Goal: stop guessing about model names and endpoints.

What this phase does:
- use search engines and live browser access where needed
- look up model/provider details from Hugging Face, ModelScope, or provider docs
- verify the provider website and the provider endpoint itself
- confirm model IDs, versions, context limits, and auth style from live truth
- detect the specific failure mode where the right key is paired with the wrong endpoint

Inputs:
- provider docs and websites
- live provider API endpoints
- model catalog pages
- search engine results
- browser-accessible docs when scraping is blocked

Outputs:
- provider truth records
- model truth records
- endpoint mismatch findings
- version mismatch findings

Acceptance criteria:
- the tool can tell the difference between auth failure and endpoint mismatch
- the tool can identify stale model names even when the key is valid
- live provider truth beats local repo text when they disagree
- lookup results are stored in the same canonical format as Hermes findings

## Phase 3 — Routing diagnosis and prioritized optimization proposals

Goal: explain what should change first, and why.

What this phase does:
- infer agent routing decisions from Hermes config and runtime behavior
- map providers/models to the intended lane or use case
- detect bad routing, stale defaults, and broken fallback chains
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

Outputs:
- prioritized recommendations
- config change proposals
- routing fixes
- a human-readable action list

Acceptance criteria:
- every major issue lands in a sensible priority bucket
- routing problems are separated from provider problems
- the report explains why something is critical versus merely useful
- proposed changes are specific enough to apply later

## Phase 4 — Closed loop verification and v1.0 hardening

Goal: turn the analysis into a stable, repeatable Hermes v1.0 system.

What this phase does:
- rerun the scan after changes
- confirm that fixes actually reduced the target failure signals
- add tests for the discovered paths, parser behavior, provider lookup, and routing diagnosis
- keep the loop stable across repeated runs
- define v1.0 readiness

Inputs:
- previous phase outputs
- updated config or runtime state
- regression test fixtures

Outputs:
- verified reports
- regression tests
- a v1.0 readiness signal
- a stable Hermes-only optimizer loop

Acceptance criteria:
- a Hermes scan can run end to end without manual cleanup
- the optimizer can show before/after improvement
- the system can explain its own recommendations
- v1.0 is ready when Hermes-only discovery, parsing, enrichment, routing diagnosis, and reporting all work together

## What v1.0 means here

v1.0 is complete when Hermes only can do all of this:
- discover its own runtime truth sources
- parse config, session, log, database, and gateway/runtime state
- enrich provider and model data from live sources
- detect endpoint mismatch and stale model issues
- propose ranked optimizations
- generate reproducible reports
- verify that the loop still works after changes

## The short version

Phase 0 finds the truth sources.
Phase 1 reads them.
Phase 2 checks live provider truth.
Phase 3 ranks the fixes.
Phase 4 proves the loop is stable enough to call v1.0.
