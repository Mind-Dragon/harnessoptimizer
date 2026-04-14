# Hermes Optimizer Phase 0 TODO

Phase 0 is the discovery and loop-skeleton phase for Hermes only.
The job is to find every Hermes source of truth, define the runtime loop, and make the inventory reproducible before we start deeper parsing.

## Goal

Build the smallest useful Hermes foundation that can:
- discover Hermes config, session, log, cache, database, and runtime/gateway locations
- record those locations in a canonical inventory
- establish the scan loop: discover -> parse -> enrich -> rank -> report -> verify -> repeat
- prove the tool can locate the right surfaces before it tries to interpret them

## TODO

### 1) Discover Hermes truth sources

- [ ] Identify every Hermes config file in use on the live machine
- [ ] Identify Hermes session directories and file types
- [ ] Identify Hermes log directories and file types
- [ ] Identify Hermes cache/state directories that affect runs
- [ ] Identify Hermes database files or durable state files
- [ ] Identify Hermes gateway/runtime surfaces and status commands
- [ ] Record the discovered paths in a machine-readable inventory file

### 2) Verify source locations against the live environment

- [ ] Confirm each discovered path exists on the current machine
- [ ] Distinguish authoritative paths from fallback or legacy paths
- [ ] Capture any path that is referenced by runtime output but not yet documented
- [ ] Add a note for each source: config, session, log, cache, db, runtime, gateway

### 3) Define the Hermes loop

- [ ] Create the outer execution loop contract
- [ ] Define the order of operations: discover -> parse -> enrich -> rank -> report -> verify -> repeat
- [ ] Add a checkpoint or run marker so repeated runs can compare results
- [ ] Keep the loop explicit and testable, not hidden inside one big script

### 4) Establish baseline fixtures

- [ ] Save representative Hermes config samples
- [ ] Save representative Hermes session samples
- [ ] Save representative Hermes log samples
- [ ] Save at least one example of runtime/gateway status output
- [ ] Keep fixtures small and deterministic

### 5) Add the first scanner skeleton

- [ ] Add a source inventory loader
- [ ] Add a file/type classifier for discovered paths
- [ ] Add stub scanners for config, session, log, database, and runtime sources
- [ ] Make the scanner return structured records even before deeper parsing exists

### 6) Add phase 0 validation

- [ ] Write tests that prove discovered paths are captured correctly
- [ ] Write tests that prove the loop order is stable
- [ ] Write tests that prove runtime/gateway sources are included in the inventory
- [ ] Write tests that prove the scanner can operate on fixtures without crashing

### 7) Define phase 0 exit criteria

- [ ] Hermes source inventory is complete enough to trust
- [ ] Gateway/runtime surfaces are included in discovery
- [ ] The loop is explicit and repeatable
- [ ] Baseline fixtures exist
- [ ] Scanner skeleton runs end to end on Hermes-only data

## Done when

Phase 0 is done when the project can answer:
- where Hermes actually reads and writes state
- how the Hermes runtime/gateway is observed
- what files the optimizer should inspect on every run
- how the optimizer repeats the same discovery loop reliably

## Not yet

Do not build the deeper logic here yet:
- no full config repair rules
- no provider enrichment logic
- no live endpoint matching
- no ranking engine beyond the inventory and loop scaffolding
- no OpenClaw or OpenCode work
