# Hermes Project Brain

Purpose: compile recurring operational knowledge into a deterministic, testable project brain instead of relying on large prompt memory.

## Core rules

1. Deterministic before latent.
2. No durable learning without a structure change.
3. Retrieval first, summarization second.
4. Provider health is part of cognition.
5. Every persistent output needs a filing rule.
6. Resolver coverage matters as much as skill quality.
7. Repeated pain becomes a test, canary, or skill.

## Directory map

- `filing-rules.md` — where durable outputs belong
- `resolver.md` — intent families, routing, and exclusions
- `providers/` — provider registry and lane health notes
- `incidents/` — normalized postmortems and structural fixes
- `active-work/` — resumable task snapshots
- `evals/` — routing and health fixtures
- `reports/` — generated machine and human reports
- `scripts/` — deterministic helpers for recall, probes, and digestion
- `patterns/` — reusable cross-project patterns and anti-patterns

## Bootstrap priorities

1. Keep provider registry current.
2. Digest request dumps and session failures into incidents.
3. Maintain resolver cases and canaries.
4. Write active-work snapshots before context gets compacted away.
5. Promote repeated failures into skills plus tests.

## Initial findings from live Hermes corpus

- Context summary generation has repeatedly failed behind Cloudflare challenge HTML on `chatgpt.com/backend-api/codex`.
- Minimax chat lanes show repeated retry exhaustion.
- Kimi coding lanes show repeated non-retryable 404/resource-not-found failures.
- SOUL prefill loading has a contract mismatch and needs a loader check.

Treat those as known operating constraints, not surprises.
