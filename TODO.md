# Hermes Optimizer v1.0 TODO

Version 1.0 is the Hermes-only release. The job here is to make the optimizer able to inspect Hermes runtime state, turn that into structured findings, and recommend concrete config or workflow fixes.

## Goal

Build a Hermes-focused optimizer that:
- discovers Hermes config, session, log, cache, and database locations
- parses those files for errors and action items
- normalizes repeated signals into actionable issues
- proposes ranked optimizations
- enriches provider/model data from live sources when endpoint details matter

## Workstream 1: Source discovery

- [ ] Inventory every Hermes config file, session directory, log directory, cache directory, and database path
- [ ] Verify discovered paths against the live machine, not just docs
- [ ] Add the discovered paths to the Hermes source adapter registry
- [ ] Keep a machine-readable path map in the repo

## Workstream 2: Local parsing

- [ ] Parse Hermes config files for invalid values, missing fields, stale model names, and bad endpoints
- [ ] Parse session files for errors, warnings, retries, crashes, stalls, and repeated failures
- [ ] Parse logs for auth failures, provider failures, timeouts, and congestion
- [ ] Parse any Hermes databases that store recent run state or catalog data
- [ ] Normalize repeated signals so the same issue is counted once with samples

## Workstream 3: Issue shaping

- [ ] Turn raw findings into structured issue records
- [ ] Group issues by category, fingerprint, and source path
- [ ] Attach severity, confidence, and lane to each issue
- [ ] Preserve raw text snippets for auditability

## Workstream 4: Optimizations

Each issue should land in one of these buckets:
- [ ] Critical
- [ ] Important
- [ ] Good ideas
- [ ] Nice to have
- [ ] Whatever

Rules:
- Critical means the harness is broken or dangerously misconfigured
- Important means the harness is working but unreliable, stale, or wasteful
- Good ideas improve quality, maintainability, or clarity
- Nice to have is optional polish
- Whatever is speculative and low confidence

## Workstream 5: Provider/model enrichment

- [ ] Use live search to find provider/model details from Hugging Face, ModelScope, or provider docs
- [ ] Verify model names against the provider website and the provider API endpoint
- [ ] Detect wrong-endpoint-right-key failures separately from auth failures
- [ ] Capture the provider’s real endpoint, model ID, and auth style in the canonical record
- [ ] Prefer live truth over cloned repos or stale docs when the two disagree

## Workstream 6: Reporting

- [ ] Write JSON output for machines
- [ ] Write Markdown output for humans
- [ ] Include discovered paths, issues, optimizations, and provider/model facts
- [ ] Keep reports deterministic and diff-friendly

## Workstream 7: Validation

- [ ] Add tests for Hermes path discovery
- [ ] Add tests for config parsing
- [ ] Add tests for session/log scanning
- [ ] Add tests for issue ranking
- [ ] Add tests for provider enrichment and endpoint mismatch detection

## v1.0 done when

- Hermes paths are discovered from the live environment
- Hermes config/session/log/database parsing works
- issues are grouped and ranked
- reports are generated automatically
- provider/model lookups are grounded in live truth
- tests cover the above

## Notes

Do not add OpenClaw or OpenCode logic to v1.0 beyond shared abstractions.
Those belong to v1.1 and v1.2.
