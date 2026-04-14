# Hermes Optimizer — Implementation Plan

**Status:** Draft. Awaiting confirmation before execution.

---

## What it is

Hermes Optimizer is a local routing-and-analysis tool that:
1. Scans Hermes session logs and runtime logs for failures, block conditions, and congestion
2. Scrapes external catalogs (Hugging Face, ModelScope) for provider/model/endpoint metadata
3. Routes scraped content through a small local model that classifies and labels records without editing
4. Validates and normalizes records into a canonical catalog
5. Writes SQLite + JSON + Markdown outputs

It runs two ways:
- **Inside Hermes**: reads active session context and current config
- **Outside Hermes**: standalone CLI or cron job with explicit paths

---

## Install directory

```
~/hermesoptimizer/
```

All persistent output goes here, never `/tmp`.

---

## Canonical record schema

Every catalog entry is a tuple:

```json
{
  "provider":    "string",
  "model":       "string",
  "base_url":    "string",
  "auth_type":   "bearer|api_key|oauth|jwt",
  "auth_key":    "string (env var name, not the value)",
  "lane":        "coding|compression|web-extract|research|auxiliary",
  "region":      "string or null",
  "capabilities":["text","vision","reasoning","function_calling"],
  "context_window": 0,
  "source":      "huggingface|modelscope|manual|hermes-log",
  "confidence":  "high|medium|low",
  "raw_text":    "string (original snippet)"
}
```

The router model produces this tuple. The validator checks it. Nothing is stored that doesn't match the schema.

---

## Directory layout

```
~/hermesoptimizer/
  PLAN.md                          this file
  README.md                        usage docs
  catalog.db                       SQLite source of truth
  src/
    __init__.py
    catalog.py                     SQLite schema + CRUD
    sources/
      __init__.py
      hermes_logs.py               Hermes log adapter
      hermes_sessions.py           Hermes session adapter
      hf_catalog.py                Hugging Face catalog scraper
      modelscope_catalog.py         ModelScope catalog scraper
    scrape/
      __init__.py
      exa_scraper.py               Exa collector
      firecrawl_scraper.py         Firecrawl collector
      merge.py                     Merge raw scraped content
    route/
      __init__.py
      router.py                    OpenAI-compatible router model
      prompts.py                   router system/user prompts
    validate/
      __init__.py
      normalizer.py                alias + schema validator
      lanes.py                     lane assignment logic
    report/
      __init__.py
      issues.py                    group findings into buckets
      markdown.py                  Markdown report writer
      json_export.py               JSON report writer
    run_hermes_mode.py             inside-Hermes entry point
    run_standalone.py               outside-Hermes CLI entry point
  tests/
    __init__.py
    test_catalog.py
    test_sources.py
    test_router.py
    test_validator.py
    test_reports.py
  scripts/
    run.sh                         cron-friendly wrapper
    diff-since.sh                  optional: scan since last run

---

## Architecture

```
hermes-logs/         hermes-sessions/         HF/ModelScope pages
sessions/            logs/
     |                    |                    |
     v                    v                    v
hermes_logs.py     hermes_sessions.py     hf_catalog.py + modelscope_catalog.py
     |                    |                    |
     +--------------------+--------------------+
                          v
                   scrape/merge.py
                          |
                          v
                   exa_scraper.py + firecrawl_scraper.py
                          |
                          v
                   route/router.py   ← small OAI-compatible model
                          |           (classifies + labels only, no edits)
                          v
                   validate/normalizer.py + lanes.py
                          |
                          v
                   catalog.py   →  catalog.db (SQLite)
                          |
                          v
                   report/issues.py + markdown.py + json_export.py
                          |
                          v
                   reports/YYYY-MM-DD-*.{md,json}
```

**Rule: the router model never edits. It only labels, classifies, and routes.**

---

## Module responsibilities

### catalog.py

SQLite schema:

```sql
CREATE TABLE records (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  provider    TEXT NOT NULL,
  model       TEXT NOT NULL,
  base_url    TEXT NOT NULL,
  auth_type   TEXT NOT NULL,
  auth_key    TEXT NOT NULL,
  lane        TEXT,
  region      TEXT,
  capabilities TEXT,
  context_window INTEGER DEFAULT 0,
  source      TEXT NOT NULL,
  confidence  TEXT NOT NULL,
  raw_text    TEXT,
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(provider, model, base_url, lane)
);

