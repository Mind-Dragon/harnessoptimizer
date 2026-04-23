"""Hot-reload proof inspector for local Hermes.

Reports whether the local Hermes installation is ready for optimizer-driven
hot reload and recommends the smallest patch boundary.
"""

from __future__ import annotations

import dataclasses
import sqlite3
from pathlib import Path
from typing import Any

from hermesoptimizer.sources.provider_registry import ProviderRegistry

DEFAULT_HERMES_AGENT = Path("/home/agent/hermes-agent")
DEFAULT_HERMES_HOME = Path.home() / ".hermes"

RELOAD_PATCH_MARKER = "HOT-RELOAD PATCH (hermesoptimizer)"
CLI_CONFIG_MARKER = "CLI_CONFIG = load_cli_config()"
LOAD_CLI_CONFIG_DEF = "def load_cli_config()"
RELOAD_ENV_IMPORT = "from hermes_cli.config import reload_env"


@dataclasses.dataclass(frozen=True)
class HotReloadReadiness:
    hermes_agent_path: Path
    hermes_home_path: Path
    cli_py_exists: bool
    cli_py_size: int
    reload_patch_present: bool
    cli_config_global_present: bool
    load_cli_config_present: bool
    reload_env_present: bool
    provider_db_exists: bool
    provider_db_path: Path | None
    provider_db_provider_count: int
    provider_db_model_count: int
    provider_db_providers: list[str]
    recommended_patch_point: str
    ready: bool
    issues: list[str]


def _count_providers(db_path: Path) -> tuple[int, int, list[str]]:
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM providers")
        provider_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM models")
        model_count = cur.fetchone()[0]
        cur.execute("SELECT name FROM providers ORDER BY name")
        providers = [row[0] for row in cur.fetchall()]
        conn.close()
        return provider_count, model_count, providers
    except Exception:
        return -1, -1, []


def inspect_hot_reload_readiness(
    hermes_agent: Path | str | None = None,
    hermes_home: Path | str | None = None,
) -> HotReloadReadiness:
    agent = Path(hermes_agent) if hermes_agent else DEFAULT_HERMES_AGENT
    home = Path(hermes_home) if hermes_home else DEFAULT_HERMES_HOME

    cli_py = agent / "cli.py"
    cli_py_exists = cli_py.exists()
    cli_py_text = ""
    cli_py_size = 0
    if cli_py_exists:
        try:
            cli_py_text = cli_py.read_text(encoding="utf-8")
            cli_py_size = len(cli_py_text)
        except Exception:
            cli_py_exists = False

    reload_patch_present = RELOAD_PATCH_MARKER in cli_py_text
    cli_config_global_present = CLI_CONFIG_MARKER in cli_py_text
    load_cli_config_present = LOAD_CLI_CONFIG_DEF in cli_py_text
    reload_env_present = RELOAD_ENV_IMPORT in cli_py_text

    provider_db = home / "provider-db" / "provider_model.sqlite"
    provider_db_exists = provider_db.exists()
    provider_count = 0
    model_count = 0
    providers: list[str] = []
    if provider_db_exists:
        provider_count, model_count, providers = _count_providers(provider_db)

    issues: list[str] = []
    if not cli_py_exists:
        issues.append(f"cli.py not found at {cli_py}")
    if cli_py_exists and not reload_patch_present:
        issues.append("Existing hot-reload patch missing; /reload will not re-read config.yaml")
    if cli_py_exists and not cli_config_global_present:
        issues.append("CLI_CONFIG module global missing; patch boundary may have shifted")
    if cli_py_exists and not load_cli_config_present:
        issues.append("load_cli_config() missing; patch boundary may have shifted")
    if cli_py_exists and not reload_env_present:
        issues.append("reload_env import missing; patch boundary may have shifted")
    if not provider_db_exists:
        issues.append(f"Provider DB missing at {provider_db}")
    if provider_db_exists and provider_count == 0:
        issues.append("Provider DB has zero providers")

    if reload_patch_present:
        recommended = (
            "Extend existing patch block inside 'elif canonical == \"reload\":' "
            "(lines ~6085-6123) to also reload provider registry / provider_model.sqlite "
            "via a small helper imported from hermesoptimizer.verify.hot_reload"
        )
    elif cli_py_exists and load_cli_config_present and reload_env_present:
        recommended = (
            "Insert new patch block inside 'elif canonical == \"reload\":' "
            "after 'from hermes_cli.config import reload_env' and before the print. "
            "Re-read config.yaml into CLI_CONFIG, then add provider-model refresh hook."
        )
    else:
        recommended = (
            "Cannot recommend a safe patch: cli.py missing expected symbols. "
            "Manual inspection required."
        )

    ready = bool(
        cli_py_exists
        and reload_patch_present
        and cli_config_global_present
        and load_cli_config_present
        and reload_env_present
        and provider_db_exists
        and provider_count > 0
        and not issues
    )

    return HotReloadReadiness(
        hermes_agent_path=agent,
        hermes_home_path=home,
        cli_py_exists=cli_py_exists,
        cli_py_size=cli_py_size,
        reload_patch_present=reload_patch_present,
        cli_config_global_present=cli_config_global_present,
        load_cli_config_present=load_cli_config_present,
        reload_env_present=reload_env_present,
        provider_db_exists=provider_db_exists,
        provider_db_path=provider_db if provider_db_exists else None,
        provider_db_provider_count=provider_count,
        provider_db_model_count=model_count,
        provider_db_providers=providers,
        recommended_patch_point=recommended,
        ready=ready,
        issues=issues,
    )


