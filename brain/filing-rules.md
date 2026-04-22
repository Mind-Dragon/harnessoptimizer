# Filing Rules

## Goal

Store durable knowledge once, in the right place, with the smallest artifact that preserves truth.

## Placement rules

### `providers/`
Use for:
- endpoints
- auth mode
- supported models
- failure history
- canary commands
- fallback policy

Do not store:
- one-off debugging transcripts
- user-specific preferences

### `incidents/`
Use for:
- normalized failures
- root cause
- structural fix
- follow-up test/eval/canary

Create an incident when:
- the same failure class happens twice
- a user correction reveals a systematic bug
- a provider/tool path fails in a repeatable way

### `active-work/`
Use for:
- current objective
- current verified state
- blockers
- next deterministic step
- files/artifacts involved

Do not keep finished work here forever. Archive or promote the durable part elsewhere.

### `patterns/`
Use for:
- reusable design patterns
- anti-patterns
- cross-project conventions

### memory tools vs brain files
- user preferences and stable interpersonal facts belong in memory
- project facts, incidents, providers, and active work belong in `brain/`
- procedures belong in skills, not in memory and not in generic brain notes

## Naming

- providers: `providers/<provider-or-lane>.md`
- incidents: `incidents/YYYY-MM-DD-<slug>.md`
- active work: `active-work/<project-or-thread>.md`
- patterns: `patterns/<slug>.md`

## Promotion rules

When a note becomes procedural, move it into a skill.
When a failure becomes recurring, add an eval or canary.
When a temporary note becomes stable truth, move it out of `active-work/`.

## Duplicate avoidance

Before writing:
1. search for an existing provider/incident/pattern entry
2. patch the existing artifact if it is the same entity
3. create a new file only for a genuinely new entity

## Current known hot spots

- `providers/minimax-chat.md`
- `providers/kimi-coding.md`
- `providers/chatgpt-codex-summary-lane.md`
- incident around SOUL prefill loader mismatch
