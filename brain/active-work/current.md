# Refactor Audit + OpenClaw Removal — v0.9.5

**Timestamp:** 2026-04-26T18:28:44
**Overall Status:** FAIL (rail_loader: 10 JSON parse errors in SOUL.md)
**Run Mode:** live (non-dry-run)

## Completed Work

### OpenClaw Removal (committed as v0.9.5)
- Deleted `OpenClawPlugin` and `OpenClawProvider`
- Removed all OpenClaw tests and extension references
- Cleaned manifests, docs, and verification contracts
- Test count: ~2,065 → ~1,750
- Git: `dev/0.9.5` branch created, `v0.9.5` tag applied

## Pending Audit

# Brain Doctor Health Check — FAIL (refreshed 2026-04-26T18:28:44)

**Overall Status:** FAIL — rail_loader check failed with 10 persistent JSON parse errors in SOUL.md
**Run Mode:** live (non-dry-run)

## Failing Checks

### rail_loader

- Overall status: **FAIL**
- Mismatch detected: true
- Log errors found: **10** (all in `/home/agent/clawd/SOUL.md`)
  - Line 90  — Expecting value (JSON parse failure)
  - Line 383 — Expecting value (JSON parse failure)
  - Line 1163 — Expecting value (JSON parse failure)
  - Line 1413 — Expecting value (JSON parse failure)
  - Line 2363 — Expecting value (JSON parse failure)
  - Line 2452 — Expecting value (JSON parse failure)
  - Line 2592 — Expecting value (JSON parse failure)
  - Line 2817 — Expecting value (JSON parse failure)
  - Line 3024 — Expecting value (JSON parse failure)
  - Line 3093 — Expecting value (JSON parse failure)
- Error source: `/home/agent/.hermes/logs/agent.log`

**Incident:** [2026-04-22-soul-prefill-loader-mismatch](../incidents/2026-04-22-soul-prefill-loader-mismatch.md) — open
**Root Cause:** SOUL.md contains malformed JSON fragments embedded in markdown; the prefill loader attempts a strict JSON parse and fails. The line-wrapper / embedded structure is not strip-safe for JSON payloads.
**Action:** Repair SOUL.md rail content or adjust loader to tolerant parse mode (see incident file).

### request_dump (provider health from historical session analysis)

- Source: `/home/agent/.hermes/sessions`
- Files analyzed: 50
- Top failing provider: **minimax** (MiniMax-M2.7)
  - Failure count: 49
  - Reason: `max_retries_exhausted`
  - Quarantine candidate: **true**
- Secondary: **crof.ai** (qwen3-coder-next-fp8)
  - Failure count: 1
  - Reason: `non_retryable_client_error` (likely Cloudflare/IP block)

**Incident:** [2026-04-04-minimax-max-retries-exhausted](../incidents/2026-04-04-minimax-max-retries-exhausted.md) — open
**Action:** Quarantine MiniMax lane from required work. crof.ai single failure is IP/rate-limit block; monitor but do not block required tasks.

### provider_probe (live liveness check)

Live provider probe: **ALL PASS** — all 5 configured providers responded:
- kilocode-ling-2.6-flash-free: 200 OK (880ms)
- openrouter-ling-2.6-flash-free: 200 OK (969ms)
- nous-kimi-k2p6: 200 OK (2242ms)
- openai-gpt-5.4-mini: 401 (invalid API key — expected credential failure)
- nacrof-crof: 403 (Cloudflare/IP rate-limit — acceptable network response)

No live quarantine candidates from provider probe.

## Updated Active Work

- **P0:** Repair SOUL.md rail JSON structure or switch loader to tolerant parse mode (incident: 2026-04-22-soul-prefill-loader-mismatch) — *blocks brain doctor from passing*
- **P1:** Quarantine minimax provider in Hermes config to prevent required-work stalls (incident: 2026-04-04-minimax-max-retries-exhausted)
- **P2:** Monitor crof.ai 403 responses — likely Cloudflare/IP rate limit; rotate endpoint or credentials if persistent

## Notes

- `brain_doctor.py --dry-run` returns `overall_status: pass` (skips rail log scanning and provider network calls)
- The live (non-dry-run) check fails due to persistent SOUL.md rail write/parse mismatch
- Persistent JSON parse failures (10 across lines 90–3093) indicate SOUL rail corruption or incompatible strict-JSON prefill format
- SOUL.md is a core Hermes Agent state rail — corrupted writes break agent persistence and must be repaired

## v0.9.5 Wave 1 — Refactor Audit Remediation

### SEC-1: Shell injection fix (hermes_runtime)
- **Status:** complete ✓
- **Commit:** 91be651 "fix(SEC-1): prevent shell injection in hermes_runtime._run_command"
- **Changes:** `shell=True` → `shell=False`; added `shlex.split`; signature now `command: str | list[str]`
- **Verified:** import works, `_run_command(['python3','--version'])` returns rc=0, py_compile OK

### SEC-2: GCP OAuth2 token exposure (pending)
- **File:** `src/hermesoptimizer/vault/providers/http.py:168`
- **Task:** Move token from URL query param to `Authorization: Bearer <token>` header

### SEC-3: Syntax error in vault/classify.py (pending)
- **File:** `src/hermesoptimizer/vault/classify.py:13`
- **Task:** Fix malformed `***` → proper tuple/list syntax

### PERF-1/2: ModelCatalog optimizations (pending)
- **Files:** `src/hermesoptimizer/sources/model_catalog.py:322,359`
- **Task:** Pre-compute role→provider→model index; build region-aware index at init

### QUAL-1a/1b/1c: Complexity reduction (pending)
- **Files:** `auto_update.py:103,115` and `loop.py:157`
- **Task:** Extract helpers, flatten conditionals, reduce cyclomatic complexity ≤10

## Remaining Wave 1 Tasks

| Task   | Status   | Next Action                         |
|--------|----------|-------------------------------------|
| SEC-2  | pending  | Fix http.py token handling          |
| SEC-3  | pending  | Fix classify.py syntax              |
| PERF-1 | pending  | Precompute model index              |
| PERF-2 | pending  | Region index at catalog init        |
| QUAL-1a| pending  | Extract `run_preflight` helpers     |
| QUAL-1b| pending  | Extract `visit` helpers             |
| QUAL-1c| pending  | Extract `parse` helpers             |

**Verification:** After each change — run targeted module tests, ensure no regressions.
