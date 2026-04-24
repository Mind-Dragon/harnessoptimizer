# ARCHITECTURE.md

## Purpose

This repository is a local-first workspace for building a compiled brain system for Hermes-style agent work. The architecture is designed around one principle: durable intelligence should come from structure, not from larger prompts or fragile conversation summaries. The working model is deterministic-first recall, skill-based procedural memory, explicit filing rules, provider health gates, and resumable active-work state. [R1][R2][R3]

## Scope

This repo currently has two meaningful surfaces:

1. `brain/` — the operational brain scaffold, reports, eval fixtures, and deterministic helper scripts
2. `src/hermesoptimizer/` plus related tests — the CLI, config governance, provider truth, release readiness, vault, workflow, and analysis code surface

The brain system is the primary source of truth for future buildout in this folder.

## System model

The system is split into seven layers.

### 1. Governance layer

Files:
- `GUIDELINE.md`
- `AGENTS.md`
- `docs/PLAN.md`

This layer defines the non-negotiables, operating vocabulary, and build phases. Governance wins when there is conflict between implementation convenience and system discipline.

### 2. Brain artifact layer

Files under `brain/`:
- `README.md`
- `filing-rules.md`
- `resolver.md`
- `providers/`
- `incidents/`
- `active-work/`
- `patterns/`
- `evals/`
- `reports/`

This is the durable project-knowledge surface. It stores structured truth about providers, incidents, routing, and current work. It is not a dump of session text.

### 3. Deterministic helper layer

Files under `brain/scripts/`:
- `provider_probe.py`
- `request_dump_digest.py`
- `rail_loader_check.py`
- `brain_doctor.py`
- `resolver_audit.py`
- `active_work_lint.py`

These scripts convert repeatable work into code. If a task has stable inputs and outputs, it should be compiled here instead of re-done in latent space. [R1]

### 4. Eval and canary layer

Files under `brain/evals/`:
- `provider-canaries.json`
- `resolver-cases.json`

These fixtures define what must stay true:
- providers should respond in acceptable ways
- blocked or challenge-page lanes should be treated as unhealthy
- resolver paths should route to the right deterministic helper or artifact first

### 5. Evidence layer

Primary evidence sources:
- `brain.md`
- `brain/reports/request-dump-summary.json`
- `~/.hermes/sessions/*`
- `~/.hermes/logs/*`

Evidence is upstream of architecture decisions. The local analysis already shows repeated summary failures, provider instability, and rail-loading mismatch. Those are design inputs, not incidental bugs. [R1][R3]

### 6. Config governance layer

Files:
- `src/hermesoptimizer/config_maintainer.py` — backup dedup, deep merge, force-restore, config-status
- `src/hermesoptimizer/auto_update.py` — non-interactive update with preflight destructive detection
- `src/hermesoptimizer/yolo_mode.py` — safe-maximum auto-approve with destructive blocklist and audit trail
- `src/hermesoptimizer/config_watcher.py` — polling file watcher with change classification and auto-repair
- `src/hermesoptimizer/service.py` — config watcher daemon lifecycle (start/stop/status/flush)

This layer ensures the user's config is never silently overwritten, updates can run unattended, and destructive resets are caught and repaired automatically. Major config changes trigger `[HERMES_FORCE_FIX]` via the backup chain.

### 7. Model evaluation layer

Files:
- `src/hermesoptimizer/model_evaluator.py` — generic role-to-model ranking engine
- `src/hermesoptimizer/auxiliary_optimizer.py` — auxiliary routing table derived from evaluator + user config

This layer replaces hardcoded model assignments with evaluated selections. The evaluator scores models against role requirements (capabilities, context windows, speed, cost preferences) and the auxiliary optimizer applies those scores to produce the routing table. Compression context window is constrained to match the primary model's context window. A repeated workflow should be promoted from:
- session pain
- to incident
- to deterministic helper and/or skill
- to eval/canary

