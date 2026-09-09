from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import typer
import uvicorn

from .analytics import category_breakdown, export_run_csv, failure_signals, run_summary
from .copilot import create_case, draft_case, get_case, save_review
from .db import init_db
from .orchestrator import execute_run
from .procedures import sync_to_db
from .schemas import CaseRequest, CaseReview, ProviderConfig, RunRequest

app = typer.Typer(no_args_is_help=True, help="Northstar Support Copilot and Quality Lab")


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
    provider: str = typer.Option(
        "openai_compatible", help="openai_compatible, anthropic, or ollama"
    ),
    model: str = typer.Option(..., help="Responder model name"),
    base_url: str | None = typer.Option(None, help="Provider API base URL"),
    api_key_env: str = typer.Option(
        "NORTHSTAR_API_KEY", help="Environment variable containing API key"
    ),
    tickets: int = typer.Option(8, min=1, max=100),
    concurrency: int = typer.Option(2, min=1, max=12),
    categories: str | None = typer.Option(
        None, help="Comma-separated categories or procedure slugs"
    ),
    judge_model: str | None = typer.Option(None, help="Optional separate judge model"),
    judge_provider: str | None = typer.Option(None, help="Optional separate judge provider"),
    judge_base_url: str | None = typer.Option(None, help="Optional separate judge endpoint"),
    judge_api_key_env: str = typer.Option(
        "NORTHSTAR_JUDGE_API_KEY", help="Judge credential environment variable"
    ),
    temperature: float | None = typer.Option(None, min=0, max=2),
):
    """Run a full multi-agent evaluation from the command line."""
    init_db()
    sync_to_db()
    key = os.getenv(api_key_env)
    config = ProviderConfig(
        provider=provider, model=model, base_url=base_url, api_key=key, temperature=temperature
    )
    judge = None
    if judge_model:
        judge = ProviderConfig(
            provider=judge_provider or provider,
            model=judge_model,
            base_url=judge_base_url
            or (base_url if not judge_provider or judge_provider == provider else None),
            api_key=os.getenv(judge_api_key_env)
            or (key if not judge_provider or judge_provider == provider else None),
            temperature=temperature,
        )
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
    typer.echo(
        json.dumps(
            {
                "summary": run_summary(run_id),
                "categories": category_breakdown(run_id),
                "failure_signals": failure_signals(run_id),
            },
            indent=2,
        )
    )


@app.command("export-csv")
def export_csv(run_id: str, output: Path = Path("./data/northstar-export.csv")):
    """Export ticket-level results for external analysis."""
    path = export_run_csv(run_id, output)
    typer.echo(str(path.resolve()))


@app.command()
def assist(
    title: str = typer.Option(..., help="Ticket subject"),
    ticket_file: Path = typer.Option(
        ..., exists=True, dir_okay=False, help="Text file containing ticket details"
    ),
    model: str = typer.Option(..., help="Current model identifier"),
    provider: str = typer.Option(
        "openai", help="openai, openrouter, anthropic, ollama, or openai_compatible"
    ),
    base_url: str | None = None,
    api_key_env: str = "NORTHSTAR_API_KEY",
    procedure: str | None = typer.Option(None, help="Optional authoritative procedure slug"),
):
    """Prepare a draft for human review; never sends a reply or executes actions."""
    init_db()
    sync_to_db()
    request = CaseRequest(
        title=title,
        body=ticket_file.read_text(encoding="utf-8"),
        provider=ProviderConfig(
            provider=provider, model=model, base_url=base_url, api_key=os.getenv(api_key_env)
        ),
        procedure_slugs=[procedure] if procedure else [],
    )
    case_id = create_case(request)
    asyncio.run(draft_case(request, case_id))
    case = get_case(case_id)
    typer.echo(json.dumps(case, indent=2))
    if case["status"] == "failed":
        raise typer.Exit(1)


@app.command("case")
def show_case(case_id: str):
    """Read a saved support case and its human review history."""
    case = get_case(case_id)
    if not case:
        raise typer.BadParameter("Case not found")
    typer.echo(json.dumps(case, indent=2))


@app.command()
def review(
    case_id: str,
    reply_file: Path = typer.Option(
        ..., exists=True, dir_okay=False, help="Your reviewed reply, in a text file"
    ),
    notes: str = "",
    close: bool = False,
):
    """Record your human review locally. Does not send the reply."""
    save_review(
        case_id,
        CaseReview(
            reply=reply_file.read_text(encoding="utf-8"),
            notes=notes,
            status="closed" if close else "reviewed",
        ),
    )
    typer.echo("Review saved. Nothing was sent to the requester.")


if __name__ == "__main__":
    app()
