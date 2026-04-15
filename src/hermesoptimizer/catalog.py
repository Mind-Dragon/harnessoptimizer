from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Sequence
import json
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  base_url TEXT NOT NULL,
  auth_type TEXT NOT NULL,
  auth_key TEXT NOT NULL,
  lane TEXT,
  region TEXT,
  capabilities TEXT NOT NULL,
  context_window INTEGER NOT NULL DEFAULT 0,
  source TEXT NOT NULL,
  confidence TEXT NOT NULL,
  raw_text TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(provider, model, base_url, lane)
);

CREATE TABLE IF NOT EXISTS findings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_path TEXT,
  line_num INTEGER,
  category TEXT NOT NULL,
  severity TEXT NOT NULL,
  kind TEXT,
  fingerprint TEXT,
  sample_text TEXT,
  count INTEGER DEFAULT 1,
  confidence TEXT,
  router_note TEXT,
  lane TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  mode TEXT NOT NULL,
  started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  finished_at TIMESTAMP,
  record_count INTEGER DEFAULT 0,
  finding_count INTEGER DEFAULT 0,
  status TEXT DEFAULT 'running',
  metrics_json TEXT
);
"""


@dataclass(slots=True)
class Record:
    provider: str
    model: str
    base_url: str
    auth_type: str
    auth_key: str
    lane: str | None
    region: str | None
    capabilities: list[str]
    context_window: int
    source: str
    confidence: str
    raw_text: str | None = None

    def to_row(self) -> tuple:
        return (
            self.provider,
            self.model,
            self.base_url,
            self.auth_type,
            self.auth_key,
            self.lane,
            self.region,
            json.dumps(self.capabilities, sort_keys=True),
            self.context_window,
            self.source,
            self.confidence,
            self.raw_text,
        )


@dataclass(slots=True)
class Finding:
    file_path: str | None
    line_num: int | None
    category: str
    severity: str
    kind: str | None = None
    fingerprint: str | None = None
    sample_text: str | None = None
    count: int = 1
    confidence: str | None = None
    router_note: str | None = None
    lane: str | None = None

    def to_row(self) -> tuple:
        return (
            self.file_path,
            self.line_num,
            self.category,
            self.severity,
            self.kind,
            self.fingerprint,
            self.sample_text,
            self.count,
            self.confidence,
            self.router_note,
            self.lane,
        )


@dataclass(slots=True)
class Run:
    id: int
    mode: str
    started_at: str | None
    finished_at: str | None
    record_count: int
    finding_count: int
    status: str


def connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | Path) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
        _ensure_column(conn, "runs", "metrics_json", "TEXT")


def _upsert(
    conn: sqlite3.Connection,
    sql: str,
    values: Sequence,
) -> None:
    conn.execute(sql, values)


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def upsert_record(db_path: str | Path, record: Record) -> None:
    sql = """
    INSERT INTO records (
      provider, model, base_url, auth_type, auth_key, lane, region,
      capabilities, context_window, source, confidence, raw_text
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(provider, model, base_url, lane) DO UPDATE SET
      auth_type=excluded.auth_type,
      auth_key=excluded.auth_key,
      region=excluded.region,
      capabilities=excluded.capabilities,
      context_window=excluded.context_window,
      source=excluded.source,
      confidence=excluded.confidence,
      raw_text=excluded.raw_text
    """
    with connect(db_path) as conn:
        _upsert(conn, sql, record.to_row())
        conn.commit()


def upsert_finding(db_path: str | Path, finding: Finding) -> None:
    sql = """
    INSERT INTO findings (
      file_path, line_num, category, severity, kind, fingerprint,
      sample_text, count, confidence, router_note, lane
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    with connect(db_path) as conn:
        conn.execute(sql, finding.to_row())
        conn.commit()


def get_records(db_path: str | Path) -> list[dict]:
    with connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM records ORDER BY id").fetchall()
    output: list[dict] = []
    for row in rows:
        data = dict(row)
        data["capabilities"] = json.loads(data["capabilities"])
        output.append(data)
    return output


def get_findings(db_path: str | Path) -> list[dict]:
    with connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM findings ORDER BY id").fetchall()
    return [dict(row) for row in rows]


def get_run(db_path: str | Path, run_id: int) -> Run | None:
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        return None
    return Run(**dict(row))


def start_run(db_path: str | Path, mode: str) -> int:
    with connect(db_path) as conn:
        cur = conn.execute("INSERT INTO runs (mode) VALUES (?)", (mode,))
        conn.commit()
        return int(cur.lastrowid)


def finish_run(
    db_path: str | Path,
    run_id: int,
    *,
    record_count: int,
    finding_count: int,
    metrics: dict[str, int] | None = None,
    status: str = "completed",
) -> None:
    with connect(db_path) as conn:
        conn.execute(
            """
            UPDATE runs
            SET finished_at = CURRENT_TIMESTAMP,
                record_count = ?,
                finding_count = ?,
                status = ?,
                metrics_json = ?
            WHERE id = ?
            """,
            (record_count, finding_count, status, json.dumps(metrics, sort_keys=True) if metrics is not None else None, run_id),
        )
        conn.commit()


def get_run_history(db_path: str | Path, limit: int = 10) -> list[dict]:
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM runs
            WHERE status = 'completed' AND metrics_json IS NOT NULL
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    history: list[dict] = []
    for row in rows:
        data = dict(row)
        metrics_json = data.get("metrics_json")
        data["metrics"] = json.loads(metrics_json) if metrics_json else {}
        history.append(data)
    return history
