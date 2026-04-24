# nacrof-crof

## Identity

- Lane: crof.ai / nacrof OpenAI-compatible coding lane
- Base URL: `https://crof.ai/v1/chat/completions`
- Auth: bearer token from `nacrof` provider config, `NACROF_API_KEY`, or auth pool
- Typical model: `qwen3-coder-next-fp8`
- Intended use: coding-specialized fallback lane when healthy

## Known behavior

- Strengths: configured local fallback lane; now included in merged provider-list via Hermes config source.
- Weaknesses: latest request-dump sample contains a non-retryable client error.
- Known failure modes: `non_retryable_client_error`, model missing/not found, HTML/challenge body.
- Last verified good: unknown from current brain-doctor sample.
- Last verified bad: 2026-04-23 brain-doctor request_dump sample found 1 `non_retryable_client_error`.

## Canary status

- Config fixture: `evals/provider-canaries.json` entry `nacrof-crof`.
- Probe command: `python3 brain/scripts/provider_probe.py --config brain/evals/provider-canaries.json --provider nacrof-crof --timeout 20`.
- Dry-run/list behavior is safe without credentials; live probe skips when `NACROF_API_KEY` or auth-pool credential is unavailable.
- Success condition: OpenAI-compatible JSON response or expected auth/rate-limit shape, not HTML and not model-not-found.
- Fail-closed or fail-open: fail-closed for required coding work; do not use for required release work unless the canary is green.

## Routing policy

- Use for: opportunistic fallback only after a live probe passes.
- Avoid for: release gates, compression, or mandatory coding work while the current non-retryable failure is unexplained.
- Do-not-use conditions: `non_retryable_client_error`; model missing/not found; HTML challenge body; no recent live canary.
- Preferred fallback: a provider/model pair with a recent green canary and explicit model/plan truth.

## Evidence

- Brain-doctor 2026-04-23 latest 50-file sample: `https://crof.ai/v1/chat/completions` / `qwen3-coder-next-fp8` produced 1 `non_retryable_client_error`.
- Brain-doctor 2026-04-24 dry-run still lists crof/nacrof as a single non-quarantine failure input.
- Sample artifact: `/home/agent/.hermes/sessions/request_dump_cron_c58f2a1e087a_20260402_180053_20260402_180104_558996.json`.

## Next check

- Run the live canary with current credentials before enabling this lane as a required fallback.
- If it fails twice with the same signature, promote or update a normalized incident and keep the lane quarantined for required work.
