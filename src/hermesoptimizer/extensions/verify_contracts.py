"""Family-specific verification contracts for managed extensions.

Each verify_* function returns exit code 0 on pass, 1 on fail,
and prints structured diagnostic output to stdout/stderr.

Intended for use via CLI:
    python -m hermesoptimizer.extensions.verify_contracts <family>
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from hermesoptimizer.extensions.resolver import _repo_root


def _config_path() -> Path:
    return Path("~/.hermes/config.yaml").expanduser()


# ---------------------------------------------------------------------------
# Caveman
# ---------------------------------------------------------------------------


def verify_caveman() -> int:
    """Verify caveman mode config, toggle, compression guardrails, and skill reference."""
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Module importable
    try:
        from hermesoptimizer.caveman import compress, is_enabled, toggle
    except Exception as exc:
        print(f"FAIL: caveman module not importable: {exc}", file=sys.stderr)
        return 1

    # 2. Config readable
    config_path = _config_path()
    if config_path.exists():
        try:
            import yaml

            data = yaml.safe_load(config_path.read_text()) or {}
            if "caveman_mode" not in data:
                warnings.append("caveman_mode key missing from config (will default to False)")
        except Exception as exc:
            errors.append(f"config not readable: {exc}")
    else:
        warnings.append("config file does not exist (will default to False)")

    # 3. Toggle works without crashing
    try:
        original = is_enabled()
        new_state = toggle()
        # Restore
        if new_state != original:
            toggle()
    except Exception as exc:
        errors.append(f"toggle failed: {exc}")

    # 4. Compression guardrails: safety-critical text should NOT be compressed
    try:
        from hermesoptimizer.caveman import compress

        safety_text = "Confirm destructive vault write-back before proceeding."
        compressed = compress(safety_text)
        if compressed != safety_text:
            errors.append("safety-critical text was incorrectly compressed")
    except Exception as exc:
        errors.append(f"compression guardrail check failed: {exc}")

    # 5. Skill reference
    skill_path = Path("~/.hermes/skills/software-development/caveman/SKILL.md").expanduser()
    if not skill_path.exists():
        warnings.append(f"caveman skill not installed at {skill_path}")

    for w in warnings:
        print(f"WARN: {w}")
    for e in errors:
        print(f"FAIL: {e}", file=sys.stderr)

    if errors:
        return 1
    print("PASS: caveman verification OK")
    return 0


# ---------------------------------------------------------------------------
# Dreams
# ---------------------------------------------------------------------------


def verify_dreams() -> int:
    """Verify dreams sidecar: DB, external scripts, cron-linked surfaces."""
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Module importable
    try:
        from hermesoptimizer.dreams.sweep import run_sweep
    except Exception as exc:
        print(f"FAIL: dreams module not importable: {exc}", file=sys.stderr)
        return 1

    # 2. memory_meta.db presence
    db_path = Path("~/.hermes/dreams/memory_meta.db").expanduser()
    if not db_path.exists():
        warnings.append(f"memory_meta.db not found at {db_path}")
    else:
        try:
            from hermesoptimizer.dreams.memory_meta import init_db, query_by_score

            init_db(db_path)
            query_by_score(db_path, threshold=0.0)
        except Exception as exc:
            errors.append(f"memory_meta.db not readable: {exc}")

    # 3. External scripts
    expected_scripts = [
        Path("~/.hermes/scripts/dreaming_reflection_context.py").expanduser(),
        Path("~/.hermes/scripts/supermemory_store.js").expanduser(),
    ]
    for script in expected_scripts:
        if not script.exists():
            warnings.append(f"external script missing: {script}")

    # 4. Repo scripts
    repo_scripts = [
        _repo_root() / "scripts" / "dreaming_pre_sweep.py",
        _repo_root() / "scripts" / "probe_memory_meta.py",
    ]
    for script in repo_scripts:
        if not script.exists():
            errors.append(f"repo script missing: {script}")

    # 5. Sweep callable
    try:
        result = run_sweep([], injected_memory_pct=0.0)
        assert "decisions" in result
        assert "summary" in result
    except Exception as exc:
        errors.append(f"run_sweep failed: {exc}")

    for w in warnings:
        print(f"WARN: {w}")
    for e in errors:
        print(f"FAIL: {e}", file=sys.stderr)

    if errors:
        return 1
    print("PASS: dreams verification OK")
    return 0


# ---------------------------------------------------------------------------
# Vault plugins
# ---------------------------------------------------------------------------


def verify_vault_plugins() -> int:
    """Verify vault plugin importability, status shapes, and sidecar health."""
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Importability
    try:
        from hermesoptimizer.vault.plugins import (
            HermesPlugin,
            OpenClawPlugin,
            OpenCodePlugin,
        )
    except Exception as exc:
        print(f"FAIL: vault plugins not importable: {exc}", file=sys.stderr)
        return 1

    # 2. HermesPlugin status shape
    try:
        hp = HermesPlugin()
        st = hp.status()
        required = {"plugin_name", "vault_path", "entry_count", "encrypted_count"}
        missing = required - set(st.keys())
        if missing:
            errors.append(f"HermesPlugin.status() missing keys: {missing}")
    except Exception as exc:
        warnings.append(f"HermesPlugin status check failed: {exc}")

    # 3. OpenCodePlugin status shape and read-only contract
    try:
        ocp = OpenCodePlugin()
        st = ocp.status()
        required = {"plugin_name", "vault_path", "entry_count", "encrypted_count", "readonly"}
        missing = required - set(st.keys())
        if missing:
            errors.append(f"OpenCodePlugin.status() missing keys: {missing}")
        if not st.get("readonly"):
            errors.append("OpenCodePlugin.status() does not report readonly=True")

        # Read-only contract: set/delete must raise
        try:
            ocp.set("__test_key__", "value")
            errors.append("OpenCodePlugin.set() did not raise NotImplementedError")
        except NotImplementedError:
            pass
        except Exception as exc:
            errors.append(f"OpenCodePlugin.set() raised unexpected {type(exc).__name__}: {exc}")

        try:
            ocp.delete("__test_key__")
            errors.append("OpenCodePlugin.delete() did not raise NotImplementedError")
        except NotImplementedError:
            pass
        except Exception as exc:
            errors.append(f"OpenCodePlugin.delete() raised unexpected {type(exc).__name__}: {exc}")

        # Config generation
        tmp_config = Path("/tmp/opencode_plugin_test_config.yaml")
        try:
            ocp.generate_config(tmp_config)
            if not tmp_config.exists():
                errors.append("OpenCodePlugin.generate_config() did not create file")
        finally:
            if tmp_config.exists():
                tmp_config.unlink()
    except Exception as exc:
        warnings.append(f"OpenCodePlugin check failed: {exc}")

    # 4. OpenClawPlugin sidecar health
    try:
        ocp_sidecar = OpenClawPlugin(port=0)  # port 0 lets OS assign
        st = ocp_sidecar.status()
        required = {"plugin_name", "vault_path", "entry_count", "encrypted_count"}
        missing = required - set(st.keys())
        if missing:
            errors.append(f"OpenClawPlugin.status() missing keys: {missing}")
    except Exception as exc:
        warnings.append(f"OpenClawPlugin status check failed: {exc}")

    for w in warnings:
        print(f"WARN: {w}")
    for e in errors:
        print(f"FAIL: {e}", file=sys.stderr)

    if errors:
        return 1
    print("PASS: vault_plugins verification OK")
    return 0


# ---------------------------------------------------------------------------
# Tool surface
# ---------------------------------------------------------------------------


def verify_tool_surface() -> int:
    """Verify tool-surface commands are available and help text is not stale."""
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Module importable
    try:
        from hermesoptimizer.tool_surface.commands import (
            AVAILABLE_COMMANDS,
            execute_command,
            get_help,
            list_commands,
        )
    except Exception as exc:
        print(f"FAIL: tool_surface module not importable: {exc}", file=sys.stderr)
        return 1

    # 2. Commands are available
    expected = ["provider list", "provider recommend", "workflow list", "dreams inspect", "report latest"]
    actual = list_commands()
    for cmd in expected:
        if cmd not in actual:
            errors.append(f"expected command missing: {cmd}")

    # 3. Help text does not contain placeholder language
    help_text = get_help()
    placeholder_patterns = [
        r"Placeholder",
        r"placeholder",
        r"TODO",
        r"FIXME",
        r"Task \d+",
    ]
    for pattern in placeholder_patterns:
        if re.search(pattern, help_text):
            errors.append(f"help text contains placeholder pattern: {pattern}")

    # 4. Each command can execute without crashing (dry-run style)
    for cmd in ["provider list", "workflow list", "report latest"]:
        try:
            result = execute_command(cmd)
            # These are read-only; failure is OK if it returns a result struct
            if not hasattr(result, "success"):
                errors.append(f"command {cmd} returned unexpected type")
        except Exception as exc:
            errors.append(f"command {cmd} raised: {exc}")

    for w in warnings:
        print(f"WARN: {w}")
    for e in errors:
        print(f"FAIL: {e}", file=sys.stderr)

    if errors:
        return 1
    print("PASS: tool_surface verification OK")
    return 0


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

_FAMILIES: dict[str, callable] = {
    "caveman": verify_caveman,
    "dreams": verify_dreams,
    "vault_plugins": verify_vault_plugins,
    "tool_surface": verify_tool_surface,
}


def main(argv: list[str] | None = None) -> int:
    """Run a verification contract by family name."""
    argv = argv or sys.argv[1:]
    if not argv:
        print(f"Usage: python -m hermesoptimizer.extensions.verify_contracts <family>")
        print(f"Families: {', '.join(_FAMILIES.keys())}")
        return 1

    family = argv[0]
    fn = _FAMILIES.get(family)
    if fn is None:
        print(f"Unknown family: {family}", file=sys.stderr)
        print(f"Known families: {', '.join(_FAMILIES.keys())}", file=sys.stderr)
        return 1

    return fn()


if __name__ == "__main__":
    sys.exit(main())
