# Hermes Optimizer

Hermes Optimizer is a local scaffold for scanning Hermes logs, routing catalog records, validating them, and exporting a small canonical catalog.

## What is in this repo

- SQLite-backed catalog storage
- Minimal CLI for initializing the database and exporting records
- Foundational dataclasses and report helpers
- Test coverage for the storage and export path

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
hermesoptimizer init-db --db catalog.db
```

## Layout

- `src/hermesoptimizer/catalog.py` — SQLite schema and CRUD helpers
- `src/hermesoptimizer/report/markdown.py` — Markdown report writer
- `src/hermesoptimizer/run_standalone.py` — CLI entry point
- `tests/` — unit tests for the scaffold

This is an initial implementation, not the full planned system.
