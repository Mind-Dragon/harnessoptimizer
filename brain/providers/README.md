# Provider Registry

Each file here tracks one provider lane or distinct operational surface.

Required fields per provider note:

- base URL / lane
- auth source
- primary use case
- known failure modes
- last known evidence
- canary command or config entry
- fallback policy
- do-not-use conditions

Current provider notes:

- `minimax-chat.md` — quarantined/non-required candidate until canary health is restored.
- `kimi-coding.md` — legacy Kimi coding lane note.
- `chatgpt-codex-summary-lane.md` — summary-lane risk note.
- `nacrof-crof.md` — config-sourced fallback lane; has canary fixture but is not required-release eligible until green.
- `_template.md`
