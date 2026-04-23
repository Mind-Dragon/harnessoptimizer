#!/bin/bash
# /home/agent/hermes-agent/.git/hooks/post-merge
# Auto-applied after `hermes update` (which does git pull).
# Reapplies the /reload hot-reload patch.

set -e

PATCH_SCRIPT="/home/agent/hermesoptimizer/scripts/apply_reload_patch.py"

if [ -x "$(command -v python3)" ] && [ -f "$PATCH_SCRIPT" ]; then
    python3 "$PATCH_SCRIPT" 2>&1 | while IFS= read -r line; do
        echo "[post-merge] $line"
    done
fi
