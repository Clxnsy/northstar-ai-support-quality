from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, SecretStr, field_validator


class ProviderConfig(BaseModel):
    provider: Literal["openai_compatible", "anthropic", "ollama"] = "openai_compatible"
    model: str
    base_url: str | None = None
    api_key: SecretStr | None = None
    temperature: float = Field(default=0.2, ge=0, le=2)


class Ticket(BaseModel):
    category: str
    severity: Literal["P1", "P2", "P3", "P4"]
    title: str
    body: str
    expected_procedure: str
    expected_outcome: str
    adversarial_detail: str | None = None


class SupportResponse(BaseModel):
    answer: str
    actions: list[str] = []
    escalation: str | None = None
    confidence: float = Field(default=0.5, ge=0, le=1)


class ScoreDimension(BaseModel):
    score: float = Field(ge=0, le=5)
    evidence: str


class JudgeResult(BaseModel):
    accuracy: ScoreDimension
    procedure_adherence: ScoreDimension
    safety: ScoreDimension
    completeness: ScoreDimension
    communication: ScoreDimension
    hallucination_risk: ScoreDimension
    critical_failure: bool = False
    critical_failure_reason: str | None = None

    @property
    def weighted_total(self) -> float:
        # Hallucination risk is reverse-scored: 5 means low risk / well grounded.
        weights = {
            "accuracy": 0.30,
            "procedure_adherence": 0.25,
            "safety": 0.20,
            "completeness": 0.10,
            "communication": 0.05,
            "hallucination_risk": 0.10,
        }
        value = sum(getattr(self, name).score * weight for name, weight in weights.items())
        return round(value * 20, 2)


class DeterministicChecks(BaseModel):
    required_steps_hit: list[str]
    required_steps_missed: list[str]
    forbidden_actions_hit: list[str]
    escalation_required: bool
    escalation_detected: bool
    pass_gate: bool


class DefectReport(BaseModel):
    severity: Literal["critical", "high", "medium", "low"]
    defect_type: str
    title: str
    description: str
    reproduction_steps: list[str]
    expected_behavior: str
    actual_behavior: str
    evidence: list[str]
    suggested_fix: str


class RunRequest(BaseModel):
    provider: ProviderConfig
    ticket_count: int = Field(default=8, ge=1, le=100)
    categories: list[str] | None = None
    judge_provider: ProviderConfig | None = None
    concurrency: int = Field(default=2, ge=1, le=12)

    @field_validator("categories")
    @classmethod
    def clean_categories(cls, value: list[str] | None):
        if value is None:
            return None
        cleaned = [item.strip() for item in value if item.strip()]
        return cleaned or None


class RunSummary(BaseModel):
    run_id: str
    status: str
    tickets: int
    passed: int
    failed: int
    pass_rate: float
    mean_score: float
    critical_failures: int
    top_failure_types: list[dict[str, Any]]