This follows the “failure becomes structure” model rather than the “agent promises to remember better next time” model. [R1]

## Directory architecture

```text
/home/agent/hermesoptimizer/
├── AGENTS.md
├── ARCHITECTURE.md
├── GUIDELINE.md
├── brain.md
├── brain/
│   ├── README.md
│   ├── filing-rules.md
│   ├── resolver.md
│   ├── active-work/
│   ├── evals/
│   ├── incidents/
│   ├── patterns/
│   ├── providers/
│   ├── reports/
│   └── scripts/
├── docs/
│   └── PLAN.md
├── src/hermesoptimizer/
└── tests/
```

## Data flow

### A. Failure digestion path

1. Hermes runtime emits logs / request dumps / session artifacts
2. `request_dump_digest.py` aggregates repeated endpoint/model/reason failures
3. provider notes in `brain/providers/` are updated
4. repeated failures become incidents in `brain/incidents/`
5. incidents drive skills, resolver patches, or new deterministic scripts
6. eval fixtures are updated so the failure is less likely to recur

### B. Work continuity path

1. a live task is active
2. current verified state is written into `brain/active-work/`
3. future sessions resume from active-work first
4. raw session search is fallback, not primary continuity

### C. Provider gate path

1. provider canary definition lives in `brain/evals/provider-canaries.json`
2. `provider_probe.py` evaluates health or obvious misconfiguration
3. result updates provider notes or reports
4. unhealthy lanes are avoided for required work

## Source-of-truth hierarchy

When two artifacts disagree, use this order:

1. `GUIDELINE.md`
2. `ARCHITECTURE.md`
3. current release proof (`VERSION0.9.3.md` for v0.9.3)
4. `TODO.md` and `brain/active-work/current.md` for active execution state
5. `docs/PLAN.md`
6. `TESTPLAN.md`, `CHANGELOG.md`, `ROADMAP.md`, `README.md`
7. `brain/` structured artifacts
8. ad hoc notes or transient session context

`brain.md` is the analysis seed and rationale document. The operational truth lives in the smaller files under `brain/` plus this architecture/governance suite.

## Architectural constraints

### Constraint 1: deterministic before latent

No stable task should rely on freeform model behavior if a small script can do it more reliably. [R1]

### Constraint 2: no mandatory dependence on lossy summarization

The local evidence shows repeated context-summary failure behind Cloudflare challenge HTML. Work continuity must survive even when model-side compression fails. [R2][R3]

### Constraint 3: provider health is part of the architecture

Providers are not interchangeable. The design must encode lane-specific failure history, canaries, and fallback rules. [R2][R4][R5]

### Constraint 4: durable knowledge must be filed once

A fact should have one canonical durable home:
- user preference → memory
- provider/system/project fact → `brain/`
- procedure → skill
- current task state → `brain/active-work/`

### Constraint 5: repeated failure must change structure

If the same failure class appears twice, the default response is a structural change, not a verbal reminder. [R1]

## Planned architecture extensions

Deferred beyond v0.9.3:
- broader resolver fixture coverage
- incident promotion helper that scaffolds normalized incident files and skill candidates
- skill scaffolding from normalized incidents
- optional native Hermes status/doctor bridge, only if it stays small and separately proven

## Verification expectations

Any architectural change should be verified with one or more of:
- script compilation check
- dry-run or live probe
- generated report artifact
- resolver fixture update
- incident note update
- git-tracked doc update

## References

- [R1] User-provided Garry Tan article in this conversation: “How to really stop your agents from making the same mistakes”
- [R2] `/home/agent/hermesoptimizer/brain.md`
- [R3] `/home/agent/hermesoptimizer/brain/reports/request-dump-summary.json`
- [R4] https://github.com/NousResearch/hermes-agent
- [R5] https://github.com/stephenschoettler/hermes-lcm
- [R6] https://github.com/plastic-labs/honcho
