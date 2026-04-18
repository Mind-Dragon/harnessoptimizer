# Hermes Dreaming — Memory Consolidation Plan

**Status:** Draft. Not started.

## What this is

A background memory consolidation system for Hermes Agent that mirrors the biological sleep metaphor OpenClaw uses, adapted to Hermes's memory architecture.

OpenClaw dreaming (reviewed at `~/openclaw/`) has three phases (light, deep, REM), a cron-triggered sweep, weighted promotion scoring, and a dream diary. Hermes doesn't have OpenClaw's internal plugin SDK or a built-in cron runtime, but it has four memory stores with clear tiering (documented in the `memory-hygiene` skill) and the `cronjob` tool for scheduling.

The goal: make Hermes autonomously prune, compact, merge, and promote its own memories during idle time so the next session starts with a cleaner, higher-signal context.

## Why Hermes needs this

Without dreaming:
- Supermemory accumulates stale entries (50+ observed) that dilute recall quality
- Injected memory slowly fills with re-derivable facts (61% observed, target < 50%)
- User profile entries get verbose and don't get compacted
- No automated decay -- the memory-hygiene skill exists but requires a human to trigger it
- Skills duplicate supermemory content without automatic reconciliation

With dreaming:
- A cron job runs the hygiene protocol autonomously every 6 hours
- Short-term recall signals accumulate during active sessions (search queries, tool usage)
- A promotion pass identifies high-signal supermemory candidates for graduation to injected memory
- A compaction pass shortens verbose entries
- A pruning pass removes stale, duplicated, and expired entries
- A dream diary in `~/.hermes/dreams/` records what happened for human audit

## Architecture

```
hermes cronjob (every 6h, configurable)
  |
  v
dreaming skill (loaded on demand)
  |
  +-- Phase 1: INGEST (light sleep)
  |     Read session logs, recall signals, recent memory operations
  |     Write staging data to ~/.hermes/dreams/staging.json
  |
  +-- Phase 2: PRUNE (light sleep)
  |     Apply decay rules from memory-hygiene skill
  |     Forget stale supermemory entries
  |     Remove redundant injected memory entries
  |
  +-- Phase 3: COMPACT (deep sleep)
  |     Merge overlapping injected memory entries
  |     Shorten verbose entries
  |     Graduate high-signal supermemory to user profile
  |     Demote low-signal user profile entries to supermemory
  |
  +-- Phase 4: REFLECT (REM sleep)
  |     Scan session_search for recurring themes
  |     Identify facts referenced across multiple sessions
  |     Score candidates for promotion
  |
  +-- Phase 5: REPORT
        Write ~/.hermes/dreams/YYYY-MM-DD.md
        Update ~/.hermes/dreams/state.json with sweep metadata
```

## Memory store mapping

Hermes has four stores. The dreaming system touches all of them:

| Store | Tool | Dreaming action |
|-------|------|-----------------|
| Injected memory | `memory(target='memory')` | Compact, merge, remove re-derivable facts |
| User profile | `memory(target='user')` | Graduate preferences, compact verbose entries |
| Supermemory | `supermemory_*` | Prune stale/skill-duplicate entries, store new facts |
| Skills | `skill_manage` | Never modified by dreaming -- skills are manual |

## Phase detail

### Phase 1: INGEST (light sleep)

**What it reads:**
- `supermemory_profile()` -- current entry count, metadata
- `supermemory_search()` with broad queries to catalog what's stored
- Recent session data via `session_search()` (last 7 days, broad query)
- Current injected memory content (from context injection)

**What it produces:**
- `~/.hermes/dreams/staging.json` -- a JSON file with:
  - `supermemory_entries`: array of `{id, content_preview, age_days, topic_tags}`
  - `session_themes`: array of `{theme, session_count, last_seen}`
  - `injected_memory_usage_pct`: number
  - `user_profile_usage_pct`: number
  - `sweep_timestamp`: ISO string

