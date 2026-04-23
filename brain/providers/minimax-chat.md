# minimax-chat

## Identity
- Lane: primary Minimax OpenAI-compatible chat lane
- Base URL: `https://api.minimax.io/v1/chat/completions`
- Auth: bearer token via environment/config
- Typical models: `MiniMax-M2.7`, `MiniMax-M2.7-highspeed`
- Intended use: general chat/reasoning paths when healthy

## Known behavior
- Strengths: heavily used in corpus; broad availability in config
- Weaknesses: repeated retry exhaustion in live request dumps
- Known failure modes: `max_retries_exhausted`
- Last verified good: unknown from this scaffold bootstrap
- Last verified bad: request dump corpus showing 229 retry-exhausted artifacts; latest 50-file doctor sample still shows 49 retry-exhausted artifacts on 2026-04-23

## Canary status
- Config fixture: `evals/provider-canaries.json` entry `minimax-chat`
- Probe command: `python3 scripts/provider_probe.py --config ../evals/provider-canaries.json --provider minimax-chat --timeout 20`
- Success condition: HTTP 200 or expected auth failure shape from configured lane
- Fail-closed or fail-open: fail-open for non-critical experimentation; fail-closed for core production paths until probe is green
- **Probe status (2026-04-22T20:37Z): LIVE PROBE — PASS via `~/.hermes/auth.json` fallback**
- **Live probe result: HTTP 200, elapsed 789.9ms, model `MiniMax-M2.7`, no violations**
- **Credential source: `~/.hermes/auth.json` label `MINIMAX_API_KEY` (env var not required)**

## Routing policy
- Use for: general reasoning only when recent canary is green
- Avoid for: critical chains that cannot tolerate repeated retries without alternate path
- **Do-not-use conditions: if authenticated live probe stops passing; if canary has not passed in >24h; if request-dump shows new retry-exhausted burst; if brain-doctor request_dump sample shows >5 retry-exhausted MiniMax failures in the latest 50 files**
- Preferred fallback: project-specific secondary lane with recent green probe

## Evidence
- Request dump examples: 99 `max_retries_exhausted` artifacts in `request-dump-summary.json` (digest --limit 100, 2026-04-22); brain.md references 229 total across full corpus; brain-doctor 2026-04-23 latest 50-file sample reports 49 `max_retries_exhausted` for `https://api.minimax.io/v1/chat/completions` / `MiniMax-M2.7`
- Digest date: 2026-04-22 (100-file bounded sample)
- Consistency: 99/100 files in digest cluster show same failure pattern
- Log references: `brain.md` (2026-04-22 analysis); `request-dump-summary.json`
- Sample artifact path: `/home/agent/.hermes/sessions/request_dump_cron_92803da5237b_20260404_155523_20260404_155545_421122.json`
- Incident links: `brain/incidents/2026-04-04-minimax-max-retries-exhausted.md` (promoted 2026-04-22, meets promotion threshold: count=99, consistency=99%, multi-day spread)
