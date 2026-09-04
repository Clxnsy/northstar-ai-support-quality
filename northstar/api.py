from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from .analytics import category_breakdown, failure_signals, run_summary
from .config import settings
from .db import init_db, query_all, query_one
from .orchestrator import execute_run
from .procedures import sync_to_db
from .schemas import RunRequest

app = FastAPI(title="Northstar AI Support Quality Evaluation", version="1.0.0")
RUN_TASKS: dict[str, asyncio.Task] = {}
STATIC_DIR = Path(__file__).parent / "static"


@app.on_event("startup")
def startup() -> None:
    init_db()
    sync_to_db()


@app.get("/")
def dashboard():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "database": str(settings.db_path), "procedures": str(settings.procedures_dir)}


@app.get("/api/procedures")
def procedures():
    return query_all(
        "SELECT slug,title,category,severity,source_path,updated_at FROM procedures ORDER BY category,title"
    )


@app.get("/api/runs")
def runs():
    return query_all(
        """
        SELECT r.id,r.created_at,r.finished_at,r.status,r.provider,r.model,r.ticket_count,
               COUNT(s.id) AS scored,
               ROUND(AVG(s.total),2) AS mean_score,
               ROUND(100.0*AVG(CASE WHEN s.verdict='pass' THEN 1 ELSE 0 END),2) AS pass_rate
        FROM runs r
        LEFT JOIN tickets t ON t.run_id=r.id
        LEFT JOIN scores s ON s.ticket_id=t.id
        GROUP BY r.id ORDER BY r.created_at DESC LIMIT 50
        """
    )


@app.post("/api/runs", status_code=202)
async def create_run(request: RunRequest):
    run_id = str(uuid.uuid4())
    task = asyncio.create_task(execute_run(request, run_id=run_id))
    RUN_TASKS[run_id] = task

    def _cleanup(done: asyncio.Task) -> None:
        RUN_TASKS.pop(run_id, None)
        if not done.cancelled():
            # Consume the exception; execute_run has already persisted the failure on the run row.
            done.exception()

    task.add_done_callback(_cleanup)
    return {"run_id": run_id, "status": "running"}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    run = query_one("SELECT * FROM runs WHERE id=?", (run_id,))
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    run["summary"] = run_summary(run_id)
    run["categories"] = category_breakdown(run_id)
    run["failure_signals"] = failure_signals(run_id)
    run["tickets"] = query_all(
        """
        SELECT t.id,t.ordinal,t.category,t.severity,t.title,t.body,t.expected_procedure,
               r.answer,r.latency_ms,s.total,s.verdict,s.critical_failure,
               d.id AS defect_id,d.severity AS defect_severity,d.defect_type,d.title AS defect_title
        FROM tickets t
        LEFT JOIN responses r ON r.ticket_id=t.id
        LEFT JOIN scores s ON s.ticket_id=t.id
        LEFT JOIN defects d ON d.ticket_id=t.id
        WHERE t.run_id=? ORDER BY t.ordinal
        """,
        (run_id,),
    )
    return run


@app.get("/api/defects")
def defects(run_id: str | None = None):
    if run_id:
        return query_all("SELECT * FROM defects WHERE run_id=? ORDER BY created_at DESC", (run_id,))
    return query_all("SELECT * FROM defects ORDER BY created_at DESC LIMIT 100")
