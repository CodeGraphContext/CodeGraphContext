# src/codegraphcontext/tools/indexing/discovery.py
"""Enumerate files to index with ignore rules."""

from pathlib import Path
from typing import FrozenSet, List, Optional, Set, Tuple

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

    all_files = path.rglob("*") if path.is_dir() else [path]

    if supported_extensions is not None:
        allowed_exts = supported_extensions | _GENERIC_EXTENSIONS
        files = [
            f for f in all_files
            if f.is_file() and (f.suffix in allowed_exts or f.name in _GENERIC_FILENAMES)
        ]
    else:
        files = [f for f in all_files if f.is_file()]

    from ...cli.config_manager import get_config_value

    ignore_dirs_str = get_config_value("IGNORE_DIRS") or ""
    if ignore_dirs_str and path.is_dir():
        ignore_dirs = {d.strip().lower() for d in ignore_dirs_str.split(",") if d.strip()}
        if ignore_dirs:
            kept_files = []
            for f in files:
                try:
                    parts = set(p.lower() for p in f.relative_to(path).parent.parts)
                    if not parts.intersection(ignore_dirs):
                        kept_files.append(f)
                except ValueError:
                    kept_files.append(f)
            files = kept_files

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
