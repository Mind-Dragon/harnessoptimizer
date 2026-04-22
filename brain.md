# Brain system for Hermes-style project work

## Executive thesis

A brain that works for our projects should not be a giant memory dump or a vague “agent memory” layer. It should be a compiled system with five distinct layers:

1. Intake and filing
2. Deterministic recall and retrieval
3. Procedure memory via skills
4. Control/eval loops that turn failures into permanent fixes
5. Runtime observability and provider health gates

The attached Garry Tan article is right about the missing piece: most stacks ship primitives, not a practice. The useful pattern is not “give the model more memory.” It is “convert recurring failures into constrained, testable structure.”

For our projects, the right design is:

- thin harness
- fat skills
- small durable memory
- deterministic tools for anything repeatable
- daily evals and routing checks
- provider/runtime canaries before trust
- explicit brain filing rules

The goal is not an omniscient assistant. The goal is an agent stack that gets more disciplined after every miss.

---

## What the session logs say

I inspected the live Hermes session and log corpus, not just the attached text.

Evidence base:

- 3,630 session files in `/home/agent/.hermes/sessions`
- session range: `2026-03-09T13:52:40.871017` through `2026-04-22T20:21:08.890477`
- platforms: 2,501 CLI sessions, 1,123 cron sessions
- 357 request-dump failure artifacts (`229 max_retries_exhausted`, `128 non_retryable_client_error`)

### Primary failure patterns from logs

#### 1. Context summarization/compression is brittle and externally blocked

From live logs:

- 72 occurrences of `Failed to generate context summary: <html>` in `agent.log` / `errors.log`
- repeated Cloudflare challenge HTML payloads from `chatgpt.com/backend-api/codex`
- auxiliary compression explicitly routed there at least 3 times

Meaning:

The system is over-dependent on opportunistic context summarization through a flaky external lane. When that lane gets challenged, the brain loses its ability to compact context and starts degrading.

Design implication:

The brain cannot depend on one-shot latent summarization as a core mechanism. Summaries should be a convenience layer, not the spine. The spine must be deterministic artifacts:

- structured notes
- tested skills
- machine-readable reports
- typed memories
- project-local filings

#### 2. Provider routing is unstable enough to poison cognition

Across request dumps:

- `https://api.minimax.io/v1/chat/completions` produced 229 `max_retries_exhausted`
- `https://api.kimi.com/coding/chat/completions` produced 23 `non_retryable_client_error`
- Kimi-family and OpenRouter Kimi variants repeatedly hit non-retryable failures
- there are also non-trivial failure pockets on Crof and DashScope lanes

Meaning:

A brain system that assumes “the model will be there when needed” is already wrong here. Provider instability is not an edge case. It is part of the operating environment.

Design implication:

Provider health must be part of the brain architecture:

- active lane registry
- canary probes
- fail-open vs fail-closed policy per task type
- quarantine bad lanes automatically
- prefer deterministic execution when providers are flaky

The system should know the difference between:

- memory/retrieval work
- heavy reasoning work
- compression/summarization work
- eval/judge work

Each of those can route to different providers or skip model use entirely.

#### 3. Governance/prefill wiring is drifting

Observed repeatedly:

- 10 occurrences of `Failed to load prefill messages from /home/agent/clawd/SOUL.md: Expecting value: line 1 column 1 (char 0)`

Meaning:

The system’s own behavioral rails are being loaded through a path that appears to expect JSON or another structured format, while the source document is markdown/plaintext. That is a contract mismatch inside the control plane.

Design implication:

The brain system needs typed rails and rail-loading tests.

Not just:

- `SOUL.md`
- `HEARTBEAT.md`

Also:

- loader contract tests
- format expectations
- “rail loaded successfully” canary
- fail-closed behavior when rails are unavailable

If identity/governance documents can silently fail to load, the brain is not compiled. It is aspirational.

#### 4. The system already uses tools heavily, which is good

In the focused session set I analyzed:

- 10,782 terminal tool calls
- 3,669 read_file calls
- 1,362 search_files calls
- 681 execute_code calls
- 352 skill_view calls
- 156 skill_manage calls
- 118 delegate_task calls

Meaning:

This stack already behaves more like an instrumented worker than a chatbot. That is a strength. The missing piece is not tool access. It is converting tool outcomes into durable project memory and testable procedures.

#### 5. Session compaction gaps are already visible

Focused session analysis showed:

- 97 hits of `Summary generation was unavailable`
- 167 non-zero terminal result hits in the inspected focus set

Meaning:

When summaries fail, the session falls back to fragile handoff text like “summary generation was unavailable.” That is better than hallucinating, but it means continuity is still too dependent on latent compression.

Design implication:

The brain needs explicit state snapshots for ongoing work, not just conversation summaries.

