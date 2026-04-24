# Provider health notes — v0.9.3

Live canary lanes for this release:

- Kilocode: `inclusionai/ling-2.6-flash:free` through Kilocode OpenRouter-compatible gateway.
- OpenRouter: `inclusionai/ling-2.6-flash:free` through `https://openrouter.ai/api/v1`.
- Nous Portal: `moonshotai/kimi-k2.6` through `https://inference-api.nousresearch.com/v1` using the agent key credential.
- OpenAI Codex plan: `gpt-5.4-mini` as the single OpenAI fallback lane, authenticated via provider-scoped OAuth `device_code`.

Request dump health handling:

- `brain/scripts/request_dump_digest.py` now emits `provider_health_inputs` from request-dump URL/model/reason buckets.
- Rows with at least three failure-class reasons are marked `quarantine_candidate: true` for provider health/quarantine ingestion.
- MiniMax and legacy Kimi/crof lanes are not release candidates for v0.9.3 unless their canaries are explicitly restored to passing status.
