from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ReviewFindingOutput(BaseModel):
    severity: Literal["critical", "high", "medium", "low", "info"]
    category: str
    title: str
    evidence: str
    impact: str
    suggestion: str
    example_fix: str | None = None


class ReviewGraphOutput(BaseModel):
    summary: str
    overall_risk: Literal["low", "medium", "high"]
    findings: list[ReviewFindingOutput] = Field(default_factory=list)
    suggestions: list[dict] = Field(default_factory=list)
    positive_notes: list[str] = Field(default_factory=list)
    uncertain_points: list[str] = Field(default_factory=list)


class TestPlanItem(BaseModel):
    name: str
    case_type: Literal["happy_path", "edge_case", "exception"]
    description: str


class TestPlanOutput(BaseModel):
    scenarios: list[TestPlanItem] = Field(default_factory=list)


class TestCodeOutput(BaseModel):
    test_code: str
    self_check_report: dict = Field(default_factory=dict)


class RagCitationOutput(BaseModel):
    chunk_id: str
    snippet: str
    source_type: str
    source_title: str | None = None


class RagAnswerOutput(BaseModel):
    answer: str
    reasoning_summary: str
    citations: list[RagCitationOutput] = Field(default_factory=list)
    confidence: float = 0.0

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, value: object) -> float:
        if isinstance(value, str):
            normalized = value.strip().lower()
            label_scores = {
                "high": 0.9,
                "medium": 0.6,
                "middle": 0.6,
                "moderate": 0.6,
                "low": 0.3,
                "高": 0.9,
                "中": 0.6,
                "低": 0.3,
            }
            if normalized in label_scores:
                return label_scores[normalized]
            if normalized.endswith("%"):
                return max(0.0, min(float(normalized.rstrip("%")) / 100, 1.0))
        score = float(value)
        return max(0.0, min(score, 1.0))
