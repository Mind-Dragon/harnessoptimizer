# Harness Optimizer /todo — v0.9.2 release hardening

Current package version: `0.9.2`
Current focus: finish the v0.9.2 release surface by reconciling docs, release proof, brain health, and install-integrity gaps found in the 2026-04-23 audit.

## Current verified state

- Branch: `dev/0.9.2`
- Package version: `pyproject.toml` and `src/hermesoptimizer/__init__.py` are `0.9.2`
- Full test suite: `python -m pytest -q` passes: 1956 passed, 4 skipped
- Release gate: `PYTHONPATH=src python -m hermesoptimizer release-readiness --dry-run` passes
- CLI boot: `PYTHONPATH=src python -m hermesoptimizer --help` passes
- Brain health: `PYTHONPATH=src python -m hermesoptimizer brain-doctor --dry-run` passes; provider dump evidence remains documented policy input
- Detailed audit and release notes: `VERSION0.9.2.md`

## Release rule

Do not call v0.9.2 solid until every CRITICAL and HIGH task below is either complete with proof or explicitly moved to a non-blocking known-issue section in `VERSION0.9.2.md`.

---

## Wave 0 — Release Truth Lock

### Task 0.1: Reconcile package version labels

**Status:** complete — active package labels now point at 0.9.2.
**Priority:** CRITICAL

**Objective:** remove stale `0.9.1` package-version claims from active release docs.

**Files:**
- Modify: `ROADMAP.md`
- Modify: `TESTPLAN.md`
- Modify: `CHANGELOG.md` if the v0.9.2/v0.9.1 headings disagree with the intended milestone split
- Check: `README.md`

**Acceptance:**
- Active package version references say `0.9.2`
- Historical v0.9.1 section names remain only where they describe the old milestone
- Search for stale active-version references returns only historical hits

**Verification:**
- `rg "Current package version: 0\.9\.1|v0\.9\.1 closeout|0\.9\.1 is safe" *.md docs src tests`
- `PYTHONPATH=src python -m hermesoptimizer release-readiness --dry-run`

### Task 0.2: Add canonical `VERSION0.9.2.md`

**Status:** complete — `VERSION0.9.2.md` created.
**Priority:** CRITICAL

**Objective:** make the release contract, current findings, proof commands, and known gaps durable in one versioned file.

**Files:**
- Create: `VERSION0.9.2.md`
- Reference from: `README.md` or `CHANGELOG.md` if needed

**Acceptance:**
- Includes release scope, shipped changes, verification results, known blockers, and post-release queue
- Separates build-verified from live-verified status
- Names `brain-doctor --dry-run` failure as either blocking or intentionally non-blocking

**Verification:**
- `test -f VERSION0.9.2.md`
- `rg "Build-verified|Live-verified|brain-doctor|release-readiness" VERSION0.9.2.md`

### Task 0.3: Fix stale repo-root paths

**Status:** complete — current docs now use `/home/agent/hermesoptimizer`; remaining mentions are intentional audit/TODO text.
**Priority:** HIGH

**Objective:** prevent future agents from following the old `hermesagent` repo-root references inside this repo.

**Files:**
- Modify: `AGENTS.md`
- Modify: `GUIDELINE.md`
- Modify: `ARCHITECTURE.md`
- Modify: `docs/PLAN.md`
- Modify: `brain.md`
- Modify: `skills/provider-debug/SKILL.md`

**Acceptance:**
- Current repo docs use `/home/agent/hermesoptimizer`
- Archived material can remain stale under `.archives/`

**Verification:**
- `rg "/home/agent/hermesagent" --glob '!TODO.md' --glob '!VERSION0.9.2.md' --glob '!/.archives/**' .`

### Task 0.4: Remove or reframe nonexistent `sysdx/` architecture references

**Status:** complete — architecture now names `src/hermesoptimizer/` and `tests/`.
**Priority:** HIGH

**Objective:** align architecture docs with the live `src/hermesoptimizer/` code surface.

**Files:**
- Modify: `ARCHITECTURE.md`

**Acceptance:**
- `ARCHITECTURE.md` no longer claims `sysdx/` exists
- Directory architecture shows `src/hermesoptimizer/` and `brain/` as the live code/brain surfaces

**Verification:**
- `rg "sysdx" ARCHITECTURE.md`

---

## Wave 1 — Release Surface Cleanup