**Decay scoring** (applied to each supermemory entry):
- `age_days < 14` -> no age penalty
- `age_days 14-30` -> -0.1 per week
- `age_days > 30` -> -0.3 plus staleness check
- References specific version/PR/build -> automatic -0.5 if age > 14 days
- Duplicates a known skill -> automatic -1.0 (prune candidate)

### Phase 2: PRUNE (light sleep)

**Rules** (from memory-hygiene skill):
1. Forget supermemory entries that duplicate loaded skill content
2. Forget supermemory entries about specific versions, PRs, or resolved bugs older than 14 days
3. Forget supermemory entries about transient model/provider choices older than 30 days
4. Remove injected memory entries that are re-derivable from codebase inspection
5. Never remove: user preferences, credential locations, environment topology, architectural decisions

**Implementation:**
- Load skill list via `skills_list()`
- For each skill, `skill_view(name)` and extract key facts
- Cross-reference supermemory entries against skill content
- Batch-forget pruned entries (collect IDs first, then forget in groups of 10)

### Phase 3: COMPACT (deep sleep)

**Compaction patterns for injected memory:**
- "X is located at /path/to/file" -> "X: /path/to/file"
- "For X-related identity fields, treat variants as email" -> "X identity: email for all variants"
- Remove parenthetical clarifications
- Merge two entries about the same system into one shorter entry
- Replace verbose descriptions with abbreviated forms

**Graduation** (supermemory -> user profile):
- Scan supermemory for entries matching user preference patterns
- If entry is a preference/steering rule and user profile < 85%, add to user profile
- Forget the supermemory source entry

**Demotion** (user profile -> supermemory):
- If user profile > 85%, find the lowest-priority entry
- Store it in supermemory, remove from user profile

### Phase 4: REFLECT (REM sleep)

**What it does:**
- Run `session_search()` with broad queries to find recurring topics
- Cross-reference topics with current memory stores
- Identify facts that appear in 3+ sessions but aren't in any memory store
- Score these as promotion candidates

