"""Repo walkers for Python (.py) and Go (.go) HTTP-server extractors (MULTI_REPO_LINKS)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence

from codegraphcontext.wire.config_values import BASE_PROFILE, ConfigValueStore
from codegraphcontext.wire.go_extractor import (
    extract_from_source as extract_go,
    looks_like_go_http_source,
)
from codegraphcontext.wire.http_extractor import HttpServerRecord
from codegraphcontext.wire.python_extractor import (
    extract_from_source as extract_py,
    looks_like_python_http_source,
)


DEFAULT_PYTHON_DIRS = (".",)
DEFAULT_GO_DIRS = (".",)


@dataclass
class LanguageScanResult:
    servers: List[HttpServerRecord] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    files_scanned: int = 0
    files_skipped: int = 0


def _scan(
    repo_root: Path,
    *,
    glob: str,
    trigger,
    extractor,
    store: Optional[ConfigValueStore],
    active_profile: str,
    include_dirs: Sequence[str],
    max_file_kb: int,
) -> LanguageScanResult:
    root = Path(repo_root).resolve()
    result = LanguageScanResult()
    seen: set = set()
    max_bytes = max_file_kb * 1024
    for rel in include_dirs:
        base = (root / rel).resolve()
        if not base.is_dir(): continue
        for path in base.rglob(glob):
            resolved = path.resolve()
            if resolved in seen: continue
            seen.add(resolved)
            try:
                size = path.stat().st_size
            except OSError:
                result.files_skipped += 1; continue
            if size > max_bytes:
                result.files_skipped += 1
                result.warnings.append(f"{path}: skipped ({size/1024:.1f} KB > {max_file_kb} KB cap)")
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                result.files_skipped += 1
                result.warnings.append(f"{path}: read error: {e}"); continue
            if not trigger(text):
                result.files_scanned += 1; continue
            per_file = extractor(text, path, store=store, active_profile=active_profile)
            result.files_scanned += 1
            result.servers.extend(per_file.servers)
            result.warnings.extend(per_file.warnings)
    return result


def scan_repo_python_http(
    repo_root: Path,
    *,
    store: Optional[ConfigValueStore] = None,
    active_profile: str = BASE_PROFILE,
    include_dirs: Sequence[str] = DEFAULT_PYTHON_DIRS,
    max_file_kb: int = 512,
) -> LanguageScanResult:
    return _scan(
        repo_root, glob="*.py",
        trigger=looks_like_python_http_source, extractor=extract_py,
        store=store, active_profile=active_profile,
        include_dirs=include_dirs, max_file_kb=max_file_kb,
    )


def scan_repo_go_http(
    repo_root: Path,
    *,
    store: Optional[ConfigValueStore] = None,
    active_profile: str = BASE_PROFILE,
    include_dirs: Sequence[str] = DEFAULT_GO_DIRS,
    max_file_kb: int = 512,
) -> LanguageScanResult:
    return _scan(
        repo_root, glob="*.go",
        trigger=looks_like_go_http_source, extractor=extract_go,
        store=store, active_profile=active_profile,
        include_dirs=include_dirs, max_file_kb=max_file_kb,
    )


__all__ = [
    "DEFAULT_GO_DIRS",
    "DEFAULT_PYTHON_DIRS",
    "LanguageScanResult",
    "scan_repo_go_http",
    "scan_repo_python_http",
]
