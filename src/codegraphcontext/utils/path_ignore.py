"""
Path segment helpers aligned with IGNORE_DIRS indexing rules.

`is_dependency` on graph nodes marks separately indexed packages, not vendored
dirs inside a repo (e.g. node_modules). Analysis queries must also exclude
those paths when IGNORE_DIRS would skip them during indexing.
"""

from pathlib import Path
from typing import List, Optional

from ..cli.config_manager import DEFAULT_CONFIG, get_config_value


def parse_ignore_dir_names() -> List[str]:
    """Directory names from IGNORE_DIRS, falling back to defaults when unset or empty."""
    raw = (get_config_value("IGNORE_DIRS") or "").strip()
    if not raw:
        raw = DEFAULT_CONFIG["IGNORE_DIRS"]
    return [d.strip() for d in raw.split(",") if d.strip()]


def cypher_path_not_under_ignore_dirs(path_var: str, ignore_dir_names: Optional[List[str]] = None) -> str:
    """
    Returns a Cypher fragment that keeps only paths not under any IGNORE_DIRS segment
    (Unix `/name/` or Windows `\\name\\`).
    """
    names = ignore_dir_names if ignore_dir_names is not None else parse_ignore_dir_names()
    if not names:
        return ""
    parts: List[str] = []
    for d in names:
        esc = d.replace("\\", "\\\\").replace("'", "\\'")
        parts.append(f"{path_var} CONTAINS '/{esc}/'")
        parts.append(f"{path_var} CONTAINS '\\\\{esc}\\\\'")
    return " AND NOT (" + " OR ".join(parts) + ")"


def file_path_has_ignore_dir_segment(file_path: Path, index_root: Path) -> bool:
    """
    True if any directory segment of file_path relative to index_root matches
    IGNORE_DIRS (same logic as Tree-sitter indexing).
    """
    ignore_dirs_str = (get_config_value("IGNORE_DIRS") or "").strip()
    if not ignore_dirs_str:
        ignore_dirs_str = DEFAULT_CONFIG["IGNORE_DIRS"]
    ignore_dirs = {d.strip().lower() for d in ignore_dirs_str.split(",") if d.strip()}
    if not ignore_dirs:
        return False
    try:
        rel = file_path.resolve().relative_to(index_root.resolve())
        parts = {p.lower() for p in rel.parent.parts}
        return bool(parts.intersection(ignore_dirs))
    except ValueError:
        return False
