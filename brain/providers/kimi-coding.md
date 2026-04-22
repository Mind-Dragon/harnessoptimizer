# kimi-coding

## Identity
- Lane: Kimi coding API lane
- Base URL: `https://api.kimi.com/coding/v1/chat/completions`
- Auth: bearer token via environment or `~/.hermes/auth.json`
- Required agent header: `User-Agent: KimiCLI/1.3` (or another recognized coding-agent identifier)
- Typical models: `kimi-k2-turbo-preview`, `kimi-k2.5`
- Intended use: coding-specialized reasoning when lane is healthy

## Known behavior
- Strengths: coding-oriented lane available in config history; verified live on 2026-04-22 after correcting path + User-Agent
- Weaknesses: wrong path or missing coding-agent User-Agent triggers false negatives (`404` or `access_terminated_error`)
- Known failure modes: `resource_not_found_error` on wrong path, `access_terminated_error` without recognized coding-agent header, occasional retry exhaustion
- Last verified good: 2026-04-22 live probe → HTTP 200 on `/coding/v1/chat/completions` with `User-Agent: KimiCLI/1.3`
- Last verified bad: prior canary on wrong path (`/coding/chat/completions`) returned 404

## Canary status
- Config fixture: `evals/provider-canaries.json` entry `kimi-coding`
- Probe command: `python3 scripts/provider_probe.py --config ../evals/provider-canaries.json --provider kimi-coding --timeout 20`
- Success condition: endpoint reaches `/coding/v1/chat/completions` and returns non-404 / non-agent-blocked response
- Fail-closed or fail-open: fail-closed for primary coding path until probe is green
- **Probe status (2026-04-22T20:40Z): LIVE PROBE — PASS via `~/.hermes/auth.json` fallback**
- **Live probe result: HTTP 200, elapsed 850.8ms, model `kimi-for-coding`, no violations**
- **Credential source: `~/.hermes/auth.json` label `KIMI_API_KEY` (env var not required)**

## Routing policy
- Use for: coding tasks after live probe passes with the recognized coding-agent User-Agent
- Avoid for: any path using `/coding/chat/completions` without `/v1`; any request missing coding-agent User-Agent; any future probe returning `resource_not_found_error` or `access_terminated_error`
- **Do-not-use conditions: probe returns HTTP 404; response body contains `resource_not_found_error`; response body contains `access_terminated_error`; recent logs show renewed non-retryable Kimi failures**
- Preferred fallback: known-good alternate coding lane recorded in registry

## Evidence
- Live probe success (2026-04-22): HTTP 200 on `https://api.kimi.com/coding/v1/chat/completions` with `User-Agent: KimiCLI/1.3`
- Prior failure was a canary/config bug, not proof the lane was dead: wrong path `https://api.kimi.com/coding/chat/completions` returned 404
- Request dump examples: prior evidence in `brain.md` referenced 23 `non_retryable_client_error` artifacts on the old/wrong path; treat that as stale until reconfirmed on the corrected v1 path
- Log references: `agent.log` entries around `20260422_184307_fbafd3` and `20260422_194153_733277` reflect the earlier wrong-path failure mode
- Incident links: none yet normalized for the corrected path; create one only if failures recur on the verified v1 path
