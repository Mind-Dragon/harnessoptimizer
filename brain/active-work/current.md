# Brain Doctor Health Check — FAIL

**Timestamp:** 2026-04-26T16:00:54.979035+00:00
**Overall Status:** FAIL (rail_loader check failed: 10 JSON parse errors in SOUL.md)
**Run Mode:** live (non-dry-run)

## Failing Checks

### rail_loader

- Mismatch detected: True
- Log errors found: 10
  - /home/agent/clawd/SOUL.md:90 — Expecting value (JSON parse failure)
  - /home/agent/clawd/SOUL.md:383 — Expecting value (JSON parse failure)
  - /home/agent/clawd/SOUL.md:1163 — Expecting value (JSON parse failure)
  - /home/agent/clawd/SOUL.md:1413 — Expecting value (JSON parse failure)
  - /home/agent/clawd/SOUL.md:2363 — Expecting value (JSON parse failure)
  - /home/agent/clawd/SOUL.md:2452 — Expecting value (JSON parse failure)
  - /home/agent/clawd/SOUL.md:2592 — Expecting value (JSON parse failure)
  - /home/agent/clawd/SOUL.md:2817 — Expecting value (JSON parse failure)
  - /home/agent/clawd/SOUL.md:3024 — Expecting value (JSON parse failure)
  - /home/agent/clawd/SOUL.md:3093 — Expecting value (JSON parse failure)

**Incident:** [2026-04-22-soul-prefill-loader-mismatch](../incidents/2026-04-22-soul-prefill-loader-mismatch.md) — open
**Root Cause:** SOUL.md contains malformed JSON fragments embedded in markdown; the prefill loader attempts a strict JSON parse and fails. The line-wrapper / embedded structure is not strip-safe for JSON payloads.
**Action:** Repair SOUL.md rail content or adjust loader to tolerant parse mode (see incident file).

### request_dump (provider health from historical session analysis)

- Files analyzed: 50
- Top failing provider: **minimax** (MiniMax-M2.7)
  - Failure count: 49
  - Reason: `max_retries_exhausted`
  - Quarantine candidate: **true**
- Secondary: **crof.ai** (qwen3-coder-next-fp8)
  - Failure count: 1
  - Reason: `non_retryable_client_error` (likely CF/IP block)

**Incident:** [2026-04-04-minimax-max-retries-exhausted](../incidents/2026-04-04-minimax-max-retries-exhausted.md) — open
**Action:** Quarantine MiniMax lane from required work. crof.ai single failure is IP/rate-limit block; monitor but do not block required tasks.

### provider_probe (live liveness check)

Live provider probe PASSED — all 5 configured providers responded:
- kilocode-ling-2.6-flash-free: 200 OK (686ms)
- openrouter-ling-2.6-flash-free: 200 OK (762ms)
- nous-kimi-k2p6: 200 OK (5997ms)
- openai-gpt-5.4-mini: 401 (invalid API key — expected)
- nacrof-crof: 403 (IP/rate-limit block — acceptable network response)

No quarantine candidates from live probe.

## Updated Active Work

- **P0:** Repair SOUL.md rail JSON structure or switch loader to tolerant parse mode (incident: 2026-04-22-soul-prefill-loader-mismatch)
- **P1:** Review and quarantine minimax provider in Hermes config to prevent required-work stalls
- **P2:** Monitor crof.ai 403 responses — likely Cloudflare/IP rate limit; rotate endpoint or credentials if persistent

## Notes

- brain_doctor.py --dry-run returns overall_status: pass (dry-run skips rail log scanning and provider network calls).
- The live (non-dry-run) check fails due to persistent SOUL.md rail write/parse mismatch.
- Persistent JSON parse failures indicate the SOUL rail is in a corrupted or incompatible state for strict JSON parsing.
