from typing import Any
from urllib.parse import urlparse, urlunparse

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import ModelProvider
from app.services.llm.exceptions import LLMConfigurationError


def resolve_model_config(db: Session, project_id: str) -> dict[str, Any]:
    provider = (
        db.query(ModelProvider)
        .filter(ModelProvider.project_id == project_id)
        .order_by(ModelProvider.is_default.desc(), ModelProvider.created_at.desc())
        .first()
    )
    if provider:
        return {
            "provider_id": provider.id,
            "provider_type": provider.provider_type,
            "provider_name": provider.name,
            "base_url": normalize_base_url(provider.provider_type, provider.base_url),
            "api_key": provider.api_key,
            "chat_model": _litellm_model_name(
                provider.provider_type, provider.default_chat_model
            ),
            "embedding_model": _litellm_model_name(
                provider.provider_type, provider.default_embedding_model
            ),
        }

    settings = get_settings()
    if settings.llm_api_key or settings.enable_mock_llm:
        return {
            "provider_id": "env-default",
            "provider_type": "openai-compatible",
            "provider_name": "Environment Default",
            "base_url": normalize_base_url("openai-compatible", settings.llm_base_url),
            "api_key": settings.llm_api_key,
            "chat_model": _litellm_model_name("openai-compatible", settings.llm_chat_model),
            "embedding_model": _litellm_model_name(
                "openai-compatible", settings.llm_embedding_model
            ),
        }
    raise LLMConfigurationError("No model provider configured for this project.")


def _litellm_model_name(provider_type: str, model_name: str) -> str:
    if "/" in model_name:
        return model_name
    if provider_type == "openai-compatible":
        return f"openai/{model_name}"
    return model_name


def normalize_base_url(provider_type: str, base_url: str | None) -> str | None:
    if not base_url:
        return base_url
    normalized = base_url.strip().rstrip("/")
    for suffix in ("/chat/completions", "/embeddings", "/models"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
            break

    if provider_type != "openai-compatible":
        return normalized

    parsed = urlparse(normalized)
    if parsed.scheme and parsed.netloc and parsed.path in ("", "/"):
        return urlunparse(parsed._replace(path="/v1"))
    return normalized


def normalize_model_config(payload: dict[str, Any]) -> dict[str, Any]:
    provider_type = str(payload.get("provider_type") or "openai-compatible")
    return {
        "provider_id": payload.get("provider_id", "adhoc"),
        "provider_type": provider_type,
        "provider_name": payload.get("provider_name", payload.get("name", "Adhoc Provider")),
        "base_url": normalize_base_url(provider_type, payload.get("base_url")),
        "api_key": payload.get("api_key"),
        "chat_model": _litellm_model_name(provider_type, str(payload.get("default_chat_model") or "")),
        "embedding_model": _litellm_model_name(
            provider_type, str(payload.get("default_embedding_model") or "")
        ),
    }
