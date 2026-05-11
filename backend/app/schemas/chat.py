from pydantic import BaseModel, Field


class ChatSessionCreate(BaseModel):
    title: str
    user_id: str = "demo-user"


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1)


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
