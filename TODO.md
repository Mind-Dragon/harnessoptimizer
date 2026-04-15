# Hermes Optimizer TODO

This file records the implementation work that was completed and the few remaining validation gaps that still need a real external target.

## Done

- [x] Phase 0 code fixes: real gateway probe, canonical inventory coverage, report inspected-inputs header, and runtime-canary noise reduction
- [x] Phase 2 code fixes: live-truth gate, endpoint probing, AUTH_FAILURE vs RKWE vs STALE_MODEL separation, and opt-in network checks
- [x] Phase 3 code fixes: grouped finding summaries, multi-provider fallback coverage, bucket labels, and human-readable recommendation summaries
- [x] Phase 4 code fixes: repeat-run stability checks, before/after proof scaffolding, and explicit readiness criteria in tests
- [x] Added grouped finding and inspected-input support to report output
- [x] Updated the local optimizer run report against the current fixture bundle
- [x] Verified the full test suite passes

## Remaining validation gaps

- [ ] Run the live-truth path against a real provider docs/endpoints source with `HERMES_LIVE_TRUTH_ENABLED=1`
  - Verify: a real live-truth fetch resolves a record and can classify endpoint/auth/model mismatches without fixture stubs.
- [ ] Prove before/after improvement against a real changed target, not only a fixture-level simulation
  - Verify: the second run is measurably cleaner after a real fix.

## Notes

- Keep Hermes-only for v1.0.
- OpenClaw and OpenCode stay out of scope for now.
- Live provider truth still beats local cached text when they disagree.
- Gateway and runtime canaries should remain explicit, named, and verifiable.
