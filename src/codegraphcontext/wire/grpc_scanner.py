"""Walk Java sources and feed each to the gRPC extractor (MULTI_REPO_LINKS)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence

from codegraphcontext.wire.config_values import BASE_PROFILE, ConfigValueStore
from codegraphcontext.wire.grpc_extractor import (
    GrpcClientRecord,
    GrpcExtractionResult,
    GrpcServerRecord,
    extract_from_source,
    looks_like_grpc_source,
)
from codegraphcontext.wire.kafka_scanner import (
    DEFAULT_JAVA_EXCLUDE_PATH_PARTS,
    DEFAULT_JAVA_SOURCE_DIRS,
    _is_excluded_java_path,
)


@dataclass
class GrpcScanResult:
    servers: List[GrpcServerRecord] = field(default_factory=list)
    clients: List[GrpcClientRecord] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    files_scanned: int = 0
    files_skipped: int = 0

    def extend(self, per_file: GrpcExtractionResult) -> None:
        self.servers.extend(per_file.servers)
        self.clients.extend(per_file.clients)
        self.warnings.extend(per_file.warnings)


def scan_repo_grpc(
    repo_root: Path,
    *,
    store: Optional[ConfigValueStore] = None,
    active_profile: str = BASE_PROFILE,
    include_dirs: Sequence[str] = DEFAULT_JAVA_SOURCE_DIRS,
    exclude_path_parts: Sequence[str] = DEFAULT_JAVA_EXCLUDE_PATH_PARTS,
    max_file_kb: int = 512,
) -> GrpcScanResult:
    root = Path(repo_root).resolve()
    result = GrpcScanResult()
    seen: set = set()
    max_bytes = max_file_kb * 1024

    for rel in include_dirs:
        base = (root / rel).resolve()
        if not base.is_dir(): continue
        for path in base.rglob("*.java"):
            resolved = path.resolve()
            if resolved in seen: continue
            seen.add(resolved)
            if _is_excluded_java_path(resolved, exclude_path_parts):
                result.files_skipped += 1; continue
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
            if not looks_like_grpc_source(text):
                result.files_scanned += 1; continue
            per_file = extract_from_source(text, path, store=store, active_profile=active_profile)
            result.files_scanned += 1
            result.extend(per_file)
    return result


__all__ = ["GrpcScanResult", "scan_repo_grpc"]
