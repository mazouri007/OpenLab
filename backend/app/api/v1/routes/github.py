from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.integrations.github.webhook import verify_github_signature
from app.schemas.common import ApiResponse
from app.schemas.github import GithubIntegrationCreate, GithubRepositoryRead, GithubWebhookAck
from app.services.github.service import GithubService

router = APIRouter()


@router.post("/projects/{project_id}/github/integrations", response_model=ApiResponse[dict])
def create_github_integration(
    project_id: str, payload: GithubIntegrationCreate, db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    item = GithubService(db).create_integration(project_id, payload)
    return ApiResponse(data={"id": item.id, "status": item.status})


@router.post("/projects/{project_id}/github/repositories/sync", response_model=ApiResponse[list[GithubRepositoryRead]])
def sync_github_repositories(
    project_id: str, db: Session = Depends(get_db)
) -> ApiResponse[list[GithubRepositoryRead]]:
    repos = GithubService(db).sync_repositories(project_id)
    return ApiResponse(data=[GithubRepositoryRead.model_validate(item) for item in repos])


@router.get("/projects/{project_id}/github/repositories", response_model=ApiResponse[list[GithubRepositoryRead]])
def list_github_repositories(
    project_id: str, db: Session = Depends(get_db)
) -> ApiResponse[list[GithubRepositoryRead]]:
    items = GithubService(db).list_repositories(project_id)
    return ApiResponse(data=[GithubRepositoryRead.model_validate(item) for item in items])


@router.post("/github/webhooks/{project_id}", response_model=ApiResponse[GithubWebhookAck])
async def github_webhook(
    project_id: str,
    request: Request,
    x_github_event: str = Header(default="unknown"),
    x_github_delivery: str = Header(default="dev-delivery"),
    x_hub_signature_256: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> ApiResponse[GithubWebhookAck]:
    settings = get_settings()
    payload_bytes = await request.body()
    if not verify_github_signature(
        settings.github_webhook_secret, payload_bytes, x_hub_signature_256
    ) and settings.app_env != "dev":
        raise HTTPException(status_code=401, detail="invalid webhook signature")
    payload = await request.json()
    GithubService(db).save_webhook_event(project_id, x_github_event, x_github_delivery, payload)
    return ApiResponse(
        data=GithubWebhookAck(
            accepted=True, event_type=x_github_event, delivery_id=x_github_delivery
        )
    )

