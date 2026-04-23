# Harness Optimizer /todo — 0.9.1 hardening pass

Current package version: `0.9.1`
Current focus: 0.9.1 closeout completed and verified. Keep this file as the truth record for what shipped and how it was proven.

## Status
- Overall: complete
- Full test suite: `pytest -q` passing
- Release gate: `PYTHONPATH=src python -m hermesoptimizer release-readiness --dry-run` passing
- Remaining non-critical note: extension doctor reports one dry-run drift warning for the `dreams` repo-external install targets not being present under `~/.hermes/scripts/` in this environment.

This pass exists to prevent three classes of failure:
- install corruption or partial writeback
- wrong model selected for the wrong config/plan/provider
- optimistic "available" claims that were never live-verified

---

## Phase A — Install integrity gate

### Task A.0: Validate the install contract before, during, and after work

**Objective:** prove we are installing the right thing, proving it is happening, and proving the result works.

**Files:**
- Modify: install/bootstrap/doctor path code
- Modify: tests that cover install flow
- Modify: any config writeback path touched by install

**Requirements:**
- beginning: confirm the user request and intended target before any write
- during: confirm the expected write or sync is actually in progress and hitting the intended files
- end: confirm the result matches the request and a proof check passes
- do not mark success until the post-install proof is green

**Verification:**
- pre-install intent check passes
- mid-install progress/state check passes
- post-install proof check passes
- rollback path exists if any stage fails

### Task A.1: Make every install path transactional

**Objective:** never leave Hermes in a corrupted or half-written state after install or sync.

**Files:**
- Modify: `src/hermesoptimizer/caveman/__init__.py`
- Modify: `src/hermesoptimizer/extensions/sync.py`
- Modify: `src/hermesoptimizer/extensions/doctor.py`
- Add tests under `tests/`

**Requirements:**
- write to temp files first
- validate parsed output before replace
- use atomic rename / replace only after validation
- keep a backup or rollback path for every writeback that can affect Hermes config

**Verification:**
- install/sync path passes syntax + parse + post-write smoke checks
- failing validation leaves the original file intact
- no partial YAML/JSON ever lands in live config

### Task A.2: Add an end-of-install canary

**Objective:** prove the install did not wreck the runtime surface.

**Files:**
- Modify: `src/hermesoptimizer/extensions/doctor.py`
- Add test coverage in `tests/test_extensions_*`

**Requirements:**
- run targeted post-install checks for the affected surface
- verify the CLI still boots
- verify the changed config still parses
- verify the changed config still matches the intended effective state

**Verification:**
- a broken install fails closed
- a good install reports a clean, auditable success artifact

---

## Phase B — Model / provider / plan truth

### Task B.1: Split user model choice from harness model choice

**Objective:** stop harnessoptimizer from overwriting the user’s Hermes compression model.

**Files:**
- Modify: config handling code for Hermes/HarnessOptimizer model selection
- Modify: tests that cover config writeback and model choice
- Update docs if a config schema is documented

**Requirements:**
- user-preferred model stays user-owned
- harnessoptimizer gets its own internal compression/model policy key
- installer must not replace GPT-5.4 with a repo default unless explicitly asked
- preserve existing user config unless the user requested a change

**Verification:**
- seeded config with GPT-5.4 stays GPT-5.4 after install/update
- harnessoptimizer internal model can differ without touching the user setting

### Task B.2: Enforce provider / model / plan matching

**Objective:** only select models that are actually available on the current provider and plan.

**Files:**
- Add or modify provider capability catalog code
- Add provider probe coverage
- Add tests for unavailable-plan cases

**Requirements:**
- model selection checks provider availability first
- plan eligibility is part of the decision
- blocked models stay blocked even if they exist somewhere upstream
- example rule: GLM 5.1V is not selectable on a coding plan if the live plan does not expose it

**Verification:**
- unavailable provider/model/plan combinations are rejected
- live-verified combinations are accepted
- stale registry entries do not become default picks

### Task B.3: Add a model capability matrix

**Objective:** map feature requirements to verified working models.

**Files:**
- Add: capability registry / model catalog files
- Add: tests for feature matching and live availability gating

**Requirements:**
- features: text, code, vision, audio, long-context, tool-use, structured output
- each model entry records provider, plan, context, and last verification state
- selection ranks verified matches only

**Verification:**
- a task with vision/audio/etc. selects a model that actually supports it
- a task never selects a model that is merely advertised but not usable

---

## Phase C — Streamed deployment to origin

### Task C.1: Define dev / beta / release channels

**Objective:** let changes stream through GitHub without manual push/pull chaos.

**Files:**
- Update branch/promotion docs
- Add CI or workflow definitions if missing
- Add repo-local notes for the three channels

**Requirements:**
- `dev` = active integration
- `beta` = promoted candidate
- `release` = locked shipped state
- promotion only moves forward
- each promotion runs tests before branch advancement

**Verification:**
- a bad build cannot advance from dev to beta
- beta and release each have explicit green gates

### Task C.2: Add automatic local update flow for each channel

**Objective:** let the local repo follow the branch it is meant to track.

**Files:**
- Add update/watch script or service
- Add install notes
- Add tests or dry-run checks for branch switching logic

**Requirements:**
- separate worktrees or equivalent isolation per channel
- fetch + fast-forward only
- no silent merge of unrelated changes
- post-update install canary runs automatically

**Verification:**
- each tracked channel can update without manual pull
- channel update only completes after tests and install integrity pass

---

## Phase D — Closeout proof

### Task D.1: Add a final 0.9.1 closeout gate

**Objective:** prove the repo is safe to call done for 0.9.1.

**Files:**
- Modify: release/doctor/report surface
- Update: README / ROADMAP / CHANGELOG only if needed for truth

**Requirements:**
- include install integrity
- include model/provider/plan truth
- include branch/channel update status
- include a live or dry-run result for the changed surface

**Verification:**
- one command or one compact report tells you whether 0.9.1 is safe to ship
- the report must fail closed if any critical check is missing

---

## Exit criteria

0.9.1 is not done until:
- install paths are atomic and validated
- YAML/JSON writes cannot corrupt Hermes
- user model choice is preserved
- provider/model/plan selection is live-verified
- dev / beta / release flow is defined
- final closeout gate reports green

---

## Notes

- Best effort means live probe, not assumption.
- If provider truth and config truth disagree, provider truth wins.
- If install safety and convenience disagree, install safety wins.