---

## What the article gets right

The attached article’s core idea is sound:

“Every failure becomes a skill. Every skill has tests. Every eval runs daily.”

That is the right center of gravity.

The strongest ideas in it are:

1. Separate latent work from deterministic work.
2. Force deterministic tasks into scripts/tools.
3. Treat a skill as a contract, not a vibe.
4. Add resolver triggers and resolver evals.
5. Run ongoing checks so the system rots slower than it learns.

That is exactly the missing layer between:

- raw memory stores
- raw eval tooling
- raw agent execution

What needs adaptation for our projects is scope and rigor. We should not copy “GBrain” as branding or doctrine whole. We should compile the useful operating model into our own project architecture.

---

## The brain system we actually want

## Layer 0. Project truth model

Before memory, define what is allowed to become durable truth.

Each project should have a compact truth schema:

- `people/`
- `projects/`
- `systems/`
- `providers/`
- `skills/`
- `incidents/`
- `decisions/`
- `patterns/`
- `artifacts/`
- `active-work/`

Each entry should answer one question only.

Examples:

- person note: stable facts about a human collaborator
- provider note: live endpoint, auth mode, known failure modes, canary command
- incident note: symptom, root cause, structural fix, eval added
- decision note: why we chose Minimax for X but not for compression
- active-work note: current task state, checkpoints, next deterministic step

This keeps the brain from becoming one undifferentiated markdown swamp.

## Layer 1. Filing rules

The article is right that filing rules matter. For us they matter even more because we work across multiple projects, providers, and operational surfaces.

The filing rules should be deterministic and enforced by tests.

Examples:

- provider failures go to `providers/<provider>.md` and `incidents/`
- reusable procedures go to skills, never to general memory
- temporary task progress goes to `active-work/`, never to durable memory
- user preferences go to user memory, not project brain
- environment truths go to system/project notes
- postmortems create or patch skills if recurrence is possible

The worst failure mode is mixed ontology: the same fact stored in memory, session text, a scratch note, and a skill. That creates split-brain retrieval.

## Layer 2. Deterministic recall first

Historical lookup, provider inspection, config checks, path discovery, file classification, log bucketing, routing audits, and time math should not happen in latent space if a script can do them.

For our projects, likely deterministic brain primitives include:

- provider canary checks
- session-log bucketing
- path discovery for project roots and vault/env files
- artifact classification and filing
- “what changed since last run?” diff scripts
- routing/resolver audits
- skill reachability audits
- active-work snapshot generation
- issue clustering from logs and request dumps

This is the most important architectural rule:

If a task is repeated and has a stable input/output shape, the brain should compile it into code.

Not because models are bad. Because models are expensive places to do boring work.

## Layer 3. Skill system as procedural memory

A skill should be the unit of operational learning.

For our environment, a real skill is not just a markdown hint. It is a bundle:

1. trigger/intent description
2. contract and boundaries
3. deterministic helper scripts if applicable
4. tests
5. resolver entry
6. resolver eval cases
7. example transcripts or fixtures
8. anti-patterns
9. filing rules for outputs
10. verification commands

This is the “compiled” part of the brain.

A skill should answer:

- when does this fire?
- what exact steps does the agent follow?
- what parts are deterministic?
- what evidence proves it worked?
- where does the output get filed?
- what failure modes does it prevent from recurring?

## Layer 4. Memory system with strict scope

Memory should stay small and boring.

Memory is for:

- user preferences
- stable environment facts
- enduring project conventions
- persistent identity/relationship context

Memory is not for:

- long narratives
- scratch investigation notes
- giant summaries of prior sessions
- temporary task state
- copies of docs that already exist elsewhere

Our logs strongly suggest that relying on summarized conversation context is fragile. So durable continuity should come from structured stores, not swollen prompt memory.

Recommended split:

- user memory: who the user is, preferences, recurring constraints
- project brain: structured markdown/JSON artifacts under project control
- skills: procedures
- session logs: raw evidence
- active-work snapshots: resumable state for current threads

## Layer 5. Control plane and observability

This is where most agent stacks stay weak.

A useful brain must observe its own reliability.

At minimum, track:

- provider success/failure rates
- request dump reasons by provider/model/endpoint
- skill trigger frequency
- resolver misses
- resolver ambiguities
- repeated non-zero terminal outcomes
- summarization failures
- MCP server availability
- time-to-answer for deterministic vs latent paths
- repeated user corrections

The live logs already show enough repeated failure to justify this. Without a control layer, the system forgets operational pain faster than it fixes it.

---

## Proposed compiled architecture

## A. Brain repo layout

For each active project, create a project-local brain surface:

