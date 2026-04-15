# Hermes Optimizer Version 1.1

> Current working version for Hermes runtime hygiene, provider cleanup, and honest live-health checks.

## Goal

Make Hermes sessions start cleanly and stay honest: no blank providers, no duplicate providers, no stale aliases, and no false claim that Hermes is healthy when the gateway or CLI is not.

## What changes in v1.1

- Normalize provider registry entries before new sessions start.
- Deduplicate provider aliases and remove blank providers.
- Verify Hermes gateway and Hermes CLI health on each session bootstrap.
- Classify invalid new-session data separately from provider auth or endpoint failures.
- Preserve live truth over cached text and stale session state.
- Keep reports explicit about what was inspected and what was actually healthy.
- Keep Hermes-only scope for v1.1.

## Runtime health contract

A Hermes session is only considered ready when all of the following are true:

- the gateway is listening and passes its live health endpoint
- the Hermes CLI reports healthy status
- the provider registry has no blank aliases
- duplicate provider aliases have been collapsed to one canonical entry
- any invalid session bootstrap data is detected before the session is reused

If any of those checks fail, the system should say which layer failed and why.

## Canonical provider cleanup rule

For canonical providers, Hermes resolves `base_url` and `api_key` from environment variables automatically.
If a config entry still contains stale model-local values, Hermes should strip them before the session is reused.

The cleanup behavior should follow this rule:
- if `model.base_url` exists, remove it and record that the stale value was cleared
- if `model.api_key` exists, remove it and record that the stale value was cleared without exposing the full secret
- if a canonical provider is also listed in a `providers:` block as a user-defined endpoint, collapse it back to the canonical entry instead of keeping both
- if a provider-specific env override like `KIMI_BASE_URL` conflicts with canonical routing for an auto-routed provider, clear or ignore the override so the canonical route wins
- write the cleaned configuration back in a stable YAML order
- confirm the cleaned config is now the source of truth for the next session

That logic prevents old embedded provider fields, duplicate provider declarations, and stale env overrides from shadowing the env-backed canonical provider config.

## Credential source suppression rule

When a credential source is removed deliberately, Hermes should remember that source as suppressed so it does not get re-seeded by a helper like `gh auth token`.
This applies to the copilot credential path and any similar auto-discovered source of truth.

The cleanup behavior should follow this rule:
- when a credential is removed, mark the source as suppressed
- suppress re-import from the same source until the user explicitly re-enables it
- keep the suppression state explicit in auth metadata
- do not silently resurrect a removed credential just because the external tool still has a token

That prevents the `hermes auth remove` action from being undone by a hidden re-seed path.

## Work tracks

### Track A: Provider registry cleanup

- Inventory every place provider aliases are declared or generated.
- Identify blank entries, duplicate entries, and stale aliases.
- Normalize the canonical provider list so new sessions inherit one clean registry.
- Preserve safe provenance data so we can explain where the bad entry came from.

### Track B: Gateway and CLI bootstrap checks

- Check the Hermes gateway before a session is marked usable.
- Check the Hermes CLI status before a session is marked usable.
- Treat gateway health and CLI health as separate signals.
- Fail loudly if the gateway is live but the CLI state is not, or vice versa.

### Track C: Invalid session data repair

- Detect malformed new-session data early.
- Distinguish blank-provider corruption from auth failures and endpoint failures.
- Repair or isolate the bad state before it is written back into the next session.
- Avoid silent mutation of unrelated config.

### Track D: Tests, docs, and live verification

- Add regression tests for duplicate provider cleanup.
- Add live checks for gateway and CLI readiness.
- Add tests for invalid new-session data classification.
- Re-run the optimizer against a fresh Hermes session and verify the invalid state is gone.

## Acceptance criteria

- New Hermes sessions do not contain duplicate or blank providers.
- Gateway and CLI health are checked explicitly and separately.
- Invalid session bootstrap data is visible and actionable.
- Reports show the inspected inputs and the exact failure class.
- No raw secret material is written into persisted state.
- Hermes-only scope stays intact.

## Non-goals

- No broad architecture rewrite.
- No silent config mutation.
- No storing passphrases.
- No OpenClaw or OpenCode feature work in this version.
- No pretending the session is healthy if the runtime evidence disagrees.

## Related later work

The following requested features are tracked separately and can be layered on after v1.1:

- managed Hermes upgrade flow with safe prompt handling
- broader live-truth coverage for additional providers and endpoints
- downstream harness work such as OpenClaw and OpenCode
