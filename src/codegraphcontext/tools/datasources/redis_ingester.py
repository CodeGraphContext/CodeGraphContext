# src/codegraphcontext/tools/datasources/redis_ingester.py
"""Redis schema ingester (#843).

Redis is schema-less, so "schema" here means key-pattern discovery.
Scans keyspace for key patterns via SCAN + TYPE and groups them into
RedisKeyPattern nodes (e.g. "user:*", "session:*").

Requires: pip install redis
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, List, Optional


def _normalize_pattern(key: str) -> str:
    """Replace numeric / UUID segments with * to group keys into patterns.

    Examples:
        user:12345        -> user:*
        session:abc-def   -> session:*
        cache:user:99     -> cache:user:*
    """
    # Replace numeric IDs
    key = re.sub(r":\d+", ":*", key)
    # Replace UUID-like segments
    key = re.sub(
        r":[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        ":*",
        key,
        flags=re.IGNORECASE,
    )
    # Replace long hex strings (>= 12 chars)
    key = re.sub(r":[0-9a-f]{12,}", ":*", key, flags=re.IGNORECASE)
    return key


def ingest(
    host: str,
    port: int,
    db: int = 0,
    password: Optional[str] = None,
    name: Optional[str] = None,
    env: str = "production",
    scan_count: int = 1000,
    max_keys: int = 10000,
) -> Dict[str, Any]:
    """Discover Redis key patterns and return a datasource graph dict.

    Args:
        host, port, db, password: Connection parameters.
        name:        Logical datasource name. Defaults to "redis-{host}:{port}/{db}".
        env:         Deployment environment label.
        scan_count:  SCAN COUNT hint per iteration.
        max_keys:    Stop after scanning this many keys (avoid full keyspace scan in prod).

    Returns:
        {
            datasource:   {name, kind, host, env, db},
            key_patterns: [{pattern, key_type, example_key, count, datasource_name}],
        }
    """
    try:
        import redis as redis_lib
    except ImportError:
        raise ImportError(
            "Redis driver not found. Install with: pip install redis"
        )

    datasource_name = name or f"redis-{host}:{port}/{db}"

    r = redis_lib.Redis(
        host=host, port=port, db=db,
        password=password, socket_connect_timeout=10,
        decode_responses=True,
    )
    r.ping()  # fail fast if unreachable

    # SCAN for key samples
    pattern_types: Dict[str, str] = {}      # pattern -> redis type
    pattern_examples: Dict[str, str] = {}   # pattern -> one real key
    pattern_counts: Counter = Counter()

    cursor = 0
    total_scanned = 0
    while total_scanned < max_keys:
        cursor, keys = r.scan(cursor=cursor, count=scan_count)
        for key in keys:
            pat = _normalize_pattern(key)
            pattern_counts[pat] += 1
            if pat not in pattern_types:
                try:
                    pattern_types[pat] = r.type(key)
                    pattern_examples[pat] = key
                except Exception:
                    pattern_types[pat] = "unknown"
                    pattern_examples[pat] = key
        total_scanned += len(keys)
        if cursor == 0:
            break  # full scan complete

    key_patterns: List[Dict[str, Any]] = []
    for pattern, count in pattern_counts.most_common():
        key_patterns.append({
            "pattern": pattern,
            "key_type": pattern_types.get(pattern, "unknown"),
            "example_key": pattern_examples.get(pattern, ""),
            "count": count,
            "datasource_name": datasource_name,
        })

    return {
        "datasource": {
            "name": datasource_name,
            "kind": "redis",
            "host": host,
            "env": env,
            "db": db,
        },
        "key_patterns": key_patterns,
    }
