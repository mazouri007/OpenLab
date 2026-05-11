from functools import lru_cache
from typing import Literal

from pydantic import Field
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