```text
brain/
  README.md
  filing-rules.md
  resolver.md
  active-work/
  decisions/
  incidents/
  patterns/
  providers/
  systems/
  projects/
  people/
  artifacts/
  evals/
  reports/
  scripts/
  fixtures/
```

If one shared operator brain is needed across projects, keep it separate from project-local brains. Do not mix personal/user notes with repo-operational notes.

## B. Brain compiler loop

Turn the article’s “skillify” into a stricter local loop:

1. Observe failure or repeated friction.
2. Classify it:
   - retrieval failure
   - routing failure
   - provider failure
   - tool misuse
   - filing failure
   - hallucination / latent-over-deterministic failure
3. Decide whether it belongs in:
   - code/script
   - skill
   - resolver
   - memory
   - filing rules
   - provider registry
4. Add deterministic helper if possible.
5. Add or patch skill.
6. Add tests/evals.
7. Add filing rule if outputs are persistent.
8. Add canary/monitor if runtime reliability matters.
9. Record incident + structural fix.
10. Re-run relevant smoke tests.

Nothing counts as “learned” until it changes structure.

## C. Resolver system

Resolver should be explicit, versioned, and testable.

It maps intents to:

- skills
- scripts
- project brains
- providers
- required tools

Resolver entries should include:

- intent family
- examples
- exclusions
- precedence
- required environment
- preferred provider lane if a model is needed
- deterministic preflight steps

Example intent families for our work:

- log analysis
- provider debugging
- repo audit
- deployment triage
- browser path repair
- cron maintenance
- incident response
- doc/code reconciliation
- skill creation/patching
- cross-session recall

Resolver evals should test both:

- structural correctness of the mapping
- actual routing behavior by the model

## D. Provider registry

This is mandatory in our environment.

Each provider entry should track:

- base URL
- auth mechanism
- supported models
- known broken endpoints
- last successful probe timestamp
- failure class history
- intended use cases
- fallback order
- cost/latency notes

Given the live corpus, the registry should already flag:

- Minimax chat lane as a repeated retry-exhaustion source
- Kimi coding endpoints as repeated 404/non-retryable sources
- chatgpt.com backend-api/codex as unsafe for required summarization/compression because of Cloudflare challenge risk

This alone would prevent a lot of wasted latent effort.

## E. Active-work snapshots

To reduce dependence on summarization, every substantial task should write or update an active-work snapshot:

- objective
- current repo/path
- what has been verified
- current blockers
- key files touched
- next deterministic step
- last successful test/probe

This is better than hoping compressed conversation state survives model/provider turbulence.

---

## The minimal checklist for a real brain feature

For our stack, a “brain feature” should not ship unless it has these:

1. Contract doc
2. Filing destination
3. Deterministic helper if applicable
4. Unit test or fixture test
5. Integration probe if external dependency exists
6. Resolver entry
7. Resolver eval
8. Observability hook
9. Smoke test
10. Incident/update path when it breaks

That is basically the article’s skillify checklist, extended for provider instability and project filing discipline.

---

## Concrete subsystems to build first

Ordered by leverage.

### 1. Provider health brain

Why first:

The logs show provider/runtime instability is one of the biggest actual failure sources.

Build:

- `brain/providers/*.md`
- `brain/scripts/provider_probe.py`
- `brain/reports/provider-health.json`
- daily or hourly canary cron
- routing policy that avoids unhealthy lanes for critical functions

Definition of done:

- a bad provider gets quarantined automatically or visibly
- summarization/compression does not silently route to blocked lanes
- provider failure counts are queryable historically

### 2. Session-log digestion pipeline

Why:

We already have rich logs, but raw logs are too noisy to become memory by themselves.

Build:

- bucket request dumps by endpoint/model/reason
- detect repeat incidents
- generate `incidents/` candidates
- emit “candidate skill to create” suggestions

Definition of done:

- repeated failures turn into structured incident notes
- log pain becomes build input, not forgotten exhaust

### 3. Resolver registry + eval suite

Why:

A brain without good routing becomes a landfill of capabilities.

Build:

- `brain/resolver.md` or structured resolver file
- intent fixtures
- expected skill/script/provider mappings
- ambiguity checker

Definition of done:

- adding a skill without a resolver entry fails review
- overlapping intent families are caught before runtime

### 4. Active-work state snapshots

Why:

The logs show summarization can disappear. Work continuity needs a deterministic fallback.

Build:

- `brain/active-work/<thread>.md`
- small update command/script
- task-end or compaction-end snapshot rule

Definition of done:

- losing model-side summary does not lose work continuity

### 5. Filing rules and brain lint

Why:

Without filing discipline, knowledge becomes unrecoverable.

Build:

- `brain/filing-rules.md`
- linter to detect wrong destinations or duplicate entities
- duplicate detector for near-identical notes/skills

