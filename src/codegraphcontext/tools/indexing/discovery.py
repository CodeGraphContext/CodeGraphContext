"""Enumerate files to index with ignore rules."""

import os
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

    from ...cli.config_manager import get_config_value

    ignore_dirs_str = get_config_value("IGNORE_DIRS") or ""
    ignore_dirs = {d.strip().lower() for d in ignore_dirs_str.split(",") if d.strip()}

    files: List[Path] = []
    if path.is_dir():
        for root, dirs, filenames in os.walk(path):
            root_path = Path(root)
            if ignore_dirs:
                dirs[:] = [d for d in dirs if d.lower() not in ignore_dirs]
            for filename in filenames:
                file_path = root_path / filename
                if spec:
                    try:
                        rel_path = file_path.relative_to(ignore_root).as_posix()
                        if spec.match_file(rel_path):
                            debug_log(f"Ignored file based on .cgcignore: {rel_path}")
                            continue
                    except ValueError:
                        pass
                files.append(file_path)
    elif path.is_file():
        if spec:
            try:
                rel_path = path.relative_to(ignore_root).as_posix()
                if spec.match_file(rel_path):
                    debug_log(f"Ignored file based on .cgcignore: {rel_path}")
                    return [], ignore_root
            except ValueError:
                pass
        files = [path]

    return files, ignore_root
