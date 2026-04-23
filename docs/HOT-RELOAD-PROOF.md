# Hot-Reload Proof — v0.9.3

Goal: prove that a provider/model registry update can reach the running local
Hermes without `hermes restart` or `hermes update`.

## Live proof command

```bash
PYTHONPATH=src python -m hermesoptimizer verify hot-reload
```

(If no `verify hot-reload` CLI entry exists yet, run the module directly:)

```bash
PYTHONPATH=src python -c \
  "from hermesoptimizer.verify.hot_reload import inspect_hot_reload_readiness, format_readiness; \
   print(format_readiness(inspect_hot_reload_readiness()))"
```

## What the inspector checks

1. `cli.py` exists at `/home/agent/hermes-agent/cli.py`.
2. The existing hot-reload patch marker is present (`HOT-RELOAD PATCH (hermesoptimizer)`).
3. Required symbols are still in `cli.py`:
   - `CLI_CONFIG = load_cli_config()` (module global)
   - `def load_cli_config()`
   - `from hermes_cli.config import reload_env`
4. Provider DB exists at `~/.hermes/provider-db/provider_model.sqlite`.
5. Provider DB is non-empty (at least one provider, at least one model).

## Acceptance criteria

- `ready` field is `True`.
- `issues` list is empty.
- `recommended_patch_point` names the existing patch block (`elif canonical == "reload"`).
- No restart or `hermes update` is required to ingest a new provider or model.

## Recommended Hermes patch boundary (first pass)

Location: `cli.py` inside the `/reload` slash-command handler,
`elif canonical == "reload":` block (currently ~lines 6085-6123).

Current behavior:
- Re-read `.env` via `reload_env()`.
- Re-read `config.yaml` via `load_cli_config()`.
- Patch `self.config` and display/agent/compression settings.

Next step (minimal):
- After `config.yaml` is reloaded, call `refresh_provider_db()` to upsert the
  provider/model registry from the optimizer cache or packaged seed into Hermes'
  provider DB.
- The Hermes patch stays small by importing one helper:
  `from hermesoptimizer.verify.hot_reload import refresh_provider_db`
- The helper updates `~/.hermes/provider-db/provider_model.sqlite` additively so
  Hermes sees newly registered providers/models on `/reload`.

## Files involved

- `src/hermesoptimizer/verify/hot_reload.py` — inspector + future refresh helper
- `tests/test_hot_reload_proof.py` — unit tests (tmp_path, no live Hermes)
- `/home/agent/hermes-agent/cli.py` — read-only inspection target
