"""
Phase 0 Hermes inventory loader.

Loads Hermes configuration once and produces a HermesInventory dataclass
with all the paths the scanner will need: config, session, log, cache,
database, runtime, and gateway.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os

import yaml


@dataclass(slots=True)
class HermesInventory:
    config_path: Path | None = None
    session_paths: list[Path] = field(default_factory=list)
    log_paths: list[Path] = field(default_factory=list)
    cache_paths: list[Path] = field(default_factory=list)
    db_paths: list[Path] = field(default_factory=list)
    runtime_paths: list[Path] = field(default_factory=list)
    gateway_entries: list[str] = field(default_factory=list)  # commands

    def all_paths(self) -> list[Path]:
        """Return every filesystem path in the inventory."""
        paths: list[Path] = []
        if self.config_path:
            paths.append(self.config_path)
        paths.extend(self.session_paths)
        paths.extend(self.log_paths)
        paths.extend(self.cache_paths)
        paths.extend(self.db_paths)
        paths.extend(self.runtime_paths)
        return paths


def _expand(p: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(p)))


def load_hermes_inventory(config_path: str | Path) -> HermesInventory:
    """
    Load a Hermes config.yaml and extract all known paths from it.

    This is the single canonical place where Hermes config structure
    is read for discovery purposes. Parsing for findings happens elsewhere.
    """
    p = Path(config_path)
    if not p.exists():
        return HermesInventory()

    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}

    inv = HermesInventory()

    # config path is the file itself
    inv.config_path = p

    # session paths
    session_cfg = data.get("session", {})
    if isinstance(session_cfg, dict):
        sp = session_cfg.get("path")
        if sp:
            inv.session_paths.append(_expand(sp))
    elif isinstance(session_cfg, str):
        inv.session_paths.append(_expand(session_cfg))

    # log paths
    log_cfg = data.get("log", {})
    if isinstance(log_cfg, dict):
        lp = log_cfg.get("path")
        if lp:
            inv.log_paths.append(_expand(lp))
    elif isinstance(log_cfg, str):
        inv.log_paths.append(_expand(log_cfg))

    # cache paths
    cache_cfg = data.get("cache", {})
    if isinstance(cache_cfg, dict):
        cp = cache_cfg.get("path")
        if cp:
            inv.cache_paths.append(_expand(cp))
    elif isinstance(cache_cfg, str):
        inv.cache_paths.append(_expand(cache_cfg))

    # database paths
    db_cfg = data.get("database", {})
    if isinstance(db_cfg, dict):
        dp = db_cfg.get("path")
        if dp:
            inv.db_paths.append(_expand(dp))
    elif isinstance(db_cfg, str):
        inv.db_paths.append(_expand(db_cfg))

    # runtime paths
    runtime_cfg = data.get("runtime", {})
    if isinstance(runtime_cfg, dict):
        rp = runtime_cfg.get("path")
        if rp:
            inv.runtime_paths.append(_expand(rp))

    # gateway entries
    gateway_cfg = data.get("gateway", {})
    if isinstance(gateway_cfg, dict):
        cmd = gateway_cfg.get("status_command") or gateway_cfg.get("command")
        if cmd:
            inv.gateway_entries.append(cmd)

    return inv
