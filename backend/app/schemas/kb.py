from datetime import datetime

from pydantic import BaseModel


class KnowledgeDocumentCreate(BaseModel):
    title: str
    source_type: str = "text"
    source_name: str | None = None
    raw_text: str


class KnowledgeDocumentRead(BaseModel):
    id: str
    title: str
    source_type: str
    source_name: str | None = None
    parse_status: str
    chunk_count: int = 0
    error_message: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
