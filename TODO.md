# Hermes Optimizer /todo + /devdo Implementation TODO

## Goal
Build an oh-my-opencode style two-command workflow where `/todo` owns planning and `/devdo` owns execution, with `/devdo` using Hermes-grade orchestration to fan out 10+ subagents when the task graph allows it.

## Decisions already made
- Canonical execution command: `/devdo`
- Backward-compatible alias during migration: `/dodev`
- Canonical workflow state lives in repo-local disk state: `.hermes/workflows/<workflow_id>/`
- Shared schema uses separate files for intent and execution:
  - `plan.yaml` for the frozen plan
  - `run.yaml` for live execution state
- Guard behavior defaults to hard-block on missing or invalid state
- Auto-repair is allowed only for reversible drift with explicit logging
- Swarm execution is task-graph-driven, not a fixed linear loop
- `/todo` may re-plan; `/devdo` may only re-plan when blocked, invalid, or contradicted by live evidence

## Workstream 1: Define the workflow contract

- [ ] Create the workflow schema module
  - `src/hermesoptimizer/workflow/schema.py`
  - define `WorkflowPlan`, `WorkflowRun`, `WorkflowTask`, `WorkflowCheckpoint`, and `WorkflowBlocker`
  - include schema versioning so future migrations are explicit
- [ ] Define the plan packet fields
  - objective
  - scope
  - non-goals
  - acceptance criteria
  - test plan
  - risks
  - execution hints
  - next action for `/devdo`
- [ ] Define the run packet fields
  - current status
  - active task(s)
  - owner
  - checkpoint history
  - guard state
  - blocker history
  - artifact refs
- [ ] Define the task graph fields
  - task_id
  - parent_id
  - dependencies
  - role
  - expected artifact
  - exit criteria
  - retry policy
  - budget hints
  - status
- [ ] Decide the canonical on-disk layout
  - `.hermes/workflows/<workflow_id>/plan.yaml`
  - `.hermes/workflows/<workflow_id>/run.yaml`
  - `.hermes/workflows/<workflow_id>/tasks/`
  - `.hermes/workflows/<workflow_id>/checkpoints/`
  - `.hermes/workflows/<workflow_id>/artifacts/`

## Workstream 2: Add persistence and loading

- [ ] Create the workflow store module
  - `src/hermesoptimizer/workflow/store.py`
  - load, save, list, and validate workflow state
- [ ] Add deterministic serialization helpers
  - stable YAML/JSON output
  - schema version preserved on round-trip
- [ ] Add plan locking behavior
  - `/todo` writes the plan file
  - `/devdo` reads the frozen plan without mutating intent unless blocked
- [ ] Add checkpoint persistence helpers
  - append checkpoint records without rewriting history
  - keep last-clean-checkpoint pointer separate from full history
- [ ] Add artifact reference helpers
  - record where each subagent wrote its output
  - keep task-specific artifacts isolated
- [ ] Add unit tests for round-trip persistence
  - plan save/load
  - run save/load
  - task graph save/load
  - checkpoint append semantics

## Workstream 3: Wire the slash commands

- [ ] Create the `/todo` command module
  - `src/hermesoptimizer/commands/todo.py`
  - read current workflow state if it exists
  - create a new plan if none exists
  - update plan content without executing work
- [ ] Create the `/devdo` command module
  - `src/hermesoptimizer/commands/devdo.py`
  - load the current plan
  - validate state through the guard
  - build the execution graph
  - dispatch work through the orchestrator
- [ ] Add alias support for `/dodev`
  - route `/dodev` to `/devdo`
  - keep aliasing explicit and testable
- [ ] Wire commands into the CLI entrypoint
  - `src/hermesoptimizer/__main__.py`
  - or the project’s existing command entrypoint if that is the real integration point
- [ ] Add command dispatch tests
  - `/todo` creates or updates only the plan
  - `/devdo` consumes an existing plan and does not reinitialize it
  - `/dodev` maps to `/devdo`

## Workstream 4: Build the runtime guard

- [ ] Create the guard module
  - `src/hermesoptimizer/workflow/guard.py`
  - validate command mode, workflow phase, plan version, and live state
- [ ] Add preflight checks before `/devdo` starts
  - plan exists
  - plan is valid
  - run state matches plan version
  - no unresolved guard violation is present
- [ ] Add boundary checks during execution
  - before writes
  - before marking a task complete
  - before phase transitions
  - before large fan-out dispatches
- [ ] Add drift repair behavior
  - restore correct mode when safe
  - reload state from disk when the run pointer is stale
  - block when repair is not safe
- [ ] Add guard logging
  - decision
  - reason
  - recovery action
  - block reason when repair fails
- [ ] Add guard tests
  - missing plan is blocked
  - stale run version is blocked or repaired as intended
  - invalid phase transitions are blocked
  - safe repair succeeds and logs the action

## Workstream 5: Build Hermes-grade execution orchestration

- [ ] Create the scheduler module
  - `src/hermesoptimizer/workflow/scheduler.py`
  - convert plan items into a task DAG
  - choose execution order from dependencies
  - compute independent batches for parallel fan-out
- [ ] Define role pools for subagents
  - planner / researcher
  - implementer
  - test writer
  - reviewer
  - verifier
  - integration checker
  - sentinel / guardrail checker
