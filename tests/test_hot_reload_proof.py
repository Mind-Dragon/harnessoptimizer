"""Unit tests for hot-reload proof inspector.

All tests use tmp_path fixtures and do NOT depend on a live Hermes installation.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hermesoptimizer.sources.provider_registry import ProviderRegistry
from hermesoptimizer.verify.hot_reload import (
    RELOAD_PATCH_MARKER,
    format_readiness,
    inspect_hot_reload_readiness,
    recommend_hermes_patch_boundary,
    refresh_provider_db,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cli_py(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _make_provider_db(path: Path, providers: list[tuple[str, list[str]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE providers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            source TEXT NOT NULL DEFAULT 'test',
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE models (
            id INTEGER PRIMARY KEY,
            provider_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'test',
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (provider_id, name)
        )
        """
    )
    for provider_name, models in providers:
        cur.execute("INSERT INTO providers (name, source) VALUES (?, 'test')", (provider_name,))
        provider_id = cur.lastrowid
        for model_name in models:
            cur.execute(
                "INSERT INTO models (provider_id, name, source) VALUES (?, ?, 'test')",
                (provider_id, model_name),
            )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestInspectHotReloadReadiness:
    def test_empty_paths_report_not_ready(self, tmp_path: Path) -> None:
        report = inspect_hot_reload_readiness(
            hermes_agent=tmp_path / "no-agent",
            hermes_home=tmp_path / "no-home",
        )
        assert report.cli_py_exists is False
        assert report.provider_db_exists is False
        assert report.ready is False
        assert any("cli.py not found" in i for i in report.issues)
        assert any("Provider DB missing" in i for i in report.issues)

    def test_cli_py_without_symbols_is_not_ready(self, tmp_path: Path) -> None:
        agent = tmp_path / "agent"
        agent.mkdir()
        _make_cli_py(agent / "cli.py", "print('hello')")
        home = tmp_path / "home"
        home.mkdir()
        _make_provider_db(home / "provider-db" / "provider_model.sqlite", [("x", ["m1"])])
        report = inspect_hot_reload_readiness(hermes_agent=agent, hermes_home=home)
        assert report.cli_py_exists is True
        assert report.reload_patch_present is False
        assert report.cli_config_global_present is False
        assert report.load_cli_config_present is False
        assert report.reload_env_present is False
        assert report.ready is False
        assert any("patch boundary may have shifted" in i for i in report.issues)

    def test_cli_py_with_all_symbols_and_db_is_ready(self, tmp_path: Path) -> None:
        agent = tmp_path / "agent"
        agent.mkdir()
        cli_text = (
            f"{RELOAD_PATCH_MARKER}\n"
            "CLI_CONFIG = load_cli_config()\n"
            "def load_cli_config():\n"
            "    pass\n"
            "from hermes_cli.config import reload_env\n"
        )
        _make_cli_py(agent / "cli.py", cli_text)
        home = tmp_path / "home"
        home.mkdir()
        _make_provider_db(
            home / "provider-db" / "provider_model.sqlite",
            [("nacrof", ["m1", "m2"]), ("openai", ["gpt-5.5"])],
        )
        report = inspect_hot_reload_readiness(hermes_agent=agent, hermes_home=home)
        assert report.cli_py_exists is True
        assert report.reload_patch_present is True
        assert report.cli_config_global_present is True
        assert report.load_cli_config_present is True
        assert report.reload_env_present is True
        assert report.provider_db_exists is True
        assert report.provider_db_provider_count == 2
        assert report.provider_db_model_count == 3
        assert report.provider_db_providers == ["nacrof", "openai"]
        assert report.ready is True
        assert report.issues == []
        assert "Extend existing patch" in report.recommended_patch_point

    def test_empty_provider_db_flags_issue(self, tmp_path: Path) -> None:
        agent = tmp_path / "agent"
        agent.mkdir()
        cli_text = (
            f"{RELOAD_PATCH_MARKER}\n"
            "CLI_CONFIG = load_cli_config()\n"
            "def load_cli_config():\n"
            "    pass\n"
            "from hermes_cli.config import reload_env\n"
        )
        _make_cli_py(agent / "cli.py", cli_text)
        home = tmp_path / "home"
        home.mkdir()
        _make_provider_db(home / "provider-db" / "provider_model.sqlite", [])
        report = inspect_hot_reload_readiness(hermes_agent=agent, hermes_home=home)
        assert report.provider_db_exists is True
        assert report.provider_db_provider_count == 0
        assert report.ready is False
        assert any("Provider DB has zero providers" in i for i in report.issues)

    def test_partial_patch_recommends_insertion(self, tmp_path: Path) -> None:
        agent = tmp_path / "agent"
        agent.mkdir()
        cli_text = (
            "CLI_CONFIG = load_cli_config()\n"
            "def load_cli_config():\n"
            "    pass\n"
            "from hermes_cli.config import reload_env\n"
        )
        _make_cli_py(agent / "cli.py", cli_text)
        home = tmp_path / "home"
        home.mkdir()
        _make_provider_db(home / "provider-db" / "provider_model.sqlite", [("p", ["m"])])
        report = inspect_hot_reload_readiness(hermes_agent=agent, hermes_home=home)
        assert report.reload_patch_present is False
        assert "Insert new patch block" in report.recommended_patch_point
        assert report.ready is False

    def test_format_readiness_includes_all_fields(self, tmp_path: Path) -> None:
        agent = tmp_path / "agent"
        agent.mkdir()
        cli_text = (
            f"{RELOAD_PATCH_MARKER}\n"
            "CLI_CONFIG = load_cli_config()\n"
            "def load_cli_config():\n"
            "    pass\n"
            "from hermes_cli.config import reload_env\n"
        )
        _make_cli_py(agent / "cli.py", cli_text)
        home = tmp_path / "home"
        home.mkdir()
        _make_provider_db(home / "provider-db" / "provider_model.sqlite", [("p", ["m"])])
        report = inspect_hot_reload_readiness(hermes_agent=agent, hermes_home=home)
        text = format_readiness(report)
        assert "hermes_agent:" in text
        assert "cli_py_exists:" in text
        assert "reload_patch_present:" in text
        assert "provider_db_exists:" in text
        assert "ready:" in text
        assert "recommended_patch_point:" in text

    def test_recommend_boundary_returns_structure(self, tmp_path: Path) -> None:
        agent = tmp_path / "agent"
        agent.mkdir()
        cli_text = (
            f"{RELOAD_PATCH_MARKER}\n"
            "CLI_CONFIG = load_cli_config()\n"
            "def load_cli_config():\n"
            "    pass\n"
            "from hermes_cli.config import reload_env\n"
        )
        _make_cli_py(agent / "cli.py", cli_text)
        home = tmp_path / "home"
        home.mkdir()
        _make_provider_db(home / "provider-db" / "provider_model.sqlite", [("p", ["m"])])
        report = inspect_hot_reload_readiness(hermes_agent=agent, hermes_home=home)
        rec = recommend_hermes_patch_boundary(report)
        assert rec["patch_location"] == "cli.py /reload command handler (canonical == 'reload')"
        assert rec["existing_patch"] is True
        assert "proposal" in rec
        assert "refresh_provider_db" in rec["proposal"]

    def test_refresh_provider_db_upserts_liminal_registry(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        registry = ProviderRegistry.from_seed()
        result = refresh_provider_db(home, registry, source="unit-test")
        assert result.provider_count == 4
        assert result.model_count == 5
        assert result.endpoint_count == 4

        conn = sqlite3.connect(result.provider_db_path)
        rows = conn.execute(
            """
            SELECT p.name, m.name
            FROM providers p
            JOIN models m ON m.provider_id = p.id
            ORDER BY p.name, m.name
            """
        ).fetchall()
        conn.close()
        assert ("openai-codex", "gpt-5.5") in rows
        assert ("openai-codex", "gpt-5.4-mini") in rows
        assert ("nous", "moonshotai/kimi-k2.6") in rows
        assert ("kilocode", "inclusionai/ling-2.6-flash:free") in rows
        assert ("openrouter", "inclusionai/ling-2.6-flash:free") in rows
