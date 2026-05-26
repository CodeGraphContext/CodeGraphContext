# src/codegraphcontext/tools/indexing/discovery.py
"""Enumerate files to index with ignore rules."""

import os
import re
from pathlib import Path
from typing import Any, FrozenSet, List, Optional, Set, Tuple

from ...core.cgcignore import build_ignore_spec
from ...utils.debug_log import debug_log, info_logger, warning_logger
from ...cli.config_manager import get_config_value
from .constants import DEFAULT_IGNORE_PATTERNS

# Generic file types that are added as minimal File nodes (no source parsing).
# Must stay in sync with GraphBuilder.generic_extensions / generic_filenames.
_GENERIC_EXTENSIONS: FrozenSet[str] = frozenset({
    ".toml", ".sh", ".yaml", ".yml", ".json", ".ini", ".cfg",
    ".md", ".txt", ".env", ".bat", ".ps1", ".dockerignore", ".gitignore",
})
_GENERIC_FILENAMES: FrozenSet[str] = frozenset({"Dockerfile", "Makefile"})

# Directories that are considered test infrastructure across all supported languages.
_TEST_DIR_NAMES: FrozenSet[str] = frozenset({
    "tests", "test", "spec", "__tests__", "e2e", "__mocks__", "__snapshots__",
    "fixtures", "testdata", "test_data",
})

# File-level test patterns: matches the stem/name portion of common test file conventions.
_TEST_FILE_RE = re.compile(
    r"(^test_|_test\.|_spec\.|\.test\.|\.spec\.|^conftest\.|"
    r"Test\.(java|kt|scala|cs|swift|rb|go)$|Spec\.(java|kt|scala|cs)$)",
    re.IGNORECASE,
)


def safe_walk(
    path: Path,
    spec: Optional[Any] = None,
    ignore_dirs: Optional[Set[str]] = None,
    ignore_root: Optional[Path] = None,
    max_depth: Optional[int] = None,
) -> List[Path]:
    """Recursively find files under path while:
    1. Pruning directories early if they match ignore_dirs or spec (avoiding walking into ignored directories).
    2. Pruning directories beyond *max_depth* levels below *path* (None = unlimited).
    3. Logging and recovering from PermissionError / OSError.
    """
    if not path.exists():
        return []
    if not path.is_dir():
        return [path]

    if ignore_root is None:
        ignore_root = path

    if ignore_dirs is None:
        ignore_dirs = set()

    walk_root = path.resolve()
    discovered_files: List[Path] = []

    def onerror(err: OSError):
        warning_logger(f"Access error during walk, skipping: {err}")

    for root_str, dirs, files in os.walk(str(path), topdown=True, onerror=onerror):
        root_path = Path(root_str)

        # Compute depth relative to the walk root so we can enforce MAX_DEPTH.
        try:
            current_depth = len(root_path.resolve().relative_to(walk_root).parts)
        except ValueError:
            current_depth = 0

        # Prune ignored directories in-place so os.walk does not descend into them
        i = len(dirs) - 1
        while i >= 0:
            d = dirs[i]
            d_path = root_path / d
            try:
                rel_d = d_path.relative_to(ignore_root)
                is_ignored = False

                # Depth guard: do not descend if the child directory would exceed max_depth.
                if max_depth is not None and current_depth >= max_depth:
                    is_ignored = True

                if not is_ignored and ignore_dirs:
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

    ignore_dirs_str = get_config_value("IGNORE_DIRS") or ""
    ignore_dirs = set()
    if ignore_dirs_str and path.is_dir():
        ignore_dirs = {d.strip().lower() for d in ignore_dirs_str.split(",") if d.strip()}

    # ── IGNORE_TEST_FILES ────────────────────────────────────────────────────
    # When enabled, add canonical test directory names to the ignore-dirs set
    # so os.walk prunes them during traversal (fast, no per-file stat needed).
    ignore_test_files = (get_config_value("IGNORE_TEST_FILES") or "false").strip().lower() == "true"
    if ignore_test_files and path.is_dir():
        ignore_dirs = ignore_dirs | _TEST_DIR_NAMES

    # ── MAX_DEPTH ────────────────────────────────────────────────────────────
    max_depth: Optional[int] = None
    max_depth_cfg = (get_config_value("MAX_DEPTH") or "unlimited").strip().lower()
    if max_depth_cfg != "unlimited":
        try:
            max_depth = int(max_depth_cfg)
            if max_depth < 1:
                max_depth = None
        except ValueError:
            warning_logger(f"Invalid MAX_DEPTH value '{max_depth_cfg}', ignoring.")

    all_files = safe_walk(
        path, spec=spec, ignore_dirs=ignore_dirs, ignore_root=ignore_root, max_depth=max_depth
    )

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

    # ── IGNORE_TEST_FILES (file-level patterns) ──────────────────────────────
    # Directory-level pruning is done above; this pass catches individual test
    # files that live outside dedicated test directories (e.g. unit.test.ts
    # sitting next to the source file it tests).
    if ignore_test_files:
        before = len(files)
        files = [f for f in files if not _TEST_FILE_RE.search(f.name)]
        skipped = before - len(files)
        if skipped:
            info_logger(f"IGNORE_TEST_FILES: skipped {skipped} test file(s).")

    # ── MAX_FILE_SIZE_MB ─────────────────────────────────────────────────────
    max_size_mb_cfg = get_config_value("MAX_FILE_SIZE_MB") or "10"
    try:
        max_size_bytes = float(max_size_mb_cfg) * 1024 * 1024
    except (ValueError, TypeError):
        max_size_bytes = 10 * 1024 * 1024  # default 10 MB

    before = len(files)
    oversized: List[Path] = []
    accepted: List[Path] = []
    for f in files:
        try:
            if f.stat().st_size <= max_size_bytes:
                accepted.append(f)
            else:
                oversized.append(f)
        except OSError:
            accepted.append(f)  # stat failed; include and let the parser handle it
    if oversized:
        info_logger(
            f"MAX_FILE_SIZE_MB={max_size_mb_cfg}: skipped {len(oversized)} oversized file(s) "
            f"(e.g. {oversized[0].name})."
        )
    files = accepted

    return files, ignore_root

