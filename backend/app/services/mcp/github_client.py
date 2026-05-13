from __future__ import annotations

import asyncio
import json
from typing import Any

from app.core.config import get_settings


class GitHubMCPError(RuntimeError):
    """Raised when the GitHub MCP server cannot provide repository context."""


class GitHubMCPClient:
    def __init__(self, token: str) -> None:
        self.token = token
        self.settings = get_settings()

    def get_commit(self, repo_full_name: str, commit_sha: str) -> dict[str, Any]:
        owner, repo = _split_repo_full_name(repo_full_name)
        return self._call_tool(
            "get_commit",
            {
                "owner": owner,
                "repo": repo,
                "sha": commit_sha,
                "include_diff": True,
            },
        )

    def get_file_contents(
        self, repo_full_name: str, path: str, ref: str | None = None
    ) -> dict[str, Any]:
        owner, repo = _split_repo_full_name(repo_full_name)
        arguments: dict[str, Any] = {"owner": owner, "repo": repo, "path": path}
        if ref:
            arguments["ref"] = ref
        return self._call_tool("get_file_contents", arguments)

    def get_pull_request_diff(self, repo_full_name: str, pr_number: int) -> dict[str, Any]:
        owner, repo = _split_repo_full_name(repo_full_name)
        pr_payload = self._call_tool(
            "get_pull_request",
            {"owner": owner, "repo": repo, "pullNumber": pr_number},
        )
        try:
            files_payload = self._call_tool(
                "get_pull_request_files",
                {"owner": owner, "repo": repo, "pullNumber": pr_number},
            )
        except GitHubMCPError:
            files_payload = {}
        files = files_payload.get("files") or files_payload.get("data") or pr_payload.get("files") or []
        return {
            "repo_full_name": repo_full_name,
            "pr_number": pr_number,
            "title": pr_payload.get("title") or pr_payload.get("raw_text") or f"PR #{pr_number}",
            "files": files,
        }

    def _call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if not self.settings.mcp_github_enabled:
            raise GitHubMCPError("GitHub MCP is disabled by MCP_GITHUB_ENABLED=false.")
        if not self.token:
            raise GitHubMCPError("GitHub token is required for GitHub MCP calls.")
        try:
            return asyncio.run(
                asyncio.wait_for(
                    self._call_tool_async(tool_name, arguments),
                    timeout=self.settings.mcp_timeout_seconds,
                )
            )
        except GitHubMCPError:
            raise
        except FileNotFoundError as exc:
            raise GitHubMCPError(
                f"GitHub MCP command not found: {self.settings.mcp_github_command}. "
                "Install Docker or configure MCP_GITHUB_COMMAND/MCP_GITHUB_ARGS_JSON."
            ) from exc
        except TimeoutError as exc:
            raise GitHubMCPError(f"GitHub MCP tool timed out: {tool_name}") from exc
        except Exception as exc:  # noqa: BLE001
            raise GitHubMCPError(f"GitHub MCP tool failed: {tool_name}: {exc}") from exc

    async def _call_tool_async(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError as exc:
            raise GitHubMCPError(
                "Python package mcp[cli] is required for GitHub MCP integration."
            ) from exc

        env = {
            "GITHUB_PERSONAL_ACCESS_TOKEN": self.token,
            "GITHUB_TOOLSETS": self.settings.mcp_github_toolsets,
            "GITHUB_READ_ONLY": "1" if self.settings.mcp_github_read_only else "0",
        }
        server_params = StdioServerParameters(
            command=self.settings.mcp_github_command,
            args=self.settings.mcp_github_args,
            env=env,
        )
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=arguments)
                return _tool_result_to_dict(result)


def _tool_result_to_dict(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None) or getattr(
        result, "structured_content", None
    )
    if isinstance(structured, dict):
        return structured

    text_parts: list[str] = []
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if text:
            text_parts.append(text)
    raw_text = "\n".join(text_parts).strip()
    if not raw_text:
        return {}
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return {"raw_text": raw_text}
    return parsed if isinstance(parsed, dict) else {"data": parsed}


def _split_repo_full_name(repo_full_name: str) -> tuple[str, str]:
    parts = repo_full_name.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise GitHubMCPError(f"Invalid GitHub repository name: {repo_full_name}")
    return parts[0], parts[1]
