# GUIDELINE.md

## Mission

Build a local-first compiled brain for Hermes-style project work in this repository.

The system should improve by converting failures into durable structure:
- scripts
- provider notes
- incidents
- active-work snapshots
- skills
- evals and canaries

Not by growing prompt size or relying on lossy session summaries. [R1][R2]

## Non-negotiables

### 1. Deterministic before latent

If code can do the work, do not ask the model to improvise it.

Examples:
- provider probes
- request-dump aggregation
- rail loading checks
- resolver audits
- active-work snapshots

### 2. Retrieval before summarization

Use structured artifacts and deterministic retrieval before any compressed narrative summary. The observed summary failures make this mandatory. [R2][R3]

### 3. No durable learning without a structure change

A recurring failure is only considered learned when at least one of these changes:
- a script exists
- a provider note is updated
- an incident exists
- a skill is created or patched
- an eval or canary exists
- a filing rule is clarified

### 4. Provider-specific truth only

Do not treat providers as interchangeable abstractions. Every lane used by this repo must have:
- a provider note
- a canary definition or explicit reason not to probe
- a fallback or quarantine policy

### 5. One canonical home per durable fact

- user preferences → memory
- repo/provider/system/project truth → `brain/`
- procedures → skills
- temporary ongoing state → `brain/active-work/`
- raw evidence → logs, sessions, reports

### 6. Reports are generated artifacts

Generated reports are useful evidence but not the final source of truth. Promote enduring conclusions out of reports into provider notes, incidents, or docs.

### 7. No synthetic success

Do not mark a provider, script, or workflow as healthy without a real check, a dry-run with explicit limits, or a concrete artifact proving the behavior.

### 8. Keep the brain small and queryable

Do not turn `brain/` into a prose landfill. Prefer short, typed, narrow files over giant narrative notes.

## Build priorities

1. provider health and fallback discipline
2. request-dump and session-failure digestion
3. active-work continuity
4. resolver coverage
5. incident-to-skill promotion

## Review rules

Before landing changes, check:
- does the change reduce recurrence or only describe it?
- did the canonical file get updated?
- is there a clear place to resume work later?
- if a provider is involved, was health or failure mode recorded?
- if a workflow repeats, should it become a skill or script?

## Anti-patterns

Do not do these:
- store procedures in memory
- rely on one-shot summaries for continuity
- use a blocked provider for required compaction
- leave repeated failures only in logs
- create overlapping artifacts without naming one canonical file
- commit caches, local DB/WAL files, or generated Python bytecode

## Minimum definition of done for a new brain feature

A new feature should usually have:
- doc update
- deterministic helper or explicit rationale for not having one
- eval/canary or follow-up note
- filing decision
- verification step

## References

- [R1] User-provided Garry Tan article in this conversation
- [R2] `/home/agent/hermesagent/brain.md`
- [R3] `/home/agent/hermesagent/brain/reports/request-dump-summary.json`
- [R4] https://github.com/NousResearch/hermes-agent
- [R5] https://github.com/stephenschoettler/hermes-lcm
- [R6] https://github.com/plastic-labs/honcho
