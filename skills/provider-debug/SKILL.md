---
name: provider-debug
version: 1.0.0
description: >
  Debug a failing AI provider lane deterministically.
  Probes health, checks request-dump history, routes to canonical
  artifacts, and records findings. Never freeform-reason about
  provider state without running the probe first.
category: devops
---

# Provider Debug

## Purpose

When a provider lane (Minimax, Kimi, ChatGPT, etc.) returns errors,
use this skill to diagnose deterministically and record the outcome.

## Trigger conditions

- Any request to a provider endpoint returns retry-exhaustion,
  non-retryable error, or unexpected HTML
- User asks "why is X provider failing"
- Session compaction fails behind a provider challenge page
- Cron job produces repeated request-dump artifacts for one lane

## Steps

1. **Identify the lane**
   - Extract provider name and endpoint URL from error or request dump
   - Canonical names: `minimax-chat`, `kimi-coding`, `chatgpt-codex-summary-lane`

2. **Run provider probe**
   ```bash
   python3 /home/agent/hermesoptimizer/brain/scripts/provider_probe.py \
     --config /home/agent/hermesoptimizer/brain/evals/provider-canaries.json \
     --provider <name> --timeout 20
   ```
   - If pass: lane is currently healthy. Look for transient or auth issue.
   - If fail: record exact status code, response body preview, and timestamp.

3. **Check request-dump history**
   ```bash
   python3 /home/agent/hermesoptimizer/brain/scripts/request_dump_digest.py \
     --limit 50
   ```
   - Filter to the provider's URL pattern.
   - Count `reason` values (`max_retries_exhausted`, `non_retryable_client_error`).
   - If count >= 5 with same reason + URL, treat as recurring class.

4. **Read canonical provider note**
   - File: `/home/agent/hermesoptimizer/brain/providers/<name>.md`
   - Check: known failure modes, last probe timestamp, fallback policy.

5. **Check for existing incident**
   - Search `/home/agent/hermesoptimizer/brain/incidents/` for provider name.
   - If incident exists, append new evidence. Do not create duplicate.

6. **Decide structural action**

   | Probe result | Dump cluster size | Action |
   |--------------|-------------------|--------|
   | Pass | < 5 | Transient. Record in provider note, no incident. |
   | Pass | >= 5 | Recurring despite current health. File incident. |
   | Fail | Any | File or update incident. Update provider note. |

7. **Record findings**
   - Update provider note with last-checked timestamp and result.
   - If incident warranted, create/update incident file per template.
   - Update `brain/active-work/current.md` if this blocks active work.

## Verification

After running this skill:
- `provider_probe.py` emitted a JSON result with `status` field
- Either provider note or incident file was modified
- No freeform diagnosis was given without probe evidence

## Anti-patterns

- Do not guess provider health from one error message.
- Do not create an incident for a single failure.
- Do not omit the probe step even if "it was working yesterday."

## References

- [R1] `/home/agent/hermesoptimizer/brain/scripts/provider_probe.py`
- [R2] `/home/agent/hermesoptimizer/brain/scripts/request_dump_digest.py`
- [R3] `/home/agent/hermesoptimizer/brain/providers/_template.md`
- [R4] `/home/agent/hermesoptimizer/brain/incidents/_template.md`
- [R5] `/home/agent/hermesoptimizer/brain/patterns/incident-promotion.md`
