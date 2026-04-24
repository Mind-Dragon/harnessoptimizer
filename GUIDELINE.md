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

### 5. Install integrity is sacred

Do not corrupt an install. Ever.

Any writeback that can affect Hermes, HermesOptimizer, or a live config surface must:
- stage first
- validate before replace
- swap atomically
- leave the original intact on failure
- run a post-install smoke or canary before calling the work done

If a change cannot prove it preserves install integrity, it does not ship.

### 6. Model selection must be truthful

Best effort means live-verified best effort.

When selecting a model for compression or other work, the system must verify:
- the model exists in the configured provider surface
- the provider itself is healthy enough to use
- the model is allowed on the active plan
- the model matches the requested capability set

A model advertised somewhere upstream is not enough. If GLM 5.1V is present in a provider catalog but not available on the current coding plan, it must not be selected for that plan.

### 7. Keep provider / model / plan in sync

A model choice is only valid when provider, model, and plan all agree.

If any one of these is wrong:
- provider unavailable
- model missing
- plan mismatch
- capability mismatch

then the selection is invalid and must be rejected or rerouted before install or execution proceeds.

### 8. Config is user-owned

Any key present in the user's config is user-owned. Never silently overwrite it. Deep-merge: dicts merge recursively, scalars user-wins, lists replace. On conflict, user value wins and the action is logged.

### 9. Updates must be non-interactive capable

All interactive prompts during update must have a documented default answer. In non-interactive mode, pick the default. Any prompt not covered by a default must fail closed, not guess.

### 10. Auxiliary routing must be evaluated, not hardcoded

The auxiliary model routing table is derived from the model evaluator against the live catalog and user's primary model. Compression context window must be >= the primary model's context window. No hardcoded model names or providers.

### 11. Destructive changes are blocked by default

YOLO mode maximizes autonomy while blocking destructive commands via substring blocklist and regex patterns. All auto-approved commands are audited. Credential mutations are blocked in safe mode.

### 12. Keep the brain small and queryable

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
- [R2] `/home/agent/hermesoptimizer/brain.md`
- [R3] `/home/agent/hermesoptimizer/brain/reports/request-dump-summary.json`
- [R4] https://github.com/NousResearch/hermes-agent
- [R5] https://github.com/stephenschoettler/hermes-lcm
- [R6] https://github.com/plastic-labs/honcho
