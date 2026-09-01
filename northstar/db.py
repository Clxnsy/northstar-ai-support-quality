from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .config import settings


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    judge_provider TEXT NOT NULL,
    judge_model TEXT NOT NULL,
    ticket_count INTEGER NOT NULL,
    config_json TEXT NOT NULL,
    error TEXT
);

CREATE TABLE IF NOT EXISTS tickets (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    expected_procedure TEXT NOT NULL,
    expected_outcome TEXT NOT NULL,
    adversarial_detail TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id TEXT NOT NULL UNIQUE REFERENCES tickets(id) ON DELETE CASCADE,
    answer TEXT NOT NULL,
    actions_json TEXT NOT NULL,
    escalation TEXT,
    confidence REAL NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    latency_ms INTEGER NOT NULL,
    retrieved_procedures_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id TEXT NOT NULL UNIQUE REFERENCES tickets(id) ON DELETE CASCADE,
    total REAL NOT NULL,
    accuracy REAL NOT NULL,
    procedure_adherence REAL NOT NULL,
    safety REAL NOT NULL,
    completeness REAL NOT NULL,
    communication REAL NOT NULL,
    hallucination_risk REAL NOT NULL,
    critical_failure INTEGER NOT NULL,
    critical_failure_reason TEXT,
    judge_json TEXT NOT NULL,
    deterministic_json TEXT NOT NULL,
    verdict TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS defects (
    id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    severity TEXT NOT NULL,
    defect_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    reproduction_steps_json TEXT NOT NULL,
    expected_behavior TEXT NOT NULL,
    actual_behavior TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    suggested_fix TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS procedures (
    slug TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    source_path TEXT NOT NULL,
    checksum TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    body TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS procedure_fts USING fts5(
    slug UNINDEXED,
    title,
    category,
    body,
    content='procedures',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS procedures_ai AFTER INSERT ON procedures BEGIN
  INSERT INTO procedure_fts(rowid, slug, title, category, body)
  VALUES (new.rowid, new.slug, new.title, new.category, new.body);
END;
CREATE TRIGGER IF NOT EXISTS procedures_ad AFTER DELETE ON procedures BEGIN
  INSERT INTO procedure_fts(procedure_fts, rowid, slug, title, category, body)
  VALUES('delete', old.rowid, old.slug, old.title, old.category, old.body);
END;
CREATE TRIGGER IF NOT EXISTS procedures_au AFTER UPDATE ON procedures BEGIN
  INSERT INTO procedure_fts(procedure_fts, rowid, slug, title, category, body)
  VALUES('delete', old.rowid, old.slug, old.title, old.category, old.body);
  INSERT INTO procedure_fts(rowid, slug, title, category, body)
  VALUES (new.rowid, new.slug, new.title, new.category, new.body);
END;

CREATE INDEX IF NOT EXISTS idx_tickets_run ON tickets(run_id);
CREATE INDEX IF NOT EXISTS idx_defects_run ON defects(run_id);
CREATE INDEX IF NOT EXISTS idx_scores_verdict ON scores(verdict);
"""


def _connect(path: Path | None = None) -> sqlite3.Connection:
    db_path = Path(path or settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(path: Path | None = None) -> None:
    with _connect(path) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def connection(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    conn = _connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute(sql: str, params: tuple[Any, ...] = ()) -> None:
    with connection() as conn:
        conn.execute(sql, params)


def query_all(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def query_one(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    rows = query_all(sql, params)
    return rows[0] if rows else None


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