### Task 1.1: Update release-readiness CLI help text

**Status:** complete — help text is version-neutral.
**Priority:** HIGH

**Objective:** make the CLI help describe the current version-neutral release gate.

**Files:**
- Modify: `src/hermesoptimizer/cli/orphan.py`

**Acceptance:**
- Help no longer says `Run 0.9.1 closeout gate`
- `--help` still boots

**Verification:**
- `PYTHONPATH=src python -m hermesoptimizer --help | rg "release-readiness"`
- `python -m pytest tests/test_release_readiness.py -q`

### Task 1.2: Audit v0.9.2 changelog headings

**Status:** complete — roadmap/changelog now describe v0.9.2 as extension lifecycle plus config governance hardening.
**Priority:** HIGH

**Objective:** clarify whether extension lifecycle belongs to v0.9.2 or v0.9.1, and ensure the changelog/roadmap agree.

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `ROADMAP.md` if needed
- Update: `VERSION0.9.2.md`

**Acceptance:**
- No duplicate or contradictory v0.9.2/v0.9.1 milestone descriptions
- Current v0.9.2 scope is explicit: extension lifecycle plus config/model/service hardening if both shipped in this release

**Verification:**
- `rg "## v0\.9\.[12]|### v0\.9\.[12]" CHANGELOG.md ROADMAP.md VERSION0.9.2.md`

### Task 1.3: Reconcile TESTPLAN title and status

**Status:** complete — title/status/baseline updated to the current 1,960-test surface.
**Priority:** MEDIUM

**Objective:** make `TESTPLAN.md` describe the current v0.9.2 validation surface.

**Files:**
- Modify: `TESTPLAN.md`

**Acceptance:**
- Title/status reference v0.9.2 where describing the active test plan
- Historical test domains can retain original version names
- Current test count is refreshed if stated

**Verification:**
- `rg "v0\.9\.1|1,534|1,680" TESTPLAN.md`
- `python -m pytest -q`

---

## Wave 2 — Brain Health and Live Truth

### Task 2.1: Decide brain-doctor release blocking policy

**Status:** complete — brain-doctor dry-run now passes after rail contract correction; request-dump remains evidence, not a critical doctor failure.
**Priority:** CRITICAL

**Objective:** make the release gate and brain-health gate relationship explicit.

**Files:**
- Modify: `VERSION0.9.2.md`
- Modify: `src/hermesoptimizer/release/readiness.py` only if brain-doctor must become part of release readiness
- Add/update tests if release readiness behavior changes

**Acceptance:**
- `brain-doctor --dry-run` red state is either a release blocker or a documented known live-health issue
- The release gate is not silently green while users believe all project health is green

**Verification:**
- `PYTHONPATH=src python -m hermesoptimizer brain-doctor --dry-run || true`
- `PYTHONPATH=src python -m hermesoptimizer release-readiness --dry-run`

### Task 2.2: Fix rail loader markdown/JSON mismatch

**Status:** complete — `prefill_messages_file` was cleared in `~/.hermes/config.yaml`; SOUL/HEARTBEAT are verified as markdown rails.
**Priority:** HIGH

**Objective:** stop repeated SOUL/HEARTBEAT JSON parse failures by making the rail loader contract truthful.

**Files:**
- Inspect/modify: `brain/scripts/rail_loader_check.py`
- Inspect/modify: loader code that expects JSON for `/home/agent/clawd/SOUL.md` and `HEARTBEAT.md`
- Add/update tests: `brain/scripts/test_rail_loader_check.py` or `tests/`
- Update: `brain/active-work/current.md`
- Update: relevant incident/provider notes if present

**Acceptance:**
- Markdown/plaintext rails are accepted when configured as markdown/plaintext, or the config points to JSON rails
- No new SOUL/HEARTBEAT JSON parse errors appear in the checked log window

**Verification:**
- `python3 brain/scripts/rail_loader_check.py --dry-run`
- `PYTHONPATH=src python -m hermesoptimizer brain-doctor --dry-run`

### Task 2.3: Promote MiniMax/crof provider failures into provider policy

**Status:** complete — MiniMax incident/provider note updated; `brain/providers/nacrof-crof.md` added for crof.ai failure policy.
**Priority:** HIGH

**Objective:** convert repeated request-dump failures into provider notes, fallback policy, or quarantine rules.

