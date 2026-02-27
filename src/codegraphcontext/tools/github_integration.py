import requests
from typing import Dict, Any, Optional, List
from pathlib import Path
from ...utils.debug_log import debug_log


class GitHubIntegration:
    """Handles GitHub API interactions for repository operations."""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: Optional[str] = None):
        self.token = token
        self.headers = {}
        if token:
            self.headers["Authorization"] = f"token {token}"

    def get_repository(self, owner: str, repo: str) -> Dict[str, Any]:
        """Get repository information from GitHub."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}"
        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Failed to fetch repository: {response.status_code}"}

    def get_commits(
        self, owner: str, repo: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get commit history for a repository."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/commits"
        params = {"per_page": limit}
        response = requests.get(url, headers=self.headers, params=params)

        if response.status_code == 200:
            commits = response.json()
            return [
                {
                    "sha": commit.get("sha"),
                    "message": commit.get("commit", {}).get("message"),
                    "author": commit.get("commit", {}).get("author", {}).get("name"),
                    "date": commit.get("commit", {}).get("author", {}).get("date"),
                }
                for commit in commits
            ]
        else:
            return []

    def get_pull_requests(
        self, owner: str, repo: str, state: str = "open"
    ) -> List[Dict[str, Any]]:
        """Get pull requests for a repository."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls"
        params = {"state": state}
        response = requests.get(url, headers=self.headers, params=params)

        if response.status_code == 200:
            prs = response.json()
            return [
                {
                    "number": pr.get("number"),
                    "title": pr.get("title"),
                    "state": pr.get("state"),
                    "author": pr.get("user", {}).get("login"),
                    "created_at": pr.get("created_at"),
                    "updated_at": pr.get("updated_at"),
                }
                for pr in prs
            ]
        else:
            return []

    def get_issues(
        self, owner: str, repo: str, state: str = "open"
    ) -> List[Dict[str, Any]]:
        """Get issues for a repository."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues"
        params = {"state": state}
        response = requests.get(url, headers=self.headers, params=params)

        if response.status_code == 200:
            issues = response.json()
            return [
                {
                    "number": issue.get("number"),
                    "title": issue.get("title"),
                    "state": issue.get("state"),
                    "author": issue.get("user", {}).get("login"),
                    "created_at": issue.get("created_at"),
                    "labels": [label.get("name") for label in issue.get("labels", [])],
                }
                for issue in issues
            ]
        else:
            return []

    def clone_repository(self, clone_url: str, target_path: str) -> Dict[str, Any]:
        """Clone a GitHub repository to a local path."""
        import subprocess
        from pathlib import Path

        target_dir = Path(target_path)
        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            result = subprocess.run(
                ["git", "clone", clone_url, str(target_dir)],
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode == 0:
                return {"success": True, "path": str(target_dir)}
            else:
                return {"error": result.stderr}
        except subprocess.TimeoutExpired:
            return {"error": "Clone operation timed out"}
        except Exception as e:
            return {"error": str(e)}


def authenticate_github(token: str) -> Dict[str, Any]:
    """Authenticate with GitHub using a personal access token."""
    integration = GitHubIntegration(token)

    url = f"{GitHubIntegration.BASE_URL}/user"
    response = requests.get(url, headers=integration.headers)

    if response.status_code == 200:
        user = response.json()
        return {
            "success": True,
            "authenticated": True,
            "user": {
                "login": user.get("login"),
                "name": user.get("name"),
                "email": user.get("email"),
            },
        }
    else:
        return {
            "success": False,
            "authenticated": False,
            "error": "Invalid token or authentication failed",
        }


def import_github_repository(
    owner: str,
    repo: str,
    token: Optional[str] = None,
    target_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Import a GitHub repository for analysis."""
    integration = GitHubIntegration(token)

    repo_info = integration.get_repository(owner, repo)

    if "error" in repo_info:
        return repo_info

    if target_path is None:
        target_path = f"./{repo}"

    clone_url = repo_info.get("clone_url")
    if not clone_url:
        return {"error": "Repository clone URL not found"}

    result = integration.clone_repository(clone_url, target_path)

    if "success" in result:
        result.update({"owner": owner, "repo": repo, "clone_url": clone_url})

    return result


def analyze_github_commits(
    owner: str, repo: str, token: Optional[str] = None, limit: int = 10
) -> Dict[str, Any]:
    """Analyze commit history for a GitHub repository."""
    integration = GitHubIntegration(token)

    commits = integration.get_commits(owner, repo, limit)

    if not commits:
        return {"error": "No commits found or authentication failed"}

    return {
        "success": True,
        "repository": f"{owner}/{repo}",
        "commit_count": len(commits),
        "commits": commits,
    }


def track_github_pull_requests(
    owner: str, repo: str, token: Optional[str] = None, state: str = "open"
) -> Dict[str, Any]:
    """Track pull requests for a GitHub repository."""
    integration = GitHubIntegration(token)

    prs = integration.get_pull_requests(owner, repo, state)

    return {
        "success": True,
        "repository": f"{owner}/{repo}",
        "pull_request_count": len(prs),
        "pull_requests": prs,
    }


def sync_github_issues(
    owner: str, repo: str, token: Optional[str] = None, state: str = "open"
) -> Dict[str, Any]:
    """Synchronize issues from a GitHub repository."""
    integration = GitHubIntegration(token)

    issues = integration.get_issues(owner, repo, state)

    return {
        "success": True,
        "repository": f"{owner}/{repo}",
        "issue_count": len(issues),
        "issues": issues,
    }
