from pydantic import BaseModel, Field


class ModelProviderCreate(BaseModel):
    name: str
    provider_type: str
    base_url: str | None = None
    api_key: str | None = None
    default_chat_model: str
    default_embedding_model: str
    embedding_provider_type: str | None = None
    embedding_base_url: str | None = None
    embedding_api_key: str | None = None
    is_default: bool = False


class ModelProviderSecretsUpdate(BaseModel):
    api_key: str | None = Field(default=None, min_length=1)
    embedding_api_key: str | None = Field(default=None, min_length=1)


class ModelProviderUpdate(BaseModel):
    name: str | None = None
    provider_type: str | None = None
    base_url: str | None = None
    api_key: str | None = Field(default=None, min_length=1)
    default_chat_model: str | None = None
    default_embedding_model: str | None = None
    embedding_provider_type: str | None = None
    embedding_base_url: str | None = None
    embedding_api_key: str | None = Field(default=None, min_length=1)
    is_default: bool | None = None


class ModelProviderRead(BaseModel):
    id: str
    name: str
    provider_type: str
    base_url: str | None
    default_chat_model: str
    default_embedding_model: str
    embedding_provider_type: str | None = None
    embedding_base_url: str | None = None
    has_api_key: bool = False
    has_embedding_api_key: bool = False
    api_key_masked: str | None = None
    embedding_api_key_masked: str | None = None
    is_default: bool

    model_config = {"from_attributes": True}
