from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.integrations.github.client import GithubClient
from app.models import GithubIntegration, GithubRepository
from app.schemas.chat import ChatMessageCreate
from app.services.code_context.models import CodeChangedFile, CodeChangeContext
from app.services.commit_context.service import CommitContextService
from app.services.github.context_detection import GitHubContextInference, infer_github_context
from app.services.mcp.github_client import GitHubMCPClient, GitHubMCPError


DIFF_HEADER_RE = re.compile(r"^diff --git a/(?P<left>\S+) b/(?P<right>\S+)", re.MULTILINE)
FILE_MARKER_RE = re.compile(r"^\+\+\+ b/(?P<path>\S+)", re.MULTILINE)


@dataclass
class CodeContextResolution:
    context: CodeChangeContext | None = None
    missing_fields: list[str] = field(default_factory=list)
    unsupported_reason: str | None = None
    inference: GitHubContextInference | None = None

    @property
    def needs_clarification(self) -> bool:
        return bool(self.missing_fields or self.unsupported_reason)


class PullRequestContextService:
    def __init__(
        self,
        db: Session,
        mcp_client_cls: type[GitHubMCPClient] = GitHubMCPClient,
        rest_client_cls: type[GithubClient] = GithubClient,
    ) -> None:
        self.db = db
        self.mcp_client_cls = mcp_client_cls
        self.rest_client_cls = rest_client_cls

    def load_pr_context(self, project_id: str, repository_id: str, pr_number: int) -> CodeChangeContext:
        repo = self.db.get(GithubRepository, repository_id)
        if repo is None:
            raise ValueError("GitHub repository not found.")
        integration = self.db.get(GithubIntegration, repo.integration_id)
        if integration is None or integration.project_id != project_id:
            raise ValueError("GitHub repository does not belong to this project.")

        provider = "github_mcp"
        try:
            payload = self.mcp_client_cls(token=integration.encrypted_token).get_pull_request_diff(
                repo.repo_full_name, pr_number
            )
        except GitHubMCPError:
            provider = "github_rest_fallback"
            payload = self.rest_client_cls(token=integration.encrypted_token).fetch_pull_request_diff(
                repo.repo_full_name, pr_number
            )
        files = [
            CodeChangedFile(
                path=str(item.get("filename") or item.get("path") or ""),
                status=str(item.get("status") or "modified"),
                patch=str(item.get("patch") or ""),
                additions=_as_int(item.get("additions")),
                deletions=_as_int(item.get("deletions")),
            )
            for item in payload.get("files", [])
            if isinstance(item, dict)
        ]
        title = str(payload.get("title") or f"PR #{pr_number}")
        return CodeChangeContext(
            kind="github_pr",
            title=f"{repo.repo_full_name} {title}",
            repository_id=repo.id,
            repo_full_name=repo.repo_full_name,
            pr_number=pr_number,
            summary=title,
            source_provider=provider,
            files=files,
            metadata={"raw": payload},
        )


class CodeContextResolver:
    def __init__(self, db: Session) -> None:
        self.db = db

    def resolve(
        self,
        project_id: str,
        request: ChatMessageCreate,
        needs_code_context: bool,
    ) -> CodeContextResolution:
        question = request.content
        manual_diff = _extract_manual_diff(question)
        if manual_diff:
            return CodeContextResolution(context=_context_from_manual_diff(manual_diff))

        inference = infer_github_context(self.db, project_id, question)
        repository_id = request.repository_id or inference.repository_id
        commit_sha = request.commit_sha or inference.commit_sha
        pr_number = request.pr_number or inference.pr_number
        has_concrete_reference = bool(
            repository_id or commit_sha or pr_number is not None or inference.file_paths
        )

        if request.context_type == "github_commit" or (repository_id and commit_sha):
            context = CommitContextService(self.db).load_commit_context(
                project_id=project_id,
                repository_id=repository_id or "",
                commit_sha=commit_sha or "",
            )
            return CodeContextResolution(context=_context_from_commit(context), inference=inference)

        if repository_id and pr_number is not None:
            context = PullRequestContextService(self.db).load_pr_context(project_id, repository_id, pr_number)
            return CodeContextResolution(context=context, inference=inference)

        if not needs_code_context and (not inference.needs_github_context or not has_concrete_reference):
            return CodeContextResolution(inference=inference)

        missing = []
        if not repository_id:
            missing.append("仓库")
        if pr_number is None and not commit_sha and not manual_diff:
            missing.append("PR 编号、commit SHA 或 diff 内容")
        return CodeContextResolution(missing_fields=missing, inference=inference)


def _context_from_commit(context) -> CodeChangeContext:
    return CodeChangeContext(
        kind="github_commit",
        title=f"{context.repo_full_name}@{context.commit_sha[:12]}",
        repository_id=context.repository_id,
        repo_full_name=context.repo_full_name,
        commit_sha=context.commit_sha,
        summary=context.message,
        source_provider=context.source_provider,
        files=[
            CodeChangedFile(
                path=file.path,
                status=file.status,
                patch=file.patch,
                additions=file.additions,
                deletions=file.deletions,
                content_excerpt=file.content_excerpt,
                truncated=file.truncated,
            )
            for file in context.files
        ],
    )


def _extract_manual_diff(question: str) -> str:
    fenced = re.search(r"```(?:diff|patch)?\n(?P<diff>[\s\S]+?)```", question, re.IGNORECASE)
    if fenced and _looks_like_diff(fenced.group("diff")):
        return fenced.group("diff").strip()
    return question.strip() if _looks_like_diff(question) else ""


def _looks_like_diff(text: str) -> bool:
    return "diff --git " in text or "@@ " in text or "\n+++" in text


def _context_from_manual_diff(diff: str) -> CodeChangeContext:
    paths = [match.group("right") for match in DIFF_HEADER_RE.finditer(diff)]
    if not paths:
        paths = [match.group("path") for match in FILE_MARKER_RE.finditer(diff)]
    if not paths:
        paths = ["manual.diff"]
    files = [
        CodeChangedFile(path=path, status="modified", patch=diff)
        for path in list(dict.fromkeys(paths))
    ]
    return CodeChangeContext(
        kind="manual_diff",
        title="用户粘贴的 diff",
        summary="用户在聊天中提供的手动 diff",
        source_provider="user_message",
        files=files,
    )


def _as_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
