from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models import GithubIntegration, GithubRepository


COMMIT_SHA_RE = re.compile(r"(?<![0-9a-fA-F])([0-9a-fA-F]{7,40})(?![0-9a-fA-F])")
PR_RE = re.compile(
    r"(?:\bpr\b|pull\s+request|合并请求|PR\s*编号|pr\s*编号)\s*#?\s*(\d+)",
    re.IGNORECASE,
)
FILE_PATH_RE = re.compile(
    r"[\w./-]+/[\w./-]+\.(?:py|ts|tsx|js|jsx|java|go|md|json|ya?ml|toml|rs|c|cc|cpp|h)"
)

GITHUB_CONTEXT_KEYWORDS = {
    "commit",
    "提交",
    "sha",
    "diff",
    "变更",
    "仓库",
    "repo",
    "repository",
    "pr",
    "pull request",
    "合并请求",
    "文件",
}


@dataclass
class GitHubContextInference:
    needs_github_context: bool = False
    repository_id: str | None = None
    repo_full_name: str | None = None
    commit_sha: str | None = None
    pr_number: int | None = None
    file_paths: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    matched_repositories: list[str] = field(default_factory=list)
    reason: str = ""

    @property
    def is_complete_commit_context(self) -> bool:
        return bool(self.needs_github_context and self.repository_id and self.commit_sha)

    @property
    def needs_clarification(self) -> bool:
        return bool(self.needs_github_context and not self.is_complete_commit_context)


def infer_github_context(db: Session, project_id: str, question: str) -> GitHubContextInference:
    repositories = _project_repositories(db, project_id)
    matched_repositories = _match_repositories(question, repositories)
    commit_sha = _extract_commit_sha(question)
    pr_number = _extract_pr_number(question)
    file_paths = _extract_file_paths(question)
    has_keyword = _has_github_keyword(question)
    needs_context = bool(
        commit_sha or pr_number or file_paths or matched_repositories or has_keyword
    )
    inference = GitHubContextInference(
        needs_github_context=needs_context,
        commit_sha=commit_sha,
        pr_number=pr_number,
        file_paths=file_paths,
        matched_repositories=[repo.repo_full_name for repo in matched_repositories],
        reason=_context_reason(commit_sha, pr_number, file_paths, matched_repositories, has_keyword),
    )
    if not needs_context:
        return inference

    selected_repo = _select_repository(matched_repositories, repositories, commit_sha)
    if selected_repo:
        inference.repository_id = selected_repo.id
        inference.repo_full_name = selected_repo.repo_full_name

    if not repositories:
        inference.missing_fields.append("已同步 GitHub 仓库")
    elif not inference.repository_id:
        inference.missing_fields.append("仓库")
    if not inference.commit_sha:
        inference.missing_fields.append("commit SHA")
    return inference


def build_github_clarification_answer(inference: GitHubContextInference) -> str:
    missing = "、".join(inference.missing_fields) or "仓库和 commit SHA"
    lines = [
        "我识别到你在问代码仓库相关问题，但还缺少可以安全读取真实 GitHub 上下文的信息。",
        "",
        f"请补充：{missing}。",
    ]
    if inference.pr_number is not None:
        lines.append(
            f"我也识别到了 PR #{inference.pr_number}。当前自动 MCP 问答优先支持 commit 级上下文，请提供对应 commit SHA；GitHub PR 审查仍可在代码审查入口使用。"
        )
    if inference.matched_repositories:
        lines.append("已识别仓库候选：" + "、".join(inference.matched_repositories))
    if inference.file_paths:
        lines.append("已识别文件线索：" + "、".join(inference.file_paths[:3]))
    lines.append("")
    lines.append("例如：`请审查 lab/demo-platform 仓库的 commit abc1234`。")
    return "\n".join(lines)


def _project_repositories(db: Session, project_id: str) -> list[GithubRepository]:
    return (
        db.query(GithubRepository)
        .join(GithubIntegration, GithubIntegration.id == GithubRepository.integration_id)
        .filter(GithubIntegration.project_id == project_id)
        .filter(GithubRepository.status == "active")
        .order_by(GithubRepository.repo_full_name.asc())
        .all()
    )


def _match_repositories(question: str, repositories: list[GithubRepository]) -> list[GithubRepository]:
    normalized = question.lower()
    matches = []
    for repo in repositories:
        full_name = repo.repo_full_name.lower()
        short_name = full_name.rsplit("/", 1)[-1]
        if full_name in normalized or short_name in normalized:
            matches.append(repo)
    return matches


def _select_repository(
    matched: list[GithubRepository], repositories: list[GithubRepository], commit_sha: str | None
) -> GithubRepository | None:
    if len(matched) == 1:
        return matched[0]
    if len(matched) > 1:
        return None
    if commit_sha and len(repositories) == 1:
        return repositories[0]
    return None


def _extract_commit_sha(question: str) -> str | None:
    match = COMMIT_SHA_RE.search(question)
    return match.group(1) if match else None


def _extract_pr_number(question: str) -> int | None:
    match = PR_RE.search(question)
    return int(match.group(1)) if match else None


def _extract_file_paths(question: str) -> list[str]:
    return list(dict.fromkeys(FILE_PATH_RE.findall(question)))


def _has_github_keyword(question: str) -> bool:
    normalized = question.lower()
    return any(keyword in normalized for keyword in GITHUB_CONTEXT_KEYWORDS)


def _context_reason(
    commit_sha: str | None,
    pr_number: int | None,
    file_paths: list[str],
    matched_repositories: list[GithubRepository],
    has_keyword: bool,
) -> str:
    if commit_sha:
        return "commit_sha_detected"
    if pr_number is not None:
        return "pr_number_detected"
    if matched_repositories:
        return "repository_detected"
    if file_paths:
        return "file_path_detected"
    if has_keyword:
        return "github_keyword_detected"
    return ""
