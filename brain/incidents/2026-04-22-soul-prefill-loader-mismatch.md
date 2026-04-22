# Incident: soul-prefill-loader-mismatch

- Date: 2026-04-22
- Severity: medium
- Status: open
- Owner: unassigned

## Symptom
Gateway startup repeatedly logged:
`Failed to load prefill messages from /home/agent/clawd/SOUL.md: Expecting value: line 1 column 1 (char 0)`

## Scope
This affects governance/identity rail loading. If the loader expects structured JSON while the source is markdown/plaintext, the agent may start without intended rails or with partial rails.

## Evidence
- logs: repeated warnings in `~/.hermes/logs/agent.log` and `errors.log`
- request dumps: not required for this incident
- sessions: runtime starts continued after warning

## Root cause
Probable contract mismatch between loader expectation and document format.

## Why existing rails failed
The rail exists as content, but the loading path appears to parse the file using the wrong format assumptions.

## Structural fix
- skill: `provider-debug` (created 2026-04-23)
- script: `brain/scripts/rail_loader_check.py` (canonical verification)
  - dry-run: `python3 brain/scripts/rail_loader_check.py --dry-run`
  - full check: `python3 brain/scripts/rail_loader_check.py`
  - Statuses: `pass` | `fail` | `mismatch_risk` | `missing`
- resolver change: provider/governance troubleshooting routes to `provider-debug` skill
- canary/eval: `brain/scripts/test_rail_loader_check.py` (TDD tests, 12 passing)
- filing update: keep governance loader incidents under `incidents/`

## Verification
A future fix is verified only when startup logs show successful prefill loading or an intentional markdown/plaintext load path.

## Follow-up
- locate the loader contract
- add a focused regression test
- record the correct file format in project docs
