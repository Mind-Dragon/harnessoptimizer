"""Hermes optimizer service: lifecycle management for the config watcher daemon.

Phase I.2: Start/stop/status for the config watcher service.
Phase I.3: Integration with auto-update and accumulated flags.
"""
from __future__ import annotations

import json
import os
import signal
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hermesoptimizer.config_watcher import create_watcher, start_watching


@dataclass
class ServiceStatus:
    running: bool = False
    pid: int | None = None
    uptime_seconds: float = 0.0
    last_event: str | None = None
    pending_flags: int = 0
    error: str | None = None


_SERVICE_THREAD: threading.Thread | None = None
_SERVICE_STOP: threading.Event | None = None
_SERVICE_STARTED_AT: float | None = None
_SERVICE_LAST_EVENT: str | None = None


def _pid_path() -> Path:
    return Path.home() / ".hermes" / "optimizer.pid"


def _flags_path() -> Path:
    return Path.home() / ".hermes" / "optimizer_flags.json"


def _state_path() -> Path:
    return Path.home() / ".hermes" / "optimizer.state.json"


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


def _write_state(last_event: str | None = None) -> None:
    state = {
        "pid": _read_pid(),
        "started_at": _SERVICE_STARTED_AT,
        "last_event": last_event or _SERVICE_LAST_EVENT,
        "pending_flags": len(_load_flags()),
    }
    p = _state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2), encoding="utf-8")


def add_flag(flag: str) -> None:
    """Add a flag to the pending queue."""
    flags = _load_flags()
    flags.append(flag)
    _save_flags(flags)
    _write_state(flag)


def service_status() -> ServiceStatus:
    """Report current service status."""
    pid = _read_pid()
    if pid is None:
        return ServiceStatus(running=False, pending_flags=len(_load_flags()))

    if not _is_running(pid):
        _remove_pid()
        return ServiceStatus(running=False, pending_flags=len(_load_flags()))

    try:
        started_at = _pid_path().stat().st_mtime
        uptime = time.time() - started_at
    except OSError:
        uptime = 0.0

    flags = _load_flags()
    state = _load_state()

    return ServiceStatus(
        running=True,
        pid=pid,
        uptime_seconds=uptime,
        last_event=state.get("last_event"),
        pending_flags=len(flags),
    )


def _load_state() -> dict[str, Any]:
    p = _state_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def service_start(config_dir: Path | None = None, poll_interval: float = 2.0) -> ServiceStatus:
    """Start the watcher service and write the PID file.

    This is foreground-safe for tests, and also initializes a daemon thread so
    the watcher keeps running in-process when used from a long-lived command.
    """
    global _SERVICE_THREAD, _SERVICE_STOP, _SERVICE_STARTED_AT, _SERVICE_LAST_EVENT

    pid = _read_pid()
    if pid is not None and _is_running(pid):
        return service_status()

    _SERVICE_STARTED_AT = time.time()
    _SERVICE_LAST_EVENT = "service started"
    _write_pid(os.getpid())
    _write_state(_SERVICE_LAST_EVENT)

    if _SERVICE_STOP is None:
        _SERVICE_STOP = threading.Event()
    else:
        _SERVICE_STOP.clear()

    watcher = create_watcher(
        config_dir=config_dir,
        poll_interval=poll_interval,
        origin_pid=os.getpid(),
    )
    watcher.allow_current_process_events = True

    def _repair_callback(file_path: Path) -> str | None:
        global _SERVICE_LAST_EVENT
        _SERVICE_LAST_EVENT = f"auto-repair: {file_path.name}"
        _write_state(_SERVICE_LAST_EVENT)
        return _SERVICE_LAST_EVENT

    def _run() -> None:
        try:
            start_watching(
                watcher,
                repair_callback=_repair_callback,
                log_path=(config_dir or Path.home() / ".hermes") / "config_watch.log" if config_dir else None,
                stop_event=_SERVICE_STOP,
            )
        finally:
            _write_state("service stopped")

    if _SERVICE_THREAD is None or not _SERVICE_THREAD.is_alive():
        _SERVICE_THREAD = threading.Thread(target=_run, name="hermesoptimizer-config-watcher", daemon=True)
        _SERVICE_THREAD.start()

    return service_status()


def service_stop() -> bool:
    """Stop the service. Returns True if stopped."""
    global _SERVICE_THREAD, _SERVICE_STOP, _SERVICE_LAST_EVENT

    pid = _read_pid()
    if pid is None:
        return True

    if _SERVICE_STOP is not None:
        _SERVICE_STOP.set()

    if _SERVICE_THREAD is not None and _SERVICE_THREAD.is_alive():
        _SERVICE_THREAD.join(timeout=2.0)

    # If the PID belongs to this current process, don't SIGTERM ourselves.
    if pid != os.getpid() and _is_running(pid):
        try:
            os.kill(pid, signal.SIGTERM)
        except (OSError, ProcessLookupError):
            pass

    _remove_pid()
    _SERVICE_LAST_EVENT = "service stopped"
    _write_state(_SERVICE_LAST_EVENT)
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

    _save_flags([])
    _write_state("flags flushed")
    return result
