# VERSION0.9.2 — Release Audit and Contract

## Release identity

- Package: `hermesoptimizer`
- Version: `0.9.2`
- Branch observed: `dev/0.9.2`
- Audit date: 2026-04-23
- Canonical TODO: `TODO.md`

## Release scope

v0.9.2 is the release-hardening milestone that combines:

- extension lifecycle management and drift detection
- config governance and service lifecycle work
- model/provider/plan truth hardening
- auxiliary model routing drift detection
- release readiness reporting that is version-aware instead of hardcoded to 0.9.1

## Build-verified state

The following checks passed during the audit:

```bash
git diff --check
PYTHONPATH=src python -m hermesoptimizer --help
PYTHONPATH=src python -m hermesoptimizer release-readiness --dry-run
python -m pytest -q
python3 scripts/apply_reload_patch.py --check
```

Observed results:

- `git diff --check`: pass
- CLI help: pass
- release readiness dry-run: pass, `GATE: PASSED — 0.9.2 is safe to ship`
- pytest: pass, 1956 passed, 4 skipped, docling deprecation warnings only
- hot-reload patch check: pass, patch is currently applied

## Live-verified state

The release gate is green and `brain-doctor --dry-run` is green after the rail contract correction:

```bash
PYTHONPATH=src python -m hermesoptimizer brain-doctor --dry-run
```

Observed result:

- overall_status: `pass`
- checks_run: 3
- rail_loader: pass; SOUL/HEARTBEAT are markdown/plaintext rails
- request_dump: evidence-only signal; 49 MiniMax retry exhaustions and 1 crof.ai non-retryable error remain captured in provider policy
- provider_probe: dry-run list only

This means v0.9.2 is build-verified and brain-doctor dry-run verified. Provider dump failures remain documented do-not-use/fallback policy input, not a release gate failure.

## Findings

### F1 — Stale package version labels

Active docs still referenced 0.9.1 even though the package and release gate are 0.9.2.

Affected surfaces found:

- `TODO.md`: stale title and current package version
- `ROADMAP.md`: stale current package version line
- `TESTPLAN.md`: stale active test-plan title/status
- `src/hermesoptimizer/cli/orphan.py`: release-readiness help text said 0.9.1 closeout gate

Impact:

- Future agents can run the right code but update the wrong release docs.
- The release gate can print 0.9.2 while nearby docs say 0.9.1.

Remediation:

- `TODO.md` is now the v0.9.2 release-hardening queue.
- Active doc/code labels found in the audit were updated to 0.9.2 or made version-neutral.

### F2 — Stale repo-root references

Several current docs reference `/home/agent/hermesagent`, but the live repo is `/home/agent/hermesoptimizer`.

Affected surfaces found:

- `AGENTS.md`
- `GUIDELINE.md`
- `ARCHITECTURE.md`
- `docs/PLAN.md`
- `brain.md`
- `skills/provider-debug/SKILL.md`

Impact:

- New agents following the repo-local instructions can inspect or patch the wrong directory.

Remediation:

- Current repo docs were updated to `/home/agent/hermesoptimizer`.
- Archived historical docs under `.archives/` are allowed to remain stale.
- Remaining mentions in `TODO.md` and this file are intentional audit text.

### F3 — Nonexistent architecture surface

`ARCHITECTURE.md` references `sysdx/`, but the live code surface is `src/hermesoptimizer/` and no `sysdx/` directory exists.

Impact:

- The architecture map misleads future work planning.

Remediation:

- `ARCHITECTURE.md` now identifies `src/hermesoptimizer/` plus tests as the live code surface.

### F4 — Brain health red while release readiness green

`release-readiness --dry-run` and `brain-doctor --dry-run` now both pass.

Previous brain-doctor findings:

