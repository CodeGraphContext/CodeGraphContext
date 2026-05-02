"""Worker-count resolution for indexing pipelines."""

from __future__ import annotations

import os

from ...cli.config_manager import get_config_value


def _auto_worker_count() -> int:
    cpu_total = os.cpu_count() or 1
    return max(1, cpu_total - 2)


def resolve_parallel_workers() -> int:
    """
    Resolve PARALLEL_WORKERS with support for auto-detection.

    Precedence is inherited from get_config_value():
      1) environment variable PARALLEL_WORKERS
      2) local/global config value from `cgc config set`
      3) default config fallback
    """
    raw = (get_config_value("PARALLEL_WORKERS") or "").strip()
    if not raw or raw.lower() == "auto":
        return _auto_worker_count()

    try:
        return max(1, int(raw))
    except ValueError:
        return _auto_worker_count()


def resolve_file_write_workers() -> int:
    """
    Resolve PARALLEL_WRITE_WORKERS for DB write fan-out.

    Precedence:
      1) PARALLEL_WRITE_WORKERS env/config
      2) PARALLEL_WORKERS env/config
      3) auto fallback

    We keep this moderately bounded by default because overly-aggressive
    parallel writes can increase lock contention on Neo4j.
    """
    raw = (get_config_value("PARALLEL_WRITE_WORKERS") or "").strip()
    if not raw:
        raw = (get_config_value("PARALLEL_WORKERS") or "").strip()

    if not raw or raw.lower() == "auto":
        base = _auto_worker_count()
    else:
        try:
            base = max(1, int(raw))
        except ValueError:
            base = _auto_worker_count()

    return max(1, min(8, base))