- [ ] Add batch sizing logic
  - scale from small batches to 10+ workers when the task graph allows it
  - avoid spawning redundant workers for dependent tasks
  - keep at least one orchestrator in control of shared state
- [ ] Add task-to-role routing rules
  - research tasks go to research agents
  - implementation tasks go to implementers
  - tests go to test writers
  - review tasks go to reviewers
  - smoke checks go to verifiers
- [ ] Add checkpoint emission after every meaningful milestone
  - graph built
  - batch dispatched
  - batch completed
  - task blocked
  - task verified
  - phase completed
- [ ] Add resume behavior from the last clean checkpoint
  - restore the task graph
  - skip completed tasks
  - re-open only tasks that are blocked or stale
- [ ] Add execution tests
  - independent tasks fan out in parallel
  - dependent tasks stay serialized
  - resume picks up from the last clean checkpoint
  - 10+ worker batches are possible for sufficiently wide graphs

## Workstream 6: Make `/todo` smarter and more opinionated

- [ ] Add plan-shaping rules to `/todo`
  - force objective, scope, non-goals, risks, and acceptance criteria
  - require a next action that can be executed by `/devdo`
- [ ] Add extended-thinking behavior to `/todo`
  - ask for missing constraints before freezing the plan
  - resolve contradictions before execution begins
- [ ] Add plan quality checks
  - each task is small enough to be delegated
  - each task has a verification step
  - each task has a concrete artifact or proof
- [ ] Add blocked-plan handling
  - if the plan is incomplete, mark it blocked rather than guessing
  - surface the exact missing input
- [ ] Add `/todo` tests
  - plan creation from scratch
  - plan update without execution
  - blocked plan output when required fields are missing

## Workstream 7: Make `/devdo` aggressively autonomous

- [ ] Add mandatory delegation rules for non-trivial work
  - every non-trivial task must be dispatched to a fresh subagent
  - the controller coordinates, validates, and integrates only
- [ ] Add two-stage review for each implemented task
  - spec compliance review
  - code-quality / regression review
- [ ] Add parallel work splitting for independent tasks
  - research branches
  - implementation branches
  - review branches
  - verification branches
- [ ] Add progress output after each meaningful step
  - what started
  - what finished
  - what blocked
  - what checkpoint was written
- [ ] Add resume and recovery flow
  - continue from the last clean checkpoint
  - preserve successful branches when one branch blocks
- [ ] Add `/devdo` tests
  - does not overwrite the plan
  - dispatches multiple subagents for wide tasks
  - continues unblocked work when one task blocks
  - preserves progress between checkpoints

## Workstream 8: Add UX that feels like a real two-step workflow

- [ ] Define the `/todo` handoff format
  - objective
  - scope
  - non-goals
  - acceptance criteria
  - test plan
  - risks
  - next action for `/devdo`
- [ ] Define the `/devdo` startup format
  - plan echo
  - constraints
  - execution strategy
  - first dispatch wave
  - checkpoint policy
- [ ] Add explicit examples for
  - normal flow
  - blocked flow
  - resume flow
  - alias flow (`/dodev` -> `/devdo`)
- [ ] Add a short operator guide
  - when to use `/todo`
  - when to use `/devdo`
  - how to read checkpoints
  - how to recover from a blocked run

## Workstream 9: Update docs and source-of-truth files

- [ ] Update `GUIDELINE.md`
  - describe the `/todo` and `/devdo` contract
  - describe the guard and drift rules
  - describe how deep-agent execution should behave
- [ ] Update `ARCHITECTURE.md`
  - add the workflow state layout
  - add the scheduler / orchestrator shape
  - add the alias migration path
- [ ] Add a dedicated workflow doc
  - `docs/WORKFLOW.md` or `docs/todo-devdo.md`
  - include examples and operator notes
- [ ] Keep docs aligned with the implementation
  - if the command contract changes, update docs in the same pass

## Workstream 10: Validate the whole cycle

- [ ] Add a schema validation test suite
- [ ] Add command behavior tests for `/todo`, `/devdo`, and `/dodev`
- [ ] Add runtime guard failure and recovery tests
- [ ] Add checkpoint/resume tests
- [ ] Add swarm fan-out tests with wide task graphs
- [ ] Add a full smoke test for the slash-command cycle
  - create plan
  - execute a small task graph
  - checkpoint
  - interrupt and resume
  - verify final audit
- [ ] Run one end-to-end dry run against a realistic sample workflow
  - prove the plan is frozen
  - prove `/devdo` consumes it
  - prove parallel dispatch works
  - prove resume works

## Recommended build order
1. Schema and storage
2. Command wiring
3. Runtime guard
4. Scheduler and swarm orchestration
5. Resume and checkpointing
6. UX polish
7. Tests
8. Docs

## Open questions to close during implementation
- Which module should own CLI parsing if the current entrypoint changes?
- Should task graphs be stored as one file or one file per task?
- How many worker roles are actually needed in the first pass?
- What is the smallest meaningful smoke test that still proves parallel execution and resume?

## Definition of done
- `/todo` produces or updates a frozen, structured plan
- `/devdo` consumes that plan and executes from it
- `/dodev` remains a working alias during migration
- the guard blocks invalid state and repairs safe drift
- the scheduler can fan out into large parallel batches
- checkpoints and resume work
- tests prove the whole cycle
- docs describe the workflow clearly enough that an operator can use it without guessing
