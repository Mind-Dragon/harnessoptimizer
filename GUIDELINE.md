# Hermes Optimizer Success Guidelines

This file defines how v1.0 is judged and how later versions should be measured.

## The measurement idea

Success is not "it ran once."
Success is:
- it found the right files
- it recognized real problems
- it separated noise from signal
- it ranked fixes sensibly
- it grounded provider/model recommendations in live truth
- it produced reports that a human can act on

## What good looks like

A good run should answer these questions clearly:
- What files did we inspect?
- What failed or looks suspicious?
- Is the issue local config, session drift, provider mismatch, or endpoint mismatch?
- What should be fixed first?
- What is a reasonable next action?

## Success metrics for v1.0

### Discovery
- 100% of known Hermes config/session/log/database locations are represented in the path inventory
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

### Provider/model truth
- the optimizer prefers live provider docs and provider endpoints over local cached text
- it can detect when the key is valid but the endpoint is wrong
- it can detect when the model name is stale even if the provider account is fine
- if the website and endpoint disagree, the report should show that mismatch instead of hiding it

### Reporting
- JSON output is machine-readable and stable
- Markdown output is readable and useful to a human
- reports show enough context to make a repair decision without opening the raw logs first

### Tests
- unit tests cover the discovery, parsing, ranking, and export layers
- tests do not depend on a fragile live network unless they are explicitly integration tests
- shared behavior remains stable across Hermes, OpenClaw, OpenCode, and later harnesses

## Operational rule

If a result cannot be explained in plain language, it is not ready to be trusted.

## Version gates

### v1.0 gate
- Hermes adapter works end to end
- real source locations are discovered
- findings are grouped and prioritized
- reports are useful

### v1.1 gate
- OpenClaw adds gateway, config, and provider diagnosis
- repair recommendations are specific and safe

### v1.2 gate
- OpenCode adds provider-routing and worktree/runtime diagnosis
- multi-harness reports stay coherent

## Anti-goals

- Do not measure success by line count
- Do not count every warning as a finding
- Do not trust cloned docs over the live provider
- Do not silently mutate config as part of measurement
- Do not call the system healthy if the endpoint is wrong but the key happens to work elsewhere
