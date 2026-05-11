from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ModelProvider
from app.schemas.common import ApiResponse
from app.schemas.provider import ModelProviderCreate, ModelProviderRead
from app.schemas.provider_test import ModelProviderTestRequest, ModelProviderTestResponse
from app.services.llm.exceptions import LLMConfigurationError, LLMInvocationError
from app.services.llm.litellm_provider import LiteLLMProvider
from app.services.llm.provider_resolver import normalize_base_url, normalize_model_config

router = APIRouter(prefix="/projects/{project_id}/models/providers")


@router.post("", response_model=ApiResponse[ModelProviderRead])
def create_model_provider(
    project_id: str, payload: ModelProviderCreate, db: Session = Depends(get_db)
) -> ApiResponse[ModelProviderRead]:
    if payload.is_default:
        existing = db.query(ModelProvider).filter(ModelProvider.project_id == project_id).all()
        for item in existing:
            item.is_default = False
            db.add(item)
    values = payload.model_dump()
    values["base_url"] = normalize_base_url(values["provider_type"], values.get("base_url"))
    item = ModelProvider(project_id=project_id, **values)
    db.add(item)
    db.commit()
    db.refresh(item)
    return ApiResponse(data=ModelProviderRead.model_validate(item))


@router.get("", response_model=ApiResponse[list[ModelProviderRead]])
def list_model_providers(
    project_id: str, db: Session = Depends(get_db)
) -> ApiResponse[list[ModelProviderRead]]:
    items = db.query(ModelProvider).filter(ModelProvider.project_id == project_id).all()
    return ApiResponse(data=[ModelProviderRead.model_validate(item) for item in items])


@router.post("/test", response_model=ApiResponse[ModelProviderTestResponse])
def test_model_provider(
    project_id: str, payload: ModelProviderTestRequest, db: Session = Depends(get_db)
) -> ApiResponse[ModelProviderTestResponse]:
    _ = project_id
    model_config = normalize_model_config(payload.model_dump())
    provider = LiteLLMProvider()
    try:
        message = provider.chat_text(
            system_prompt="You are a connectivity check assistant.",
            user_prompt="Reply with: connection ok",
            model_config=model_config,
        )
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMInvocationError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "模型供应商连通性测试失败。请检查 Base URL 是否为 OpenAI-Compatible "
                "chat completions 地址、模型名称是否存在、API Key 是否有效，以及本机代理配置。"
                f" 原始错误：{exc}"
            ),
        ) from exc
    return ApiResponse(
        data=ModelProviderTestResponse(
            ok=True,
            model=model_config["chat_model"],
            message=message[:200],
        )
    )