**Scoring** (adapted from OpenClaw's 6-signal model):

| Signal | Weight | Hermes equivalent |
|--------|--------|-------------------|
| Frequency | 0.24 | How many sessions mentioned it |
| Relevance | 0.30 | Was it central to the task or incidental |
| Diversity | 0.15 | Distinct session contexts (different projects) |
| Recency | 0.15 | Exponential decay, 14-day half-life |
| Consolidation | 0.10 | Multi-week recurrence |
| Conceptual | 0.06 | Tags the user keeps searching for |

**Promotion thresholds:**
- `score >= 0.8` and `session_count >= 3` and `unique_contexts >= 2` -> candidate for supermemory
- `score >= 0.9` and is a user preference -> candidate for user profile graduation

### Phase 5: REPORT

Write a markdown file at `~/.hermes/dreams/YYYY-MM-DD.md` with:

```markdown
# Dream Report — YYYY-MM-DD HH:MM TZ

## Summary
- Supermemory: X entries before, Y entries after (Z pruned, W promoted)
- Injected memory: X% before, Y% after
- User profile: X% before, Y% after

## Pruned
- [list of forgotten entries with reason]

## Compacted
- [list of merged/shortened entries]

## Promoted
- [list of new entries added to supermemory or user profile]

## Candidates (not yet promoted)
- [list of facts seen in 3+ sessions not yet stored]

## Errors
- [any failures during the sweep]
```

Update `~/.hermes/dreams/state.json`:
```json
{
  "last_sweep": "ISO timestamp",
  "last_sweep_ok": true,
  "sweep_count": 42,
  "total_pruned": 150,
  "total_compacted": 30,
  "total_promoted": 12,
  "next_sweep": "ISO timestamp"
}
```

## Implementation plan

### Step 1: Create the dreaming skill

File: `~/.hermes/skills/dogfood/dreaming/SKILL.md`

The skill defines:
- When dreaming runs (trigger conditions)
- What each phase does (step by step)
- What tools to call and in what order
- How to handle errors (continue on failure, log to report)
- How to write the report

This is a skill, not a Python module, because Hermes dreaming runs as a cron-triggered Hermes session -- the same agent, same tools, just a different prompt. The skill IS the code.

### Step 2: Create the dreaming script

File: `~/.hermes/scripts/dreaming.py`

A lightweight Python script that:
- Reads `~/.hermes/dreams/state.json` to check if a sweep is due
- Reads supermemory profile and counts
- Outputs a JSON summary that the cron prompt can use as context

This script runs before the agent prompt (cron `script` field) and injects its stdout into the prompt. The agent then follows the skill instructions.

### Step 3: Create the cron job

Using Hermes's `cronjob` tool:
- Schedule: `0 */6 * * *` (every 6 hours, adjustable)
- Script: `~/.hermes/scripts/dreaming.py`
- Prompt: references the dreaming skill
- Deliver: local (no chat delivery -- dreaming is autonomous)

### Step 4: Create the directory structure

```
~/.hermes/dreams/
  state.json          -- sweep metadata
  YYYY-MM-DD.md       -- dream reports (one per sweep)
  staging.json        -- current sweep staging data (overwritten each sweep)
```

### Step 5: Create the memory-hygiene skill update

Patch the existing `memory-hygiene` skill to reference dreaming as the automated execution path. Add a section:

```
## Automated execution
Dreaming runs the hygiene protocol every 6 hours via cron.
If dreaming is enabled, manual hygiene runs are still safe but redundant.
Check ~/.hermes/dreams/state.json for last sweep status.
```

## Key differences from OpenClaw dreaming

| Aspect | OpenClaw | Hermes |
|--------|----------|--------|
| Implementation | TypeScript plugin inside the gateway | Cron-triggered Hermes session using skills + scripts |
| Memory backend | Custom QMD store, daily MD files, recall JSON | supermemory (vector DB), injected memory (KV), skills (filesystem) |
| Phase execution | Hooked into heartbeat system events | Cron schedule, no heartbeat needed |
| Narrative | Subagent generates poetic diary entries | Markdown report with structured sections, no prose generation |
| Promotion target | MEMORY.md (long-term memory file) | Injected memory store and user profile store |
| Recall tracking | Built into memory-core, tracks every search | session_search for cross-session patterns, no real-time recall tracking |
| Locking | File lock with PID, stale detection | No locking needed -- single cron sweep, no concurrency |

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Dreaming prunes a useful entry | Dream reports list everything pruned with reason. Manual restore via `supermemory_store`. State.json tracks sweep history. |
| Dreaming fills user profile to capacity | Compaction phase runs before graduation. If profile > 85% after compaction, demote lowest-priority entry. Hard cap: never add if > 90%. |
| Cron job fails silently | `state.json` records `last_sweep_ok`. Hermes cron delivers to local. Check `state.json` periodically. |
| Dreaming runs during active session | No locking issue -- supermemory and memory tools are idempotent. Worst case: a duplicate prune attempt on an already-forgotten entry, which is a no-op. |
| Session search returns too much data | Broad queries return summaries, not full transcripts. Limit to 5 sessions per query. Cap total sessions scanned at 20. |
| Staging.json grows large | Overwritten each sweep. No accumulation. |

## Configuration

Dreaming configuration lives in `~/.hermes/config.yaml` under a `dreaming` key:

```yaml
dreaming:
  enabled: true
  schedule: "0 */6 * * *"    # cron expression
  timezone: "UTC"             # optional, defaults to UTC
  phases:
    ingest: true
    prune: true
    compact: true
    reflect: true
    report: true
  thresholds:
    prune_age_days: 14        # entries older than this are eligible for pruning
    promotion_score: 0.8      # minimum score for promotion candidates
    promotion_sessions: 3     # minimum sessions a fact must appear in
    max_profile_pct: 85       # don't graduate if profile above this %
```

If `dreaming.enabled` is false or missing, the cron job still runs but exits immediately after reading config.

## Success criteria

A dreaming system is working when:
1. A cron sweep runs every 6 hours without manual intervention
2. Supermemory stays under 25 entries after each sweep
3. Injected memory stays under 50% after each sweep
4. User profile stays under 85% after each sweep
5. Every sweep produces a dated report in `~/.hermes/dreams/`
6. `state.json` accurately reflects last sweep status
7. Pruned entries can be identified and restored from the report
8. No session-visible side effects -- dreaming doesn't interrupt active work

## File inventory

| File | Purpose | Created in step |
|------|---------|-----------------|
| `~/.hermes/skills/dogfood/dreaming/SKILL.md` | Dreaming skill definition | Step 1 |
| `~/.hermes/scripts/dreaming.py` | Pre-sweep data collection script | Step 2 |
| `~/.hermes/dreams/state.json` | Sweep metadata | Step 4 |
| `~/.hermes/dreams/YYYY-MM-DD.md` | Dream reports | Step 4 |
| `~/.hermes/dreams/staging.json` | Transient staging data | Step 4 |
| `~/.hermes/config.yaml` (dreaming section) | Configuration | Step 5 |

## Resolved design questions

### 1. Recall tracking: Parse session transcripts first, add log later if needed

OpenClaw gets real recall data because it owns the entire memory stack. Hermes doesn't intercept its own tool calls.

Approach: the dreaming script reads `~/.hermes/sessions/` and scans recent session transcripts for `supermemory_search` tool calls. Tool call arguments include the query; responses include result counts. Parse those out, aggregate by query pattern, produce a recall frequency map. Zero instrumentation, no runtime changes.

This is post-hoc analysis. It misses searches from the currently-running session. Acceptable -- dreaming runs on a 6-hour cycle, so at most 6 hours of data are lost.

Fallback: if transcript parsing proves unreliable (format changes, truncation), add a lightweight append-only log at `~/.hermes/dreams/recall-log.jsonl` where each line is `{"ts": "...", "query": "...", "hit_count": N}`. But start with transcript parsing.

### 2. Narrative: Structured report only, no prose

OpenClaw's narrative diary exists because it has a Dreams UI tab for human browsing. Hermes has no equivalent UI. Nobody scrolls through poetic diary entries in a terminal.

The structured markdown report is the right format: machine-parseable, diffable, fast to scan. The summary section should be written to read well as a standalone document (not prose, not a bare table -- something scannable in 10 seconds).

If a narrative layer is ever wanted, add it as an optional phase behind a config flag later. Don't burn tokens on output nobody reads.

### 3. Concurrency: Not a real problem, no guards needed

Hermes is single-user. The cron job fires into its own isolated session, not shared with an active conversation.

The only scenario: you're mid-conversation when cron fires. Dreaming reads stores, prunes something, writes report. Your next turn sees updated stores. This is harmless and is exactly what dreaming is supposed to do.

No locks, no coordination, no mutex. If it ever becomes a problem (unlikely), add a timestamp check in the script: skip if `state.json` shows a sweep started in the last 10 minutes.

### 4. Skill + script, not a standalone module

The module approach is faster and cheaper (no LLM tokens) but can't call MCP tools (`memory`, `session_search`, `skill_view`, `skills_list`) without reimplementing them as API calls. That's exactly the extra abstraction the project's minimal-first principle warns against.

Skill + script uses the tools Hermes already has:
- Pre-sweep script (`dreaming.py`) does cheap data collection (read files, count entries, parse state)
- Agent prompt follows the skill to call `supermemory_forget`, `memory(action='replace')`, etc. via real MCP tools

Advantages:
- Works with existing tool surface, no reimplementation
- Auditable (skill is readable, report shows what happened)
- Debuggable (run the skill manually in any session)
- Stays in the Hermes paradigm

Token cost: a sweep that prunes 10 entries, compacts 3, and writes a report costs ~2,000-4,000 tokens. At 4 sweeps/day, under $0.10/day. Increase interval to 12h or daily if cost matters.
