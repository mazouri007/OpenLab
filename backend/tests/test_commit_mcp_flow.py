from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.agents.chat_graph import run_chat_graph
from app.db.base import Base
from app.models import (
    ChatMessage,
    ChatSession,
    CodeReviewTask,
    GithubIntegration,
    GithubRepository,
    Project,
    User,
)
from app.schemas.chat import ChatMessageCreate
from app.schemas.review import ReviewRequest
from app.services.commit_context.service import (
    CommitContext,
    CommitContextService,
    CommitFileChange,
)
from app.services.code_context.models import CodeChangeContext, CodeChangedFile
from app.services.code_context.resolver import PullRequestContextService
from app.services.mcp.github_client import GitHubMCPError


class FakeGitHubMCPClient:
    def __init__(self, token: str) -> None:
        self.token = token

    def get_commit(self, repo_full_name: str, commit_sha: str) -> dict:
        return {
            "sha": commit_sha,
            "commit": {
                "message": "Add commit-aware review flow",
                "author": {"name": "Ada"},
            },
            "stats": {"additions": 12, "deletions": 3, "total": 15},
            "files": [
                {
                    "filename": "backend/app/main.py",
                    "status": "modified",
                    "patch": "@@ -1 +1 @@\n" + "x" * 80,
                    "additions": 10,
                    "deletions": 1,
                    "changes": 11,
                },
                {
                    "filename": "README.md",
                    "status": "modified",
                    "patch": "",
                    "additions": 2,
                    "deletions": 2,
                    "changes": 4,
                },
            ],
        }

    def get_file_contents(self, repo_full_name: str, path: str, ref: str | None = None) -> dict:
        return {"content": f"{path} content at {ref}\n" * 20}


class BrokenGitHubMCPClient:
    def __init__(self, token: str) -> None:
        self.token = token

    def get_commit(self, repo_full_name: str, commit_sha: str) -> dict:
        raise GitHubMCPError("GitHub MCP command not found: docker")


class FakeRestGitHubClient:
    def __init__(self, token: str) -> None:
        self.token = token

    def fetch_commit_diff(self, repo_full_name: str, commit_sha: str) -> dict:
        return {
            "sha": commit_sha,
            "message": "REST fallback commit",
            "author": {"login": "fallback-user"},
            "stats": {"additions": 3, "deletions": 1, "total": 4},
            "files": [
                {
                    "path": "backend/app/fallback.py",
                    "status": "modified",
                    "patch": "@@ -1 +1 @@\n+fallback",
                }
            ],
        }


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    with factory() as db:
        _seed_project_repo(db)
        yield db


