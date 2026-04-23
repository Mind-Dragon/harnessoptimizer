# Channel System — dev / beta / release

HermesOptimizer uses a three-channel promotion model. Changes stream from `dev` through `beta` to `release` with automated gates between each stage.

## Channel definitions

| Channel  | Purpose                                    | Auto-merge? | Protected? |
|----------|--------------------------------------------|-------------|------------|
| `dev`    | Active integration — all work lands here   | Yes (ff)    | No         |
| `beta`   | Promoted candidate — feature-frozen        | No          | Yes        |
| `release`| Locked shipped state — hotfix only         | No          | Yes (force push blocked) |

## Promotion flow

```
dev ──(pass tests + install canary)──> beta ──(pass full suite + release gate)──> release
```

### Stage rules

1. **dev → beta**  
   - Push to `dev` triggers the `channel-promote.yml` workflow automatically.  
   - Workflow runs the smoke gate (`test_extensions_sync`, `test_extensions_loader`, `test_extensions_schema`).  
   - If all green and install canary passes, promotion to `beta` is unblocked.  
   - Promotion is **fast-forward only** — no silent merge of unrelated changes.

2. **beta → release**  
   - Manual trigger via `workflow_dispatch` with `channel=release`.  
   - Full test suite must pass.  
   - Doctor report must show zero critical issues.  
   - Release artifact is written to `promotion-artifacts/`.

3. **release**  
   - Immutable after promotion.  
   - Hotfixes branch from `release` → `dev` → `beta` → `release`.

## Local update flow

Each channel can be tracked independently via worktrees or a local update script.

### Using the channel update script

```bash
# Track the dev channel (default)
python scripts/channel_update.py dev

# Track beta
python scripts/channel_update.py beta

# Track release (read-only by design)
python scripts/channel_update.py release
```

### How it works

1. Fetches latest from origin
2. Verifies the update is fast-forward only
3. Runs the post-update full test suite
4. Runs the install canary (doctor dry-run)
5. Reports status — update completes only after tests and install integrity pass

### Worktree layout

```
hermesoptimizer/           # main worktree (dev)
  .git/worktrees/
    beta/                  # beta worktree
    release/               # release worktree
```

## Channel report command

After any channel change, generate a status report:

```bash
python -c "
from hermesoptimizer.extensions.doctor import run_doctor
report = run_doctor(dry_run=True)
print('Channel:', 'dev')  # detect from git
print('Extensions:', report['extensions_checked'])
print('Healthy:', report['healthy'])
print('Issues:', len(report['issues']))
"
```

## Adding a new channel

1. Create the branch: `git branch dev` / `git branch beta` / `git branch release`
2. Add a worktree entry in `.git/worktrees/`
3. Add a case in `scripts/channel_update.py` CHANNELS map
4. Document the new channel in this file

## CI/GitHub Actions

The promotion pipeline lives in `.github/workflows/channel-promote.yml`. Key behaviors:

- **No direct push to beta or release** — all changes come through promotion
- **Fast-forward only** — prevents unrelated branches from bleeding into the channel
- **Install canary** — post-update doctor check gates promotion
- **Dry-run mode** — `workflow_dispatch` with `dry_run=true` simulates without committing

## Version alignment

Channel promotion does NOT increment the version. Version bumps happen in `pyproject.toml` via a separate commit that lands on `dev` first.
