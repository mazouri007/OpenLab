from typing import Any, Literal

from pydantic import BaseModel, Field


class ReviewRequest(BaseModel):
    title: str
    source_type: Literal["snippet", "file_upload", "github_pr", "github_commit", "manual_diff"]
    language: str = "python"
    content: str | None = None
    repository_id: str | None = None
    pr_number: int | None = None
    commit_sha: str | None = None
    related_document_ids: list[str] = Field(default_factory=list)


class ReviewFinding(BaseModel):
    severity: Literal["critical", "high", "medium", "low", "info"]
    category: str
    title: str
    evidence: str
    impact: str
    suggestion: str
    example_fix: str | None = None


class ReviewResultRead(BaseModel):
    summary: str
    overall_risk: str
    findings: list[ReviewFinding]
    suggestions: list[dict[str, Any]] = Field(default_factory=list)
    positive_notes: list[str] = Field(default_factory=list)
    uncertain_points: list[str] = Field(default_factory=list)


class ReviewTaskRead(BaseModel):
    id: str
    title: str
    language: str
    source_type: str
    status: str
    progress_stage: str
    error_message: str | None = None

    model_config = {"from_attributes": True}
