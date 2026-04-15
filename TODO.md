# Hermes Optimizer TODO

This is the current execution queue for v1.2.

## Objective

Extend the Hermes optimizer with a provider-model catalog, thorough model validation, and agent-level management and routing diagnosis, while keeping Hermes runtime hygiene from v1.1 intact.

## Ready work queue

### 1. Provider-model catalog — canonical store

**Goal:** Build a canonical provider-model catalog that can validate which models exist, which are deprecated, and which capabilities each provider supports.

**What to do:**
- populate the `ProviderTruthStore` with real provider and model data
- include Qwen3.6 Plus explicitly in the known models list
- note that Alibaba has vision, rerank, embedding, speech, image, and video models
- add provider aliases for all known variants (kimi-for-coding, bailian, tongyi, etc.)
- support region and scope constraints where known (some models are CN-only or global-only)

**Done when:**
- the provider truth store has entries for the most common providers used with Hermes
- qwen3.6-plus is listed as a known model under the qwen family
- Alibaba multi-modal model types are reflected in capabilities
- canonical endpoints are correct for each provider family

**Verify:**
- query the store for known providers and confirm models are listed
- confirm Qwen3.6 Plus appears in the qwen provider entry
- confirm Alibaba capabilities include vision, rerank, embedding, speech, image, video

### 2. Model validation — stale and deprecated model detection

**Goal:** Detect when a configured model is stale, deprecated, or not in the provider's known model list before a session starts.

**What to do:**
- wire `verify_endpoint` and `verify_endpoint_with_live` into the main loop's verify step
- check configured model names against `ProviderTruthRecord.known_models`
- flag deprecated models via `ProviderTruthRecord.deprecated_models`
- surface RKWE (right-key-wrong-endpoint) errors with the correct canonical endpoint
- handle auth failures separately from model-not-found errors

**Done when:**
- a session with a stale model name is flagged with STALE_MODEL
- a deprecated model name is flagged with a deprecation notice
- an endpoint that does not match the canonical endpoint is flagged as RKWE
- the live truth gate can refresh provider truth from a source URL when enabled

**Verify:**
- feed a config with gpt-4 (deprecated) and confirm it is flagged
- feed a config with a wrong endpoint for openai and confirm RKWE is detected
- confirm the live truth gate is off by default and can be enabled via HERMES_LIVE_TRUTH_ENABLED

### 3. Agent management and routing diagnosis

**Goal:** Add routing-level diagnosis so the system can explain which provider and model are active per lane, detect broken fallback chains, and rank agent-level failures separately from raw provider failures.

**What to do:**
- keep `RoutingDiagnosis` and `Recommendation` from the existing route/diagnosis.py
- add agent-level findings that distinguish config drift from agent routing failures
- detect broken fallback chains where only some providers in a lane are failing
- add CRITICAL for primary provider auth failures, IMPORTANT for fallback failures
- keep the priority bucket model: CRITICAL > IMPORTANT > GOOD_IDEA > NICE_TO_HAVE > WHATEVER

**Done when:**
- auth failures on a lane's primary provider are CRITICAL
- auth failures on a fallback provider are IMPORTANT
- timeouts with 3+ retries are CRITICAL
- broken fallback chains produce a BROKEN_FALLBACK diagnosis
- stale model defaults produce a STALE_MODEL diagnosis

**Verify:**
- feed findings with a primary provider auth failure and confirm CRITICAL priority
- feed a multi-provider lane where one is failing and confirm BROKEN_FALLBACK fires
- run the full routing diagnosis on a real Hermes session and confirm diagnoses are ranked

### 4. Keep v1.1 hygiene work intact

**Goal:** Ensure all v1.1 provider cleanup and health gate work is not broken by v1.2 additions.

**What to do:**
- confirm blank provider and duplicate provider cleanup still works
- confirm gateway and CLI health checks are still explicit and separate
- confirm invalid session data is still detected and surfaced
- confirm removed credentials do not silently re-seed

**Done when:**
- the existing TODO items from v1.1 still pass their verify criteria
- the loop runs through all phases without error

**Verify:**
- run the full test suite and confirm all v1.1 tests still pass
- inspect a fresh Hermes session and confirm it is clean

### 5. Document scope and region constraints honestly

**Goal:** Ensure the documentation does not overclaim capabilities that are region or scope limited.

**What to do:**
- note which models are CN-only vs global in the provider truth store comments
- note that some Alibaba models (vision, rerank, embedding, speech, image, video) may require specific region access
- do not claim full global availability for models that are CN or region-restricted

**Done when:**
- the documentation honestly reflects known constraints
- no model is listed as globally available if it is CN-only

### 6. Add regression tests for v1.2 features

**Goal:** Lock in v1.2 behavior so it does not regress.

**What to do:**
- add tests for Qwen3.6 Plus in the provider truth store
- add tests for RKWE detection with the correct canonical endpoint
- add tests for stale model detection across multiple providers
- add tests for routing diagnosis priority ordering
- add tests for broken fallback chain detection

**Done when:**
- the test suite covers the new v1.2 behavior end to end
- the full suite passes

**Verify:**
- run the targeted tests for the new behavior
- run the full suite

### 7. Commit local changes after each completed track

**Goal:** Keep the work auditable and easy to resume.

**What to do:**
- commit after each completed track
- keep the worktree clean before starting the next track
- do not push unless explicitly asked

**Done when:**
- each completed track has a local commit
- the worktree is clean at the end of the track

## Later backlog

These are requested features that remain queued after v1.2 unless explicitly reprioritized:

- managed Hermes upgrade flow with safe prompt handling
- broader live-truth coverage for additional providers and endpoints
- OpenClaw adapter (gateway health, config integrity, provider failures, plugin drift)
- OpenCode adapter (agent config, provider routing, worktree/task behavior)
- additional harness adapters following the same shape

## Notes

- Hermes-only scope stays intact for v1.2.
- Gateway health and CLI health must remain explicit, named, and verifiable.
- Do not silently mutate unrelated config.
- Do not declare a session healthy if the new-session state still contains invalid provider data.
- Provider truth is canonical; live truth is an optional refresh layer gated by HERMES_LIVE_TRUTH_ENABLED.
- Qwen3.6 Plus must be listed explicitly in the qwen provider family.
- Alibaba model types (vision, rerank, embedding, speech, image, video) must be noted in capabilities with honest scope constraints.
