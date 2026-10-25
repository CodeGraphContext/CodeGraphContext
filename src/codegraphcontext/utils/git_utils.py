# src/codegraphcontext/utils/git_utils.py
"""Lightweight git helpers used across the indexing pipeline."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional


def get_repo_commit_hash(repo_path: Path) -> Optional[str]:
    """Return the full HEAD commit SHA for *repo_path*, or ``None`` if the path
    is not inside a git working tree or the ``git`` binary is unavailable.

    This function is intentionally silent — it never raises; callers that need
    the hash for non-critical enrichment can safely ignore a ``None`` return.
    """
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        return sha if sha else None
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None


def get_repo_branch_name(repo_path: Path) -> Optional[str]:
    """Return the active git branch name for *repo_path*, or ``None``."""
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path,
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        return branch if branch else None
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None


def get_repo_remote_url(repo_path: Path) -> Optional[str]:
    """Return the configured origin URL, or ``None`` without an origin/git.

    This only reads local git configuration; it does not contact the remote.
    The value is returned verbatim and is not logged or persisted here.
    """
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=repo_path,
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        return url if url else None
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
