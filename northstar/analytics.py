from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from .db import connection, query_all, query_one


def run_summary(run_id: str) -> dict[str, Any]:
    aggregate = (
        query_one(
            """
        SELECT
          COUNT(*) AS tickets,
          SUM(CASE WHEN s.verdict='pass' THEN 1 ELSE 0 END) AS passed,
          SUM(CASE WHEN s.verdict='fail' THEN 1 ELSE 0 END) AS failed,
          ROUND(AVG(s.total),2) AS mean_score,
          SUM(s.critical_failure) AS critical_failures
        FROM tickets t
        JOIN scores s ON s.ticket_id=t.id
        WHERE t.run_id=?
        """,
            (run_id,),
        )
        or {}
    )
    tickets = int(aggregate.get("tickets") or 0)
    passed = int(aggregate.get("passed") or 0)
    aggregate["pass_rate"] = round((passed / tickets * 100) if tickets else 0, 2)
    for key in ("passed", "failed", "mean_score", "critical_failures"):
        aggregate[key] = aggregate.get(key) or 0
    aggregate["defects_by_severity"] = query_all(
        "SELECT severity, COUNT(*) AS count FROM defects WHERE run_id=? GROUP BY severity",
        (run_id,),
    )
    aggregate["top_failure_types"] = query_all(
        """
        SELECT defect_type, COUNT(*) AS count
        FROM defects WHERE run_id=?
        GROUP BY defect_type ORDER BY count DESC, defect_type LIMIT 5
        """,
        (run_id,),
    )
    return aggregate


def category_breakdown(run_id: str) -> list[dict[str, Any]]:
    return query_all(
        """
        SELECT t.category,
               COUNT(*) AS tickets,
               ROUND(AVG(s.total),2) AS mean_score,
               ROUND(100.0*AVG(CASE WHEN s.verdict='pass' THEN 1 ELSE 0 END),2) AS pass_rate,
               SUM(s.critical_failure) AS critical_failures
        FROM tickets t JOIN scores s ON s.ticket_id=t.id
        WHERE t.run_id=?
        GROUP BY t.category ORDER BY pass_rate ASC, mean_score ASC
        """,
        (run_id,),
    )


def failure_signals(run_id: str) -> list[dict[str, Any]]:
    rows = query_all(
        """
        SELECT s.deterministic_json, s.judge_json
        FROM tickets t JOIN scores s ON s.ticket_id=t.id
        WHERE t.run_id=? AND s.verdict='fail'
        """,
        (run_id,),
    )
    import json

    counter: Counter[str] = Counter()
    for row in rows:
        deterministic = json.loads(row["deterministic_json"])
        for step in deterministic.get("required_steps_missed", []):
            counter[f"missed_step: {step}"] += 1
        for action in deterministic.get("forbidden_actions_hit", []):
            counter[f"forbidden_action: {action}"] += 1
        if deterministic.get("escalation_required") and not deterministic.get(
            "escalation_detected"
        ):
            counter["missed_escalation"] += 1
        judge = json.loads(row["judge_json"])
        for dimension in (
            "accuracy",
            "procedure_adherence",
            "safety",
            "completeness",
            "hallucination_risk",
        ):
            if judge.get(dimension, {}).get("score", 5) < 3:
                counter[f"low_{dimension}"] += 1
    return [{"signal": key, "count": value} for key, value in counter.most_common(12)]


def run_dataframe(run_id: str) -> pd.DataFrame:
    with connection() as conn:
        df = pd.read_sql_query(
            """
            SELECT t.id AS ticket_id, t.category, t.severity, t.title,
                   r.answer, r.model AS responder_model, r.latency_ms,
                   s.total, s.verdict, s.accuracy, s.procedure_adherence,
                   s.safety, s.completeness, s.communication, s.hallucination_risk,
                   s.critical_failure, d.defect_type, d.severity AS defect_severity
            FROM tickets t
            LEFT JOIN responses r ON r.ticket_id=t.id
            LEFT JOIN scores s ON s.ticket_id=t.id
            LEFT JOIN defects d ON d.ticket_id=t.id
            WHERE t.run_id=? ORDER BY t.ordinal
            """,
            conn,
            params=(run_id,),
        )
    # Spreadsheet programs interpret leading formula characters even in quoted CSV cells.
    for column in df.select_dtypes(include=["object", "string"]).columns:
        df[column] = df[column].map(
            lambda value: (
                "'" + value
                if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@"))
                else value
            )
        )
    return df


def export_run_csv(run_id: str, output: Path) -> Path:
    df = run_dataframe(run_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)
    return output
