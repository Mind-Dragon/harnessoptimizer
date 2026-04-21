# Hermes Optimizer — Real Data Issues (Lane A Audit)

Status: Active. Issues found by running against real `~/.hermes`.

## FIXED

### Issue 1: session error field is dict, not string
- File: `sources/hermes_sessions.py`
- Fix: `_error_to_str()` normalizer
- Tests: test_lane_a_smoke.py
- Status: FIXED

### Issue 2: config provider structure mismatch
- File: `loop.py` — `_extract_configured_providers`
- Fix: `_normalize_provider_def()` handles api/default_model/key_env
- Tests: test_lane_a_smoke.py
- Status: FIXED

### Issue 3: hermes_config.py — _REQUIRED_PROVIDER_FIELDS uses old names
- File: `sources/hermes_config.py:287`
- Fix: Added real field names to list + _REQUIRED_PROVIDER_ALIASES fallback
- Tests: existing config tests + Lane A provider tests
- Status: FIXED

### Issue 4: hermes_logs.py — all patterns miss real log format
- File: `sources/hermes_logs.py`
- Fix: Added patterns for Error code: 40[13], unknown provider, Request timed out, unknown model, \w+Error:. Added ERROR-prefix fallback for unmatched lines.
- Tests: TestLaneALogPatterns (7 tests)
- Status: FIXED

### Issue 5: Provider truth store is empty — all providers return UNKNOWN_PROVIDER
- File: `sources/provider_truth.py`
- Fix: Added `seed_from_config()` that builds truth records from config.yaml providers. Wired into enrich() as fallback when no external YAML given.
- Tests: test_provider_truth_seeded_from_config
- Status: FIXED

### Issue 6: hermes_runtime.py — gateway health blind to real state
- File: `sources/hermes_runtime.py`
- Fix: Added `scan_gateway_state_file()` that reads gateway_state.json. Wired into loop.py parse step.
- Tests: TestScanGatewayStateFile (9 tests)
- Status: FIXED

## NOTED — LOW

### Issue 7: 72 long functions (>50 lines)
- Biggest: `_build_model_catalog` at 829 lines
- Not a bug — maintainability concern
- Status: NOTED

### Issue 8: run_standalone.py has no dedicated tests
- 368 lines, 10 functions
- Lane A CLI test covers init/add/export
- Status: NOTED

### Issue 9: scrape modules are stubs
- exa_scraper.py, firecrawl_scraper.py return empty chunks
- Status: NOTED
