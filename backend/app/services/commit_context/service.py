from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.integrations.github.client import GithubClient
from app.models import GithubIntegration, GithubRepository
from app.services.mcp.github_client import GitHubMCPClient, GitHubMCPError


class CommitContextError(RuntimeError):
    """Raised when commit context cannot be loaded safely."""


@dataclass
class CommitFileChange:
    path: str
    status: str = "modified"
    patch: str = ""
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    content_excerpt: str = ""
    truncated: bool = False

    def to_prompt_block(self) -> str:
        lines = [
            f"FILE: {self.path}",
            f"STATUS: {self.status}",
            f"ADDITIONS: {self.additions}",
            f"DELETIONS: {self.deletions}",
        ]
        if self.patch:
            lines.extend(["PATCH:", self.patch])
        if self.content_excerpt:
            lines.extend(["FILE_CONTENT_EXCERPT:", self.content_excerpt])
        if self.truncated:
            lines.append("TRUNCATED: true")
        return "\n".join(lines)


@dataclass
class CommitContext:
    repository_id: str
    repo_full_name: str
    commit_sha: str
    message: str = ""
    author: str = ""
    html_url: str | None = None
    stats: dict[str, Any] = field(default_factory=dict)
    files: list[CommitFileChange] = field(default_factory=list)
    truncated: bool = False
    source_provider: str = "github_mcp"

    def to_review_input(self) -> str:
        header = [
            f"REPOSITORY: {self.repo_full_name}",
            f"COMMIT: {self.commit_sha}",
            f"MESSAGE: {self.message or '无提交说明'}",
            f"AUTHOR: {self.author or 'unknown'}",
            f"STATS: {self.stats}",
            f"CONTEXT_PROVIDER: {self.source_provider}",
            f"TRUNCATED: {self.truncated}",
        ]
        return "\n".join(header + ["", *[file.to_prompt_block() for file in self.files]])

    def to_question_context(self) -> str:
        changed_paths = ", ".join(file.path for file in self.files) or "unknown"
        blocks = [
            f"[github_commit:{self.repo_full_name}@{self.commit_sha}]",
            f"仓库：{self.repo_full_name}",
            f"Commit：{self.commit_sha}",
            f"提交说明：{self.message or '无提交说明'}",
            f"作者：{self.author or 'unknown'}",
            f"统计：{self.stats}",
            f"上下文来源：{self.source_provider}",
            f"变更文件：{changed_paths}",
            f"上下文是否截断：{self.truncated}",
        ]
        for file in self.files:
            blocks.extend(["", f"[github_file:{file.path}]", file.to_prompt_block()])
        return "\n".join(blocks)

    def citations(self) -> list[dict[str, Any]]:
        citations = [
            {
                "chunk_id": f"github_commit:{self.repo_full_name}@{self.commit_sha}",
                "snippet": self.message or f"Commit {self.commit_sha}",
                "source_type": "github_commit",
                "source_title": f"{self.repo_full_name}@{self.commit_sha[:12]}",
            }
        ]
        for file in self.files:
            snippet = file.patch or file.content_excerpt or f"{file.status} {file.path}"
            citations.append(
                {
                    "chunk_id": f"github_file:{file.path}",
                    "snippet": snippet[:240],
                    "source_type": "github_file",
                    "source_title": file.path,
                }
            )
        return citations


