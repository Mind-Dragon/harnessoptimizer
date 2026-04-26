# Extension Management Operator Recipe

## Fresh machine onboarding

1. Clone the repo and install:
```
pip install -e .
```

2. List what the repo owns:
```
PYTHONPATH=src python -m hermesoptimizer ext-list
```

3. Check health and drift:
```
PYTHONPATH=src python -m hermesoptimizer ext-doctor
```

4. Review missing targets and drift warnings. For each item:
- `missing_target`: the repo expects a file/dir that is not on this machine
- `drift (warning)`: the repo owns something but the runtime state is incomplete
- `drift (error)`: the runtime state conflicts with repo truth

5. Sync repo-managed artifacts (dry-run first):
```
PYTHONPATH=src python -m hermesoptimizer ext-sync --dry-run
```

6. If the dry-run looks correct, run without `--dry-run`:
```
PYTHONPATH=src python -m hermesoptimizer ext-sync
```

7. Re-run doctor to confirm:
```
PYTHONPATH=src python -m hermesoptimizer ext-doctor
```

## Daily drift check

Run this to catch drift early:
```
PYTHONPATH=src python -m hermesoptimizer ext-doctor
```

If drift_errors > 0, investigate before starting work.

## Safe sync policy

| Ownership | Sync behavior |
|-----------|---------------|
| repo_only with target_paths | Copied to target. `--force` required to overwrite. |
| repo_only with `target_paths: []` + `metadata.install_mode: repo_only_no_sync` | Verified from the checkout/package only; no runtime copy target exists. |
| repo_external | Repo artifacts copied; external paths are verify-only. |
| external_runtime | Never synced. Registry tracks for visibility only. |

Never sync without `--dry-run` first on a new machine.
Never use `--force` on external_runtime targets.

## Extension families

### caveman
- Config key: `caveman_mode` in `~/.hermes/config.yaml`
- Skill path: `~/.hermes/skills/software-development/caveman/SKILL.md`
- Toggle: `hermesoptimizer caveman`

### dreams
- DB: `~/.hermes/dreams/memory_meta.db`
- External scripts: `~/.hermes/scripts/dreaming_reflection_context.py`, `~/.hermes/scripts/supermemory_store.js`
- Cron: tracked but not synced by the registry

### vault_plugins
- Vault file: `~/.vault/vault.enc.json`

### tool_surface
- Commands: `provider list`, `provider recommend`, `workflow list`, `dreams inspect`, `report latest`
- Placeholder text guard: `ext-doctor` fails if help text contains "Placeholder" or "TODO"
