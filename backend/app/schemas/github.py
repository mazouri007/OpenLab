from datetime import datetime

from pydantic import BaseModel, Field


class GithubIntegrationCreate(BaseModel):
    auth_type: str = "pat"
    token: str = Field(min_length=5)
    webhook_secret: str


class GithubRepositoryRead(BaseModel):
    id: str
    repo_full_name: str
    default_branch: str
    status: str
    last_synced_at: datetime | None = None
    open_pr_count: int = 0

    model_config = {"from_attributes": True}


class GithubWebhookAck(BaseModel):
    accepted: bool
    event_type: str
    delivery_id: str
