# Incident Promotion Pattern

## Purpose

Define when a failure pattern in provider notes is mature enough to be promoted to a formal incident artifact under `brain/incidents/`.

## Promotion Threshold

A finding is promoted to incident when ALL of the following are true:

| Criterion | Threshold | Rationale |
|-----------|-----------|-----------|
| Occurrence count | >= 5 distinct session artifacts in a single bounded digest | Rules out one-off glitches |
| Consistency | Same `reason` + same `url` (or url pattern) in >= 80% of the cluster | Confirms a reproducible failure class |
| Provider coverage | Provider note already exists with the failure mode documented | Incident extends, not replaces, provider truth |
| Time spread | Artifacts span at least 2 different days OR 3 different cron cycles | Rules out a single burst |

## Minimum Required Fields for a Valid Incident

```yaml
- Date: YYYY-MM-DD              # First observed occurrence
- Severity: low|medium|high     # Based on impact scope
- Status: open|mitigated|closed
- Owner: unassigned|name        # Who owns resolution

## Symptom
# What the error looks like in logs/dumps

## Scope  
# Which lanes/users/workflows are affected

## Evidence
- request_dump: N artifacts, list sample paths
- log_references: grep-friendly identifiers
- session_ids: comma-separated sample session IDs

## Root cause
# Probable cause (not confirmed until fix lands)

## Structural fix
# skill: name if exists, "none yet" if not
# script: verification script if any
# resolver_change: yes/no + brief description

## Verification
# How to confirm the incident is resolved
```

## Imprecise Handling

If evidence is suggestive but below threshold:
- Leave in provider note with timestamped observation
- Tag with `ambiguous: true` in evidence block
- Do not create incident file
- Re-evaluate on next digest run

## Ambiguity Markers

Evidence clusters that do NOT meet promotion threshold must be tagged:

```
## Ambiguous evidence
- reason: <reason>
- count: <N>  # below threshold
- sample_paths: [...]
- next_recheck: YYYY-MM-DD  # next scheduled digest
```

## Review Cadence

- After every `request_dump_digest` run, controller reviews new clusters
- Quarterly full review of open incidents to verify still valid
- If incident has no new evidence in 60 days, mark `stale: true` in status
