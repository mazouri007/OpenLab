from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.secrets import (
    SecretConfigurationError,
    SecretDecryptionError,
    encrypt_secret,
    has_secret,
    mask_secret,
)
from app.db.session import get_db
from app.models import ModelProvider
from app.schemas.common import ApiResponse
from app.schemas.provider import (
    ModelProviderCreate,
    ModelProviderRead,
    ModelProviderSecretsUpdate,
    ModelProviderUpdate,
)
from app.schemas.provider_test import ModelProviderTestRequest, ModelProviderTestResponse
from app.services.llm.exceptions import LLMConfigurationError, LLMInvocationError
from app.services.llm.langchain_provider import LangChainLLMProvider
from app.services.llm.provider_resolver import normalize_base_url, normalize_model_config

router = APIRouter(prefix="/projects/{project_id}/models/providers")


@router.post("", response_model=ApiResponse[ModelProviderRead])
def create_model_provider(
    project_id: str, payload: ModelProviderCreate, db: Session = Depends(get_db)
) -> ApiResponse[ModelProviderRead]:
    if payload.is_default:
        _clear_default_providers(db, project_id)
    values = payload.model_dump()
    values["base_url"] = normalize_base_url(values["provider_type"], values.get("base_url"))
    values["embedding_provider_type"] = (
        values.get("embedding_provider_type") or values["provider_type"]
    )
    values["embedding_base_url"] = normalize_base_url(
        values["embedding_provider_type"],
        values.get("embedding_base_url") or values.get("base_url"),
    )
    values["api_key"] = _encrypt_secret_or_400(values.get("api_key"))
    values["embedding_api_key"] = _encrypt_secret_or_400(values.get("embedding_api_key"))
    item = ModelProvider(project_id=project_id, **values)
    db.add(item)
    db.commit()
    db.refresh(item)
    return ApiResponse(data=_provider_read(item))


@router.get("", response_model=ApiResponse[list[ModelProviderRead]])
def list_model_providers(
    project_id: str, db: Session = Depends(get_db)
) -> ApiResponse[list[ModelProviderRead]]:
    items = db.query(ModelProvider).filter(ModelProvider.project_id == project_id).all()
    return ApiResponse(data=[_provider_read(item) for item in items])


@router.patch("/{provider_id}", response_model=ApiResponse[ModelProviderRead])
def update_model_provider(
    project_id: str,
    provider_id: str,
    payload: ModelProviderUpdate,
    db: Session = Depends(get_db),
) -> ApiResponse[ModelProviderRead]:
    item = _get_provider_or_404(db, project_id, provider_id)
    values = payload.model_dump(exclude_unset=True)
    if values.get("is_default") is True:
        _clear_default_providers(db, project_id, exclude_provider_id=item.id)
    _apply_provider_updates(item, values)
    db.add(item)
    db.commit()
    db.refresh(item)
    return ApiResponse(data=_provider_read(item))


@router.patch("/{provider_id}/secrets", response_model=ApiResponse[ModelProviderRead])
def update_model_provider_secrets(
    project_id: str,
    provider_id: str,
    payload: ModelProviderSecretsUpdate,
    db: Session = Depends(get_db),
) -> ApiResponse[ModelProviderRead]:
    item = _get_provider_or_404(db, project_id, provider_id)
    values = payload.model_dump(exclude_unset=True)
    if "api_key" in values:
        item.api_key = _encrypt_secret_or_400(values["api_key"])
    if "embedding_api_key" in values:
        item.embedding_api_key = _encrypt_secret_or_400(values["embedding_api_key"])
    db.add(item)
    db.commit()
    db.refresh(item)
    return ApiResponse(data=_provider_read(item))


def _get_provider_or_404(db: Session, project_id: str, provider_id: str) -> ModelProvider:
    item = (
        db.query(ModelProvider)
        .filter(ModelProvider.project_id == project_id, ModelProvider.id == provider_id)
        .first()
    )
    if item is None:
        raise HTTPException(status_code=404, detail="model provider not found")
    return item


