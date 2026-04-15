# Hermes Optimizer TODO

This file records the implementation work that was completed and the validation that now passes against real live sources.

## Doc alignment

- Matches PHASES.md Phase 2: live provider truth and endpoint verification, including auth vs endpoint vs stale-model separation.
- Matches PHASES.md Phase 4: closed-loop verification, repeat-run stability, before/after proof, and v1.0 readiness.
- Matches ARCHITECTURE.md by keeping Hermes-only scope, live truth over cached text, grouped findings, and prioritized recommendations.
- Matches GUIDELINE.md by preserving discovery coverage, deduped findings, plain-language reports, and explicit live-verified truth where applicable.

## Done

- [x] Phase 0 code fixes: real gateway probe, canonical inventory coverage, report inspected-inputs header, and runtime-canary noise reduction
- [x] Phase 2 code fixes: live-truth gate, endpoint probing, AUTH_FAILURE vs RKWE vs STALE_MODEL separation, and opt-in network checks
- [x] Phase 3 code fixes: grouped finding summaries, multi-provider fallback coverage, bucket labels, and human-readable recommendation summaries
- [x] Phase 4 code fixes: repeat-run stability checks, before/after proof scaffolding, and explicit readiness criteria in tests
- [x] Added grouped finding and inspected-input support to report output
- [x] Updated the local optimizer run report against the current fixture bundle
- [x] Verified the full test suite passes
- [x] Verified live-truth resolution against real provider docs/endpoints sources
- [x] Verified before/after improvement on a changed local target with a real gateway probe

## Notes

- Keep Hermes-only for v1.0.
- OpenClaw and OpenCode stay out of scope for now.
- Live provider truth still beats local cached text when they disagree.
- Gateway and runtime canaries should remain explicit, named, and verifiable.
