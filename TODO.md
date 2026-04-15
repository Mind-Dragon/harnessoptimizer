# Hermes Optimizer TODO

This is the current execution queue for v1.1.

## Objective

Harden Hermes so a new session starts from a clean, truthful runtime state:
- no blank providers
- no duplicate providers
- no stale aliases
- gateway and CLI health checked explicitly
- invalid session bootstrap data detected before reuse

## Ready work queue

### 1. Audit provider registry sources

**Goal:** Find every place provider aliases are declared, merged, cached, re-emitted, or auto-seeded into a new Hermes session.

**What to inspect:**
- `~/.hermes/config.yaml`
- generated session/bootstrap state
- provider fallback lists
- any cache or state file that serializes provider aliases
- env overrides that can force provider endpoints or keys
- auth sources that can re-seed removed credentials

**Done when:**
- every provider alias source is named
- blank providers are identified
- duplicate providers are identified
- the current canonical provider list is clear
- stale env overrides that conflict with canonical routing are identified
- auto-seeded credential sources are identified

**Verify:**
- start or synthesize a fresh Hermes session
- dump the session state
- confirm there is exactly one canonical entry per provider alias
- confirm canonical providers are not duplicated in the user-defined provider block
- confirm removed credentials do not reappear from a hidden source

### 2. Normalize provider registry output

**Goal:** Make the session bootstrap path emit one clean provider entry per alias.

**What to do:**
- remove blank provider entries
- collapse duplicate aliases
- preserve a canonical provider list for the session path
- strip stale `model.base_url` and `model.api_key` fields for canonical providers so env resolution wins
- collapse canonical providers out of any user-defined `providers:` duplicates
- ignore or clear env overrides that force stale canonical routing
- keep provenance metadata so the source of bad data can be explained later

**Done when:**
- a new Hermes session does not show duplicate providers
- a new Hermes session does not show blank providers
- canonical providers no longer carry stale embedded endpoint or key fields
- canonical providers do not remain duplicated in a user-defined providers block
- provider cleanup is deterministic across repeated runs

**Verify:**
- run the same bootstrap path twice
- confirm the resulting provider list is identical both times
- confirm no duplicate or blank entries remain
- confirm stale model-local endpoint/key fields are stripped from canonical providers
- confirm a forced env override does not win over canonical routing

### 3. Add explicit gateway and CLI health gates

**Goal:** Do not call Hermes healthy unless both the gateway and the CLI are healthy.

**What to do:**
- check the gateway health endpoint
- check `hermes status`
- report gateway failure and CLI failure separately
- keep the checks named and visible in logs or reports

**Done when:**
- gateway health is verified live
- CLI health is verified live
- the system can explain which layer failed

**Verify:**
- `curl -sf http://127.0.0.1:18789/health`
- `hermes status`
- confirm both pass before marking a session usable

### 4. Detect invalid new-session data

**Goal:** Catch malformed or stale data before it poisons a new Hermes session.

**What to do:**
- classify invalid bootstrap data separately from auth failures and endpoint failures
- flag stale aliases and polluted provider lists
- make the failure visible instead of hiding it behind a generic success path

**Done when:**
- invalid new-session data is surfaced as a first-class failure
- the report explains what is wrong and where it came from

**Verify:**
- feed the system a fixture with duplicate and blank providers
- confirm it emits the correct failure class

### 5. Add regression tests and end-to-end smoke checks

**Goal:** Lock in the behavior so the issue does not come back.

**What to do:**
- add tests for duplicate provider cleanup
- add tests for blank provider removal
- add tests for gateway/CLI health gating
- add tests for invalid-session classification

**Done when:**
- the test suite covers the bug class end to end
- the live smoke check confirms a clean new session

**Verify:**
- run the targeted tests for the new behavior
- run the full suite
- run a fresh Hermes session and inspect the resulting state

### 6. Commit local changes after each completed track

**Goal:** Keep the work auditable and easy to resume.

**What to do:**
- commit after each completed track
- keep the worktree clean before starting the next track
- do not push unless explicitly asked

**Done when:**
- each completed track has a local commit
- the worktree is clean at the end of the track

## Later backlog

These are requested features that should stay queued after v1.1 unless the user explicitly reprioritizes them:

- managed Hermes upgrade flow with safe prompt handling
- broader live-truth coverage for additional providers and endpoints
- OpenClaw and OpenCode work once Hermes v1.1 is stable

## Notes

- Hermes-only scope stays intact for v1.1.
- Gateway health and CLI health must remain explicit, named, and verifiable.
- Do not silently mutate unrelated config.
- Do not declare a session healthy if the new-session state still contains invalid provider data.
