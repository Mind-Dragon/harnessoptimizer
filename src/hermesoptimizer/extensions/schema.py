"""Extension registry schema for managed HermesOptimizer surfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ExtensionType(str, Enum):
    CONFIG = "config"
    SKILL = "skill"
    SCRIPT = "script"
    CRON = "cron"
    VAULT_PLUGIN = "vault_plugin"
    SIDECAR = "sidecar"
    COMMAND_SURFACE = "command_surface"


class Ownership(str, Enum):
    REPO_ONLY = "repo_only"
    REPO_EXTERNAL = "repo_external"
    EXTERNAL_RUNTIME = "external_runtime"


@dataclass(frozen=True)
class ExtensionEntry:
    """One managed extension surface."""

    id: str
    type: ExtensionType
    description: str
    source_path: str
    target_paths: list[str] = field(default_factory=list)
    verify_command: str | None = None
    ownership: Ownership = Ownership.REPO_ONLY
    selected: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("ExtensionEntry id must be non-empty")
        if self.ownership != Ownership.EXTERNAL_RUNTIME and not self.source_path:
            raise ValueError("ExtensionEntry source_path must be non-empty for repo-owned extensions")

    def source_exists(self, repo_root: Path) -> bool:
        return (repo_root / self.source_path).exists()