@dataclasses.dataclass(frozen=True)
class ProviderDbRefreshResult:
    provider_db_path: Path
    provider_count: int
    model_count: int
    endpoint_count: int
    source: str


def _ensure_provider_db_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS providers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            source TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS models (
            id INTEGER PRIMARY KEY,
            provider_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            source TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(provider_id, name)
        );
        CREATE TABLE IF NOT EXISTS provider_endpoints (
            id INTEGER PRIMARY KEY,
            provider_id INTEGER NOT NULL,
            endpoint_url TEXT NOT NULL,
            source TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            is_primary INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(provider_id, endpoint_url)
        );
        """
    )


def refresh_provider_db(
    hermes_home: Path | str | None = None,
    registry: ProviderRegistry | None = None,
    *,
    source: str = "liminal-registry",
) -> ProviderDbRefreshResult:
    """Upsert provider registry seed/cache into Hermes' provider DB.

    This is the tiny helper intended for the local Hermes `/reload` patch. It is
    additive and idempotent: existing provider/model rows are updated in place,
    unrelated rows are left untouched.
    """
    home = Path(hermes_home) if hermes_home else DEFAULT_HERMES_HOME
    db_path = home / "provider-db" / "provider_model.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    reg = registry or ProviderRegistry.from_cache_or_seed()

    conn = sqlite3.connect(db_path)
    try:
        _ensure_provider_db_schema(conn)
        provider_count = 0
        model_count = 0
        endpoint_count = 0
        for provider_id in reg.providers():
            provider = reg.providers_by_id[provider_id]
            conn.execute(
                """
                INSERT INTO providers (name, source, status)
                VALUES (?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    source=excluded.source,
                    status=excluded.status,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (provider.id, source, provider.status or "active"),
            )
            provider_pk = conn.execute(
                "SELECT id FROM providers WHERE name = ?",
                (provider.id,),
            ).fetchone()[0]
            provider_count += 1

            if provider.endpoint:
                conn.execute(
                    """
                    INSERT INTO provider_endpoints (provider_id, endpoint_url, source, status, is_primary)
                    VALUES (?, ?, ?, 'active', 1)
                    ON CONFLICT(provider_id, endpoint_url) DO UPDATE SET
                        source=excluded.source,
                        status=excluded.status,
                        is_primary=excluded.is_primary,
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    (provider_pk, provider.endpoint, source),
                )
                endpoint_count += 1

            for model in provider.models:
                conn.execute(
                    """
                    INSERT INTO models (provider_id, name, source, status)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(provider_id, name) DO UPDATE SET
                        source=excluded.source,
                        status=excluded.status,
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    (provider_pk, model.id, source, model.status or "active"),
                )
                model_count += 1
        conn.commit()
    finally:
        conn.close()

    return ProviderDbRefreshResult(
        provider_db_path=db_path,
        provider_count=provider_count,
        model_count=model_count,
        endpoint_count=endpoint_count,
        source=source,
    )


def format_readiness(report: HotReloadReadiness) -> str:
    lines = [
        f"hermes_agent: {report.hermes_agent_path}",
        f"hermes_home:  {report.hermes_home_path}",
        f"cli_py_exists: {report.cli_py_exists} ({report.cli_py_size} bytes)",
        f"reload_patch_present: {report.reload_patch_present}",
        f"CLI_CONFIG global: {report.cli_config_global_present}",
        f"load_cli_config(): {report.load_cli_config_present}",
        f"reload_env import: {report.reload_env_present}",
        f"provider_db_exists: {report.provider_db_exists}",
    ]
    if report.provider_db_exists:
        lines.append(f"  -> {report.provider_db_path}")
        lines.append(f"  -> providers: {report.provider_db_provider_count}")
        lines.append(f"  -> models: {report.provider_db_model_count}")
        lines.append(
            f"  -> provider names: {', '.join(report.provider_db_providers) or '(none)'}"
        )
    lines.append(f"ready: {report.ready}")
    lines.append(f"recommended_patch_point: {report.recommended_patch_point}")
    if report.issues:
        lines.append("issues:")
        for issue in report.issues:
            lines.append(f"  - {issue}")
    return "\n".join(lines)


def recommend_hermes_patch_boundary(report: HotReloadReadiness) -> dict[str, Any]:
    """Return a structured recommendation for the minimal Hermes patch."""
    return {
        "patch_location": "cli.py /reload command handler (canonical == 'reload')",
        "existing_patch": report.reload_patch_present,
        "module_global": "CLI_CONFIG",
        "function_to_call": "load_cli_config()",
        "env_reload_function": "reload_env()",
        "provider_db_path": str(report.provider_db_path) if report.provider_db_path else None,
        "proposal": (
            "After config.yaml is reloaded into CLI_CONFIG, add a call to "
            "hermesoptimizer.verify.hot_reload.refresh_provider_db(agent_instance) "
            "that re-imports the provider registry and updates the agent's model list."
        ),
    }
