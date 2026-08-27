from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .config import settings
from .db import connection


@dataclass(frozen=True)
class Procedure:
    slug: str
    title: str
    category: str
    severity: str
    required_steps: list[str]
    forbidden_actions: list[str]
    escalation_conditions: list[str]
    body: str
    source_path: str

    def as_context(self) -> str:
        return (
            f"PROCEDURE: {self.title} ({self.slug})\n"
            f"CATEGORY: {self.category}\nSEVERITY: {self.severity}\n"
            f"REQUIRED STEPS: {json.dumps(self.required_steps)}\n"
            f"FORBIDDEN ACTIONS: {json.dumps(self.forbidden_actions)}\n"
            f"ESCALATION CONDITIONS: {json.dumps(self.escalation_conditions)}\n\n"
            f"{self.body.strip()}"
        )


def _parse_markdown(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path} is missing YAML front matter")
    _, front, body = text.split("---", 2)
    metadata = yaml.safe_load(front) or {}
    required = {"slug", "title", "category", "severity", "required_steps"}
    missing = required - set(metadata)
    if missing:
        raise ValueError(f"{path} missing metadata: {', '.join(sorted(missing))}")
    return metadata, body.strip()


def load_all(directory: Path | None = None) -> list[Procedure]:
    directory = Path(directory or settings.procedures_dir)
    procedures: list[Procedure] = []
    for path in sorted(directory.glob("*.md")):
        metadata, body = _parse_markdown(path)
        procedures.append(
            Procedure(
                slug=str(metadata["slug"]),
                title=str(metadata["title"]),
                category=str(metadata["category"]),
                severity=str(metadata["severity"]),
                required_steps=[str(x) for x in metadata.get("required_steps", [])],
                forbidden_actions=[str(x) for x in metadata.get("forbidden_actions", [])],
                escalation_conditions=[str(x) for x in metadata.get("escalation_conditions", [])],
                body=body,
                source_path=str(path),
            )
        )
    if not procedures:
        raise RuntimeError(f"No procedures found in {directory.resolve()}")
    return procedures


def sync_to_db(directory: Path | None = None) -> int:
    now = datetime.now(timezone.utc).isoformat()
    procedures = load_all(directory)
    with connection() as conn:
        for procedure in procedures:
            raw = Path(procedure.source_path).read_bytes()
            checksum = hashlib.sha256(raw).hexdigest()
            metadata = {
                "required_steps": procedure.required_steps,
                "forbidden_actions": procedure.forbidden_actions,
                "escalation_conditions": procedure.escalation_conditions,
            }
            conn.execute(
                """
                INSERT INTO procedures(slug,title,category,severity,source_path,checksum,metadata_json,body,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(slug) DO UPDATE SET
                  title=excluded.title, category=excluded.category, severity=excluded.severity,
                  source_path=excluded.source_path, checksum=excluded.checksum,
                  metadata_json=excluded.metadata_json, body=excluded.body, updated_at=excluded.updated_at
                """,
                (
                    procedure.slug,
                    procedure.title,
                    procedure.category,
                    procedure.severity,
                    procedure.source_path,
                    checksum,
                    json.dumps(metadata),
                    procedure.body,
                    now,
                ),
            )
    return len(procedures)


def get_procedure(slug: str) -> Procedure:
    with connection() as conn:
        row = conn.execute("SELECT * FROM procedures WHERE slug=?", (slug,)).fetchone()
    if row is None:
        raise KeyError(f"Unknown procedure: {slug}")
    metadata = json.loads(row["metadata_json"])
    return Procedure(
        slug=row["slug"],
        title=row["title"],
        category=row["category"],
        severity=row["severity"],
        required_steps=metadata.get("required_steps", []),
        forbidden_actions=metadata.get("forbidden_actions", []),
        escalation_conditions=metadata.get("escalation_conditions", []),
        body=row["body"],
        source_path=row["source_path"],
    )


def _fts_query(text: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9_-]{3,}", text.lower())
    stop = {"the", "and", "for", "with", "that", "this", "from", "user", "issue", "cannot"}
    terms = [token for token in tokens if token not in stop][:14]
    return " OR ".join(f'"{term}"' for term in terms)


def retrieve(query: str, limit: int = 3) -> list[Procedure]:
    fts = _fts_query(query)
    with connection() as conn:
        if fts:
            rows = conn.execute(
                """
                SELECT p.* FROM procedure_fts f
                JOIN procedures p ON p.rowid=f.rowid
                WHERE procedure_fts MATCH ?
                ORDER BY bm25(procedure_fts)
                LIMIT ?
                """,
                (fts, limit),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM procedures ORDER BY title LIMIT ?", (limit,)).fetchall()
    procedures: list[Procedure] = []
    for row in rows:
        metadata = json.loads(row["metadata_json"])
        procedures.append(
            Procedure(
                slug=row["slug"],
                title=row["title"],
                category=row["category"],
                severity=row["severity"],
                required_steps=metadata.get("required_steps", []),
                forbidden_actions=metadata.get("forbidden_actions", []),
                escalation_conditions=metadata.get("escalation_conditions", []),
                body=row["body"],
                source_path=row["source_path"],
            )
        )
    return procedures
