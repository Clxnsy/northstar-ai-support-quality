from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Optional

import typer
import uvicorn

from .analytics import category_breakdown, export_run_csv, failure_signals, run_summary
from .db import init_db
from .orchestrator import execute_run
from .procedures import sync_to_db
from .schemas import ProviderConfig, RunRequest

app = typer.Typer(no_args_is_help=True, help="Northstar AI Support Quality Evaluation")


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
    """Start the API and dashboard."""
    init_db()
    sync_to_db()
    uvicorn.run("northstar.api:app", host=host, port=port, reload=reload)


@app.command("sync-procedures")
def sync_procedures():
    """Validate and load Markdown support procedures into SQLite/FTS."""
    init_db()
    count = sync_to_db()
    typer.echo(f"Synced {count} procedures")


@app.command()
def run(
    provider: str = typer.Option("openai_compatible", help="openai_compatible, anthropic, or ollama"),
    model: str = typer.Option(..., help="Responder model name"),
    base_url: Optional[str] = typer.Option(None, help="Provider API base URL"),
    api_key_env: str = typer.Option("NORTHSTAR_API_KEY", help="Environment variable containing API key"),
    tickets: int = typer.Option(8, min=1, max=100),
    concurrency: int = typer.Option(2, min=1, max=12),
    categories: Optional[str] = typer.Option(None, help="Comma-separated categories or procedure slugs"),
    judge_model: Optional[str] = typer.Option(None, help="Optional separate judge model"),
):
    """Run a full multi-agent evaluation from the command line."""
    init_db()
    sync_to_db()
    key = os.getenv(api_key_env)
    config = ProviderConfig(provider=provider, model=model, base_url=base_url, api_key=key)
    judge = ProviderConfig(provider=provider, model=judge_model, base_url=base_url, api_key=key) if judge_model else None
    request = RunRequest(
        provider=config,
        judge_provider=judge,
        ticket_count=tickets,
        concurrency=concurrency,
        categories=[x.strip() for x in categories.split(",")] if categories else None,
    )
    run_id = asyncio.run(execute_run(request))
    typer.echo(json.dumps({"run_id": run_id, **run_summary(run_id)}, indent=2))


@app.command()
def report(run_id: str):
    """Print SQL/Python analytics for an evaluation run."""
    typer.echo(json.dumps({
        "summary": run_summary(run_id),
        "categories": category_breakdown(run_id),
        "failure_signals": failure_signals(run_id),
    }, indent=2))


@app.command("export-csv")
def export_csv(run_id: str, output: Path = Path("./data/northstar-export.csv")):
    """Export ticket-level results for external analysis."""
    path = export_run_csv(run_id, output)
    typer.echo(str(path.resolve()))


if __name__ == "__main__":
    app()
