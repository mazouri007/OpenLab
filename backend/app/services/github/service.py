from datetime import datetime

from sqlalchemy.orm import Session

from app.integrations.github.client import GithubClient
from app.models import GithubIntegration, GithubRepository, GithubWebhookEvent
from app.schemas.github import GithubIntegrationCreate


class GithubService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_integration(self, project_id: str, payload: GithubIntegrationCreate) -> GithubIntegration:
        integration = GithubIntegration(
            project_id=project_id,
            auth_type=payload.auth_type,
            encrypted_token=payload.token,
            webhook_secret=payload.webhook_secret,
        )
        self.db.add(integration)
        self.db.commit()
        self.db.refresh(integration)
        return integration

    def sync_repositories(self, project_id: str) -> list[GithubRepository]:
        integration = (
            self.db.query(GithubIntegration)
            .filter(GithubIntegration.project_id == project_id)
            .first()
        )
        if integration is None:
            return []
        client = GithubClient(token=integration.encrypted_token)
        repos = client.list_repositories()
        created: list[GithubRepository] = []
        for repo in repos:
            existing = (
                self.db.query(GithubRepository)
                .filter(GithubRepository.integration_id == integration.id)
                .filter(GithubRepository.repo_full_name == repo["full_name"])
                .first()
            )
            if existing:
                existing.default_branch = repo["default_branch"]
                existing.last_synced_at = datetime.utcnow()
                existing.open_pr_count = repo.get("open_pr_count", 0)
                created.append(existing)
                continue
            item = GithubRepository(
                integration_id=integration.id,
                repo_full_name=repo["full_name"],
                default_branch=repo["default_branch"],
                last_synced_at=datetime.utcnow(),
                open_pr_count=repo.get("open_pr_count", 0),
            )
            self.db.add(item)
            created.append(item)
        self.db.commit()
        return created

    def list_repositories(self, project_id: str) -> list[GithubRepository]:
        integration = (
            self.db.query(GithubIntegration)
            .filter(GithubIntegration.project_id == project_id)
            .first()
        )
        if integration is None:
            return []
        return (
            self.db.query(GithubRepository)
            .filter(GithubRepository.integration_id == integration.id)
            .order_by(GithubRepository.repo_full_name.asc())
            .all()
        )

    def save_webhook_event(
        self, project_id: str, event_type: str, delivery_id: str, payload: dict
    ) -> GithubWebhookEvent:
        integration = (
            self.db.query(GithubIntegration)
            .filter(GithubIntegration.project_id == project_id)
            .first()
        )
        repository_id = None
        if integration and payload.get("repository", {}).get("full_name"):
            repo = (
                self.db.query(GithubRepository)
                .filter(GithubRepository.integration_id == integration.id)
                .filter(GithubRepository.repo_full_name == payload["repository"]["full_name"])
                .first()
            )
            if repo:
                repository_id = repo.id
        event = GithubWebhookEvent(
            repository_id=repository_id,
            event_type=event_type,
            delivery_id=delivery_id,
            payload_json=payload,
            processed_status="accepted",
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event