Definition of done:

- new notes go to one clear place
- duplicate procedures get flagged

---

## How memory, skills, and the brain should divide labor

### Memory

Use for:

- user preferences
- durable environment facts
- stable conventions

### Skills

Use for:

- repeatable procedures
- response patterns to common failure classes
- tool choice discipline
- deterministic-first execution rules

### Brain repo

Use for:

- structured project knowledge
- incidents, decisions, providers, patterns, active work
- evals, reports, fixtures, scripts

### Session logs

Use for:

- raw evidence
- replay/debugging
- failure mining

If a fact appears in all four places, the architecture is wrong.

---

## The central design rules

These are the rules I would compile into the system.

### Rule 1. Deterministic before latent

If code can answer it, the model should not improvise.

### Rule 2. No durable learning without structure change

An apology is not learning. A patched skill, test, resolver entry, or script is learning.

### Rule 3. Retrieval first, summarization second

Never make a summary the only path back to truth.

### Rule 4. Provider health is part of cognition

A broken provider is not only an infra problem. It changes what the agent is capable of knowing reliably right now.

### Rule 5. Every persistent output needs a filing rule

If the system can write it, it must know where it belongs.

### Rule 6. Resolver coverage matters as much as skill quality

A good skill that never routes is dead weight.

### Rule 7. Repeated pain becomes a test or canary

If logs show the same failure class more than once, that is compiler input.

---

## Anti-patterns to avoid

### 1. Giant all-purpose memory blob

This creates expensive prompt stuffing and bad retrieval precision.

### 2. Conversation summaries as the main continuity mechanism

The logs already show this breaks under provider/challenge pressure.

### 3. Untested skill sprawl

This is the exact rot the article is warning about.

### 4. Provider-agnostic routing

Our logs prove providers are not interchangeable in practice.

### 5. Storing procedures in user memory

That pollutes identity memory with operational instructions.

### 6. Manual filing by vibe

That produces dark knowledge nobody can route to later.

---

## Practical implementation plan

Phase 1: Stabilize the substrate

- Build provider registry and canaries
- Stop relying on blocked compression lanes as required infra
- Add rail-loading verification for SOUL/HEARTBEAT prefill
- Add request-dump aggregation report

Phase 2: Compile project memory

- Create project-local brain layout
- Add filing rules
- Add active-work snapshot format
- Add incident and decision templates

Phase 3: Compile procedures

- Convert repeated workflows into skills with deterministic helpers
- Add resolver entries and resolver evals
- Add reachability and duplicate checks

Phase 4: Continuous verification

- Daily provider health check
- Daily skill reachability check
- Daily resolver evals
- Daily brain lint/duplicate scan
- Weekly session-log digestion and incident promotion

Phase 5: Human-legible control surface

- dashboard/report view for provider failures, resolver misses, top incidents, unfiled outputs
- “what changed in the brain this week?” digest
- “what repeated failure has not yet been skillified?” report

---

## What “compile a brain” really means here

It means converting the stack from:

- memory as hope
- evals as optional
- skills as notes
- logs as exhaust
- providers as magic

into:

- memory as narrow identity/context store
- skills as executable contracts
- logs as compiler input
- providers as monitored dependencies
- filing as a deterministic system
- active work as resumable state
- evals as daily maintenance

That is the difference between an agent that sometimes remembers and a system that gets harder to break.

---

## Recommended first artifacts for this repo

If I were implementing this next, I would create these first:

- `/home/agent/hermesagent/brain/README.md`
- `/home/agent/hermesagent/brain/filing-rules.md`
- `/home/agent/hermesagent/brain/resolver.md`
- `/home/agent/hermesagent/brain/providers/`
- `/home/agent/hermesagent/brain/incidents/`
- `/home/agent/hermesagent/brain/active-work/`
- `/home/agent/hermesagent/brain/scripts/provider_probe.py`
- `/home/agent/hermesagent/brain/scripts/request_dump_digest.py`
- `/home/agent/hermesagent/brain/evals/resolver-cases.json`
- `/home/agent/hermesagent/brain/evals/provider-canaries.json`

The attached article gives the right habit. The logs give the real constraints. The compiled brain for our projects should be built around those constraints, not around idealized agent behavior.

## Bottom line

The system does not need “more memory.” It needs a better compiler from failure into structure.

The live evidence says our weakest points are:

- brittle summarization/compression
- unstable provider lanes
- rail-loading drift
- too much continuity tied to latent summaries

So the right brain system is:

- deterministic-first
- provider-aware
- resolver-tested
- filing-disciplined
- incident-driven
- skill-compiled
- small-memory, big-artifact

That will work much better for our projects than a larger prompt, a fancier vector store, or another vague memory layer.