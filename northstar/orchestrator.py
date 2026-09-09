from __future__ import annotations

import asyncio
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from .agents import DefectWriterAgent, JudgeAgent, ScenarioGeneratorAgent, SupportAgent
from .config import settings
from .db import connection, json_dumps
from .evaluator import deterministic_checks, verdict
from .procedures import load_all, retrieve, sync_to_db
from .providers import ProviderError, build_provider
from .schemas import DefectReport, ProviderConfig, RunRequest, Ticket


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _safe_config(config: ProviderConfig) -> dict[str, Any]:
    data = config.model_dump(exclude={"api_key"})
    data["api_key_supplied"] = config.api_key is not None
    return data


def _fallback_defect(
    ticket: Ticket, response_text: str, checks: dict, score: float
) -> DefectReport:
    missed = checks.get("required_steps_missed", [])
    forbidden = checks.get("forbidden_actions_hit", [])
    if forbidden:
        severity = "critical"
        defect_type = "policy_violation"
    elif missed:
        severity = "high" if ticket.severity in {"P1", "P2"} else "medium"
        defect_type = "procedure_adherence"
    else:
        severity = "medium"
        defect_type = "quality_regression"
    return DefectReport(
        severity=severity,
        defect_type=defect_type,
        title=f"{ticket.category}: failed support evaluation for {ticket.title}",
        description=f"The evaluated response scored {score:.1f}/100 and did not meet the release gate.",
        reproduction_steps=[
            f"Submit the synthetic ticket: {ticket.title}",
            "Run the support agent with the documented procedure set.",
            "Evaluate the response with the Northstar judge and deterministic checks.",
        ],
        expected_behavior=ticket.expected_outcome,
        actual_behavior=response_text,
        evidence=[
            *(f"Missed required step: {x}" for x in missed),
            *(f"Forbidden action: {x}" for x in forbidden),
        ],
        suggested_fix="Adjust the support prompt, retrieval, or policy guardrail and rerun this ticket as a regression case.",
    )


def create_run(request: RunRequest) -> str:
    run_id = str(uuid.uuid4())
    judge_config = request.judge_provider or request.provider
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO runs(id,created_at,status,provider,model,judge_provider,judge_model,ticket_count,config_json)
            VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (
                run_id,
                _now(),
                "queued",
                request.provider.provider,
                request.provider.model,
                judge_config.provider,
                judge_config.model,
                request.ticket_count,
                json_dumps(
                    {
                        "provider": _safe_config(request.provider),
                        "judge_provider": _safe_config(judge_config),
                        "ticket_count": request.ticket_count,
                        "categories": request.categories,
                        "concurrency": request.concurrency,
                    }
                ),
            ),
        )
    return run_id


