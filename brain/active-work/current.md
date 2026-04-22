# Active Work: provider auth.json fallback + Kimi canary correction

## Objective
Align provider probing with `~/.hermes/auth.json` as the default credential source and correct the Kimi coding canary so it reflects the actually working Kimi path.

## Current verified state
- `provider_probe.py` now resolves `${ENV_VAR}` placeholders from environment first, then falls back to `~/.hermes/auth.json`
  - Verified: `python3 -m pytest -q brain/scripts/test_provider_probe.py` → 9 passed
- Dry-run provider probes no longer report missing env for Minimax or Kimi when auth.json has matching labels
  - Verified: `python3 brain/scripts/provider_probe.py --config brain/evals/provider-canaries.json --provider minimax-chat --dry-run`
  - Verified: `python3 brain/scripts/provider_probe.py --config brain/evals/provider-canaries.json --provider kimi-coding --dry-run`
- Live Minimax probe passes via auth.json fallback
  - Verified: HTTP 200 on `https://api.minimax.io/v1/chat/completions`
- Kimi coding canary was corrected from the wrong path to the working path
  - Wrong path: `/coding/chat/completions` → 404/resource_not_found
  - Correct path: `/coding/v1/chat/completions` with `User-Agent: KimiCLI/1.3` → HTTP 200
- Remaining live provider blocker is `chatgpt-codex-summary-lane`
  - Verified: HTTP 403 + Cloudflare HTML challenge

## Blockers
- `chatgpt-codex-summary-lane` remains a real failing lane due to Cloudflare challenge
- Global skill creation still requires explicit user confirmation

## Files / paths in play
- brain/scripts/provider_probe.py
- brain/scripts/test_provider_probe.py
- brain/evals/provider-canaries.json
- brain/providers/minimax-chat.md
- brain/providers/kimi-coding.md
- brain/providers/chatgpt-codex-summary-lane.md
- TODO.md
- autonomous/GAP_LIST.md

## Last successful checks
- `python3 -m pytest -q /home/agent/hermesagent/brain/scripts/test_provider_probe.py` → 9 passed
- `python3 /home/agent/hermesagent/brain/scripts/provider_probe.py --config /home/agent/hermesagent/brain/evals/provider-canaries.json --provider minimax-chat --timeout 20` → pass, HTTP 200
- `python3 /home/agent/hermesagent/brain/scripts/provider_probe.py --config /home/agent/hermesagent/brain/evals/provider-canaries.json --provider kimi-coding --timeout 20` → pass, HTTP 200
- `python3 /home/agent/hermesagent/brain/scripts/provider_probe.py --config /home/agent/hermesagent/brain/evals/provider-canaries.json --provider chatgpt-codex-summary-lane --timeout 20` → fail, HTTP 403 + HTML challenge

## Next deterministic step
1. Decide whether to close Phase 3.2 as satisfied-for-now with two passing probes and one honest negative probe
2. If desired, update `brain_doctor.py` to optionally run live provider probes instead of list-only mode when not in dry-run
3. If desired, proceed to skill creation only after explicit user approval

## Notes to future session
- Kimi absolutely does work when both the path and agent User-Agent are correct
- The prior Kimi 404 was a canary/config bug, not proof of provider failure
- auth.json fallback is now the default non-env credential source for provider probing
