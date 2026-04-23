# CONFIG-MANAGER.md — Hermes Config Hot-Reload

## Mechanism

The existing `/reload` slash command in Hermes CLI reloads `.env` but not `config.yaml`.
A patch extends it to also re-read `config.yaml` and refresh the running session's
display, agent, and compression settings.

### Files

| File | Purpose |
|------|---------|
| `/home/agent/hermesoptimizer/scripts/apply_reload_patch.py` | Patches cli.py to extend `/reload` |
| `/home/agent/hermesoptimizer/scripts/post-merge-hook.sh` | Git post-merge hook to reapply after `hermes update` |
| `/home/agent/hermes-agent/.git/hooks/post-merge` | Installed hook (copy of above) |

### What `/reload` does after patching

1. Re-reads `~/.hermes/.env` (original behavior)
2. Re-reads `~/.hermes/config.yaml` via `load_cli_config()`
3. Updates the `CLI_CONFIG` module global in-place
4. Patches the running `HermesCLI` instance:
   - Display: compact, streaming, tool_progress, resume_display, bell_on_complete, show_reasoning, busy_input_mode, final_response_markdown, inline_diffs
   - Agent: max_turns
   - Compression: threshold, enabled, target_ratio
5. Does NOT switch the active provider/model — use `/model` for that

### Usage

```
# In a running hermes CLI session:
/reload

# Output:
#   Reloaded .env (3 var(s)) + config.yaml
```

### Post-update reapplication

`hermes update` does `git pull` which triggers the post-merge hook,
automatically reapplying the patch. If it doesn't fire (e.g. manual git ops):

```bash
python3 /home/agent/hermesoptimizer/scripts/apply_reload_patch.py
```

Check status:

```bash
python3 /home/agent/hermesoptimizer/scripts/apply_reload_patch.py --check
```

### Gateway reload (separate)

The gateway doesn't use the CLI's `/reload`. It uses systemd:

```bash
systemctl --user reload hermes-gateway.service
```

This sends SIGUSR1 → graceful drain → exit 75 → systemd respawns with fresh config.

### What still requires a restart

- Active ACP subagents (delegate_task workers) — independent processes with their own config snapshot
- Running cron jobs — use their own session's config snapshot
- Provider/model switches mid-session — use `/model` instead of `/reload`
- Auxiliary client routing (vision, web_extract, etc.) — these resolve via `runtime_provider` which reads `load_config()` fresh, so `/reload` + next tool call picks up changes

### If the patch target changes

If a Hermes update restructures the `/reload` handler such that the exact
string match fails, the patch script will print an error with instructions.
Update `apply_reload_patch.py` with the new `OLD_BLOCK` string and reapply.

### Install integrity

`apply_reload_patch.py` is transactional:

1. reads the live `cli.py`
2. builds the patched content in memory
3. validates Python syntax with `ast.parse()` before writing
4. writes a sibling temp file under `/home/agent/hermes-agent/`
5. validates the temp file
6. writes a `.hermesoptimizer-reload.bak` backup
7. atomically replaces `cli.py`
8. restores from backup if any write/validation step fails
