# src/codegraphcontext/tools/indexing/discovery.py
"""Enumerate files to index with ignore rules."""

import os
from pathlib import Path
from typing import Any, FrozenSet, List, Optional, Set, Tuple

from ...core.cgcignore import build_ignore_spec
from ...utils.debug_log import debug_log, warning_logger
from .constants import DEFAULT_IGNORE_PATTERNS

# Generic file types that are added as minimal File nodes (no source parsing).
# Must stay in sync with GraphBuilder.generic_extensions / generic_filenames.
_GENERIC_EXTENSIONS: FrozenSet[str] = frozenset({
    ".toml", ".sh", ".yaml", ".yml", ".json", ".ini", ".cfg",
    ".md", ".txt", ".env", ".bat", ".ps1", ".dockerignore", ".gitignore",
})
_GENERIC_FILENAMES: FrozenSet[str] = frozenset({"Dockerfile", "Makefile"})


def safe_walk(
    path: Path,
    spec: Optional[Any] = None,
    ignore_dirs: Optional[Set[str]] = None,
    ignore_root: Optional[Path] = None,
) -> List[Path]:
    """Recursively find files under path while:
    1. Pruning directories early if they match ignore_dirs or spec (avoiding walking into ignored directories).
    2. Logging and recovering from PermissionError / OSError.
    """
    if not path.exists():
        return []
    if not path.is_dir():
        return [path]

    if ignore_root is None:
        ignore_root = path

    if ignore_dirs is None:
        ignore_dirs = set()

    discovered_files: List[Path] = []

    def onerror(err: OSError):
        warning_logger(f"Access error during walk, skipping: {err}")

    for root_str, dirs, files in os.walk(str(path), topdown=True, onerror=onerror):
        root_path = Path(root_str)

        # Prune ignored directories in-place so os.walk does not descend into them
        i = len(dirs) - 1
        while i >= 0:
            d = dirs[i]
            d_path = root_path / d
            try:
                rel_d = d_path.relative_to(ignore_root)
                is_ignored = False
                if ignore_dirs:
                    parts = {p.lower() for p in rel_d.parts}
                    if parts.intersection(ignore_dirs):
                        is_ignored = True

                if not is_ignored and spec:
                    # gitwildmatch matches directory patterns with a trailing slash
                    rel_path_str = rel_d.as_posix() + "/"
                    if spec.match_file(rel_path_str):
                        is_ignored = True

                if is_ignored:
                    debug_log(f"Ignoring directory during walk: {rel_d}")
                    dirs.pop(i)
            except Exception:
                pass
            i -= 1

        for f in files:
            discovered_files.append(root_path / f)

    return discovered_files


def discover_files_to_index(
    path: Path,
    cgcignore_path: Optional[str] = None,
    supported_extensions: Optional[Set[str]] = None,
) -> Tuple[List[Path], Path]:
    """
    Returns (files, ignore_root). *ignore_root* is used for .cgcignore relative matching.

    ``supported_extensions`` should be the set of extensions the active parsers
    handle (e.g. ``set(parsers.keys())``).  When provided, only files whose
    suffix is in that set OR in the built-in generic extension / filename sets
    are returned.  This avoids walking tens-of-thousands of ``.properties``,
    ``.xml``, ``.conf`` etc. files that would produce "No parser found" warnings
    and contribute nothing to the graph.
    """
    ignore_root = path.resolve() if path.is_dir() else path.resolve().parent

    spec = None
    try:
        spec, resolved_cgcignore = build_ignore_spec(
            ignore_root=ignore_root,
            default_patterns=DEFAULT_IGNORE_PATTERNS,
            explicit_path=cgcignore_path,
        )
        if resolved_cgcignore:
            debug_log(f"Using .cgcignore at {resolved_cgcignore} (filtering relative to {ignore_root})")
    except OSError as e:
        warning_logger(f"Could not load/create .cgcignore: {e}")

    from ...cli.config_manager import get_config_value

    ignore_dirs_str = get_config_value("IGNORE_DIRS") or ""
    ignore_dirs = set()
    if ignore_dirs_str and path.is_dir():
        ignore_dirs = {d.strip().lower() for d in ignore_dirs_str.split(",") if d.strip()}

    all_files = safe_walk(path, spec=spec, ignore_dirs=ignore_dirs, ignore_root=ignore_root)

    if supported_extensions is not None:
        allowed_exts = supported_extensions | _GENERIC_EXTENSIONS
        files = [
            f for f in all_files
            if f.is_file() and (f.suffix in allowed_exts or f.name in _GENERIC_FILENAMES)
        ]
    else:
        files = [f for f in all_files if f.is_file()]

    if spec:
        filtered_files = []
        for f in files:
            try:
                rel_path = f.relative_to(ignore_root).as_posix()
                if not spec.match_file(rel_path):
                    filtered_files.append(f)
                else:
                    debug_log(f"Ignored file based on .cgcignore: {rel_path}")
            except ValueError:
                filtered_files.append(f)
        files = filtered_files

    return files, ignore_root

