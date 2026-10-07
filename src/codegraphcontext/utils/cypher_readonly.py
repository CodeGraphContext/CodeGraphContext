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

# `CALL` is not blocklisted by procedure name (apoc/dbms/db.* prefixes) — that
# approach is provably incomplete against any procedure library that doesn't
# share those prefixes, e.g. Neo4j GDS write/mutate procedures
# (`gds.pageRank.write`, `gds.louvain.mutate`) or neosemantics
# (`n10s.rdf.import.fetch`, an SSRF and a write in one call). Instead every
# `CALL` is rejected unless its procedure name is on this explicit allowlist.
# Keep this list small and read-only; see `_calls_allowed` below.
_ALLOWED_CALL_PROCEDURES = frozenset({
    "db.labels",
    "db.relationshiptypes",
    "db.propertykeys",
    "db.schema.visualization",
    "db.indexes",
})

_FORBIDDEN_PATTERNS = (
    # Write-side APOC procedures are blocked explicitly (not only via the
    # CALL allowlist above) so they are also caught when invoked inline as
    # plain functions with no CALL keyword at all, e.g.
    # `RETURN apoc.create.uuid()`. These namespaces mutate the graph and
    # must never run on a read path.
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


# A forbidden keyword only functions as a write *clause* in clause position.
# The same word is inert — and common in real codebases' graphs — when it is:
#   n.load        a property access        (preceded by '.')
#   (n:Insert)    a label / rel-type       (preceded by ':')
#   $update       a parameter name         (preceded by '$')
#   AS set        a result-column alias    (preceded by the token AS)
# Only those provably-safe positions are carved out (#1511); anything
# ambiguous stays rejected, because a false negative here is a write slipping
# through a read-only gate while a false positive is merely an inconvenience.
_TOKEN_RE = re.compile(r"\w+|[^\w\s]")


def _in_clause_position(tokens: list[str], i: int) -> bool:
    prev = tokens[i - 1] if i > 0 else ""
    return not (prev in (".", ":", "$") or prev.upper() == "AS")


def _keyword_in_clause_position(stripped: str, keyword: str) -> bool:
    tokens = _TOKEN_RE.findall(stripped)
    kw = keyword.upper()
    for i, tok in enumerate(tokens):
        if tok.upper() == kw and _in_clause_position(tokens, i):
            return True
    return False


def _calls_allowed(stripped: str) -> bool:
    """True only if every `CALL` in *stripped* invokes an allowlisted procedure.

    Fails closed: a `CALL` whose procedure name can't be parsed as a plain
    dotted identifier — e.g. the `{` that opens a `CALL { ... }` subquery —
    or that isn't in `_ALLOWED_CALL_PROCEDURES` is treated as a write.
    """
    tokens = _TOKEN_RE.findall(stripped)
    for i, tok in enumerate(tokens):
        if tok.upper() != "CALL" or not _in_clause_position(tokens, i):
            continue

        # Consume the dotted procedure name immediately after CALL:
        # IDENT ('.' IDENT)*
        name_parts: list[str] = []
        j = i + 1
        expect_ident = True
        while j < len(tokens):
            t = tokens[j]
            if expect_ident and re.fullmatch(r"[A-Za-z_]\w*", t):
                name_parts.append(t)
                j += 1
                expect_ident = False
            elif not expect_ident and t == ".":
                j += 1
                expect_ident = True
            else:
                break

        procedure_name = ".".join(name_parts).lower()
        if procedure_name not in _ALLOWED_CALL_PROCEDURES:
            return False
    return True


def is_read_only_cypher(query: str) -> bool:
    """Return True when *query* has no write keywords outside string literals
    and every CALL invokes an allowlisted read-only procedure."""
    if not query or not query.strip():
        return False
    stripped = _strip_literals_and_comments(query)
    if ";" in stripped:
        return False
    for keyword in _FORBIDDEN_KEYWORDS:
        if _keyword_in_clause_position(stripped, keyword):
            return False
    for pattern in _FORBIDDEN_PATTERNS:
        if pattern.search(stripped):
            return False
    if not _calls_allowed(stripped):
        return False
    return True


def read_only_rejection_message() -> str:
    return (
        "This tool only supports read-only queries. Prohibited keywords like "
        "CREATE, MERGE, DELETE, SET, ALTER, COPY, etc., are not allowed, and "
        "CALL is restricted to a small allowlist of read-only introspection "
        "procedures."
    )