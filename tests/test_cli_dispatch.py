from __future__ import annotations

import argparse

from hermesoptimizer import cli


class _Sentinel(Exception):
    pass


def test_dispatch_routes_to_registered_handler(monkeypatch) -> None:
    seen: list[str] = []

    def fake_handler(args: argparse.Namespace) -> int:
        seen.append(args.command)
        return 17

    monkeypatch.setattr(cli, "HANDLERS", {"verify-endpoints": fake_handler})

    rc = cli.dispatch(argparse.Namespace(command="verify-endpoints"))

    assert rc == 17
    assert seen == ["verify-endpoints"]


def test_dispatch_missing_command_returns_usage_code(capsys, monkeypatch) -> None:
    monkeypatch.setattr(cli, "HANDLERS", {"run": lambda _args: 0})

    rc = cli.dispatch(argparse.Namespace(command=None))

    captured = capsys.readouterr()
    assert rc == 1
    assert "Usage:" in captured.out
    assert "run" in captured.out


def test_dispatch_unknown_command_returns_error_code(capsys, monkeypatch) -> None:
    monkeypatch.setattr(cli, "HANDLERS", {"run": lambda _args: 0})

    rc = cli.dispatch(argparse.Namespace(command="not-real"))

    captured = capsys.readouterr()
    assert rc == 2
    assert "Unknown command: not-real" in captured.out
