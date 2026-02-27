import re
from typing import Dict, Any, List, Optional
from ...tools.github_integration import (
    authenticate_github,
    import_github_repository,
    analyze_github_commits,
    track_github_pull_requests,
    sync_github_issues,
)
from ...utils.debug_log import debug_log


def authenticate_github_handler(**args) -> Dict[str, Any]:
    """Handle GitHub authentication."""
    token = args.get("token")

    if not token:
        return {"error": "Token is required for GitHub authentication"}

    result = authenticate_github(token)
    debug_log(f"GitHub authentication: {result.get('success', False)}")

    return result


def import_github_repository_handler(**args) -> Dict[str, Any]:
    """Handle importing a GitHub repository."""
    owner = args.get("owner")
    repo = args.get("repo")
    token = args.get("token")
    target_path = args.get("target_path")

    if not owner or not repo:
        return {"error": "Owner and repository name are required"}

    result = import_github_repository(owner, repo, token, target_path)
    debug_log(f"GitHub repository import: {owner}/{repo}")

    return result


def analyze_github_commits_handler(**args) -> Dict[str, Any]:
    """Handle GitHub commit analysis."""
    owner = args.get("owner")
    repo = args.get("repo")
    token = args.get("token")
    limit = args.get("limit", 10)

    if not owner or not repo:
        return {"error": "Owner and repository name are required"}

    result = analyze_github_commits(owner, repo, token, limit)
    debug_log(f"GitHub commit analysis: {owner}/{repo}")

    return result


def track_github_pull_requests_handler(**args) -> Dict[str, Any]:
    """Handle GitHub pull request tracking."""
    owner = args.get("owner")
    repo = args.get("repo")
    token = args.get("token")
    state = args.get("state", "open")

    if not owner or not repo:
        return {"error": "Owner and repository name are required"}

    result = track_github_pull_requests(owner, repo, token, state)
    debug_log(f"GitHub PR tracking: {owner}/{repo}")

    return result


def sync_github_issues_handler(**args) -> Dict[str, Any]:
    """Handle GitHub issue synchronization."""
    owner = args.get("owner")
    repo = args.get("repo")
    token = args.get("token")
    state = args.get("state", "open")

    if not owner or not repo:
        return {"error": "Owner and repository name are required"}

    result = sync_github_issues(owner, repo, token, state)
    debug_log(f"GitHub issue sync: {owner}/{repo}")

    return result
