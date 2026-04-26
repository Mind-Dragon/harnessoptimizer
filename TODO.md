# Hermes Optimizer /todo — v0.9.5 Refactor Audit Remediation

Current package version: 0.9.5
Target package version: 0.9.5
Base release proof: VERSION0.9.5.md
Current planning contract: VERSION0.9.5.md
Status: closed locally; v0.9.5 refactor audit remediation complete.

## Wave 1 — P0 Security + P1 Performance/Quality (autonomous overnight)

### P0 Security (must land in v0.9.5)

- [x] SEC-1: Fix shell injection in `sources/hermes_runtime.py:51`
  - **File:** `src/hermesoptimizer/sources/hermes_runtime.py`
  - **Task:** Change `_run_command` signature to `command: str | list[str]`; use `shlex.split(command)` when needed; enforce `shell=False`.
  - **Acceptance:** `shell=True` eliminated; function accepts both string and list; tests pass.
  - **Status:** done ✓
  - **Commit:** `fix(SEC-1): prevent shell injection in hermes_runtime._run_command`

- [x] SEC-2: Move GCP OAuth2 token from query to Authorization header
  - **File:** `src/hermesoptimizer/vault/providers/http.py:168`
  - **Task:** Replace `?access_token=...` query param with `Authorization: Bearer <token>` header.
  - **Acceptance:** Token no longer in URL; GCP API calls succeed with header auth.
  - **Status:** pending

- [x] SEC-3: Fix syntax error in `vault/classify.py:13`
  - **File:** `src/hermesoptimizer/vault/classify.py`
  - **Task:** Replace malformed `***` token with proper tuple/list syntax.
  - **Acceptance:** File parses; py_compile OK.
  - **Status:** pending

### P1 Performance (targeted)

- [ ] PERF-1: Pre-compute role→provider→model index in ModelCatalog
  - **File:** `src/hermesoptimizer/sources/model_catalog.py:322`
  - **Task:** Cache best_model candidate lookup; eliminate O(n²) repeated scanning.
  - **Acceptance:** best_model() becomes O(1) after catalog warmup; tests pass.
  - **Status:** pending

- [ ] PERF-2: Build region-aware index during catalog initialization
  - **File:** `src/hermesoptimizer/sources/model_catalog.py:359`
  - **Task:** Create region→models lookup at init time; use index in fallback path.
  - **Acceptance:** Region-aware lookup becomes O(1); tests pass.
  - **Status:** pending

### P1 Quality (Complexity Reduction)

- [ ] QUAL-1a: Refactor `auto_update.py:run_preflight` — complexity 20 → ≤10
  - **File:** `src/hermesoptimizer/auto_update.py:103`
  - **Task:**
    1. Extract large conditional branches into helper functions (e.g., `_check_config_matches`, `_assess_destructive_actions`)
    2. Reduce nesting by returning early where possible
    3. Aim for cyclomatic complexity ≤10
  - **Acceptance:** Complexity metric reduced; behavior unchanged; tests pass.
  - **Status:** pending

- [ ] QUAL-1b: Refactor `auto_update.py:visit` — complexity 17 → ≤10
  - **File:** `src/hermesoptimizer/auto_update.py:115`
  - **Task:**
    1. Extract recursive logic helpers (e.g., `_visit_dict`, `_visit_list`, `_detect_changes`)
    2. Flatten nested if/elif chains using strategy lookup if applicable
    3. Complexity ≤10
  - **Acceptance:** Complexity metric reduced; diff/precise behavior preserved; tests pass.
  - **Status:** pending

- [ ] QUAL-1c: Refactor `loop.py:parse` — complexity 16 → ≤10
  - **File:** `src/hermesoptimizer/loop.py:157`
  - **Task:**
    1. Extract parsing branch decisions into separate methods
    2. Use early returns to reduce nesting
    3. Complexity ≤10
  - **Acceptance:** Complexity metric reduced; parsing output unchanged; tests pass.
  - **Status:** pending

## Wave 2 — Code Health (deferred to v0.9.6 unless time permits)

- QUAL-2: Module docstring campaign (0% → 100% coverage)
- QUAL-3: Replace ~301 print() calls with logging (DEBUG/INFO/WARNING/ERROR)
- QUAL-4: Type hint coverage improvement (80% → 90%+)

## Verification & Closeout

After completing Wave 1:
- [ ] `PYTHONPATH=src python -m pytest -q` — all tests pass
- [ ] `PYTHONPATH=src python -m hermesoptimizer release-readiness --dry-run` — exit 0
- [ ] `brain/active-work/current.md` updated to final v0.9.5 state
- [ ] `VERSION0.9.5.md` final proof block added
- [ ] `CHANGELOG.md` updated with v0.9.5 release notes
- [ ] `git tag -a v0.9.5 -m "v0.9.5 — OpenClaw removal + P0 security fixes + P1 perf/quality"`

## Do Not Merge Until

- All Wave 1 P0 items complete and verified
- Test suite green
- No new critical/high issues in diff
- Governance/docs drift checks pass
