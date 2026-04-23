#!/usr/bin/env python3
"""
Post-update patch: extend /reload to also hot-reload config.yaml.

Reapplies after `hermes update` overwrites cli.py.

Usage:
    python3 apply_reload_patch.py          # apply
    python3 apply_reload_patch.py --check  # check if already applied

Location: /home/agent/hermesoptimizer/scripts/apply_reload_patch.py
"""

from __future__ import annotations

import ast
import shutil
import sys
import tempfile
from pathlib import Path

CLI_PY = Path("/home/agent/hermes-agent/cli.py")
BACKUP_SUFFIX = ".hermesoptimizer-reload.bak"

OLD_BLOCK = """\
        elif canonical == "reload":
            from hermes_cli.config import reload_env
            count = reload_env()
            print(f"  Reloaded .env ({count} var(s) updated)")\
"""

NEW_BLOCK = """\
        elif canonical == "reload":
            from hermes_cli.config import reload_env
            # --- HOT-RELOAD PATCH (hermesoptimizer) ---
            env_count = reload_env()
            try:
                import cli as _cli_mod
                _fresh = _cli_mod.load_cli_config()
                _cli_mod.CLI_CONFIG.clear()
                _cli_mod.CLI_CONFIG.update(_fresh)
                self.config = _cli_mod.CLI_CONFIG

                _disp = _fresh.get("display", {})
                self.compact = _disp.get("compact", self.compact)
                self.bell_on_complete = _disp.get("bell_on_complete", self.bell_on_complete)
                self.show_reasoning = _disp.get("show_reasoning", self.show_reasoning)
                self.streaming_enabled = _disp.get("streaming", self.streaming_enabled)
                _raw_tp = _disp.get("tool_progress", "all")
                self.tool_progress_mode = "off" if _raw_tp is False else str(_raw_tp)
                self.resume_display = _disp.get("resume_display", self.resume_display)
                _bim = _disp.get("busy_input_mode", "interrupt")
                self.busy_input_mode = "queue" if str(_bim).strip().lower() == "queue" else "interrupt"
                self.final_response_markdown = str(_disp.get("final_response_markdown", "strip")).strip().lower() or "strip"
                if self.final_response_markdown not in {"render", "strip", "raw"}:
                    self.final_response_markdown = "strip"
                self._inline_diffs_enabled = _disp.get("inline_diffs", self._inline_diffs_enabled)

                _agent = _fresh.get("agent", {})
                if _agent.get("max_turns"):
                    self.max_turns = _agent["max_turns"]

                _comp = _fresh.get("compression", {})
                if _comp:
                    self.config["compression"] = _comp
                print(f"  Reloaded .env ({env_count} var(s)) + config.yaml")
            except Exception as e:
                print(f"  Reloaded .env ({env_count} var(s)). Config reload failed: {e}")
            # --- END HOT-RELOAD PATCH ---\
"""


def _read_cli() -> str:
    if not CLI_PY.exists():
        raise FileNotFoundError(f"{CLI_PY} not found")
    return CLI_PY.read_text(encoding="utf-8")


def is_applied() -> bool:
    return "HOT-RELOAD PATCH (hermesoptimizer)" in _read_cli()


def _validate_python(text: str) -> None:
    ast.parse(text, filename=str(CLI_PY))


def _atomic_replace(text: str) -> None:
    _validate_python(text)
    backup = CLI_PY.with_name(CLI_PY.name + BACKUP_SUFFIX)
    backup.write_text(_read_cli(), encoding="utf-8")

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(CLI_PY.parent),
            prefix=f".{CLI_PY.name}.",
            suffix=".tmp",
            delete=False,
        ) as fh:
            fh.write(text)
            tmp_path = Path(fh.name)
        _validate_python(tmp_path.read_text(encoding="utf-8"))
        tmp_path.replace(CLI_PY)
    except Exception:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()
        shutil.copy2(backup, CLI_PY)
        raise


def apply() -> None:
    text = _read_cli()
    if "HOT-RELOAD PATCH (hermesoptimizer)" in text:
        print("Patch already applied.")
        return

    if OLD_BLOCK not in text:
        print("ERROR: Could not find the original /reload block.")
        print("The patch target may have changed in a Hermes update.")
        print("Inspect cli.py around 'canonical == \"reload\"' and update the patch.")
        sys.exit(1)

    patched = text.replace(OLD_BLOCK, NEW_BLOCK)
    _atomic_replace(patched)
    print(f"Patched {CLI_PY} — /reload now hot-reloads config.yaml")


def check() -> None:
    if is_applied():
        print("Patch is applied.")
    else:
        print("Patch is NOT applied.")
        sys.exit(1)


if __name__ == "__main__":
    if "--check" in sys.argv:
        check()
    else:
        apply()
