"""CLI package – aggregates all command-group modules."""
from __future__ import annotations

import argparse
from typing import Callable

from hermesoptimizer.cli import legacy, v091, workflow, orphan


# ----------------------------------------------------------------------
# add_subparsers – delegates to every module's registrar
# ----------------------------------------------------------------------

def add_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Register CLI subcommands from all four command-group modules."""
    legacy.add_subparsers(subparsers)
    v091.add_subparsers(subparsers)
    workflow.add_subparsers(subparsers)
    orphan.add_subparsers(subparsers)


# ----------------------------------------------------------------------
# Combined HANDLERS – dynamically merged from all per-module dicts.
#
# workflow and orphan populate their HANDLERS as a side-effect of
# add_subparsers(), so we build the union lazily on first access (and
# refresh it on every access so that late-registered commands are
# included).
# ----------------------------------------------------------------------

class _CombinedHandlers(dict[str, Callable[[argparse.Namespace], int]]):
    """Mutable dict that always reflects the current union of all submodules."""

    def __iter__(self):
        return iter(self.keys())

    def items(self):
        return dict(self).items()

    def values(self):
        return dict(self).values()

    def __repr__(self):
        return repr(dict(self))

    def __str__(self):
        return str(dict(self))

    def __len__(self):
        return len(dict(self))

    def __bool__(self):
        return bool(dict(self))

    def __contains__(self, key):
        return key in dict(self)

    def __getitem__(self, key):
        return dict(self)[key]

    def __reduce__(self):
        return (dict, (dict(self),))

    def __call__(self):
        """Synonym for dict(self) – handy for quick merged-view access."""
        return dict(self)


def _build() -> dict[str, Callable[[argparse.Namespace], int]]:
    merged: dict[str, Callable[[argparse.Namespace], int]] = {}
    merged.update(legacy.HANDLERS)
    merged.update(v091.HANDLERS)
    merged.update(workflow.HANDLERS)
    merged.update(orphan.HANDLERS)
    return merged


#: Combined handler registry.  Reflects the live state of all four
#: submodule dicts, including handlers registered as a side-effect of
#: add_subparsers().
HANDLERS: _CombinedHandlers = _CombinedHandlers(_build())


# Ensure every access rebuilds the view so that post-add_subparsers()
# registrations are visible.
class _RebuiltHANDLERS(_CombinedHandlers):
    def __getitem__(self, key):
        return _build()[key]

    def __contains__(self, key):
        return key in _build()

    def __iter__(self):
        return iter(_build())

    def __len__(self):
        return len(_build())

    def keys(self):
        return _build().keys()

    def items(self):
        return _build().items()

    def values(self):
        return _build().values()

    def get(self, key, default=None):
        return _build().get(key, default)

    def __repr__(self):
        return repr(_build())

    def __str__(self):
        return str(_build())

    def __bool__(self):
        return bool(_build())

    def __reduce__(self):
        return (dict, (_build(),))


HANDLERS = _RebuiltHANDLERS(_build())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hermesoptimizer")
    sub = parser.add_subparsers(dest="command")
    add_subparsers(sub)
    return parser


def dispatch(args: argparse.Namespace) -> int:
    if args.command is None:
        print("Usage: hermesoptimizer <command> [args]")
        commands = sorted(HANDLERS.keys())
        if commands:
            print("Commands:", ", ".join(commands))
        return 1
    handler = HANDLERS.get(args.command)
    if handler is None:
        print(f"Unknown command: {args.command}")
        return 2
    return handler(args)
