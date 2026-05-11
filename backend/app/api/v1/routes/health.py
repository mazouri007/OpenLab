from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.common import ApiResponse, HealthResponse

router = APIRouter()


@router.get("/health", response_model=ApiResponse[HealthResponse])
def healthcheck() -> ApiResponse[HealthResponse]:
    settings = get_settings()
    return ApiResponse(
        data=HealthResponse(status="ok", app=settings.app_name, version=settings.app_version)
    )