async def execute_run(request: RunRequest, run_id: str | None = None) -> str:
    run_id = run_id or create_run(request)
    try:
        sync_to_db()
        provider = build_provider(request.provider)
        judge_provider = build_provider(request.judge_provider or request.provider)
        generator = ScenarioGeneratorAgent(provider)
        support = SupportAgent(provider)
        judge = JudgeAgent(judge_provider)
        defect_writer = DefectWriterAgent(judge_provider)
        procedures = load_all()
        if request.categories:
            wanted = {x.lower() for x in request.categories}
            procedures = [
                p for p in procedures if p.category.lower() in wanted or p.slug.lower() in wanted
            ]
            if not procedures:
                raise ValueError("No procedures match the requested categories")
        authorities = {p.slug: p for p in procedures}
        with connection() as conn:
            conn.execute("UPDATE runs SET status='running' WHERE id=?", (run_id,))
            # Preserve the actual authority for historical analysis after Markdown edits.
            conn.execute(
                "UPDATE runs SET config_json=json_set(config_json,'$.procedure_snapshot',json(?)) WHERE id=?",
                (json_dumps({p.slug: p.as_context() for p in procedures}), run_id),
            )
        tickets = []
        # Bound each generation response so large runs fit small local-model context limits.
        for offset in range(0, request.ticket_count, 5):
            tickets.extend(
                await generator.generate(procedures, min(5, request.ticket_count - offset))
            )
        semaphore = asyncio.Semaphore(min(request.concurrency, settings.max_concurrency))

        async def process(ordinal: int, ticket: Ticket) -> None:
            async with semaphore:
                ticket_id = str(uuid.uuid4())
                with connection() as conn:
                    conn.execute(
                        """
                        INSERT INTO tickets(id,run_id,ordinal,category,severity,title,body,expected_procedure,expected_outcome,adversarial_detail,created_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            ticket_id,
                            run_id,
                            ordinal,
                            ticket.category,
                            ticket.severity,
                            ticket.title,
                            ticket.body,
                            ticket.expected_procedure,
                            ticket.expected_outcome,
                            ticket.adversarial_detail,
                            _now(),
                        ),
                    )

                retrieved = retrieve(f"{ticket.title}\n{ticket.body}", limit=3)
                # Always include the authoritative procedure for evaluation fairness while preserving retrieval order.
                authority = authorities[ticket.expected_procedure]
                if all(item.slug != authority.slug for item in retrieved):
                    retrieved = [authority, *retrieved[:2]]

                started = time.perf_counter()
                response = await support.answer(ticket, retrieved)
                latency_ms = int((time.perf_counter() - started) * 1000)
                with connection() as conn:
                    conn.execute(
                        """
                        INSERT INTO responses(ticket_id,answer,actions_json,escalation,confidence,provider,model,latency_ms,retrieved_procedures_json,created_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            ticket_id,
                            response.answer,
                            json_dumps(response.actions),
                            response.escalation,
                            response.confidence,
                            request.provider.provider,
                            request.provider.model,
                            latency_ms,
                            json_dumps([p.slug for p in retrieved]),
                            _now(),
                        ),
                    )

                judge_result = await judge.judge(ticket, response, authority)
                deterministic = deterministic_checks(
                    response, authority, f"{ticket.title}\n{ticket.body}"
                )
                final_verdict = verdict(judge_result, deterministic)
                with connection() as conn:
                    conn.execute(
                        """
                        INSERT INTO scores(ticket_id,total,accuracy,procedure_adherence,safety,completeness,communication,hallucination_risk,critical_failure,critical_failure_reason,judge_json,deterministic_json,verdict,created_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            ticket_id,
                            judge_result.weighted_total,
                            judge_result.accuracy.score,
                            judge_result.procedure_adherence.score,
                            judge_result.safety.score,
                            judge_result.completeness.score,
                            judge_result.communication.score,
                            judge_result.hallucination_risk.score,
                            int(
                                judge_result.critical_failure
                                or bool(deterministic.forbidden_actions_hit)
                                or (
                                    deterministic.escalation_required
                                    and not deterministic.escalation_detected
                                )
                            ),
                            judge_result.critical_failure_reason,
                            judge_result.model_dump_json(),
                            deterministic.model_dump_json(),
                            final_verdict,
                            _now(),
                        ),
                    )

                if final_verdict == "fail":
                    defect = _fallback_defect(
                        ticket,
                        response.answer,
                        deterministic.model_dump(),
                        judge_result.weighted_total,
                    )
                    defect_id = str(uuid.uuid4())
                    with connection() as conn:
                        conn.execute(
                            """
                            INSERT INTO defects(id,ticket_id,run_id,severity,defect_type,title,description,reproduction_steps_json,expected_behavior,actual_behavior,evidence_json,suggested_fix,created_at)
                            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                            """,
                            (
                                defect_id,
                                ticket_id,
                                run_id,
                                defect.severity,
                                defect.defect_type,
                                defect.title,
                                defect.description,
                                json_dumps(defect.reproduction_steps),
                                defect.expected_behavior,
                                defect.actual_behavior,
                                json_dumps(defect.evidence),
                                defect.suggested_fix,
                                _now(),
                            ),
                        )
                    try:
                        enhanced = await defect_writer.write(
                            ticket, response, judge_result, deterministic.model_dump(), authority
                        )
                    except Exception:  # noqa: BLE001 - any writer failure must retain the fallback
                        return  # The fallback defect is already durable.
                    with connection() as conn:
                        conn.execute(
                            """UPDATE defects SET severity=?,defect_type=?,title=?,description=?,
                            reproduction_steps_json=?,expected_behavior=?,actual_behavior=?,evidence_json=?,suggested_fix=?
                            WHERE id=?""",
                            (
                                enhanced.severity,
                                enhanced.defect_type,
                                enhanced.title,
                                enhanced.description,
                                json_dumps(enhanced.reproduction_steps),
                                enhanced.expected_behavior,
                                enhanced.actual_behavior,
                                json_dumps(enhanced.evidence),
                                enhanced.suggested_fix,
                                defect_id,
                            ),
                        )

        outcomes = await asyncio.gather(
            *(process(i + 1, ticket) for i, ticket in enumerate(tickets)), return_exceptions=True
        )
        errors = [outcome for outcome in outcomes if isinstance(outcome, BaseException)]
        if errors:
            raise ProviderError(
                f"{len(errors)} ticket workflow(s) failed; completed results were retained"
            )
        with connection() as conn:
            conn.execute(
                "UPDATE runs SET status='complete', finished_at=? WHERE id=?", (_now(), run_id)
            )
        return run_id
    except BaseException as exc:
        if isinstance(exc, asyncio.CancelledError):
            error = "Run interrupted by server shutdown; start a new evaluation to retry"
        elif isinstance(exc, ProviderError):
            error = str(exc)[:500]
        else:
            error = f"Run failed ({type(exc).__name__}); check procedure configuration and provider output"
        with connection() as conn:
            conn.execute(
                "UPDATE runs SET status='failed', finished_at=?, error=? WHERE id=?",
                (_now(), error, run_id),
            )
        if isinstance(exc, asyncio.CancelledError):
            raise
        raise ProviderError(error) from None
