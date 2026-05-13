from __future__ import annotations

from github import Github


class GithubClient:
    def __init__(self, token: str) -> None:
        self.token = token
        self.client = Github(token) if token else None

    def list_repositories(self) -> list[dict]:
        if self.client is None:
            return [
                {"full_name": "lab/demo-platform", "default_branch": "main", "open_pr_count": 2},
            ]
        repos = []
        for repo in self.client.get_user().get_repos():
            repos.append(
                {
                    "full_name": repo.full_name,
                    "default_branch": repo.default_branch,
                    "open_pr_count": repo.open_issues_count,
                }
            )
        return repos

    def fetch_pull_request_diff(self, repo_full_name: str, pr_number: int) -> dict:
        if self.client is None:
            return {
                "repo_full_name": repo_full_name,
                "pr_number": pr_number,
                "title": "Mock PR",
                "files": [{"path": "app/main.py", "patch": "@@ -1,1 +1,5 @@"}],
            }
        repo = self.client.get_repo(repo_full_name)
        pr = repo.get_pull(pr_number)
        files = []
        for file in pr.get_files():
            files.append(
                {
                    "path": file.filename,
                    "patch": file.patch or "",
                    "status": file.status,
                    "additions": file.additions,
                    "deletions": file.deletions,
                    "changes": file.changes,
                }
            )
        return {
            "repo_full_name": repo_full_name,
            "pr_number": pr.number,
            "title": pr.title,
            "files": files,
        }

    def fetch_commit_diff(self, repo_full_name: str, commit_sha: str) -> dict:
        if self.client is None:
            return {
                "repo_full_name": repo_full_name,
                "commit_sha": commit_sha,
                "files": [{"path": "service/UserService.java", "patch": "@@ -10,3 +10,7 @@"}],
            }
        repo = self.client.get_repo(repo_full_name)
        commit = repo.get_commit(commit_sha)
        files = []
        for file in commit.files:
            files.append(
                {
                    "path": file.filename,
                    "patch": file.patch or "",
                    "status": file.status,
                    "additions": file.additions,
                    "deletions": file.deletions,
                    "changes": file.changes,
                }
            )
        return {
            "repo_full_name": repo_full_name,
            "commit_sha": commit.sha,
            "sha": commit.sha,
            "message": commit.commit.message,
            "author": {
                "login": commit.author.login if commit.author else None,
                "name": commit.commit.author.name if commit.commit.author else None,
                "email": commit.commit.author.email if commit.commit.author else None,
            },
            "stats": {
                "additions": commit.stats.additions,
                "deletions": commit.stats.deletions,
                "total": commit.stats.total,
            },
            "html_url": commit.html_url,
            "files": files,
        }
