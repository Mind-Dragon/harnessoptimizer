# chatgpt-codex-summary-lane

## Identity
- Lane: external ChatGPT Codex backend used for auxiliary compression / summary generation
- Base URL: `https://chatgpt.com/backend-api/codex/chat/completions`
- Auth: browser/session-backed external lane
- Typical models: custom `gpt-5.4` compression path in logs
- Intended use: auxiliary context compression and summarization

## Known behavior
- Strengths: can provide compression when reachable
- Weaknesses: repeated Cloudflare challenge HTML instead of usable API output
- Known failure modes: HTML challenge page, failed context summary generation
- Last verified good: unknown from scaffold bootstrap
- Last verified bad: repeated `Failed to generate context summary: <html>` log lines

## Canary status
- Config fixture: `evals/provider-canaries.json` entry `chatgpt-codex-summary-lane`
- Probe command: do not hard-depend on this lane for required functionality
- Success condition: not just reachability; must return valid JSON API response rather than challenge HTML
- Fail-closed or fail-open: fail-closed for required summarization; treat as opportunistic only
- **Probe status (2026-04-22T19:59:38Z): LIVE PROBE — attempted, NO AUTH KEY REQUIRED for this lane**
- **Live probe result: FAIL — HTTP 403, body contains `<html>` (Cloudflare challenge), violations: `forbidden_body:<html>`**
- **Elapsed: 49.8ms**

## Routing policy
- Use for: optional compression when green
- Avoid for: any mandatory continuity path
- **Do-not-use conditions: any time Cloudflare challenge appears in response; HTTP 403 with `<html>` body; any `Failed to generate context summary: <html>` in logs**
- Preferred fallback: deterministic active-work snapshots, structured reports, local summaries

## Evidence
- Request dump examples: NOT seen in 2026-04-22 digest (100-file bounded sample) — prior evidence from log analysis (72 `Failed to generate context summary: <html>` occurrences) was NOT confirmed in request dumps
- Digest date: 2026-04-22 (100-file bounded sample)
- Ambiguous: true — log-based evidence exists but request dump correlation missing in current sample
- next_recheck: 2026-05-06 (next scheduled digest or manual recheck)
- Live probe failure (2026-04-22): HTTP 403 with Cloudflare challenge HTML at `https://chatgpt.com/backend-api/codex/chat/completions` (live probe, still valid)
- Log references: 72 occurrences of `Failed to generate context summary: <html>` in `agent.log` / `errors.log` (brain.md, 2026-04-22)
- Incident links: none — evidence suggestive but request dump cluster not established in current digest
