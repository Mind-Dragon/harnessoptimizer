# AGENTS.md

## Purpose

This file tells future agents how to operate inside `/home/agent/hermesagent`.

This repository is not a generic scratch folder. It is a local-first brain-system buildout. Work here should strengthen deterministic recall, provider discipline, incident digestion, and resumable project state.

## First read order

When entering this repo, read in this order:

1. `GUIDELINE.md`
2. `ARCHITECTURE.md`
3. `docs/PLAN.md`
4. `brain/README.md`
5. any relevant file under `brain/providers/`, `brain/incidents/`, or `brain/active-work/`

If those docs disagree, follow `GUIDELINE.md` first, then `ARCHITECTURE.md`.

## Operating model

### What this repo is for

- building a compiled brain system for Hermes-style work
- turning runtime pain into durable structure
- maintaining provider notes, incidents, resolver rules, and active-work continuity
- adding small deterministic helpers instead of relying on vague memory

### What this repo is not for

- dumping raw logs into tracked files
- storing giant freeform memory narratives
- keeping temporary caches or local databases in git
- pretending provider failures are abstract or interchangeable

## Required habits

### 1. Deterministic first

If the task can be a script, make or use a script.

### 2. Evidence first

Use local evidence when possible:
- `brain.md`
- `brain/reports/`
- `~/.hermes/logs/`
- `~/.hermes/sessions/`

### 3. File durable truth correctly

Use:
- `brain/providers/` for provider truths
- `brain/incidents/` for recurring failure classes
- `brain/active-work/` for resumable current state
- skills for procedures

### 4. Update docs in lockstep

If the operating model changes, update:
- `GUIDELINE.md`
- `ARCHITECTURE.md`
- `docs/PLAN.md`
- affected `brain/` files

### 5. Keep generated artifacts out of the core truth layer

Generated reports can be referenced, but the durable conclusion should be promoted into a smaller maintained artifact.

## Commit discipline

This repo is local git only unless the user says otherwise.

Before commit:
- check `git status --short`
- avoid committing caches, bytecode, local DBs, WAL files, or temporary reports
- commit documentation and deterministic source files
- stage selectively if the tree contains unrelated experiments

## Preferred build sequence for new work

1. identify repeated pain or missing deterministic coverage
2. add or patch a script under `brain/scripts/`
3. add/update provider note, incident, or active-work file
4. add eval fixture or canary if applicable
5. verify with a real run or dry-run
6. commit the change with a narrow message

## Immediate next targets in this repo

- `brain/scripts/rail_loader_check.py`
- `brain/scripts/brain_doctor.py`
- first real `brain/active-work/current.md`
- resolver audit flow
- incident promotion helpers

## Archived material

- `.archives/` is historical scratch, superseded planning, validation dumps, and unrelated notes.
- Ignore `.archives/` unless the user explicitly asks for historical material.
- Do not use archived docs as current source of truth when `README.md`, `TODO.md`, `CHANGELOG.md`, `ARCHITECTURE.md`, or `docs/PLAN.md` disagree.

## References

- [R1] `/home/agent/hermesagent/GUIDELINE.md`
- [R2] `/home/agent/hermesagent/ARCHITECTURE.md`
- [R3] `/home/agent/hermesagent/docs/PLAN.md`
- [R4] `/home/agent/hermesagent/brain.md`
- [R5] User-provided Garry Tan article in this conversation
