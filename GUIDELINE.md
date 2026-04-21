# Hermes Optimizer Success Guidelines

This file defines how Hermes Optimizer v0.9.0 capability gates are judged.

These are release gates, not a package-version claim.

## The measurement idea

Success is not "it ran once."
Success is:
- it found the right files and runtime surfaces
- it recognized real problems
- it separated noise from signal
- it ranked fixes sensibly
- it grounded provider and runtime recommendations in live truth
- it produced reports that a human can act on

## What good looks like

A good run should answer these questions clearly:
- What files did we inspect?
- What health surfaces did we check?
- What failed or looks suspicious?
- Is the issue local config, session drift, provider mismatch, gateway health, or CLI health?
- What should be fixed first?
- What is a reasonable next action?

## Success metrics for v0.9.0

### Discovery
- 100% of known Hermes config, session, log, and database locations are represented in the path inventory
- any new location found in the wild can be added without restructuring the core
- path discovery is reproducible on a second run

### Parsing
- known Hermes failure cases are detected from config, session, and log files
- repeated signals are deduplicated into grouped findings
- raw evidence is preserved in samples or snippets
- false positives are low enough that the report stays readable

### Prioritization
- every finding receives one of the priority buckets:
  - critical
  - important
  - good ideas
  - nice to have
  - whatever
- critical items are reserved for things that break the harness or create bad output
- the ranking should be explainable by the text in the report

### Provider and runtime truth
- the optimizer prefers live runtime truth over local cached text when they disagree
- it can detect when the key is valid but the endpoint or alias is wrong
- it can detect when the model name is stale even if the provider account is fine
- it can detect when the gateway is healthy but the CLI state is not, and vice versa
- if live health and local config disagree, the report should show that mismatch instead of hiding it

### Reporting
- JSON output is machine-readable and stable
- Markdown output is readable and useful to a human
- reports show enough context to make a repair decision without opening the raw logs first
- reports show the inspected inputs and the exact health evidence used to make the call

### Tests
- unit tests cover the discovery, parsing, ranking, verification, and export layers
- tests do not depend on fragile live network access unless they are explicitly integration tests
- shared behavior remains stable across Hermes and later harnesses

## Operational rule

If a result cannot be explained in plain language, it is not ready to be trusted.

## Version gates

### v0.9.0 gate
- Hermes adapter works end to end
- real source locations are discovered
- findings are grouped and prioritized
- reports are useful

### next release gate
- Hermes gateway and CLI health are validated explicitly
- duplicate providers and blank providers are removed from the session path
- invalid new-session data is detected and surfaced clearly
- canonical providers resolve `base_url` and `api_key` from environment variables automatically
- stale `model.base_url` and `model.api_key` fields are stripped before reuse
- canonical providers do not stay duplicated in a user-defined `providers:` block
- provider-specific env overrides that conflict with canonical routing are cleared or ignored for the canonical path
- removed credential sources do not silently re-seed themselves
- repair recommendations are specific and safe

### Later gates
- other harnesses can be added without changing the Hermes rules above
- multi-harness reports stay coherent

## Anti-goals

- Do not measure success by line count.
- Do not count every warning as a finding.
- Do not trust cloned docs over live runtime evidence.
- Do not silently mutate config as part of measurement.
- Do not call the system healthy if the gateway or CLI is broken.
- Do not call a session clean if blank or duplicate providers still show up in new-session data.

## /todo and /devdo workflow

The optimizer now supports a two-command workflow for plan-then-execute development:

### /todo — Planning mode
- Creates and updates workflow plans
- Never executes work
- Validates plan quality before freezing
- Generates default task chains from an objective

### /devdo — Execution mode
- Consumes frozen plans
- Builds task DAGs and schedules parallel batches
- Dispatches subagents by role (research, implement, test, review, verify)
- Runs two-stage review on implementation tasks
- Checkpoints after each batch
- Resumes from last clean checkpoint on interruption
- Hard-blocks on invalid state, auto-repairs safe drift

### Command alias
- /dodev is aliased to /devdo for backward compatibility

### State on disk
- .hermes/workflows/<workflow_id>/plan.yaml — frozen plan
- .hermes/workflows/<workflow_id>/run.yaml — live execution state
- .hermes/workflows/<workflow_id>/tasks/ — per-task files
- .hermes/workflows/<workflow_id>/checkpoints/ — append-only history
- .hermes/workflows/<workflow_id>/artifacts/ — task output refs

### Guard rules
- /devdo refuses to start if the plan is missing, not frozen, or invalid
- Boundary checks run before writes, completions, phase transitions, and fan-outs
- Safe drift (version mismatch, stale guard state) is auto-repaired
- Unsafe drift (blocked guard, failed run) hard-blocks and requires human intervention

### Scheduler behavior
- Tasks are organized into a DAG with dependency depth levels
- Independent tasks at the same depth fan out in parallel batches
- Role pools limit parallelism per role (e.g., max 4 implementers, max 2 reviewers)
- The scheduler can scale to 10+ concurrent subagents for sufficiently wide task graphs