def _clear_default_providers(
    db: Session, project_id: str, exclude_provider_id: str | None = None
) -> None:
    existing = db.query(ModelProvider).filter(ModelProvider.project_id == project_id).all()
    for item in existing:
        if exclude_provider_id and item.id == exclude_provider_id:
            continue
        item.is_default = False
        db.add(item)


def _apply_provider_updates(item: ModelProvider, values: dict) -> None:
    if "name" in values:
        item.name = values["name"]
    if "provider_type" in values:
        item.provider_type = values["provider_type"]
    if "base_url" in values:
        item.base_url = normalize_base_url(item.provider_type, values["base_url"])
    if "api_key" in values:
        item.api_key = _encrypt_secret_or_400(values["api_key"])
    if "default_chat_model" in values:
        item.default_chat_model = values["default_chat_model"]
    if "default_embedding_model" in values:
        item.default_embedding_model = values["default_embedding_model"]
    if "embedding_provider_type" in values:
        item.embedding_provider_type = values["embedding_provider_type"] or None
    if "embedding_base_url" in values:
        embedding_provider_type = item.embedding_provider_type or item.provider_type
        item.embedding_base_url = normalize_base_url(
            embedding_provider_type, values["embedding_base_url"]
        )
    if "embedding_api_key" in values:
        item.embedding_api_key = _encrypt_secret_or_400(values["embedding_api_key"])
    if "is_default" in values:
        item.is_default = values["is_default"]


def _encrypt_secret_or_400(value: str | None) -> str | None:
    try:
        return encrypt_secret(value)
    except SecretConfigurationError as exc:
        raise HTTPException(
            status_code=400,
            detail="保存模型密钥前需要配置 APP_SECRET_KEYS。开发环境可使用 env 示例中的 Fernet key。",
        ) from exc


def _mask_secret_or_none(value: str | None) -> str | None:
    try:
        return mask_secret(value)
    except (SecretConfigurationError, SecretDecryptionError):
        return None


@router.post("/test", response_model=ApiResponse[ModelProviderTestResponse])
def test_model_provider(
    project_id: str, payload: ModelProviderTestRequest, db: Session = Depends(get_db)
) -> ApiResponse[ModelProviderTestResponse]:
    _ = project_id
    model_config = normalize_model_config(payload.model_dump())
    provider = LangChainLLMProvider()
    try:
        message = provider.chat_text(
            system_prompt="You are a connectivity check assistant.",
            user_prompt="Reply with: connection ok",
            model_config=model_config,
        )
        embedding = provider.embed_texts(["connection check"], model_config=model_config)
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMInvocationError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "模型供应商连通性测试失败。请检查 Base URL 是否为 OpenAI-Compatible "
                "chat/embeddings 地址、模型名称是否存在、API Key 是否有效，以及本机代理配置。"
                f" 原始错误：{exc}"
            ),
        ) from exc
    return ApiResponse(
        data=ModelProviderTestResponse(
            ok=True,
            model=model_config["chat"]["model"],
            message=f"{message[:160]} | embedding dim: {len(embedding[0]) if embedding else 0}",
        )
    )


def _provider_read(item: ModelProvider) -> ModelProviderRead:
    return ModelProviderRead(
        id=item.id,
        name=item.name,
        provider_type=item.provider_type,
        base_url=item.base_url,
        default_chat_model=item.default_chat_model,
        default_embedding_model=item.default_embedding_model,
        embedding_provider_type=item.embedding_provider_type,
        embedding_base_url=item.embedding_base_url,
        has_api_key=has_secret(item.api_key),
        has_embedding_api_key=has_secret(item.embedding_api_key),
        api_key_masked=_mask_secret_or_none(item.api_key),
        embedding_api_key_masked=_mask_secret_or_none(item.embedding_api_key),
        is_default=item.is_default,
    )
