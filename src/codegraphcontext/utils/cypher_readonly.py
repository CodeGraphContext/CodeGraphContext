"""Shared read-only Cypher validation for CLI, MCP, and viz endpoints."""
from __future__ import annotations

import re

_FORBIDDEN_KEYWORDS = (
    "CREATE",
    "MERGE",
    "DELETE",
    "DETACH",
    "SET",
    "REMOVE",
    "DROP",
    "LOAD",
    "FOREACH",
    "ALTER",
    "COPY",
    "INSERT",
    "UPDATE",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
)
_FORBIDDEN_PATTERNS = (
    re.compile(r"CALL\s+apoc\b", re.IGNORECASE),
    re.compile(r"CALL\s+dbms\b", re.IGNORECASE),
    re.compile(r"CALL\s+db\.[a-z0-9_.]*\.(?:create|drop|delete|set|add|remove|alter)\b", re.IGNORECASE),
    re.compile(r"CALL\s+db\.[a-z0-9_.]*create", re.IGNORECASE),
    re.compile(r"CALL\s*\{"),
    # Write-side APOC procedures are blocked explicitly (not only via the bare
    # `CALL apoc` rule above) so they are also caught when invoked inline, with
    # a yield/where clause, or in any spacing the `CALL apoc` rule might miss.
    # These namespaces mutate the graph and must never run on a read path.
    re.compile(r"\bapoc\.(?:create|merge|refactor|periodic)\b", re.IGNORECASE),
)
_STRING_LITERAL_RE = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')

# Quoted spans and comments must be recognised in a single left-to-right pass.
# Stripping literals first would treat a quote *inside* a comment as the start
# of a literal, pairing it with a later real quote and deleting the write
# keywords in between:
#
#     MATCH (n) // note with '
#     DELETE n WHERE n.x = 'y' RETURN n
#
# The `'` in the comment paired with the `'` of 'y', the DELETE vanished with
# it, and the query was accepted as read-only. Backtick-quoted identifiers are
# consumed here too, so `` [r:`DELETE`] `` is not mistaken for a write clause.
_LITERAL_OR_COMMENT_RE = re.compile(
    r"""
      '(?:\\.|[^'\\])*'      # '...'
    | "(?:\\.|[^"\\])*"      # "..."
    | `(?:\\.|[^`\\])*`      # `...`
    | //[^\n]*               # // line comment
    | /\*.*?\*/              # /* block comment */
    """,
    re.VERBOSE | re.DOTALL,
)


def strip_string_literals(query: str) -> str:
    return _STRING_LITERAL_RE.sub("", query)


def _strip_literals_and_comments(query: str) -> str:
    # Replace with a space rather than "" so neighbouring tokens cannot fuse
    # into a new identifier once the quoted span between them is removed.
    return _LITERAL_OR_COMMENT_RE.sub(" ", query)


def is_read_only_cypher(query: str) -> bool:
    """Return True when *query* has no write keywords outside string literals."""
    if not query or not query.strip():
        return False
    stripped = _strip_literals_and_comments(query)
    if ";" in stripped:
        return False
    for keyword in _FORBIDDEN_KEYWORDS:
        if re.search(r"\b" + keyword + r"\b", stripped, re.IGNORECASE):
            return False
    for pattern in _FORBIDDEN_PATTERNS:
        if pattern.search(stripped):
            return False
    return True


def read_only_rejection_message() -> str:
    return (
        "This tool only supports read-only queries. Prohibited keywords like "
        "CREATE, MERGE, DELETE, SET, ALTER, COPY, etc., are not allowed."
    )
