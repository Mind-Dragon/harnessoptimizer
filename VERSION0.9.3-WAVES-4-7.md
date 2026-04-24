# VERSION0.9.3 — Waves 4-7 completion proof

## Wave 4 — CLI truthfulness

Evidence:

- `dodev --help` exits 0 after restoring argparse help on the alias.
- `devdo`/`dodev` help now states the current contract: inspect/start workflow run state, not autonomous task execution.
- README command list was reconciled against the live argparse surface; unimplemented config/aux/yolo/service commands are marked planned instead of advertised as shipped.
- README collected-test count updated to 2,025 and guarded by a live collection test.
- Release readiness now includes `cli_help_smoke` and `readme_command_drift`.

## Wave 4b — release gate hardening

Evidence:

- `check_test_collection` no longer ignores `tests/test_channel_management.py`.
- Suspicious channel assertion replaced with the explicit promotion-chain invariant `sources & targets == {"beta"}`.
- `check_provider_truth` now fails closed when the merged provider registry is empty.
- `check_extension_doctor` keeps dry-run REPO_EXTERNAL drift visible in evidence as `dry_run_drift_issues`.
- Gate invariant test is unconditional: `gate_passed == all(critical checks passed)`.
- `check_installer_canary` runs `ext-sync --dry-run --fresh-root` and `ext-doctor --dry-run` in release readiness.

## Wave 5 — caveman contract

Evidence:

- Caveman extension is selected but marked `optional_runtime: true`; external runtime ownership prevents blind repo overwrite.
- Existing status/doctor paths report unselected optional features as `not_selected`; dreams currently proves that path.
- Caveman verify path remains `python -m hermesoptimizer.extensions.verify_contracts caveman`.
- Added config writer test proving `caveman_mode` can be added around adjacent comments/scalar free text without corrupting YAML or adjacent keys.
- README avoids claiming native Hermes consumption of `caveman_mode`; native response-shape behavior remains out of scope until a small Hermes patch and live probe exist.

## Wave 6 — brain/dreams/provider health

Evidence:

- `brain/scripts/request_dump_digest.py` now emits `provider_health_inputs` from URL/model/reason buckets.
- Failure-class request dump buckets with at least 3 failures are marked `quarantine_candidate: true`.
- Non-dry local brain canary is in release readiness as `brain_doctor_canary`, scoped to `request_dump` only to avoid network/provider mutation.
- Dreams remains optional with `selected: false`; status is `not_selected`, not missing/broken.
- Provider health notes added at `brain/PROVIDER_HEALTH_NOTES.md`.
- Current request dump evidence: MiniMax has 49 `max_retries_exhausted` failures and is a quarantine candidate; crof has 1 non-retryable client error.

## Wave 7 — Hermes integration proof

Evidence:

- Local Hermes dirty tree is explicitly scoped: `/home/agent/hermes-agent/cli.py` contains the small hot-reload patch block; `/home/agent/hermes-agent/internal/` is untracked Go search work and is not part of this release proof.
- `scripts/apply_reload_patch.py --check` reports the patch is applied.
- `refresh_provider_db()` upserts registry providers/models into `~/.hermes/provider-db/provider_model.sqlite` without restart.
- `inspect_hot_reload_readiness()` reports ready with provider DB present.
- SQLite proof includes:
  - `kilocode/inclusionai/ling-2.6-flash:free`
  - `openrouter/inclusionai/ling-2.6-flash:free`
  - `nous/moonshotai/kimi-k2.6`
  - `openai-codex/gpt-5.5`
  - `openai-codex/gpt-5.4-mini`
- Native `hermes status`/`hermes doctor` bridge is intentionally not added in v0.9.3; optimizer health remains external to avoid broad Hermes changes.

## Provider canary evidence

Latest live canary run:

- Kilocode `inclusionai/ling-2.6-flash:free`: 200 OK through `https://api.kilo.ai/api/gateway/chat/completions`.
- OpenRouter `inclusionai/ling-2.6-flash:free`: 200 OK through `https://openrouter.ai/api/v1/chat/completions`.
- Nous Portal `moonshotai/kimi-k2.6`: 200 OK using the provider-scoped Nous `device_code` credential/agent key path.
- OpenAI Codex `gpt-5.4-mini`: provider-scoped OpenAI OAuth `device_code` credential resolves correctly; live probe returns 429 `insufficient_quota`, not model-not-found. Keep as single fallback lane when quota is available.

## Final verification commands

Passed targeted checks:

```bash
PYTHONPATH=src python -m pytest tests/test_wave4_wave7_contracts.py tests/test_release_readiness.py tests/test_channel_management.py tests/test_caveman_config.py tests/test_extensions_status.py tests/test_extensions_sync.py tests/test_request_dump_health_inputs.py brain/scripts/test_brain_doctor.py -q
PYTHONPATH=src python -m pytest tests/test_hot_reload_proof.py tests/test_package_resources.py tests/test_provider_registry.py tests/test_provider_management.py -q
PYTHONPATH=src python -m hermesoptimizer release-readiness --dry-run
PYTHONPATH=src python -m hermesoptimizer ext-doctor --dry-run
PYTHONPATH=src python -m hermesoptimizer ext-sync --dry-run --fresh-root /tmp/hopt-fresh-root
PYTHONPATH=src python -m hermesoptimizer brain-doctor --dry-run
```