- SOUL and HEARTBEAT rail files are markdown/plaintext; the checker now treats markdown/plaintext as the correct rail contract.
- Latest request-dump sample has 49 MiniMax `max_retries_exhausted` failures; MiniMax provider policy now documents the do-not-use/fallback condition.
- Latest request-dump sample has 1 crof.ai `non_retryable_client_error` failure; `brain/providers/nacrof-crof.md` now documents the failure policy.
- Provider probe is still dry-run-listed in the doctor output.

Impact:

- Operators can now treat release readiness plus brain-doctor dry-run as the solid v0.9.2 baseline; live authenticated provider probes remain separate.

Remediation:

- Task 2.1 resolved the release blocking policy.
- Task 2.2 fixed the rail loader contract.
- Task 2.3 promoted provider failures into provider notes and fallback/quarantine policy.

### F5 — Hot-reload patch script is useful but not release-grade yet

Untracked files currently document and apply a Hermes CLI `/reload` config hot-reload patch:

- `CONFIG-MANAGER.md`
- `scripts/apply_reload_patch.py`
- `scripts/post-merge-hook.sh`

The live patch check passes. `apply_reload_patch.py` now stages the patched content, parses it, creates a backup, uses atomic replace, and restores on failure.

Impact:

- This now satisfies the install-integrity requirement for safe writeback into Hermes runtime files.

Remediation:

- Task 3.1 made the patch transactional.
- Task 3.2 classifies these files as release docs/scripts ready to track.

### F6 — Changelog / roadmap scope ambiguity

`ROADMAP.md` describes v0.9.2 as extension lifecycle management. `CHANGELOG.md` also has a top v0.9.2 section for config governance, model evaluation, and service work, plus a section labelled `v0.9.1 -- Extension Lifecycle Management` that appears to describe v0.9.2 work.

Impact:

- The release scope is ambiguous.

Remediation:

- `CHANGELOG.md` and `ROADMAP.md` now describe v0.9.2 as extension lifecycle plus config governance/model/service hardening.

## Dirty tree observed during audit

Modified files:

- `brain/active-work/current.md`
- `pyproject.toml`
- `src/hermesoptimizer/__init__.py`
- `src/hermesoptimizer/auxiliary_optimizer.py`
- `src/hermesoptimizer/extensions/doctor.py`
- `src/hermesoptimizer/loop.py`
- `src/hermesoptimizer/release/readiness.py`
- `src/hermesoptimizer/sources/provider_truth.py`
- `tests/test_lane_a_smoke.py`
- `tests/test_release_readiness.py`

Untracked files:

- `CONFIG-MANAGER.md`
- `scripts/apply_reload_patch.py`
- `scripts/post-merge-hook.sh`

These were not reverted. They appear related to v0.9.2 release hardening and config hot-reload operations.

## Release decision

Current decision: v0.9.2 is a solid release candidate.

Reason:

- Build/test/release gate is green.
- Active release docs and stale repo-root references were reconciled.
- Brain health dry-run is green.
- MiniMax/crof dump failures are captured as provider policy, not silent generated-report noise.
- Hot-reload patch artifacts are transactional and ready to track.
- Release readiness now includes a `release_doc_drift` check to prevent regression.

Solid release criteria are enumerated in `TODO.md` under "Exit Criteria For Solid v0.9.2" and passed on 2026-04-23.


## Final proof — 2026-04-23

```bash
python -m pytest -q
PYTHONPATH=src python -m hermesoptimizer release-readiness --dry-run
PYTHONPATH=src python -m hermesoptimizer brain-doctor --dry-run
python3 scripts/apply_reload_patch.py --check
python3 -m py_compile scripts/apply_reload_patch.py
git diff --check
```

Observed results:

- pytest: pass, 1956 passed, 4 skipped
- release-readiness: pass, `GATE: PASSED — 0.9.2 is safe to ship`
- brain-doctor: pass
- apply_reload_patch check: pass, patch is applied
- py_compile: pass
- git diff check: pass
- active stale-reference search: pass, no active hits outside intentional TODO/VERSION audit text