**Files:**
- Modify: `brain/providers/minimax-chat.md`
- Modify: `brain/providers/kimi-coding.md` or crof/nacrof provider note if present
- Modify: `brain/incidents/` incident file if missing
- Modify: `brain/evals/provider-canaries.json` if probe policy changes

**Acceptance:**
- 49/49 MiniMax retry exhaustion and 1 crof non-retryable error are not only present in generated reports
- Provider notes define do-not-use/fallback conditions
- Canary output cannot mark an HTML challenge, missing model, or repeated retry exhaustion as green

**Verification:**
- `python3 brain/scripts/request_dump_digest.py --source /home/agent/.hermes/sessions --limit 50`
- `PYTHONPATH=src python -m hermesoptimizer brain-probe --dry-run`

---

## Wave 3 — Install Integrity Hardening

### Task 3.1: Make `apply_reload_patch.py` transactional

**Status:** complete — script now validates syntax, stages temp file, writes backup, atomically replaces, and restores on failure.
**Priority:** HIGH

**Objective:** align the hot-reload patch script with the install-integrity rules in `GUIDELINE.md`.

**Files:**
- Modify: `scripts/apply_reload_patch.py`
- Add tests under `tests/` or script-level dry-run fixtures
- Update: `CONFIG-MANAGER.md`

**Acceptance:**
- Script stages to a temp file
- Validates the patched Python parses before replace
- Uses atomic replace
- Preserves backup or rollback path
- `--check` remains read-only

**Verification:**
- `python3 scripts/apply_reload_patch.py --check`
- targeted patch-script tests
- `python -m pytest -q`

### Task 3.2: Track or intentionally quarantine hot-reload artifacts

**Status:** complete — artifacts are release docs/scripts and are ready to track after verification.
**Priority:** MEDIUM

**Objective:** decide whether the untracked hot-reload docs/scripts are release artifacts.

**Files:**
- Decide: `CONFIG-MANAGER.md`
- Decide: `scripts/apply_reload_patch.py`
- Decide: `scripts/post-merge-hook.sh`
- Modify: `.gitignore` only if quarantining generated/local artifacts

**Acceptance:**
- These files are either tracked as part of v0.9.2 or explicitly excluded from release scope
- If tracked, the scripts meet install-integrity requirements first

**Verification:**
- `git status --short`
- `python3 scripts/apply_reload_patch.py --check`

### Task 3.3: Add release doc cross-check command

**Status:** complete — `release_doc_drift` check and tests added to release readiness.
**Priority:** MEDIUM

**Objective:** prevent future version/path/doc drift before release.

**Files:**
- Add or extend: `src/hermesoptimizer/release/readiness.py`
- Add tests: `tests/test_release_readiness.py`

**Acceptance:**
- Release readiness catches stale active package labels and stale repo-root references outside `.archives/`
- Historical references remain allowed when explicitly classified as historical

**Verification:**
- `python -m pytest tests/test_release_readiness.py -q`
- `PYTHONPATH=src python -m hermesoptimizer release-readiness --dry-run`

---

## Exit Criteria For Solid v0.9.2

- All CRITICAL tasks complete
- All HIGH tasks complete or explicitly documented as non-blocking in `VERSION0.9.2.md`
- `python -m pytest -q` passes
- `PYTHONPATH=src python -m hermesoptimizer release-readiness --dry-run` passes
- `PYTHONPATH=src python -m hermesoptimizer --help` passes
- `git diff --check` passes
- `VERSION0.9.2.md` contains final proof commands and results

## Final v0.9.2 proof — 2026-04-23

- `python -m pytest -q`: pass, 1956 passed, 4 skipped
- `PYTHONPATH=src python -m hermesoptimizer release-readiness --dry-run`: pass, `GATE: PASSED — 0.9.2 is safe to ship`
- `PYTHONPATH=src python -m hermesoptimizer brain-doctor --dry-run`: pass
- `python3 scripts/apply_reload_patch.py --check`: pass, patch is applied
- `python3 -m py_compile scripts/apply_reload_patch.py`: pass
- `git diff --check`: pass
- `rg "/home/agent/hermesagent|Current package version: 0\.9\.1|v0\.9\.1 closeout|0\.9\.1 is safe" --glob '!TODO.md' --glob '!VERSION0.9.2.md' --glob '!/.archives/**' --glob '!htmlcov/**' --glob '!*.egg-info/**' .`: pass, no active hits
