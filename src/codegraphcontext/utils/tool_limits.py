"""Per-tool result-count limits.

Reads ``TOOL_RESULT_LIMITS`` from the CGC config, which is a JSON object
mapping tool/query-type names to integer limits.  Unknown keys are silently
ignored; missing keys fall back to the supplied *default*.

Example .env entry::

    TOOL_RESULT_LIMITS={"find_code": 20, "analyze_code_relationships": 10, "find_dead_code": 30, "execute_cypher_query": 50}

If the env value is absent or unparseable the function always returns the
caller-supplied *default*, so existing behaviour is preserved.
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
