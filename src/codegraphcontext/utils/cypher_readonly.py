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
)
_STRING_LITERAL_RE = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')
_LINE_COMMENT_RE = re.compile(r"//[^\n]*")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


def strip_string_literals(query: str) -> str:
    return _STRING_LITERAL_RE.sub("", query)


def _strip_comments(query: str) -> str:
    without_block = _BLOCK_COMMENT_RE.sub("", query)
    return _LINE_COMMENT_RE.sub("", without_block)


def is_read_only_cypher(query: str) -> bool:
    """Return True when *query* has no write keywords outside string literals."""
    if not query or not query.strip():
        return False
    stripped = _strip_comments(strip_string_literals(query))
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