class CommitContextService:
    def __init__(
        self,
        db: Session,
        mcp_client_cls: type[GitHubMCPClient] = GitHubMCPClient,
        rest_client_cls: type[GithubClient] = GithubClient,
    ) -> None:
        self.db = db
        self.settings = get_settings()
        self.mcp_client_cls = mcp_client_cls
        self.rest_client_cls = rest_client_cls

    def load_commit_context(
        self, project_id: str, repository_id: str, commit_sha: str
    ) -> CommitContext:
        repo = self.db.get(GithubRepository, repository_id)
        if repo is None:
            raise CommitContextError("GitHub repository not found.")
        integration = self.db.get(GithubIntegration, repo.integration_id)
        if integration is None or integration.project_id != project_id:
            raise CommitContextError("GitHub repository does not belong to this project.")
        if integration.status != "active":
            raise CommitContextError("GitHub integration is not active.")

        client = self.mcp_client_cls(token=integration.encrypted_token)
        try:
            commit_payload = client.get_commit(repo.repo_full_name, commit_sha)
        except GitHubMCPError as exc:
            commit_payload = self._fetch_commit_with_rest_fallback(
                token=integration.encrypted_token,
                repo_full_name=repo.repo_full_name,
                commit_sha=commit_sha,
                mcp_error=exc,
            )

        context = self._normalize_commit_payload(
            repo_id=repo.id,
            repo_full_name=repo.repo_full_name,
            commit_sha=commit_sha,
            payload=commit_payload,
        )
        if context.source_provider == "github_mcp":
            self._augment_missing_file_context(client, context)
        return context

    def _fetch_commit_with_rest_fallback(
        self,
        token: str,
        repo_full_name: str,
        commit_sha: str,
        mcp_error: GitHubMCPError,
    ) -> dict[str, Any]:
        try:
            payload = self.rest_client_cls(token=token).fetch_commit_diff(repo_full_name, commit_sha)
        except Exception as rest_exc:  # noqa: BLE001
            raise CommitContextError(
                "GitHub MCP failed and GitHub REST fallback also failed. "
                f"MCP error: {mcp_error}. REST fallback error: {rest_exc}"
            ) from rest_exc
        payload["source_provider"] = "github_rest_fallback"
        payload["mcp_error"] = str(mcp_error)
        return payload

    def _normalize_commit_payload(
        self,
        repo_id: str,
        repo_full_name: str,
        commit_sha: str,
        payload: dict[str, Any],
    ) -> CommitContext:
        commit = _as_dict(payload.get("commit"))
        author_payload = _as_dict(payload.get("author")) or _as_dict(commit.get("author"))
        message = str(payload.get("message") or commit.get("message") or "")
        author = str(
            author_payload.get("login")
            or author_payload.get("name")
            or author_payload.get("email")
            or ""
        )
        stats = _as_dict(payload.get("stats"))
        files_payload = payload.get("files") or payload.get("changed_files") or []
        files = [
            self._normalize_file_change(item)
            for item in files_payload
            if isinstance(item, dict)
        ]
        context = CommitContext(
            repository_id=repo_id,
            repo_full_name=repo_full_name,
            commit_sha=str(payload.get("sha") or commit_sha),
            message=message,
            author=author,
            html_url=payload.get("html_url"),
            stats=stats,
            files=files,
            source_provider=str(payload.get("source_provider") or "github_mcp"),
        )
        self._enforce_diff_limit(context)
        return context

    def _normalize_file_change(self, payload: dict[str, Any]) -> CommitFileChange:
        patch = str(payload.get("patch") or payload.get("diff") or "")
        return CommitFileChange(
            path=str(payload.get("filename") or payload.get("path") or payload.get("file") or ""),
            status=str(payload.get("status") or "modified"),
            patch=patch,
            additions=_as_int(payload.get("additions")),
            deletions=_as_int(payload.get("deletions")),
            changes=_as_int(payload.get("changes")),
        )

    def _augment_missing_file_context(
        self, client: GitHubMCPClient, context: CommitContext
    ) -> None:
        for file in context.files:
            if file.patch or file.status == "removed" or not file.path:
                continue
            try:
                payload = client.get_file_contents(
                    context.repo_full_name, file.path, ref=context.commit_sha
                )
            except GitHubMCPError:
                continue
            text = _extract_file_text(payload)
            if not text:
                continue
            file.content_excerpt, file.truncated = _truncate(
                text, self.settings.mcp_commit_file_char_limit
            )
            context.truncated = context.truncated or file.truncated

    def _enforce_diff_limit(self, context: CommitContext) -> None:
        remaining = max(self.settings.mcp_commit_diff_char_limit, 0)
        for file in context.files:
            if not file.patch:
                continue
            if remaining <= 0:
                file.patch = ""
                file.truncated = True
                context.truncated = True
                continue
            file.patch, was_truncated = _truncate(file.patch, remaining)
            file.truncated = file.truncated or was_truncated
            context.truncated = context.truncated or was_truncated
            remaining -= len(file.patch)


def _truncate(text: str, limit: int) -> tuple[str, bool]:
    if limit <= 0:
        return "", bool(text)
    if len(text) <= limit:
        return text, False
    return text[:limit] + "\n...[truncated]", True


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _extract_file_text(payload: dict[str, Any]) -> str:
    for key in ("content", "text", "raw_text", "data"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return ""