def test_commit_context_normalizes_truncates_and_cites(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = CommitContextService(db_session, mcp_client_cls=FakeGitHubMCPClient)
    monkeypatch.setattr(service.settings, "mcp_commit_diff_char_limit", 40)
    monkeypatch.setattr(service.settings, "mcp_commit_file_char_limit", 60)

    context = service.load_commit_context("project-1", "repo-1", "abc123")

    assert context.repo_full_name == "lab/demo-platform"
    assert context.message == "Add commit-aware review flow"
    assert context.author == "Ada"
    assert context.truncated is True
    assert context.files[0].patch.endswith("...[truncated]")
    assert context.files[1].content_excerpt.endswith("...[truncated]")
    assert {item["source_type"] for item in context.citations()} == {
        "github_commit",
        "github_file",
    }


def test_commit_context_falls_back_to_rest_when_mcp_command_missing(
    db_session: Session,
) -> None:
    service = CommitContextService(
        db_session,
        mcp_client_cls=BrokenGitHubMCPClient,
        rest_client_cls=FakeRestGitHubClient,
    )

    context = service.load_commit_context("project-1", "repo-1", "abc123")

    assert context.source_provider == "github_rest_fallback"
    assert context.message == "REST fallback commit"
    assert context.files[0].path == "backend/app/fallback.py"
    assert "fallback" in context.to_question_context()


def test_commit_payload_validation_requires_repository_and_sha() -> None:
    with pytest.raises(ValidationError):
        ChatMessageCreate(content="审查这个提交", context_type="github_commit")

    with pytest.raises(ValidationError):
        ReviewRequest(title="review", source_type="github_commit", language="python")


def test_chat_graph_commit_explain_returns_metadata_and_citations(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(CommitContextService, "load_commit_context", _fake_load_commit_context)
    session = db_session.get(ChatSession, "session-1")
    assert session is not None

    state = run_chat_graph(
        db_session,
        session,
        ChatMessageCreate(
            content="这个提交增加了什么功能？",
            context_type="github_commit",
            repository_id="repo-1",
            commit_sha="abc123",
            intent="explain",
        ),
    )

    answer = state["rag_answer"]
    assert answer.metadata["repo_full_name"] == "lab/demo-platform"
    assert answer.metadata["commit_sha"] == "abc123"
    assert answer.metadata["detected_action"] == "answer"
    assert answer.metadata["context_kind"] == "github_commit"
    assert any(item["source_type"] == "github_commit" for item in answer.citations)
    assert db_session.query(ChatMessage).filter(ChatMessage.session_id == "session-1").count() == 2


def test_chat_graph_commit_review_persists_review_task(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(CommitContextService, "load_commit_context", _fake_load_commit_context)
    session = db_session.get(ChatSession, "session-1")
    assert session is not None

    state = run_chat_graph(
        db_session,
        session,
        ChatMessageCreate(
            content="请审查这个提交",
            context_type="github_commit",
            repository_id="repo-1",
            commit_sha="abc123",
            intent="review",
            persist_review=True,
        ),
    )

    answer = state["rag_answer"]
    assert "review_task_id" in answer.metadata
    assert "代码审查" in answer.answer
    task = db_session.get(CodeReviewTask, answer.metadata["review_task_id"])
    assert task is not None
    assert task.status == "completed"
    assert task.source_type == "manual_diff"


def test_chat_graph_auto_detects_commit_sha_with_single_repo(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(CommitContextService, "load_commit_context", _fake_load_commit_context)
    session = db_session.get(ChatSession, "session-1")
    assert session is not None

    state = run_chat_graph(db_session, session, "abc1234 这个提交增加了什么功能？")

    answer = state["rag_answer"]
    assert answer.metadata["context_kind"] == "github_commit"
    assert answer.metadata["repo_full_name"] == "lab/demo-platform"
    assert answer.metadata["commit_sha"] == "abc1234"
    assert answer.metadata["detected_action"] == "answer"
    assert any(item["source_type"] == "github_commit" for item in answer.citations)


def test_chat_graph_auto_clarifies_missing_commit_sha(db_session: Session) -> None:
    session = db_session.get(ChatSession, "session-1")
    assert session is not None

    state = run_chat_graph(db_session, session, "请审查 lab/demo-platform 仓库")

    answer = state["rag_answer"]
    assert answer.metadata["needs_clarification"] is True
    assert "PR 编号、commit SHA 或 diff 内容" in answer.metadata["missing_fields"]
    assert "可以补充" in answer.answer
    assert db_session.query(ChatMessage).filter(ChatMessage.session_id == "session-1").count() == 2


def test_chat_graph_executes_pr_review(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(PullRequestContextService, "load_pr_context", _fake_load_pr_context)
    session = db_session.get(ChatSession, "session-1")
    assert session is not None

    state = run_chat_graph(db_session, session, "请看一下 PR #42 的风险")

    answer = state["rag_answer"]
    assert answer.metadata["detected_action"] == "review"
    assert answer.metadata["pr_number"] == 42
    assert "review_task_id" in answer.metadata
    assert "代码审查" in answer.answer


def test_chat_graph_generates_tests_for_manual_diff(db_session: Session) -> None:
    session = db_session.get(ChatSession, "session-1")
    assert session is not None

    state = run_chat_graph(
        db_session,
        session,
        "请给这个 diff 生成 pytest 测试\n```diff\n"
        "diff --git a/app/service.py b/app/service.py\n"
        "@@ -1 +1 @@\n"
        "-def add(a,b): return a+b\n"
        "+def add(a, b): return a + b\n"
        "```",
    )

    answer = state["rag_answer"]
    assert answer.metadata["detected_action"] == "test"
    assert answer.metadata["context_kind"] == "manual_diff"
    assert "test_generation_task_id" in answer.metadata
    assert "测试生成" in answer.answer


def test_chat_graph_review_and_test_for_manual_diff(db_session: Session) -> None:
    session = db_session.get(ChatSession, "session-1")
    assert session is not None

    state = run_chat_graph(
        db_session,
        session,
        "帮我审查并补测试\n```diff\n"
        "diff --git a/app/service.py b/app/service.py\n"
        "@@ -1 +1 @@\n"
        "-def add(a,b): return a+b\n"
        "+def add(a, b): return a + b\n"
        "```",
    )

    answer = state["rag_answer"]
    assert answer.metadata["detected_action"] == "review_and_test"
    assert "review_task_id" in answer.metadata
    assert "test_generation_task_id" in answer.metadata
    assert "代码审查" in answer.answer
    assert "测试生成" in answer.answer


def test_chat_graph_testgen_reports_unsupported_language(db_session: Session) -> None:
    session = db_session.get(ChatSession, "session-1")
    assert session is not None

    state = run_chat_graph(
        db_session,
        session,
        ChatMessageCreate(
            content=(
                "请生成测试\n```diff\n"
                "diff --git a/app/service.py b/app/service.py\n"
                "@@ -1 +1 @@\n"
                "+def add(a, b): return a + b\n"
                "```"
            ),
            action="test",
            language="javascript",
        ),
    )

    answer = state["rag_answer"]
    assert answer.metadata["unsupported_reason"] == "unsupported_language"
    assert answer.metadata["test_generation_task_id"] is None
    assert "当前只支持" in answer.answer


def _seed_project_repo(db: Session) -> None:
    user = User(id="user-1", email="demo@example.com", name="Demo User", role="owner")
    project = Project(
        id="project-1",
        owner_id="user-1",
        name="Demo",
        slug="demo",
        primary_language="python",
    )
    integration = GithubIntegration(
        id="integration-1",
        project_id="project-1",
        auth_type="pat",
        encrypted_token="ghp_fake",
        webhook_secret="secret",
        status="active",
    )
    repo = GithubRepository(
        id="repo-1",
        integration_id="integration-1",
        repo_full_name="lab/demo-platform",
        default_branch="main",
        status="active",
    )
    session = ChatSession(
        id="session-1",
        project_id="project-1",
        user_id="user-1",
        title="Commit QA",
    )
    db.add_all([user, project, integration, repo, session])
    db.commit()


def _fake_load_commit_context(
    self: CommitContextService, project_id: str, repository_id: str, commit_sha: str
) -> CommitContext:
    return CommitContext(
        repository_id=repository_id,
        repo_full_name="lab/demo-platform",
        commit_sha=commit_sha,
        message="Add commit-aware review flow",
        author="Ada",
        stats={"additions": 12, "deletions": 3, "total": 15},
        files=[
            CommitFileChange(
                path="backend/app/main.py",
                status="modified",
                patch="@@ -1 +1 @@\n+commit-aware flow",
                additions=10,
                deletions=1,
                changes=11,
            )
        ],
    )


def _fake_load_pr_context(
    self: PullRequestContextService, project_id: str, repository_id: str, pr_number: int
) -> CodeChangeContext:
    return CodeChangeContext(
        kind="github_pr",
        title=f"lab/demo-platform PR #{pr_number}",
        repository_id=repository_id,
        repo_full_name="lab/demo-platform",
        pr_number=pr_number,
        summary="Mock PR",
        source_provider="test",
        files=[
            CodeChangedFile(
                path="app/service.py",
                status="modified",
                patch="@@ -1 +1 @@\n+def add(a, b): return a + b",
                additions=1,
                deletions=1,
            )
        ],
    )
