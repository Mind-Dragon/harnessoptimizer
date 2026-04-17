# Hermes Optimizer Release 0.5.0

## Status

Archived historical release note. The v0.5.0 vault package and its read-only primitives are in place, and the follow-up work now lives in `VERSION0.5.1.md` and `TODO.md`.

## What v0.5.0 delivered

The optimizer now has a vault package that can inventory credential sources, fingerprint entries without storing plaintext, mark stale material, group duplicates, identify rotation candidates, and plan non-destructive bridge/write-back actions.

The real `~/.vault` remains the production source of truth. Repo-local `tmp/.vault` fixtures are for tests and prototyping only. The code must never delete the user’s `~/.vault`; write-back stays opt-in and non-destructive by default.

### v0.5.0 capabilities
- inventory discovery across configured vault locations
- secret fingerprinting instead of plaintext storage
- stale/suspicious detection from metadata
- duplicate grouping with deterministic canonical selection
- rotation candidate hints
- bridge/write-back planning that does not mutate by default

### What moved to v0.5.1
- harness-facing skill wiring
- CLI audit/report surface
- clearer contract docs
- provider-validation adapters
- broader source-shape coverage

## Source of truth
- `ROADMAP.md` for the release sequence
- `TODO.md` for the active execution queue
- `VERSION0.5.1.md` for the next working slice
- `ARCHITECTURE.md` and `GUIDELINE.md` for system shape and release gates
