"""Initial current schema baseline.

Revision ID: 0001_initial_current_schema
Revises:
Create Date: 2026-05-13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_current_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("primary_language", sa.String(length=50), nullable=False),
        sa.Column("review_policy_json", sa.JSON(), nullable=False),
        sa.Column("model_config_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_projects_owner_id"), "projects", ["owner_id"], unique=False)
    op.create_index(op.f("ix_projects_slug"), "projects", ["slug"], unique=True)

    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("last_active_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_chat_sessions_project_id"), "chat_sessions", ["project_id"], unique=False
    )
    op.create_index(op.f("ix_chat_sessions_user_id"), "chat_sessions", ["user_id"], unique=False)

    op.create_table(
        "github_integrations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("auth_type", sa.String(length=50), nullable=False),
        sa.Column("encrypted_token", sa.Text(), nullable=False),
        sa.Column("webhook_secret", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_github_integrations_project_id"),
        "github_integrations",
        ["project_id"],
        unique=False,
    )

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("parse_status", sa.String(length=50), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_knowledge_documents_content_hash"),
        "knowledge_documents",
        ["content_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_documents_project_id"),
        "knowledge_documents",
        ["project_id"],
        unique=False,
    )

    op.create_table(
        "model_providers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("provider_type", sa.String(length=50), nullable=False),
        sa.Column("base_url", sa.String(length=255), nullable=True),
        sa.Column("api_key", sa.Text(), nullable=True),
        sa.Column("default_chat_model", sa.String(length=100), nullable=False),
        sa.Column("default_embedding_model", sa.String(length=100), nullable=False),
        sa.Column("embedding_provider_type", sa.String(length=50), nullable=True),
        sa.Column("embedding_base_url", sa.String(length=255), nullable=True),
        sa.Column("embedding_api_key", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_model_providers_project_id"), "model_providers", ["project_id"], unique=False
    )

    op.create_table(
        "operation_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=100), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("detail_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_operation_logs_action"), "operation_logs", ["action"], unique=False)
    op.create_index(
        op.f("ix_operation_logs_project_id"), "operation_logs", ["project_id"], unique=False
    )
    op.create_index(
        op.f("ix_operation_logs_user_id"), "operation_logs", ["user_id"], unique=False
    )

    op.create_table(
        "project_members",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_project_members_project_id"), "project_members", ["project_id"], unique=False
    )
    op.create_index(op.f("ix_project_members_user_id"), "project_members", ["user_id"], unique=False)

    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("template_type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_prompt", sa.Text(), nullable=False),
        sa.Column("output_schema_json", sa.JSON(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_prompt_templates_template_type"),
        "prompt_templates",
        ["template_type"],
        unique=False,
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations_json", sa.JSON(), nullable=False),
        sa.Column("prompt_trace_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chat_messages_session_id"), "chat_messages", ["session_id"])

    op.create_table(
        "code_review_tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("language", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("input_payload_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("progress_stage", sa.String(length=100), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("prompt_template_id", sa.String(length=36), nullable=True),
        sa.Column("severity_policy_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["prompt_template_id"], ["prompt_templates.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_code_review_tasks_project_id"), "code_review_tasks", ["project_id"]
    )
    op.create_index(op.f("ix_code_review_tasks_status"), "code_review_tasks", ["status"])
    op.create_index(op.f("ix_code_review_tasks_user_id"), "code_review_tasks", ["user_id"])

    op.create_table(
        "github_repositories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("integration_id", sa.String(length=36), nullable=False),
        sa.Column("repo_full_name", sa.String(length=255), nullable=False),
        sa.Column("default_branch", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("open_pr_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["integration_id"], ["github_integrations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_github_repositories_integration_id"),
        "github_repositories",
        ["integration_id"],
    )
    op.create_index(
        op.f("ix_github_repositories_repo_full_name"),
        "github_repositories",
        ["repo_full_name"],
    )

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_knowledge_chunks_document_id"), "knowledge_chunks", ["document_id"])
    op.create_index(op.f("ix_knowledge_chunks_project_id"), "knowledge_chunks", ["project_id"])

    op.create_table(
        "long_term_memories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("memory_type", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags_json", sa.JSON(), nullable=False),
        sa.Column("importance", sa.Float(), nullable=False),
        sa.Column("source_session_id", sa.String(length=36), nullable=True),
        sa.Column("embedding_ref", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["source_session_id"], ["chat_sessions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_long_term_memories_project_id"), "long_term_memories", ["project_id"]
    )
    op.create_index(op.f("ix_long_term_memories_user_id"), "long_term_memories", ["user_id"])

    op.create_table(
        "memory_summaries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("covered_until_message_id", sa.String(length=36), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_memory_summaries_session_id"), "memory_summaries", ["session_id"])

    op.create_table(
        "test_generation_tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("language", sa.String(length=50), nullable=False),
        sa.Column("framework", sa.String(length=50), nullable=False),
        sa.Column("target_name", sa.String(length=255), nullable=False),
        sa.Column("input_code", sa.Text(), nullable=False),
        sa.Column("extra_requirements", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("progress_stage", sa.String(length=100), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("prompt_template_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["prompt_template_id"], ["prompt_templates.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_test_generation_tasks_project_id"), "test_generation_tasks", ["project_id"]
    )
    op.create_index(op.f("ix_test_generation_tasks_status"), "test_generation_tasks", ["status"])
    op.create_index(op.f("ix_test_generation_tasks_user_id"), "test_generation_tasks", ["user_id"])

    op.create_table(
        "code_review_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("findings_json", sa.JSON(), nullable=False),
        sa.Column("suggestions_json", sa.JSON(), nullable=False),
        sa.Column("raw_output_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["code_review_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id"),
    )

    op.create_table(
        "github_pull_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("repository_id", sa.String(length=36), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("head_sha", sa.String(length=64), nullable=False),
        sa.Column("base_sha", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("author", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["github_repositories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_github_pull_requests_repository_id"),
        "github_pull_requests",
        ["repository_id"],
    )

    op.create_table(
        "github_webhook_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("repository_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("delivery_id", sa.String(length=100), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("processed_status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["github_repositories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_github_webhook_events_delivery_id"),
        "github_webhook_events",
        ["delivery_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_github_webhook_events_repository_id"),
        "github_webhook_events",
        ["repository_id"],
    )

    op.create_table(
        "test_generation_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("test_code", sa.Text(), nullable=False),
        sa.Column("scenarios_json", sa.JSON(), nullable=False),
        sa.Column("self_check_report_json", sa.JSON(), nullable=False),
        sa.Column("raw_output_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["test_generation_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id"),
    )


def downgrade() -> None:
    op.drop_table("test_generation_results")
    op.drop_index(op.f("ix_github_webhook_events_repository_id"), table_name="github_webhook_events")
    op.drop_index(op.f("ix_github_webhook_events_delivery_id"), table_name="github_webhook_events")
    op.drop_table("github_webhook_events")
    op.drop_index(op.f("ix_github_pull_requests_repository_id"), table_name="github_pull_requests")
    op.drop_table("github_pull_requests")
    op.drop_table("code_review_results")
    op.drop_index(op.f("ix_test_generation_tasks_user_id"), table_name="test_generation_tasks")
    op.drop_index(op.f("ix_test_generation_tasks_status"), table_name="test_generation_tasks")
    op.drop_index(op.f("ix_test_generation_tasks_project_id"), table_name="test_generation_tasks")
    op.drop_table("test_generation_tasks")
    op.drop_index(op.f("ix_memory_summaries_session_id"), table_name="memory_summaries")
    op.drop_table("memory_summaries")
    op.drop_index(op.f("ix_long_term_memories_user_id"), table_name="long_term_memories")
    op.drop_index(op.f("ix_long_term_memories_project_id"), table_name="long_term_memories")
    op.drop_table("long_term_memories")
    op.drop_index(op.f("ix_knowledge_chunks_project_id"), table_name="knowledge_chunks")
    op.drop_index(op.f("ix_knowledge_chunks_document_id"), table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_index(op.f("ix_github_repositories_repo_full_name"), table_name="github_repositories")
    op.drop_index(op.f("ix_github_repositories_integration_id"), table_name="github_repositories")
    op.drop_table("github_repositories")
    op.drop_index(op.f("ix_code_review_tasks_user_id"), table_name="code_review_tasks")
    op.drop_index(op.f("ix_code_review_tasks_status"), table_name="code_review_tasks")
    op.drop_index(op.f("ix_code_review_tasks_project_id"), table_name="code_review_tasks")
    op.drop_table("code_review_tasks")
    op.drop_index(op.f("ix_chat_messages_session_id"), table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index(op.f("ix_prompt_templates_template_type"), table_name="prompt_templates")
    op.drop_table("prompt_templates")
    op.drop_index(op.f("ix_project_members_user_id"), table_name="project_members")
    op.drop_index(op.f("ix_project_members_project_id"), table_name="project_members")
    op.drop_table("project_members")
    op.drop_index(op.f("ix_operation_logs_user_id"), table_name="operation_logs")
    op.drop_index(op.f("ix_operation_logs_project_id"), table_name="operation_logs")
    op.drop_index(op.f("ix_operation_logs_action"), table_name="operation_logs")
    op.drop_table("operation_logs")
    op.drop_index(op.f("ix_model_providers_project_id"), table_name="model_providers")
    op.drop_table("model_providers")
    op.drop_index(op.f("ix_knowledge_documents_project_id"), table_name="knowledge_documents")
    op.drop_index(op.f("ix_knowledge_documents_content_hash"), table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
    op.drop_index(op.f("ix_github_integrations_project_id"), table_name="github_integrations")
    op.drop_table("github_integrations")
    op.drop_index(op.f("ix_chat_sessions_user_id"), table_name="chat_sessions")
    op.drop_index(op.f("ix_chat_sessions_project_id"), table_name="chat_sessions")
    op.drop_table("chat_sessions")
    op.drop_index(op.f("ix_projects_slug"), table_name="projects")
    op.drop_index(op.f("ix_projects_owner_id"), table_name="projects")
    op.drop_table("projects")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
