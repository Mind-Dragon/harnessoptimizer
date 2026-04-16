# Hermes Optimizer — Historical 0.4 Working Plan

**Status:** Completed in v0.4.0. This document describes the old runtime-hygiene pass and is kept only as historical context.

## What this plan used to cover
- provider registry cleanup
- explicit gateway and CLI health checks
- invalid new-session data detection
- suppression of removed credential sources

## Why it is historical now
That entire hygiene story is already shipped in the current repository:
- runtime hygiene and provider cleanup were delivered before v0.4.0
- the workflow engine (/todo + /devdo) was delivered in v0.4.0
- the current package version is still `0.4.0`

## Current active path
Use `ROADMAP.md` as the source of truth for the next work:
1. v0.5.0 — vault management and credential lifecycle
2. v0.6.0 — OpenClaw gateway and config diagnosis
3. v0.7.0 — OpenCode agent config and provider routing
4. v0.8.0+ — cross-harness correlation and adapter template

## Notes
- Do not treat this file as the active backlog.
- Do not reopen the shipped workflow engine work.
- `VERSION0.4.md` now carries the transition note for the old 0.4 release note.
