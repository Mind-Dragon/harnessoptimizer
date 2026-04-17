# Hermes Optimizer Release 0.5.1

## Status

Archived historical release note. The v0.5.1 vault follow-up is complete.

## Goal

Turn the v0.5.0 vault primitives into a harness-usable workflow with explicit docs, a dedicated Hermes skill, and a user-facing CLI audit/report path while preserving the non-destructive contract.

## What the vault does

- inventories configured credential sources
- fingerprints secrets without storing plaintext
- marks stale or suspicious entries from metadata
- groups duplicates and chooses a canonical entry deterministically
- identifies rotation candidates
- plans bridge/write-back actions without mutating by default

## Safety contract

- production installs read from `~/.vault`
- tests and prototypes use repo-local `tmp/.vault`
- the code must never delete the user’s `~/.vault`
- write-back remains opt-in and preserves existing files by default

## v0.5.1 focus

1. archive the v0.5.0 note and keep the historical record
2. document the vault workflow in plain language
3. create a Hermes skill that explains when to load the vault workflow
4. add CLI wiring for audit/report usage
5. keep provider validation and write-back clearly bounded
6. expand tests around the no-touch contract and supported source shapes

## Source of truth
- `TODO.md` for the active execution queue
- `ROADMAP.md` for the release sequence
- `ARCHITECTURE.md` and `GUIDELINE.md` for system shape and gates
