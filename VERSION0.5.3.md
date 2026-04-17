# Hermes Optimizer Release 0.5.3

## Status

**Done.** Caveman mode is shipped and verified.

## Goal

Add caveman-style output compression as an opt-in feature for Hermes-wide work, reducing output tokens by ~75% while preserving technical accuracy and keeping safety-critical messages in full mode.

## What caveman does

- drops articles, filler words, hedging, pleasantries
- keeps code, paths, commands, and technical details exact
- uses fragments and short synonyms
- pattern: [thing] [action] [reason]. [next step].

## Safety contract

- caveman mode is OFF by default
- safety-critical paths stay in full mode regardless of setting:
  - vault write-back confirmations
  - config mutation warnings
  - destructive operation confirmations
  - auth/credential error messages
  - first-run setup instructions
- analysis, reporting, code review, debugging → caveman OK
- mutations, safety, onboarding → full mode required

## v0.5.3 focus

1. add `caveman_mode` to `config.yaml` (off by default)
2. add `/caveman` toggle command for session control
3. wire caveman skill into Hermes skill stack
4. document when to use vs. when to stay in full mode
5. keep safety-critical paths in full mode

## Source of truth

- `TODO.md` for the active execution queue
- `ROADMAP.md` for the release sequence
- `ARCHITECTURE.md` and `GUIDELINE.md` for system shape and gates

## Completion

All five v0.5.3 focus items are shipped and verified:

1. `caveman_mode` key added to `~/.hermes/config.yaml` (off by default, preserves other keys)
2. `python -m hermesoptimizer caveman` CLI toggle wired in `__main__.py`
3. Caveman skill created at `~/.hermes/skills/software-development/caveman/SKILL.md`
4. Safety guardrails documented: vault write-back, config mutations, destructive ops, auth/credentials, setup stay in full mode
5. 34 tests passing across `test_caveman.py`, `test_caveman_cli.py`, `test_caveman_config.py`
