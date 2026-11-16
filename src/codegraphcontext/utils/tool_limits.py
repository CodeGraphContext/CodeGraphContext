# src/codegraphcontext/utils/tool_limits.py
"""Per-tool result-count limits.

Reads ``TOOL_RESULT_LIMITS`` from the CGC config, which is a JSON object
mapping tool/query-type names to integer limits.  Unknown keys are silently
ignored; missing keys fall back to the supplied *default*.

Example .env entry::

    TOOL_RESULT_LIMITS={"find_code": 20, "analyze_code_relationships": 10, "find_dead_code": 30, "execute_cypher_query": 50}

If the env value is absent or unparseable the function always returns the
caller-supplied *default*, so existing behaviour is preserved.

``TOOL_QUERY_TIMEOUTS`` (same file, same shape) holds per-tool time ceilings
for read statements, in seconds; see ``get_tool_query_timeout``::

    TOOL_QUERY_TIMEOUTS={"default": 60, "find_dead_code": 600}
"""

from __future__ import annotations

import json
from typing import Optional

# Default limits applied when no config entry exists for a tool.
# These match the legacy hard-coded LIMIT values in code_finder.py so that
# the out-of-the-box experience is identical to pre-feature behaviour.
_BUILTIN_DEFAULTS: dict[str, int] = {
    "find_code": 20,
    "analyze_code_relationships": 15,
    "find_dead_code": 50,
    "find_most_complex_functions": 10,
    "execute_cypher_query": 100,
    "list_indexed_repositories": 50,
    "search_registry_bundles": 50,
    # analyze sub-types (mirrors query_type values)
    "find_callers": 20,
    "find_callees": 20,
    "find_all_callers": 50,
    "find_all_callees": 50,
    "find_importers": 20,
    "who_modifies": 20,
    "class_hierarchy": 20,
    "overrides": 20,
    "call_chain": 20,
    "module_deps": 20,
    "variable_scope": 20,
    "find_complexity": 20,
    "find_functions_by_argument": 20,
    "find_functions_by_decorator": 20,
}


def get_tool_result_limit(tool_name: str, default: Optional[int] = None) -> Optional[int]:
    """Return the configured result-count limit for *tool_name*.

    Resolution order
    ----------------
    1. ``TOOL_RESULT_LIMITS`` JSON entry for *tool_name*
    2. *default* argument (caller override)
    3. Built-in default for *tool_name* (matches legacy hard-coded limits)
    4. ``None`` (unlimited — caller must handle)

    Parameters
    ----------
    tool_name:
        The tool or query-type key, e.g. ``"find_code"`` or
        ``"analyze_code_relationships"``.
    default:
        Optional caller-supplied fallback; takes priority over built-in
        defaults when provided.
    """
    from codegraphcontext.cli.config_manager import get_config_value

    raw = get_config_value("TOOL_RESULT_LIMITS") or "{}"
    try:
        limits: dict = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        limits = {}

    if tool_name in limits:
        try:
            return max(1, int(limits[tool_name]))
        except (TypeError, ValueError):
            pass

    if default is not None:
        return default

    return _BUILTIN_DEFAULTS.get(tool_name)


# ── per-tool read-query time ceilings ─────────────────────────────────────────

#: Ceiling in seconds for every read statement of a tool without its own entry.
#: 10x the slowest read measured on a 168,745-function graph (12 s, find_dead_code).
DEFAULT_TOOL_QUERY_TIMEOUT_S: float = 120.0

#: Tools whose cost grows with repository size (measured 3-12 s on that graph).
_BUILTIN_QUERY_TIMEOUTS: dict[str, float] = {
    "find_dead_code": 300.0,
    "generate_report": 300.0,
    "get_repository_stats": 300.0,
    "export_diagram": 300.0,
    "execute_cypher_query": 300.0,
}

#: Key in TOOL_QUERY_TIMEOUTS that sets the ceiling of every tool without its own entry.
QUERY_TIMEOUT_DEFAULT_KEY = "default"


def _parse_timeout(value) -> Optional[float]:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    return seconds if seconds >= 0 else None


def get_tool_query_timeout(tool_name: Optional[str], default: Optional[float] = None) -> float:
    """Per-statement time ceiling, in seconds, for read queries of *tool_name* (0 = none).

    Applied by ``core.read_timeout.read_driver`` on Neo4j-protocol backends.

    Resolution order
    ----------------
    1. ``TOOL_QUERY_TIMEOUTS`` JSON entry for *tool_name*
    2. *default* argument (caller override)
    3. built-in entry for *tool_name* (300 s for the repo-size-bound tools)
    4. ``TOOL_QUERY_TIMEOUTS["default"]``
    5. ``DEFAULT_TOOL_QUERY_TIMEOUT_S`` (120 s)

    So ``"default"`` lowers or raises every tool *without* its own ceiling;
    the repo-size-bound tools keep their 300 s unless named explicitly.
    *tool_name* is None outside a tool call (CLI commands that open no
    ``tool_scope``), which resolves through steps 2, 4 and 5. Unparseable or
    negative values are ignored.
    """
    from codegraphcontext.cli.config_manager import get_config_value

    raw = get_config_value("TOOL_QUERY_TIMEOUTS") or "{}"
    try:
        configured = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        configured = {}
    if not isinstance(configured, dict):
        configured = {}

    def configured_value(key):
        return _parse_timeout(configured[key]) if key in configured else None

    if tool_name and configured_value(tool_name) is not None:
        return configured_value(tool_name)
    if default is not None:
        return float(default)
    if tool_name in _BUILTIN_QUERY_TIMEOUTS:
        return _BUILTIN_QUERY_TIMEOUTS[tool_name]
    if configured_value(QUERY_TIMEOUT_DEFAULT_KEY) is not None:
        return configured_value(QUERY_TIMEOUT_DEFAULT_KEY)
    return DEFAULT_TOOL_QUERY_TIMEOUT_S
