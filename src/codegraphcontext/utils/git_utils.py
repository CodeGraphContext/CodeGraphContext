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
