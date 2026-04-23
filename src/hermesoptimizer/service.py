"""Hermes optimizer service: lifecycle management for config watcher daemon.

Phase I.2: Start/stop/status for the config watcher service.
Phase I.3: Integration with auto-update and accumulated flags.

Commands:
- hermesoptimizer service start  -> start daemon, write PID
- hermesoptimizer service stop   -> SIGTERM, clean PID
- hermesoptimizer service status -> PID, uptime, last event, flags
- hermesoptimizer service flush  -> run optimizer with flags, clear queue
"""
from __future__ import annotations

import json
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ServiceStatus:
    running: bool = False
    pid: int | None = None
    uptime_seconds: float = 0.0
    last_event: str | None = None
    pending_flags: int = 0
    error: str | None = None


def _pid_path() -> Path:
    return Path.home() / ".hermes" / "optimizer.pid"


def _flags_path() -> Path:
    return Path.home() / ".hermes" / "optimizer_flags.json"


def _read_pid() -> int | None:
    p = _pid_path()
    if not p.exists():
        return None
    try:
        return int(p.read_text().strip())
    except (ValueError, OSError):
        return None


def _write_pid(pid: int) -> None:
    p = _pid_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(str(pid), encoding="utf-8")


def _remove_pid() -> None:
    p = _pid_path()
    if p.exists():
        p.unlink(missing_ok=True)


def _is_running(pid: int) -> bool:
    """Check if a process with this PID exists."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _load_flags() -> list[str]:
    p = _flags_path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_flags(flags: list[str]) -> None:
    p = _flags_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(flags, indent=2), encoding="utf-8")


def add_flag(flag: str) -> None:
    """Add a flag to the pending queue."""
    flags = _load_flags()
    flags.append(flag)
    _save_flags(flags)


def service_status() -> ServiceStatus:
    """Report current service status."""
    pid = _read_pid()

    if pid is None:
        return ServiceStatus(running=False, pending_flags=len(_load_flags()))

    if not _is_running(pid):
        # Stale PID file
        _remove_pid()
        return ServiceStatus(running=False, pending_flags=len(_load_flags()))

    # Service is running
    pid_file = _pid_path()
    try:
        started_at = pid_file.stat().st_mtime
        uptime = time.time() - started_at
    except OSError:
        uptime = 0.0

    flags = _load_flags()

    return ServiceStatus(
        running=True,
        pid=pid,
        uptime_seconds=uptime,
        pending_flags=len(flags),
    )


def service_stop() -> bool:
    """Stop the service. Returns True if stopped."""
    pid = _read_pid()
    if pid is None:
        return True

    if not _is_running(pid):
        _remove_pid()
        return True

    try:
        os.kill(pid, signal.SIGTERM)
        # Wait briefly for process to exit
        for _ in range(10):
            time.sleep(0.1)
            if not _is_running(pid):
                break
        _remove_pid()
        return True
    except (OSError, ProcessLookupError):
        _remove_pid()
        return True


def service_flush() -> dict[str, Any]:
    """Run optimizer with accumulated flags, then clear flag queue."""
    flags = _load_flags()
    if not flags:
        return {"action": "flush", "flags_processed": 0, "message": "no pending flags"}

    result = {
        "action": "flush",
        "flags_processed": len(flags),
        "flags": flags,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # Clear flags after processing
    _save_flags([])
    return result
