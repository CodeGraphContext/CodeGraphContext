# src/codegraphcontext/tools/indexing/sanitize.py
"""Property coercion for graph backends (shared helpers for dialects / writers)."""

from typing import Any, Dict, List, Optional, Tuple

# Neo4j RANGE indexes have an ~8 kB key-size limit. Long C++ template function names
# can exceed this. Cap string properties at 4096 chars.
MAX_STR_LEN = 4096

_SECRET_CACHE: Optional[bool] = None


def _redact_enabled() -> bool:
    global _SECRET_CACHE
    if _SECRET_CACHE is not None:
        return _SECRET_CACHE
    try:
        from ...cli.config_manager import get_config_value
        val = get_config_value("REDACT_SECRETS")
        _SECRET_CACHE = (val or "false").lower() == "true"
    except Exception:
        _SECRET_CACHE = False
    return _SECRET_CACHE


def reset_secret_cache() -> None:
    global _SECRET_CACHE
    _SECRET_CACHE = None


def sanitize_props(
    props: Dict[str, Any],
    *,
    _redact: Optional[bool] = None,
) -> Dict[str, Any]:
    """Return a copy of *props* with values coerced to database-safe types.

    FalkorDB and KùzuDB only accept node properties that are primitives
    (str, int, float, bool, None) or flat lists of primitives. Complex
    values are serialized to JSON. Strings are truncated to MAX_STR_LEN.

    When ``REDACT_SECRETS=true`` (or *_redact* is ``True``), string values
    that look like hardcoded secrets are replaced with ``[REDACTED]``.
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

    coerced = {k: _coerce(v) for k, v in props.items()}

    should_redact = _redact if _redact is not None else _redact_enabled()
    if should_redact:
        from ...utils.secret_scanner import scan_props_and_redact
        coerced, _findings = scan_props_and_redact(coerced, redact=True)

    return coerced


def sanitize_props_with_secrets(
    props: Dict[str, Any],
    *,
    redact: bool = False,
) -> Tuple[Dict[str, Any], List[Tuple[str, Optional[str]]]]:
    """Like :func:`sanitize_props` but also returns secret-detection findings.

    Returns
    -------
    (dict, list of (key, pattern))
        The sanitized (and possibly redacted) props and a list of
        ``(prop_key, pattern_name)`` tuples for every secret detected.
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

    coerced = {k: _coerce(v) for k, v in props.items()}

    from ...utils.secret_scanner import scan_props_and_redact
    result, findings = scan_props_and_redact(coerced, redact=redact)
    return result, findings
