# Hermes Optimizer TODO

Phase 1 through Phase 4 are complete.

## Done

- [x] Phase 1: Hermes config/session/log/runtime parsing and diagnostics
- [x] Phase 2: Provider truth lookup and endpoint verification
- [x] Phase 3: Routing diagnosis and prioritized optimization proposals
- [x] Phase 4: Loop closure, post-change verification, and hardening
- [x] Commit the current Hermes Optimizer worktree changes
- [x] Add any final smoke tests needed for Phase 4 stability

## Notes

- Keep Hermes-only for v1.0.
- OpenClaw and OpenCode stay out of this scope for now.
- Preserve the live-truth rule: config and docs are not enough when provider/model truth matters.