CREATE TABLE findings (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  file_path   TEXT,
  line_num    INTEGER,
  category    TEXT NOT NULL,
  severity    TEXT NOT NULL,
  kind        TEXT,
  fingerprint TEXT,
  sample_text TEXT,
  count       INTEGER DEFAULT 1,
  confidence  TEXT,
  router_note TEXT,
  lane        TEXT,
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE runs (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  mode        TEXT NOT NULL,
  started_at  TIMESTAMP,
  finished_at  TIMESTAMP,
  record_count INTEGER DEFAULT 0,
  finding_count INTEGER DEFAULT 0,
  status      TEXT DEFAULT 'running'
);
```

CRUD functions: `init_db()`, `upsert_record()`, `upsert_finding()`, `get_records()`, `get_findings()`, `get_run()`.

---

### sources/hermes_logs.py

- Scans `~/.hermes/logs/` for `.log` and `.jsonl` files
- Reads errors, warnings, auth failures, crashes, timeouts from raw text
- Returns list of `Finding` dataclass instances
- Does not use the session log analyzer's fingerprint logic — raw signal scan only

### sources/hermes_sessions.py

- Scans `~/.hermes/sessions/` for `.json` session dumps
- Extracts failure signals from the JSON structure
- Groups by `category`, `severity`, `fingerprint`
- Returns list of `Finding` instances

### sources/hf_catalog.py

- Fetches Hugging Face model pages and endpoint catalog pages
- Target URLs:
  - `https://huggingface.co/models`
  - `https://endpoints.huggingface.co/catalog`
  - `https://huggingface.co/<model-page>` for linked model details
- Extracts: model name, provider family, endpoint hints, auth type

### sources/modelscope_catalog.py

- Uses ModelScope internal APIs discovered from browser inspection:
  - `https://www.modelscope.cn/api/v1/dolphin/models`
  - `https://www.modelscope.cn/api/v1/dolphin/datasets`
  - `https://www.modelscope.cn/api/v1/dolphin/studios`
  - `https://www.modelscope.cn/api/v1/trend?Type=model`
- Also scrapes model page text for endpoint details
- Extracts: model name, provider family, API style, capability tags

---

### scrape/exa_scraper.py

- Calls Exa API with queries targeting provider/model/endpoint surfaces
- Query templates:
  - `"site:huggingface.co LLM API endpoint documentation"`
  - `"site:modelscope.cn model API endpoint"`
  - `"ModelScope MCP provider models"`
- Returns list of `{url, title, text, links}`
- Falls through to firecrawl if Exa fails or returns empty

### scrape/firecrawl_scraper.py

- Uses Firecrawl to crawl discovered URLs
- Extracts structured text and linked URLs
- Returns same `{url, title, text, links}` shape as exa_scraper
- Only used as secondary or fallback

### scrape/merge.py

- Deduplicates content from multiple scraper sources
- Groups by source domain and URL
- Returns single merged list of raw chunks ready for routing

---

### route/router.py

**No editing. Only classifies and labels.**

Input: raw text chunk from scrape layer
Output: structured `RouterResult` or `None` (if not a provider/model record)

```python
@dataclass
class RouterResult:
    provider:    str
    model:       str
    base_url:   str
    auth_type:  str       # bearer|api_key|oauth|jwt
    auth_key:   str       # env var name, not value
    lane:       str       # coding|compression|web-extract|research|auxiliary
    region:     str | None
    capabilities: list[str]
    context_window: int
    source:     str       # huggingface|modelscope|manual|hermes-log
    confidence: str       # high|medium|low
    raw_text:   str
```

**System prompt** (kept minimal, no instruction to edit):

```
You are a routing classifier. Given raw text from a web page or log file,
extract provider/model/endpoint records. Return ONLY a JSON object with
the fields defined in RouterResult. If the text is not about a model or
provider, return {"skip": true}. Never invent URLs, endpoints, or model
names that are not present in the input text.
```

**Model**: configurable via `ROUTER_MODEL` env var or `--router-model` flag. Default: first available OpenAI-compatible local endpoint (checks `openai-codex`, then `kilocode`, then `fireworks-ai`).

---

### validate/normalizer.py

- Receives `RouterResult` instances
- Validates each field against schema
- Resolves aliases:
  - `fireworks` / `fireworks-ai` / `firepass` → canonical `fireworks-ai`
  - `kimi` / `moonshot` → canonical `kimi`
  - `qwen` / `alibaba` / `bailian` → canonical `alibaba`
  - etc.
- Checks that `base_url` looks like a valid URL pattern
- Rejects invented endpoints (URL must be present in raw_text or be a known canonical URL)
- Returns validated `CatalogRecord` or raises `ValidationError`

### validate/lanes.py

- Assigns lane based on provider + model + capability hints
- Rules:
  - coding agents: `coding`, `function_calling` capability → coding lane
  - vision + reasoning: `research` lane
  - compression/web-extract: specific model families
  - auxiliary: catch-all for uncategorized
- Returns lane string or `None`

---

### report/issues.py

- Reads findings from catalog.db
- Groups by `category`, `fingerprint`, `lane`
- Bucket categories:
  - `auth` — 401, 403, invalid token, expired token
  - `provider` — 429, 502, 503, rate limit, upstream error
  - `crash` — traceback, exception, panic, SIGSEGV
  - `config` — missing plugin, hash mismatch, parse error
  - `io` — file not found, permission denied, broken pipe
  - `block` — blocked, stuck, hanging, waiting
  - `congestion` — retry, backlog, throttle, backoff
- Each bucket gets: count, top file, sample lines, router notes, lane

### report/markdown.py

- Writes `~/hermesoptimizer/reports/YYYY-MM-DD-HHMMSS-report.md`
- Sections: confidence summary, severity summary, category summary, top files, issues by bucket
- Includes router labels and lane assignments where available

### report/json_export.py

- Writes `~/hermesoptimizer/reports/YYYY-MM-DD-HHMMSS-report.json`
- Machine-readable, same structure as Markdown
- Includes raw findings for programmatic downstream use

---

## Execution modes

### Inside Hermes mode

Entry: `src/run_hermes_mode.py`

```bash
python3 -m hermesoptimizer.hermes_mode [--focus auth|provider|crash|all]
```

Behavior:
- Reads current session context (if Hermes session is active)
- Scans `~/.hermes/logs/` and `~/.hermes/sessions/`
- Uses Hermes's active config to determine current lanes and providers
- Does NOT use Hermes chat API — purely file-based
- Writes report to `~/hermesoptimizer/reports/`
- Returns report path in response

Detected via: env var `HERMES_ACTIVE_SESSION` or presence of `~/.hermes/sessions/current/`.

### Outside Hermes mode (standalone)

Entry: `src/run_standalone.py`

```bash
python3 -m hermesoptimizer.standalone \
  --roots ~/.hermes/logs ~/.hermes/sessions \
  --report-dir ~/hermesoptimizer/reports \
  --scraper exa,firecrawl \
  --router-model kilocode \
  --catalog ~/hermesoptimizer/catalog.db \
  --mode hermes|standalone \
  --dry-run
```

Detected via: absence of `HERMES_ACTIVE_SESSION`.

### Cron mode

Wrapper: `scripts/run.sh`

```bash
# cron-friendly: no confirm prompts, exits non-zero on findings
~/hermesoptimizer/scripts/run.sh --mode standalone
```

---

## CLI flags

| Flag | Default | Description |
|------|---------|-------------|
| `--mode` | auto-detect | `hermes` or `standalone` |
| `--roots` | `~/.hermes/logs,~/.hermes/sessions` | Scan roots |
| `--report-dir` | `~/hermesoptimizer/reports` | Output directory |
| `--catalog` | `~/hermesoptimizer/catalog.db` | SQLite catalog |
| `--scraper` | `exa,firecrawl` | Scraper priority order |
| `--router-model` | first available | OAI-compatible model to use |
| `--sources` | `hermes-logs,hermes-sessions,hf,modelscope` | Source adapters |
| `--focus` | `all` | Category filter: auth,provider,crash,config,io,block,congestion,all |
| `--dry-run` | False | Don't write to catalog or disk |
| `--fail-on-findings` | False | Exit non-zero if any signals found |

---

## Open questions

1. **Router model availability**: should the tool check all known OAI-compatible providers (`kilocode`, `fireworks-ai`, `openai-codex`) in order, or should the user pin one explicitly via `--router-model`?

2. **Scraping frequency**: how often should external catalogs (HF, ModelScope) be refreshed? Once per run, once per day, or only on explicit `--refresh-catalog` flag?

3. **Hermes session adapter**: when running inside Hermes, should it read from the live session transcript (if accessible) or only from the session files on disk?

4. **Lane assignment**: should lane be inferred by the router model, assigned by rules in `lanes.py`, or both (model suggests, rules validate)?

5. **Report delivery**: inside Hermes, should the report be printed to the chat or only written to disk (or both)?

6. **Catalog retention**: how many historical catalog snapshots should be kept? SQLite grows over time; do you want a `VACUUM`/prune policy?

7. **Diff-since**: for cron mode, should `--diff-since` compare against the last run's findings to surface only new/changed issues, or always report everything?

---

## Test strategy

Each module has a corresponding `tests/test_*.py`:

- `test_catalog.py`: CRUD operations, schema validation, uniqueness constraints
- `test_sources.py`: mock log files, verify correct `Finding` counts and categories
- `test_router.py`: mock scraped text, verify correct `RouterResult` output (or `{"skip": true}`), no invented fields
- `test_validator.py`: valid and invalid `RouterResult` instances, alias resolution, URL validation
- `test_reports.py`: mock findings, verify Markdown and JSON structure

Run with:
```bash
cd ~/hermesoptimizer
python3 -m pytest tests/ -v
```

---

## Implementation order

1. `catalog.py` + `tests/test_catalog.py` — schema and storage foundation
2. `sources/hermes_logs.py` + `sources/hermes_sessions.py` + `tests/test_sources.py` — log adapters
3. `route/router.py` + `route/prompts.py` + `tests/test_router.py` — router model interface
4. `validate/normalizer.py` + `validate/lanes.py` + `tests/test_validator.py` — validation layer
5. `report/issues.py` + `report/markdown.py` + `report/json_export.py` + `tests/test_reports.py` — reporting
6. `src/run_hermes_mode.py` + `src/run_standalone.py` — entry points
7. `scrape/exa_scraper.py` + `scrape/firecrawl_scraper.py` + `scrape/merge.py` — scraper layer (optional, defer to after core is working)
8. `scripts/run.sh` + `scripts/diff-since.sh` — cron wrappers
9. `README.md` — usage docs

Steps 1-6 are the core. Steps 7+ are additive.

---

## Verification commands

After step 1-6 are implemented:

```bash
# Inside Hermes mode (dry run)
python3 ~/hermesoptimizer/src/run_hermes_mode.py --dry-run --focus auth

# Outside Hermes mode
python3 ~/hermesoptimizer/src/run_standalone.py --roots ~/.hermes/logs --dry-run

# With scraper (after step 7)
python3 ~/hermesoptimizer/src/run_standalone.py --scraper exa,firecrawl --router-model kilocode

# Cron mode
~/hermesoptimizer/scripts/run.sh --mode standalone

# View report
cat ~/hermesoptimizer/reports/latest.md
```

---

## Key design constraints

- **Stdlib only** for catalog, validation, report, and adapter modules
- **Router model is read-only** — never writes, edits, or mutates config
- **No secrets written to disk** — only env var names, never values
- **SQLite catalog** is the source of truth, not memory
- **Reports go to `~/hermesoptimizer/reports/`**, never `/tmp`
- **Same core engine** in both Hermes mode and standalone mode
