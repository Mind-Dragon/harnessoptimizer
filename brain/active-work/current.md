# Active Work: Brain Doctor Health Check Failure — 2026-04-23 10:00 UTC

## Objective
Run brain_doctor.py --dry-run health check after data-collection script failure. Report findings.

## Overall Status: **FAIL**

brain_doctor.py --dry-run ran 3 checks. rail_loader and request_dump both failed. provider_probe passed in dry-run mode (list-only).

---

## Check 1: rail_loader — FAIL (mismatch_detected: true)

Two rail files are markdown/plaintext but the loader expects JSON:

| Rail | Path | Exists | Format | Loader Expects | Status |
|------|------|--------|--------|----------------|--------|
| SOUL | /home/agent/clawd/SOUL.md | yes | markdown/plaintext | json | **mismatch_risk** |
| HEARTBEAT | /home/agent/clawd/HEARTBEAT.md | yes | markdown/plaintext | json | **mismatch_risk** |

The original non-dry-run data-collection script (exit code 1) also found 3 JSON parse errors in agent.log:
- 2026-04-22 20:11 — SOUL.md line 90
- 2026-04-23 00:54 — SOUL.md line 383
- 2026-04-23 02:31 — SOUL.md line 1163

**Root cause:** `/home/agent/clawd/SOUL.md` and `HEARTBEAT.md` are markdown files, but the rail loader is trying to parse them as JSON. Either the files need to be converted to JSON format, or the loader needs to handle markdown.

---

## Check 2: request_dump — FAIL

50 session files analyzed. Failure breakdown:

| Reason | Count |
|--------|-------|
| max_retries_exhausted | 49 |
| non_retryable_client_error | 1 |

**Top failing endpoints:**
- `https://api.minimax.io/v1/chat/completions` / model `MiniMax-M2.7` — 49 failures (max_retries_exhausted)
- `https://crof.ai/v1/chat/completions` / model `qwen3-coder-next-fp8` — 1 failure (non_retryable_client_error)

MiniMax API is completely unreachable for this agent — all 49 recent requests exhausted retries. The crof.ai endpoint also failed.

**Note:** This is unchanged from previous checks. The issue is persistent, not transient. Failures span 2026-04-02 through 2026-04-05.

---

## Check 3: provider_probe — dry_run_list (OK in dry-run)

Listed 3 providers to probe: minimax-chat, kimi-coding, chatgpt-codex-summary-lane.

In the original non-dry-run data-collection script (from the cron failure), provider_probe crashed with a JSON parse error in `provider_probe.py` line 101 — `json.loads(path.read_text())` failed on a file that is not valid JSON. This is likely the same root cause as the rail_loader issue (config file is markdown, not JSON). **The traceback was truncated in the error output but the crash is confirmed.**

---

## Recommended Actions

1. **Immediate:** Fix the rail format mismatch — either convert SOUL.md/HEARTBEAT.md to JSON or update the loader to handle markdown.
2. **Immediate:** Investigate why MiniMax API is completely failing (49/49 retries exhausted). Check API key validity, endpoint availability, or consider removing MiniMax as a provider.
3. **Investigate:** The crof.ai / qwen3-coder-next-fp8 non-retryable error.
4. **Fix:** The JSON parse error in provider_probe.py that crashes the non-dry-run path.

## Timeline
- 2026-04-23 02:01 UTC — First brain_doctor run, issues identified
- 2026-04-23 03:00 UTC — Dry-run confirms issues persist unchanged
- 2026-04-23 03:00 UTC — Data-collection cron script exited code 1
- 2026-04-23 04:00 UTC — Re-run confirms all issues still present, no changes
- 2026-04-23 05:00 UTC — Re-run dry-run: **overall_status: FAIL** (3 checks run). rail_loader still failing (SOUL.md + HEARTBEAT.md mismatch). request_dump: 49 MiniMax max_retries_exhausted, 1 crof.ai non_retryable. provider_probe: dry_run_list OK (3 providers listed). All issues unchanged from previous runs.
- 2026-04-23 06:00 UTC — Re-run dry-run: **overall_status: FAIL** (3 checks run). rail_loader: still mismatch_risk on SOUL.md + HEARTBEAT.md (markdown vs JSON). request_dump: 49 MiniMax max_retries_exhausted, 1 crof.ai non_retryable — unchanged. provider_probe: dry_run_list OK (3 providers). All issues persistent and unchanged.
- 2026-04-23 07:00 UTC — Data-collection cron script failed (exit code 1) with same issues. Re-ran brain_doctor.py --dry-run: **overall_status: FAIL** (3 checks run). All findings unchanged. rail_loader: 2 mismatch_risks (SOUL.md, HEARTBEAT.md). request_dump: 49 MiniMax max_retries_exhausted, 1 crof.ai non_retryable. provider_probe: dry_run_list OK (3 providers). Non-dry-run provider_probe crashed with JSON parse error (same root cause as rail mismatch).
- 2026-04-23 08:00 UTC — Scheduled cron re-run brain_doctor.py --dry-run: **overall_status: FAIL** (3 checks run). All issues unchanged. rail_loader: 2 mismatch_risks (SOUL.md, HEARTBEAT.md — markdown vs JSON). request_dump: 49 MiniMax max_retries_exhausted, 1 crof.ai non_retryable — identical to all prior runs. provider_probe: dry_run_list OK (3 providers). Data-collection cron script also failed (exit code 1) with same issues. These are now 6+ hours old with no remediation.
- 2026-04-23 10:00 UTC — Scheduled cron re-run brain_doctor.py --dry-run: **overall_status: FAIL** (3 checks run). All issues unchanged. rail_loader: 2 mismatch_risks (SOUL.md, HEARTBEAT.md — markdown vs JSON). request_dump: 49 MiniMax max_retries_exhausted, 1 crof.ai non_retryable. provider_probe: dry_run_list OK (3 providers). Data-collection cron script also failed (exit code 1) with same issues. **Now 8+ hours with no remediation — all issues persistent and unchanged since first detection at 02:01 UTC.**
- 2026-04-23 11:01 UTC — Scheduled cron re-run brain_doctor.py --dry-run: **overall_status: FAIL** (3 checks run). All issues unchanged. rail_loader: 2 mismatch_risks (SOUL.md, HEARTBEAT.md — markdown vs JSON). request_dump: 49 MiniMax max_retries_exhausted, 1 crof.ai non_retryable. provider_probe: dry_run_list OK (3 providers). Data-collection cron script also failed (exit code 1) with same issues. **Now 9+ hours with no remediation — all issues persistent and unchanged since first detection at 02:01 UTC.**
- 2026-04-23 14:00 UTC — Scheduled cron re-run brain_doctor.py --dry-run: **overall_status: FAIL** (3 checks run). All issues unchanged. rail_loader: 2 mismatch_risks (SOUL.md, HEARTBEAT.md — markdown vs JSON). request_dump: 49 MiniMax max_retries_exhausted, 1 crof.ai non_retryable. provider_probe: dry_run_list OK (3 providers). Data-collection cron script also failed (exit code 1) with same issues. **Now 12+ hours with no remediation — all issues persistent and unchanged since first detection at 02:01 UTC.**
