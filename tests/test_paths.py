"""Tests for central path resolution."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from hermesoptimizer import paths


class TestPaths:
    def test_default_base_dir(self) -> None:
        base = paths.get_base_dir()
        assert base.name == ".hoptimizer"
        assert base.parent == Path.home()

    def test_env_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.get("HOPTIMIZER_HOME")
            os.environ["HOPTIMIZER_HOME"] = tmp
            try:
                base = paths.get_base_dir()
                assert base == Path(tmp)
            finally:
                if old is None:
                    os.environ.pop("HOPTIMIZER_HOME", None)
                else:
                    os.environ["HOPTIMIZER_HOME"] = old

    def test_db_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["HOPTIMIZER_HOME"] = tmp
            try:
                db = paths.get_db_path()
                assert db.name == "catalog.db"
                assert db.parent.name == "db"
            finally:
                os.environ.pop("HOPTIMIZER_HOME", None)

    def test_ensure_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["HOPTIMIZER_HOME"] = tmp
            try:
                paths.ensure_dirs()
                assert (Path(tmp) / "db").exists()
                assert (Path(tmp) / "logs").exists()
                assert (Path(tmp) / "reports").exists()
            finally:
                os.environ.pop("HOPTIMIZER_HOME", None)
