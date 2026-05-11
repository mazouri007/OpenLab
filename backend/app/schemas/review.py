from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ReviewRequest(BaseModel):
    title: str
    source_type: Literal["snippet", "file_upload", "github_pr", "github_commit", "manual_diff"]
    language: str = "python"
    content: str | None = None
    repository_id: str | None = None
    pr_number: int | None = None
    commit_sha: str | None = None
    related_document_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_source_payload(self) -> "ReviewRequest":
        if self.source_type == "github_commit":
            if not self.repository_id:
                raise ValueError("repository_id is required for github_commit reviews")
            if not self.commit_sha:
                raise ValueError("commit_sha is required for github_commit reviews")
        elif self.source_type == "github_pr":
            if not self.repository_id:
                raise ValueError("repository_id is required for github_pr reviews")
            if self.pr_number is None:
                raise ValueError("pr_number is required for github_pr reviews")
        elif self.source_type in {"snippet", "manual_diff", "file_upload"} and not self.content:
            raise ValueError("content is required for snippet, manual_diff, and file_upload reviews")
        return self


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
