from functools import lru_cache
import json
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Lab AI Reviewer"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    app_env: Literal["dev", "test", "prod"] = "dev"
    cors_allow_origins: list[str] = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]

    database_url: str = "sqlite:///./lab_ai_reviewer.db"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    celery_task_always_eager: bool = True

    llm_provider: str = "litellm"
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_chat_model: str = "gpt-4o-mini"
    llm_embedding_model: str = "text-embedding-3-small"
    llm_timeout_seconds: int = 60
    llm_use_env_proxy: bool = False

    github_webhook_secret: str = "dev-secret"
    enable_mock_llm: bool = Field(default=True)

    mcp_github_enabled: bool = True
    mcp_github_command: str = "docker"
    mcp_github_args_json: str = (
        '["run","-i","--rm",'
        '"-e","GITHUB_PERSONAL_ACCESS_TOKEN",'
        '"-e","GITHUB_TOOLSETS",'
        '"-e","GITHUB_READ_ONLY",'
        '"ghcr.io/github/github-mcp-server"]'
    )
    mcp_github_toolsets: str = "repos,pull_requests"
    mcp_github_read_only: bool = True
    mcp_timeout_seconds: int = 45
    mcp_commit_diff_char_limit: int = 40000
    mcp_commit_file_char_limit: int = 12000

    @computed_field
    @property
    def mcp_github_args(self) -> list[str]:
        try:
            parsed = json.loads(self.mcp_github_args_json)
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        return [str(item) for item in parsed]


@lru_cache
def get_settings() -> Settings:
    return Settings()
