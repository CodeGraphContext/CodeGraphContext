"""Property coercion for graph backends (shared helpers for dialects / writers)."""

from typing import Any, Dict

# Neo4j RANGE indexes have an ~8 kB key-size limit. Long C++ template function names
# can exceed this. Cap string properties at 4096 chars.
MAX_STR_LEN = 4096


def sanitize_props(props: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of *props* with values coerced to database-safe types.

    FalkorDB and KùzuDB only accept node properties that are primitives
    (str, int, float, bool, None) or flat lists of primitives. Complex
    values are serialized to JSON. Strings are truncated to MAX_STR_LEN.
    """
    import json

    MAX = MAX_STR_LEN

    def _is_primitive(v):
        return isinstance(v, (str, int, float, bool)) or v is None

    def _is_flat_list(v):
        return isinstance(v, list) and all(_is_primitive(item) for item in v)

    def _coerce(v):
        if isinstance(v, str):
            return v[:MAX] if len(v) > MAX else v
        if _is_primitive(v):
            return v
        if _is_flat_list(v):
            return [s[:MAX] if isinstance(s, str) and len(s) > MAX else s for s in v]
        try:
            serialized = json.dumps(v, default=str)
            return serialized[:MAX] if len(serialized) > MAX else serialized
        except Exception:
            s = str(v)
            return s[:MAX] if len(s) > MAX else s

    return {k: _coerce(v) for k, v in props.items()}
