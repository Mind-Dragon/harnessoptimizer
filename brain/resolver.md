# Resolver Registry

This file maps task intent families to brain artifacts, deterministic helpers, and preferred execution paths.

## Resolver table

| Intent family | Trigger phrases / shape | First path | Preferred artifact | Exclusions / notes |
|---|---|---|---|---|
| provider-health | provider failing, 404, retries, endpoint dead, model unavailable | `scripts/provider_probe.py` + provider note | `providers/` | Do not improvise by swapping providers without recording why |
| request-dump-digest | repeated request dumps, max retries, non-retryable errors | `scripts/request_dump_digest.py` | `reports/` then `incidents/` | Use deterministic aggregation first |
| incident-promotion | same failure repeated, user upset by repeat bug | incident note + skill patch/create | `incidents/` and skills | A summary alone is not a fix |
| work-resume | continue prior task, what were we doing, resume this thread | `active-work/` snapshot first, then sessions if needed | `active-work/` | Do not rely on context summary if a snapshot exists |
| filing-decision | where should this knowledge go | `filing-rules.md` | target directory note | Never dump procedures into memory |
| routing-eval | should this skill fire, wrong skill loaded | eval fixture review | `evals/resolver-cases.json` | Add explicit exclusions on overlapping skills |

## Resolver precedence

1. Deterministic helper if one exists.
2. Existing structured brain artifact.
3. Skill.
4. Session logs/raw transcripts.
5. Fresh latent reasoning.

## Required future checks

- Every new skill should add or patch at least one resolver case.
- Every provider incident should patch a provider note.
- Every active-work thread should have an obvious owner and next step.

## Known mismatches to watch

- summarization/compression paths that route through blocked external lanes
- rail/prefill loading paths that assume JSON for markdown files
- provider fallback that changes task semantics without logging it
