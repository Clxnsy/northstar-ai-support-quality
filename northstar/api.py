from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response

from .analytics import category_breakdown, failure_signals, run_dataframe, run_summary
from .config import settings
from .copilot import create_case, draft_case, get_case, save_review
from .db import connection, init_db, query_all, query_one
from .orchestrator import create_run as register_run
from .orchestrator import execute_run
from .procedures import get_procedure, sync_to_db
from .providers import ProviderError, build_provider
from .schemas import CaseRequest, CaseReview, ModelListRequest, RunRequest

RUN_TASKS: dict[str, asyncio.Task] = {}
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    sync_to_db()
    with connection() as conn:
        conn.execute(
            "UPDATE runs SET status='failed',finished_at=?,error=? WHERE status IN ('queued','running')",
            (
                datetime.now(UTC).isoformat(),
                "Run interrupted by a previous shutdown; start a new evaluation to retry",
            ),
        )
        conn.execute(
            "UPDATE support_cases SET status='failed',error='Draft interrupted by shutdown; create a new draft to retry' WHERE status='drafting'"
        )
    yield
    tasks = list(RUN_TASKS.values())
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(title="Northstar Support Copilot", version="1.1.0", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # FastAPI's default errors can include raw request input, including API keys.
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
                for error in exc.errors()
            ]
        },
    )


@app.get("/")
def dashboard():
    return FileResponse(STATIC_DIR / "support.html")


@app.get("/quality-lab")
def quality_lab():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/models")
async def models(request: ModelListRequest):
    try:
        return {"models": await build_provider(request).list_models()}
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None


@app.get("/api/cases")
def cases():
    return query_all(
        "SELECT id,title,status,provider,model,created_at,updated_at FROM support_cases ORDER BY updated_at DESC LIMIT 100"
    )


@app.post("/api/cases", status_code=202)
async def new_case(request: CaseRequest):
    try:
        case_id = create_case(request)
    except KeyError:
        raise HTTPException(status_code=422, detail="Unknown procedure slug") from None
    task = asyncio.create_task(draft_case(request, case_id))
    RUN_TASKS[case_id] = task

    def cleanup(done: asyncio.Task):
        RUN_TASKS.pop(case_id, None)
        if not done.cancelled():
            done.exception()

    task.add_done_callback(cleanup)
    return {"case_id": case_id, "status": "drafting"}


@app.get("/api/cases/{case_id}")
def case_detail(case_id: str):
    case = get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@app.post("/api/cases/{case_id}/review")
def review_case(case_id: str, request: CaseReview):
    try:
        save_review(case_id, request)
    except KeyError:
        raise HTTPException(status_code=404, detail="Case not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return case_detail(case_id)


@app.get("/api/procedures/{slug}")
def procedure_detail(slug: str):
    try:
        procedure = get_procedure(slug)
    except KeyError:
        raise HTTPException(status_code=404, detail="Procedure not found") from None
    return {"slug": procedure.slug, "title": procedure.title, "content": procedure.as_context()}


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "database": str(settings.db_path),
        "procedures": str(settings.procedures_dir),
    }


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
    if request.categories:
        available = query_all("SELECT slug,category FROM procedures")
        wanted = {x.lower() for x in request.categories}
        if not any(
            p["slug"].lower() in wanted or p["category"].lower() in wanted for p in available
        ):
            raise HTTPException(
                status_code=422, detail="No procedures match the requested categories or slugs"
            )
    run_id = register_run(request)
    task = asyncio.create_task(execute_run(request, run_id=run_id))
    RUN_TASKS[run_id] = task

    def _cleanup(done: asyncio.Task) -> None:
        RUN_TASKS.pop(run_id, None)
        if not done.cancelled():
            # Consume the exception; execute_run has already persisted the failure on the run row.
            done.exception()

    task.add_done_callback(_cleanup)
    return {"run_id": run_id, "status": "queued"}


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
               r.answer,r.latency_ms,r.actions_json,r.escalation,r.retrieved_procedures_json,
               s.total,s.verdict,s.critical_failure,s.judge_json,s.deterministic_json,
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


@app.get("/api/runs/{run_id}/export.csv")
def export_csv(run_id: str):
    if not query_one("SELECT id FROM runs WHERE id=?", (run_id,)):
        raise HTTPException(status_code=404, detail="Run not found")
    return Response(
        run_dataframe(run_id).to_csv(index=False),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="northstar-{run_id}.csv"'},
    )


@app.get("/api/defects")
def defects(run_id: str | None = None):
    if run_id:
        return query_all("SELECT * FROM defects WHERE run_id=? ORDER BY created_at DESC", (run_id,))
    return query_all("SELECT * FROM defects ORDER BY created_at DESC LIMIT 100")
