# src/codegraphcontext/tools/indexing/incremental.py
"""Content-hash-based incremental indexing helpers.

When CACHE_ENABLED=true the pipeline stores a SHA-256 digest of each file's
content on its File node in the graph.  On subsequent runs only files whose
digest has changed (or that are new) are re-parsed and re-written.

Design goals
------------
* Single bulk DB read at pipeline start (one round-trip, not N).
* Non-blocking hash computation using asyncio.to_thread.
* Single bulk DB write after each file is processed (batched via writer).
* Zero-cost on first index — the cache miss path is identical to the
  non-cache path; the only overhead is the hash computation itself.
* Safe across interrupted runs — a file whose parse failed never gets its
  hash stored, so it will be retried on the next run.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, Optional


_CHUNK = 65536  # 64 KiB read chunks for streaming hash


def compute_file_hash(file: Path) -> Optional[str]:
    """Return a hex-encoded SHA-256 digest of *file*'s content, or None on error."""
    h = hashlib.sha256()
    try:
        with open(file, "rb") as fh:
            while chunk := fh.read(_CHUNK):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def fetch_cached_hashes(driver: Any, repo_path_str: str) -> Dict[str, str]:
    """Bulk-fetch ``{absolute_file_path: content_hash}`` for all File nodes
    that belong to the given repository and have a stored hash.

    Returns an empty dict when the DB contains no cached hashes yet (first run).
    """
    result: Dict[str, str] = {}
    try:
        with driver.session() as session:
            records = session.run(
                """
                MATCH (r:Repository {path: $repo_path})-[:CONTAINS*1..]->(f:File)
                WHERE f.content_hash IS NOT NULL
                RETURN f.path AS path, f.content_hash AS hash
                """,
                repo_path=repo_path_str,
            )
            for record in records:
                if record["path"] and record["hash"]:
                    result[record["path"]] = record["hash"]
    except Exception:
        # Cache is best-effort: a DB error should not abort the index run.
        pass
    return result
