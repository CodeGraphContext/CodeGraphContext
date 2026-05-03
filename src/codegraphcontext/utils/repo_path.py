"""Helpers for comparing indexed repository records to filesystem paths.

Rows with *no* path are skipped so the CLI never raises on ``Path(None)``. That is
intentional: corrupted graph data should not block indexing. When the graph is
queried, ``CodeFinder.list_indexed_repositories`` emits a ``logging`` warning if
any ``Repository`` row has a missing path, so the issue is visible in normal CLI
runs (see application logging configuration in ``cli.main``).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable


def repo_record_matches_path(repo: Dict[str, Any], path_obj: Path) -> bool:
    """True if *repo* has a resolvable path equal to *path_obj* (resolved)."""
    raw = repo.get("path")
    if raw is None or raw == "":
        return False
    try:
        return Path(raw).resolve() == path_obj
    except (TypeError, OSError, ValueError):
        return False


def any_repo_matches_path(repos: Iterable[Dict[str, Any]], path_obj: Path) -> bool:
    return any(repo_record_matches_path(r, path_obj) for r in repos)
