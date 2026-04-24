# Brain System Build Plan

> For Hermes: this plan is the active build sequence for turning `/home/agent/hermesoptimizer` into a working compiled-brain workspace.

**Goal:** build a local-first, deterministic-first brain system that can absorb repeated runtime failures and turn them into durable project structure.

**Architecture:** the repo is organized around governance docs, structured brain artifacts, deterministic helper scripts, eval fixtures, and evidence-driven provider/incident management. The build sequence starts with substrate and hygiene, then adds provider gates, rail checks, continuity state, resolver audits, and incident-to-skill promotion. [R1][R2][R3]

**Tech Stack:** Markdown docs, Python 3.14 scripts, git, local Hermes session/log artifacts.

---

## Current status

Already present:
- `brain.md` analysis document
- `brain/` scaffold with providers, incidents, evals, scripts
- `provider_probe.py`
- `request_dump_digest.py`
- `rail_loader_check.py`
- `brain_doctor.py`
- `resolver_audit.py`
- `active_work_lint.py`
- provider bootstrap and provider health notes
- request-dump summary and provider-health inputs
- `brain/active-work/current.md` compact live snapshot
- v0.9.3 provider registry / clean-install closeout proof

Missing or still partial:
- incident-to-skill promotion automation
- broader resolver fixture coverage
- native Hermes status/doctor bridge, intentionally deferred beyond v0.9.3

---

## Phase 0: Repo hygiene and source-of-truth lock

### Task 0.1: Create repo-local ignore policy

**Objective:** keep tracked history focused on durable docs and source, not local runtime noise.

**Files:**
- Create: `.gitignore`

**Implementation instructions:**
- ignore: `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.ruff_cache/`
- ignore: `.beads/`, `.sisyphus/`
- ignore generated reports under `brain/reports/*.json`
- keep docs and source tracked

**Verification:**
Run:
`git -C /home/agent/hermesoptimizer status --short`

Expected:
- cache/db/report noise disappears from untracked set
- durable docs and source remain visible

### Task 0.2: Start clean local history

**Objective:** create the first local commit with governance docs, scaffold, and deterministic helpers.

**Files:**
- Stage: governance docs, brain scaffold, source files intended for tracking

**Verification:**
Run:
`git -C /home/agent/hermesoptimizer log --oneline -1`

Expected:
- one local bootstrap commit exists

---

## Phase 1: Governance and rails

### Task 1.1: Land the doc suite

**Objective:** keep repo-local governing docs synchronized.

**Files:**
- `AGENTS.md`
- `GUIDELINE.md`
- `ARCHITECTURE.md`
- `docs/PLAN.md`

**Implementation instructions:**
- use one vocabulary across all docs
- cite `brain.md`, request-dump report, and source repositories
- keep deterministic-first and provider-health-first language consistent

**Verification:**
- search all four docs for `deterministic`, `provider`, `active-work`, `incident`
- confirm they describe the same system

### Task 1.2: Add rail loader check

**Objective:** detect the SOUL/HEARTBEAT prefill mismatch with a deterministic script.

**Files:**
- Create: `brain/scripts/rail_loader_check.py`
- Create: `brain/evals/rail-checks.json` or embed minimal config in script
- Modify: incident note if behavior is clarified

**Implementation instructions:**
- inspect configured rail file paths
- verify file existence
- check whether loader expects structured JSON vs markdown/plaintext
- emit machine-readable result

**Verification:**
Run:
`python3 brain/scripts/rail_loader_check.py --dry-run`

Expected:
- explicit pass/fail/skipped output
- incident file can point to this script as the canonical check

---

## Phase 2: Provider health control plane

### Task 2.1: Harden provider registry notes

**Objective:** make each active lane note operationally useful.

**Files:**
- `brain/providers/minimax-chat.md`
- `brain/providers/kimi-coding.md`
- `brain/providers/chatgpt-codex-summary-lane.md`

**Implementation instructions:**
- add last-checked timestamps when probes are run
- record exact failure signatures
- set explicit fallback policy and do-not-use conditions

**Verification:**
- each provider file has identity, behavior, canaries, routing, and evidence sections filled

### Task 2.2: Run live provider probes when credentials are available

**Objective:** convert dry-run canaries into real lane health checks.

**Files:**
- Update: provider notes
- Generate: `brain/reports/provider-probe-*.json` if desired

**Implementation instructions:**
- use `provider_probe.py`
- forbid false green results from HTML challenge pages or 404 resource-not-found lanes
- record outcomes back into notes

**Verification:**
Run:
`python3 brain/scripts/provider_probe.py --config brain/evals/provider-canaries.json --provider <name>`

