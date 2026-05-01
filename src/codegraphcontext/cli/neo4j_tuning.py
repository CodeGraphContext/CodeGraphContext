from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple


def _detect_total_memory_gb() -> int:
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        pages = os.sysconf("SC_PHYS_PAGES")
        total_bytes = int(page_size) * int(pages)
        return max(1, total_bytes // (1024**3))
    except Exception:
        return 8


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def detect_neo4j_memory_settings() -> Dict[str, str]:
    total_gb = _detect_total_memory_gb()
    reserved_gb = _clamp(total_gb // 4, 4, 16)
    usable_gb = max(4, total_gb - reserved_gb)

    heap_gb = _clamp(int(usable_gb * 0.35), 2, 16)
    pagecache_gb = _clamp(int(usable_gb * 0.50), 2, 64)
    tx_gb = _clamp(int(usable_gb * 0.20), 2, 8)

    total_alloc = heap_gb + pagecache_gb + tx_gb
    if total_alloc > usable_gb:
        overflow = total_alloc - usable_gb
        pagecache_gb = max(2, pagecache_gb - overflow)

    return {
        "server.memory.heap.initial_size": f"{heap_gb}g",
        "server.memory.heap.max_size": f"{heap_gb}g",
        "server.memory.pagecache.size": f"{pagecache_gb}g",
        "dbms.memory.transaction.total.max": f"{tx_gb}g",
    }


def detect_neo4j_conf_path() -> Optional[Path]:
    env_conf = os.getenv("NEO4J_CONF")
    if env_conf:
        env_path = Path(env_conf)
        if env_path.is_dir():
            candidate = env_path / "neo4j.conf"
            if candidate.exists():
                return candidate
        elif env_path.is_file():
            return env_path

    static_candidates = [
        Path("/etc/neo4j/neo4j.conf"),
        Path.home() / ".config" / "neo4j" / "neo4j.conf",
    ]
    for candidate in static_candidates:
        if candidate.exists():
            return candidate

    glob_candidates = []
    for pattern in (
        "/opt/homebrew/Cellar/neo4j/*/libexec/conf/neo4j.conf",
        "/usr/local/Cellar/neo4j/*/libexec/conf/neo4j.conf",
    ):
        glob_candidates.extend(Path("/").glob(pattern.lstrip("/")))

    if glob_candidates:
        return max(glob_candidates, key=lambda p: p.stat().st_mtime)
    return None


def apply_neo4j_memory_tuning(conf_path: Path, settings: Dict[str, str]) -> Tuple[Path, Dict[str, str]]:
    original = conf_path.read_text()
    updated = original
    applied: Dict[str, str] = {}

    for key, value in settings.items():
        pattern = re.compile(rf"(?m)^\s*{re.escape(key)}\s*=.*$")
        replacement = f"{key}={value}"
        if pattern.search(updated):
            updated = pattern.sub(replacement, updated)
        else:
            if not updated.endswith("\n"):
                updated += "\n"
            updated += replacement + "\n"
        applied[key] = value

    backup_path = conf_path.with_name(
        f"{conf_path.name}.bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"
    )
    backup_path.write_text(original)
    conf_path.write_text(updated)
    return backup_path, applied

