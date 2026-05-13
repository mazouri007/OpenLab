from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


ContextKind = Literal["github_commit", "github_pr", "manual_diff"]


@dataclass
class CodeChangedFile:
    path: str
    status: str = "modified"
    patch: str = ""
    additions: int = 0
    deletions: int = 0
    content_excerpt: str = ""
    truncated: bool = False

    def to_prompt_block(self) -> str:
        lines = [
            f"FILE: {self.path or 'unknown'}",
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
class CodeChangeContext:
    kind: ContextKind
    title: str
    repository_id: str | None = None
    repo_full_name: str | None = None
    commit_sha: str | None = None
    pr_number: int | None = None
    summary: str = ""
    source_provider: str = ""
    files: list[CodeChangedFile] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_review_input(self) -> str:
        header = [
            f"CONTEXT_KIND: {self.kind}",
            f"TITLE: {self.title}",
            f"REPOSITORY: {self.repo_full_name or 'unknown'}",
            f"COMMIT: {self.commit_sha or ''}",
            f"PR_NUMBER: {self.pr_number or ''}",
            f"SUMMARY: {self.summary}",
            f"CONTEXT_PROVIDER: {self.source_provider}",
        ]
        return "\n".join(header + ["", *[item.to_prompt_block() for item in self.files]])

    def citations(self) -> list[dict[str, Any]]:
        source_id = self.commit_sha or (f"PR #{self.pr_number}" if self.pr_number else self.kind)
        citations = [
            {
                "chunk_id": f"{self.kind}:{self.repo_full_name or 'manual'}:{source_id}",
                "snippet": self.summary or self.title,
                "source_type": self.kind,
                "source_title": self.title,
            }
        ]
        for file in self.files:
            snippet = file.patch or file.content_excerpt or f"{file.status} {file.path}"
            citations.append(
                {
                    "chunk_id": f"github_file:{file.path}" if self.kind.startswith("github") else f"diff_file:{file.path}",
                    "snippet": snippet[:240],
                    "source_type": "github_file" if self.kind.startswith("github") else "manual_diff",
                    "source_title": file.path or "diff",
                }
            )
        return citations

    def supported_test_file(self, preferred_paths: list[str] | None = None) -> CodeChangedFile | None:
        preferred_paths = preferred_paths or []
        candidates = [file for file in self.files if _language_for_path(file.path)]
        for preferred in preferred_paths:
            for file in candidates:
                if preferred in file.path or file.path.endswith(preferred):
                    return file
        return candidates[0] if candidates else None


def _language_for_path(path: str) -> str | None:
    if path.endswith(".py"):
        return "python"
    if path.endswith(".java"):
        return "java"
    return None


def language_for_path(path: str) -> str | None:
    return _language_for_path(path)


def framework_for_language(language: str) -> str:
    if language == "java":
        return "JUnit 5"
    return "pytest"