Expected:
- explicit result artifact
- provider note updated accordingly

---

## Phase 3: Evidence digestion and incident compiler

### Task 3.1: Normalize request-dump digestion

**Objective:** keep repeated transport/provider pain queryable.

**Files:**
- `brain/scripts/request_dump_digest.py`
- generated report(s) under `brain/reports/`
- provider notes and incidents as promotions

**Implementation instructions:**
- run digest on full or bounded corpus
- identify top endpoint/model/reason clusters
- promote durable conclusions into provider notes and incidents

**Verification:**
Run:
`python3 brain/scripts/request_dump_digest.py --source /home/agent/.hermes/sessions --limit 100`

Expected:
- structured report with reasons, top URLs, top models, sample sessions

### Task 3.2: Add incident promotion pattern

**Objective:** turn repeated pain into normalized incident files faster.

**Files:**
- Create: `brain/patterns/incident-promotion.md` or helper script later
- Update: relevant incident files

**Implementation instructions:**
- define threshold for promotion
- define minimum fields required before an incident is considered valid
- link each incident to scripts/evals when possible

**Verification:**
- repeated failures are no longer only present in logs or generated JSON

---

## Phase 4: Work continuity

### Task 4.1: Create a live active-work thread

**Objective:** stop depending on summary compression for current work.

**Files:**
- Create: `brain/active-work/current.md`

**Implementation instructions:**
- record active objective
- record current verified state
- record blockers
- record next deterministic step
- keep it short and update it as work changes

**Verification:**
- a future session can resume from `brain/active-work/current.md` without depending on latent summary recovery

### Task 4.2: Add active-work linting rule

**Objective:** keep active-work files compact and current.

**Files:**
- Create: `brain/scripts/active_work_lint.py`

**Verification:**
- lint fails or warns on missing sections or overgrown snapshots

---

## Phase 5: Resolver control

### Task 5.1: Expand resolver fixtures

**Objective:** make intent routing explicit and testable.

**Files:**
- `brain/resolver.md`
- `brain/evals/resolver-cases.json`

**Implementation instructions:**
- add more real intent families
- add exclusions for overlapping categories
- ensure provider debugging routes to probes before freeform reasoning

**Verification:**
- fixture set covers provider pain, continuity, incident promotion, and filing decisions

### Task 5.2: Add resolver audit helper

**Objective:** find unreachable or overlapping deterministic paths.

**Files:**
- Create: `brain/scripts/resolver_audit.py`

**Verification:**
Run:
`python3 brain/scripts/resolver_audit.py`

Expected:
- detects missing artifacts or ambiguous routes

---

## Phase 6: Doctor runner

### Task 6.1: Add `brain_doctor.py`

**Objective:** one command should run the most important checks.

**Files:**
- Create: `brain/scripts/brain_doctor.py`

**Implementation instructions:**
- run provider probe in dry-run or selected live mode
- run request-dump digest
- run rail loader check
- later: run resolver audit and active-work lint
- emit one compact JSON summary and non-zero exit on critical failures

**Verification:**
Run:
`python3 brain/scripts/brain_doctor.py --dry-run`

Expected:
- single command summary of repo brain health

---

## Phase 7: Skillification loop

### Task 7.1: Promote the first repeated failure into a skill

**Objective:** close the loop between incident, deterministic helper, and procedural memory.

**Candidates:**
- provider debugging workflow
- rail loading validation workflow
- request-dump triage workflow

**Implementation instructions:**
- create or patch a skill outside this repo’s docs as appropriate
- reference the deterministic script and canonical artifacts
- add eval or canary coverage

**Verification:**
- same failure class is harder to repeat because routing and procedure changed

---

## Instructions for future implementation

1. Never start a new feature here by writing broad prose first.
2. Check whether the problem belongs in:
   - `brain/scripts/`
   - `brain/providers/`
   - `brain/incidents/`
   - `brain/active-work/`
   - skills
3. Prefer narrow files over mega-docs.
4. Promote durable truth out of generated reports.
5. Keep the doc suite synchronized when the operating model changes.
6. Verify every change with a real command, dry-run, or artifact.

## References

- [R1] User-provided Garry Tan article in this conversation
- [R2] `/home/agent/hermesoptimizer/brain.md`
- [R3] `/home/agent/hermesoptimizer/brain/README.md`
- [R4] `/home/agent/hermesoptimizer/brain/reports/request-dump-summary.json`
- [R5] https://github.com/NousResearch/hermes-agent
- [R6] https://github.com/stephenschoettler/hermes-lcm
- [R7] https://github.com/plastic-labs/honcho
