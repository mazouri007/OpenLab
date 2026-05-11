from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def uuid_str() -> str:
    return str(uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(50), default="member")


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_language: Mapped[str] = mapped_column(String(50), default="python")
    review_policy_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    model_config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    owner: Mapped[User] = relationship()


class ProjectMember(TimestampMixin, Base):
    __tablename__ = "project_members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(50), default="member")


class KnowledgeDocument(TimestampMixin, Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(50), default="upload")
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    parse_status: Mapped[str] = mapped_column(String(50), default="pending")
    raw_content: Mapped[str | None] = mapped_column(Text, nullable=True)


class KnowledgeChunk(TimestampMixin, Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    document_id: Mapped[str] = mapped_column(ForeignKey("knowledge_documents.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ChatSession(TimestampMixin, Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(50), default="active")
    last_active_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ChatMessage(TimestampMixin, Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(30))
    content: Mapped[str] = mapped_column(Text)
    citations_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    prompt_trace_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


class MemorySummary(TimestampMixin, Base):
    __tablename__ = "memory_summaries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id"), index=True)
    summary_text: Mapped[str] = mapped_column(Text)
    covered_until_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class LongTermMemory(TimestampMixin, Base):
    __tablename__ = "long_term_memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    memory_type: Mapped[str] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(Text)
    tags_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    source_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("chat_sessions.id"), nullable=True
    )
    embedding_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)


class CodeReviewTask(TimestampMixin, Base):
    __tablename__ = "code_review_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(50))
    language: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(255))
    input_payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    progress_stage: Mapped[str] = mapped_column(String(100), default="created")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_template_id: Mapped[str | None] = mapped_column(
        ForeignKey("prompt_templates.id"), nullable=True
    )
    severity_policy_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class CodeReviewResult(TimestampMixin, Base):
    __tablename__ = "code_review_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    task_id: Mapped[str] = mapped_column(ForeignKey("code_review_tasks.id"), unique=True)
    summary: Mapped[str] = mapped_column(Text)
    overall_score: Mapped[float] = mapped_column(Float, default=0.0)
    findings_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    suggestions_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    raw_output_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class TestGenerationTask(TimestampMixin, Base):
    __tablename__ = "test_generation_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    language: Mapped[str] = mapped_column(String(50))
    framework: Mapped[str] = mapped_column(String(50))
    target_name: Mapped[str] = mapped_column(String(255))
    input_code: Mapped[str] = mapped_column(Text)
    extra_requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    progress_stage: Mapped[str] = mapped_column(String(100), default="created")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_template_id: Mapped[str | None] = mapped_column(
        ForeignKey("prompt_templates.id"), nullable=True
    )


class TestGenerationResult(TimestampMixin, Base):
    __tablename__ = "test_generation_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    task_id: Mapped[str] = mapped_column(ForeignKey("test_generation_tasks.id"), unique=True)
    test_code: Mapped[str] = mapped_column(Text)
    scenarios_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    self_check_report_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    raw_output_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class PromptTemplate(TimestampMixin, Base):
    __tablename__ = "prompt_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    template_type: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(Integer, default=1)
    system_prompt: Mapped[str] = mapped_column(Text)
    user_prompt: Mapped[str] = mapped_column(Text)
    output_schema_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_default: Mapped[bool] = mapped_column(default=False)


class OperationLog(TimestampMixin, Base):
    __tablename__ = "operation_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    target_type: Mapped[str] = mapped_column(String(100))
    target_id: Mapped[str] = mapped_column(String(36))
    detail_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class GithubIntegration(TimestampMixin, Base):
    __tablename__ = "github_integrations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    auth_type: Mapped[str] = mapped_column(String(50), default="pat")
    encrypted_token: Mapped[str] = mapped_column(Text)
    webhook_secret: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="active")


class GithubRepository(TimestampMixin, Base):
    __tablename__ = "github_repositories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    integration_id: Mapped[str] = mapped_column(ForeignKey("github_integrations.id"), index=True)
    repo_full_name: Mapped[str] = mapped_column(String(255), index=True)
    default_branch: Mapped[str] = mapped_column(String(100), default="main")
    status: Mapped[str] = mapped_column(String(50), default="active")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    open_pr_count: Mapped[int] = mapped_column(Integer, default=0)


class GithubPullRequest(TimestampMixin, Base):
    __tablename__ = "github_pull_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    repository_id: Mapped[str] = mapped_column(ForeignKey("github_repositories.id"), index=True)
    pr_number: Mapped[int] = mapped_column(Integer)
    head_sha: Mapped[str] = mapped_column(String(64))
    base_sha: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    author: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(50), default="open")


class GithubWebhookEvent(TimestampMixin, Base):
    __tablename__ = "github_webhook_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    repository_id: Mapped[str | None] = mapped_column(
        ForeignKey("github_repositories.id"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(50))
    delivery_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    processed_status: Mapped[str] = mapped_column(String(50), default="pending")


class ModelProvider(TimestampMixin, Base):
    __tablename__ = "model_providers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    provider_type: Mapped[str] = mapped_column(String(50))
    base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    api_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    default_chat_model: Mapped[str] = mapped_column(String(100))
    default_embedding_model: Mapped[str] = mapped_column(String(100))
    is_default: Mapped[bool] = mapped_column(default=False)
