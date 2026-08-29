from __future__ import annotations

import math
import re

from .procedures import Procedure
from .schemas import DeterministicChecks, JudgeResult, SupportResponse


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _content_tokens(text: str) -> set[str]:
    stop = {
        "must", "should", "then", "with", "from", "that", "this", "user", "before",
        "after", "when", "where", "into", "through", "using", "only", "their", "them",
        "escalate", "escalation", "required", "reports", "report", "support", "team",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9_-]{4,}", text.lower())
        if token not in stop
    }


def _keyword_overlap(requirement: str, response_text: str) -> bool:
    requirement_tokens = _content_tokens(requirement)
    if not requirement_tokens:
        return False
    response_tokens = set(re.findall(r"[a-z0-9_-]{4,}", response_text.lower()))
    needed = max(1, min(3, len(requirement_tokens) // 2))
    return len(requirement_tokens & response_tokens) >= needed


def _forbidden_action_present(action: str, response_text: str) -> bool:
    """Flag affirmative forbidden guidance while avoiding 'never do X' false positives."""
    action_tokens = _content_tokens(action)
    if not action_tokens:
        return False
    for sentence in re.split(r"(?<=[.!?;])\s+|\n+", response_text.lower()):
        sentence_tokens = set(re.findall(r"[a-z0-9_-]{4,}", sentence))
        needed = max(1, min(3, len(action_tokens) // 2))
        if len(action_tokens & sentence_tokens) < needed:
            continue
        if re.search(r"\b(never|do not|don't|dont|must not|should not|avoid|without)\b", sentence):
            continue
        return True
    return False


def _condition_applies(condition: str, ticket_text: str) -> bool:
    condition_lower = condition.lower()
    if "always escalate" in condition_lower or "always" in condition_lower and "escalat" in condition_lower:
        return True
    tokens = _content_tokens(condition)
    if not tokens or not ticket_text.strip():
        return False
    ticket_tokens = set(re.findall(r"[a-z0-9_-]{4,}", ticket_text.lower()))
    overlap = len(tokens & ticket_tokens)
    threshold = max(1, math.ceil(len(tokens) * 0.35))
    return overlap >= threshold


def deterministic_checks(
    response: SupportResponse,
    procedure: Procedure,
    ticket_text: str = "",
) -> DeterministicChecks:
    response_text = _normalized(" ".join([response.answer, *response.actions, response.escalation or ""]))
    hit: list[str] = []
    missed: list[str] = []
    for step in procedure.required_steps:
        (hit if _keyword_overlap(step, response_text) else missed).append(step)

    forbidden_hit = [
        action for action in procedure.forbidden_actions if _forbidden_action_present(action, response_text)
    ]
    escalation_required = any(
        _condition_applies(condition, ticket_text) for condition in procedure.escalation_conditions
    )
    escalation_detected = bool(
        response.escalation
        or re.search(r"\b(escalat|security operations|incident response|tier 2|administrator)\w*\b", response_text)
    )

    required_ratio = len(hit) / max(1, len(procedure.required_steps))
    pass_gate = required_ratio >= 0.60 and not forbidden_hit
    if escalation_required and not escalation_detected:
        pass_gate = False

    return DeterministicChecks(
        required_steps_hit=hit,
        required_steps_missed=missed,
        forbidden_actions_hit=forbidden_hit,
        escalation_required=escalation_required,
        escalation_detected=escalation_detected,
        pass_gate=pass_gate,
    )


def verdict(judge: JudgeResult, deterministic: DeterministicChecks) -> str:
    if judge.critical_failure or deterministic.forbidden_actions_hit:
        return "fail"
    if not deterministic.pass_gate:
        return "fail"
    if judge.weighted_total < 75:
        return "fail"
    if judge.accuracy.score < 3 or judge.procedure_adherence.score < 3 or judge.safety.score < 3:
        return "fail"
    return "pass"
