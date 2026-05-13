from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ChatSessionCreate(BaseModel):
    title: str
    user_id: str = "demo-user"


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1)
    context_type: Literal["general", "github_commit"] = "general"
    action: Literal["auto", "answer", "review", "test", "review_and_test"] = "auto"
    repository_id: str | None = None
    commit_sha: str | None = None
    pr_number: int | None = None
    intent: Literal["auto", "explain", "compliance", "review"] = "auto"
    persist_review: bool = True
    persist_results: bool = True
    language: str | None = None
    framework: str | None = None

    @model_validator(mode="after")
    def validate_context(self) -> "ChatMessageCreate":
        if self.context_type == "github_commit":
            if not self.repository_id:
                raise ValueError("repository_id is required for github_commit context")
            if not self.commit_sha:
                raise ValueError("commit_sha is required for github_commit context")
        return self


class ChatMessageRead(BaseModel):
    id: str
    role: str
    content: str
    citations_json: list[dict] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ChatAnswer(BaseModel):
    answer: str
    citations: list[dict] = Field(default_factory=list)
    used_memory: list[str] = Field(default_factory=list)
    used_documents: list[str] = Field(default_factory=list)
    rewritten_queries: list[str] = Field(default_factory=list)
    reasoning_summary: str = ""
    confidence: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
