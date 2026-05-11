from pydantic import BaseModel


class ModelProviderTestRequest(BaseModel):
    provider_type: str
    base_url: str
    api_key: str
    default_chat_model: str
    default_embedding_model: str


class ModelProviderTestResponse(BaseModel):
    ok: bool
    model: str
    message: str
