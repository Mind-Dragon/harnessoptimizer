# Incident: minimax-max-retries-exhausted

- Date: 2026-04-04
- Severity: medium
- Status: open
- Owner: unassigned

## Symptom
Repeated `max_retries_exhausted` failures when routing requests to `https://api.minimax.io/v1/chat/completions` with `MiniMax-M2.7` model. Every retry attempt fails until the configured retry budget is depleted.

## Scope
- Lane: primary Minimax OpenAI-compatible chat lane (`minimax-chat`)
- Model: `MiniMax-M2.7` and `MiniMax-M2.7-highspeed`
- Trigger: any request to this endpoint when lane is unhealthy or overloaded
- Impact: failed completions, fallback to alternate lane required

## Evidence
- request dumps: 99 artifacts in digest of 100 files (2026-04-22 digest, `--limit 100`)
- consistency: 99/100 = 99% of current digest cluster
- time spread: multiple cron sessions on 2026-04-04 (cron_92803da5237b_*, cron_f8426740ccae_*)
- sample artifact paths:
  - `/home/agent/.hermes/sessions/request_dump_cron_92803da5237b_20260404_155523_20260404_155545_421122.json`
  - `/home/agent/.hermes/sessions/request_dump_cron_f8426740ccae_20260404_080023_20260404_080044_849299.json`
- total referenced: 229 across full corpus (brain.md, 2026-04-22)

## Root cause
Likely Minimax API-side stability issues or authentication token expiry during sustained cron-based polling. The retry budget (3-5 attempts) is exhausted before successful connection.

## Why existing rails failed
Provider note `minimax-chat.md` documents the failure mode but no resolver script or automatic fallback skill exists to handle this gracefully. The lane continues to be used in cron paths without circuit-breaking.

## Structural fix
- skill: `provider-debug` (created 2026-04-23)
- script: `brain/scripts/provider_probe.py` (exists, now referenced by skill)
- resolver change: provider debugging intent routes to `provider-debug` skill first
- canary/eval: provider canary for minimax-chat tracks retry exhaustion rate
- filing update: this incident is linked from `minimax-chat.md` evidence block

## Verification
When the minimax lane probe returns green AND request-dump digest shows <5 `max_retries_exhausted` artifacts in a 100-file sample, this incident can be marked mitigated.

## Follow-up
- determine if token refresh would help
- check if Minimax has regional endpoints or parallel lanes
- add retry-exhaustion counter metric to provider canary
