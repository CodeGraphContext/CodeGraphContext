"""Enumerate files to index with ignore rules."""

from pathlib import Path
from typing import List, Optional, Tuple

from ...core.cgcignore import build_ignore_spec
from ...utils.debug_log import debug_log, warning_logger
from .constants import DEFAULT_IGNORE_PATTERNS


def discover_files_to_index(
    path: Path,
    cgcignore_path: Optional[str] = None,
) -> Tuple[List[Path], Path]:
    """
    Returns (files, ignore_root). *ignore_root* is used for .cgcignore relative matching.
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
