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
    parse_status: str

    model_config = {"from_attributes": True}

