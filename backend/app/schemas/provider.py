from pydantic import BaseModel


class ModelProviderCreate(BaseModel):
    name: str
    provider_type: str
    base_url: str | None = None
    api_key: str | None = None
    default_chat_model: str
    default_embedding_model: str
    is_default: bool = False


class ModelProviderRead(BaseModel):
    id: str
    name: str
    provider_type: str
    base_url: str | None
    default_chat_model: str
    default_embedding_model: str
    is_default: bool

    model_config = {"from_attributes": True}

