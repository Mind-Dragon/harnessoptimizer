# Compaction Bug Fix Prompt

## Problem

When context compacts (removes old conversation turns to free space), the user's original request can be lost. The compaction note says "Summary generation was unavailable. 157 conversation turns were removed to free context space but could not be summarized. The removed turns contained earlier work in this session. Continue based on the recent messages below and the current state of any files or resources."

The user had asked: "set pwd to /home/work/akta2 and read the various .md files for this project and analyze the current state and return"

But the compaction happened, and the system message with the summary note became the active instruction. The agent then started investigating prATC logs instead of reading /home/work/akta2 .md files.

## Root Cause

1. **Context compressor fails to generate summary** when the removed turns contain complex tool outputs (e.g., file listings, code reads). The `_generate_summary` method in `context_compressor.py` (line ~603) may return an empty or failed summary.

2. **No user request preservation**: When summary generation fails, the system falls back to a generic note. The user's original request (which was in the removed turns) is not preserved or re-injected.

3. **Agent gets confused**: The agent sees the compaction note as the active instruction and continues from there, losing the original task context.

## Fix Strategy

### Option A: Preserve User Request in Compaction Note (Recommended)

Modify the compaction fallback message to include the last user request:

```python
# In context_compressor.py, around line 1120-1150 where the fallback note is generated:

# Before:
fallback_note = (
    "[CONTEXT COMPACTION — REFERENCE ONLY] Earlier turns were compacted..."
    "Summary generation was unavailable..."
)

# After:
last_user_request = self._extract_last_user_request(messages_to_remove)
fallback_note = (
    "[CONTEXT COMPACTION — REFERENCE ONLY] Earlier turns were compacted..."
    "Summary generation was unavailable..."
    f"\n\n[ORIGINAL USER REQUEST — PRESERVED] {last_user_request}"
    "\n\nResume exactly from this request."
)
```

### Option B: Increase Summary Generation Robustness

- Increase `summary_timeout` from 120s to 300s for large contexts
- Add retry logic with exponential backoff for summary generation
- Use a cheaper/faster model for summary generation (currently uses `gpt-5.4` via Codex)

### Option C: Hybrid Approach

1. Always extract and preserve the last user request before compaction
2. Try summary generation with increased timeout
3. If summary fails, inject the preserved user request into the fallback note
4. Add a marker like `[PRESERVED_REQUEST]` so the agent knows to continue from there

## Implementation Notes

- The `_generate_summary` method is at line ~603 in `/home/agent/hermes-agent/agent/context_compressor.py`
- The fallback note generation is around line 1120-1150
- The `protect_last_n: 20` config setting protects the last 20 messages, but if the user's request was 25+ turns ago, it's still at risk
- Consider increasing `protect_last_n` to 50 or making it dynamic based on task complexity

## Verification

After implementing the fix:
1. Start a session with a complex request
2. Trigger compaction by having a long conversation (>100 turns)
3. Verify the compaction note includes the original user request
4. Verify the agent continues from the original request, not from the compaction note

## Related Config

```yaml
compression:
  enabled: true
  threshold: 0.5
  target_ratio: 0.2
  protect_last_n: 20  # Consider increasing to 50
```

## Priority

HIGH — This causes task loss and user frustration when working on complex, multi-turn tasks.
