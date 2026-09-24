"""Classify Cypher statements as schema DDL.

Both backend wrappers used to decide "is this a CREATE INDEX / CREATE
CONSTRAINT?" with a substring search over the whole query text, e.g.::

    if "CREATE FULLTEXT INDEX" in query.upper():
        return "RETURN 1"

That also matches those words inside a *string literal*, so an ordinary read
query was silently replaced by ``RETURN 1`` — returning a fabricated value with
the wrong shape and no error::

    cgc query 'MATCH (f:Function) WHERE f.source CONTAINS "CREATE INDEX"
               RETURN count(f) AS c'
    -> [ { "1": 1 } ]        instead of  [ { "c": 5 } ]

`execute_cypher_query` is the designated expert fallback for LLM agents, so an
agent investigating CGC's own schema code hits this directly.

Detection here is anchored to the leading keyword of the statement, after
comments and string literals have been removed.
"""
from __future__ import annotations

import re

__all__ = ["strip_cypher_literals", "is_schema_ddl", "ddl_kind"]

# Single-quoted, double-quoted and backtick-quoted spans, honouring backslash
# escapes; plus // line comments and /* */ block comments.
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

_DDL_RE = re.compile(
    r"""\A\s*
    (?P<verb>CREATE|DROP)\s+
    (?:(?P<qualifier>BTREE|RANGE|TEXT|POINT|VECTOR|FULLTEXT|LOOKUP)\s+)?
    (?P<object>INDEX|CONSTRAINT)\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

#: FalkorDB's procedural index API, which is DDL despite being a CALL.
_PROC_DDL_RE = re.compile(r"\A\s*CALL\s+db\.idx\.", re.IGNORECASE)


def strip_cypher_literals(query: str) -> str:
    """Blank out string literals and comments, preserving overall length."""
    return _LITERAL_OR_COMMENT_RE.sub(lambda m: " " * len(m.group(0)), query)


def is_schema_ddl(query: str) -> bool:
    """True when *query* is a schema statement rather than a data query."""
    if not isinstance(query, str):
        return False
    stripped = strip_cypher_literals(query)
    return bool(_DDL_RE.match(stripped) or _PROC_DDL_RE.match(stripped))


def ddl_kind(query: str) -> str | None:
    """Return ``'index'``, ``'constraint'``, ``'fulltext'`` or ``None``."""
    if not isinstance(query, str):
        return None
    stripped = strip_cypher_literals(query)
    if _PROC_DDL_RE.match(stripped):
        return "fulltext"
    match = _DDL_RE.match(stripped)
    if not match:
        return None
    if (match.group("qualifier") or "").upper() == "FULLTEXT":
        return "fulltext"
    return match.group("object").lower()
