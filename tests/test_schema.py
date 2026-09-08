from northstar.schemas import JudgeResult, ScoreDimension


def test_weighted_total_is_0_to_100():
    d = ScoreDimension(score=5, evidence="ok")
    result = JudgeResult(
        accuracy=d,
        procedure_adherence=d,
        safety=d,
        completeness=d,
        communication=d,
        hallucination_risk=d,
    )
    assert result.weighted_total == 100.0
