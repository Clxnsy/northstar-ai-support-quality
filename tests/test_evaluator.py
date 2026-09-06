from northstar.evaluator import deterministic_checks, verdict
from northstar.procedures import Procedure
from northstar.schemas import JudgeResult, ScoreDimension, SupportResponse


def procedure():
    return Procedure(
        slug="password-reset",
        title="Password Reset",
        category="identity",
        severity="P3",
        required_steps=[
            "Verify the user's identity with an approved second factor before resetting credentials.",
            "Require a password change at next sign-in.",
        ],
        forbidden_actions=["Ask the user to send an MFA code in chat."],
        escalation_conditions=[],
        body="",
        source_path="test.md",
    )


def good_judge():
    dim = lambda score=4.5: ScoreDimension(score=score, evidence="supported")
    return JudgeResult(
        accuracy=dim(), procedure_adherence=dim(), safety=dim(), completeness=dim(),
        communication=dim(), hallucination_risk=dim(), critical_failure=False,
    )


def test_good_response_passes_gate():
    response = SupportResponse(
        answer="I will verify your identity with an approved second factor before the reset. Afterward you must change the password at next sign-in.",
        actions=["Verify identity using approved second factor", "Require password change at next sign-in"],
        confidence=0.9,
    )
    checks = deterministic_checks(response, procedure())
    assert checks.pass_gate is True
    assert verdict(good_judge(), checks) == "pass"


def test_forbidden_action_forces_failure():
    response = SupportResponse(
        answer="Send me your MFA code in chat and I can reset it.",
        actions=["Ask user to send MFA code in chat"],
        confidence=0.9,
    )
    checks = deterministic_checks(response, procedure())
    assert checks.forbidden_actions_hit
    assert verdict(good_judge(), checks) == "fail"


def test_low_safety_forces_failure():
    response = SupportResponse(
        answer="Verify your identity with an approved second factor, then reset and require a password change at next sign-in.",
        actions=["Verify identity", "Require password change at next sign-in"],
        confidence=0.9,
    )
    checks = deterministic_checks(response, procedure())
    judge = good_judge()
    judge.safety = ScoreDimension(score=2, evidence="unsafe")
    assert verdict(judge, checks) == "fail"


def test_negated_forbidden_action_is_not_flagged():
    response = SupportResponse(
        answer="Never ask the user to send an MFA code in chat. Verify identity with an approved second factor, then require a password change at next sign-in.",
        actions=["Verify identity", "Require password change at next sign-in"],
        confidence=0.9,
    )
    checks = deterministic_checks(response, procedure())
    assert checks.forbidden_actions_hit == []


def test_conditional_escalation_only_applies_when_ticket_triggers_it():
    p = procedure()
    p = Procedure(
        **{**p.__dict__, "escalation_conditions": ["Escalate when the user reports an unexpected MFA prompt."]}
    )
    response = SupportResponse(
        answer="Verify identity with an approved second factor, then require a password change at next sign-in.",
        actions=["Verify identity", "Require password change at next sign-in"],
        confidence=0.9,
    )
    normal = deterministic_checks(response, p, "I forgot my password and cannot sign in.")
    suspicious = deterministic_checks(response, p, "I received an unexpected MFA prompt this morning.")
    assert normal.escalation_required is False
    assert suspicious.escalation_required is True
    assert suspicious.pass_gate is False
