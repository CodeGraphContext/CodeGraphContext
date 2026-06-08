"""Path sandbox helpers for CLI and MCP tools."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List
from urllib.parse import urlparse

MAX_DISCOVERY_DEPTH = 10

# Hugging Face dataset raw URLs and GitHub release assets only.
_ALLOWED_DOWNLOAD_HOST_SUFFIXES = (
    "huggingface.co",
    "hf.co",
    "github.com",
    "raw.githubusercontent.com",
)


def get_allowed_roots() -> List[Path]:
    """Return directories under which paths may be indexed or loaded."""
    roots: List[Path] = [Path.cwd().resolve()]

    env_roots = os.environ.get("CGC_ALLOWED_ROOTS", "")
    if env_roots:
        separator = ";" if os.name == "nt" else ":"
        for entry in env_roots.split(separator):
            entry = entry.strip()
            if entry:
                roots.append(Path(entry).resolve())

    return roots


def is_path_allowed(path: Path) -> bool:
    """True when *path* resolves under an allowed root."""
    resolved = path.resolve()
    for root in get_allowed_roots():
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def is_path_under_root(path: Path, root: Path) -> bool:
    """True when *path* resolves under *root*."""
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def sanitize_bundle_filename(filename: str, default: str = "bundle.cgc") -> str:
    """Return a safe basename for a downloaded bundle file."""
    if not filename or ".." in filename or "/" in filename or "\\" in filename:
        return default
    name = Path(filename).name
    if not name or name in (".", ".."):
        return default
    if not re.fullmatch(r"[\w.\-]+\.cgc", name, flags=re.IGNORECASE):
        if not name.endswith(".cgc"):
            name = f"{re.sub(r'[^\w.\-]+', '_', name)}.cgc"
    return name


def is_safe_download_url(url: str) -> bool:
    """True when *url* uses HTTPS and points to an allowed registry host."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    return any(host == suffix or host.endswith(f".{suffix}") for suffix in _ALLOWED_DOWNLOAD_HOST_SUFFIXES)


def clamp_discovery_depth(max_depth: int) -> int:
    """Clamp discovery depth to a safe range."""
    try:
        depth = int(max_depth)
    except (TypeError, ValueError):
        return 1
    return max(0, min(depth, MAX_DISCOVERY_DEPTH))
