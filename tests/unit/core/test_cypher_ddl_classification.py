"""Regression tests for DDL classification and nested-function containment."""
import inspect

import pytest

from codegraphcontext.utils.cypher_ddl import ddl_kind, is_schema_ddl, strip_cypher_literals

REAL_DDL = [
    ("CREATE INDEX IF NOT EXISTS FOR (f:Function) ON (f.name)", "index"),
    ("CREATE INDEX function_lang IF NOT EXISTS FOR (f:Function) ON (f.lang)", "index"),
    ("  create index for (c:Class) on (c.name)", "index"),
    ("DROP INDEX foo", "index"),
    ("CREATE CONSTRAINT c1 IF NOT EXISTS FOR (f:File) REQUIRE f.path IS UNIQUE", "constraint"),
    ("CREATE FULLTEXT INDEX code_search FOR (n:Function) ON EACH [n.name]", "fulltext"),
    ("CALL db.idx.fulltext.createNodeIndex('Function', 'name', 'source')", "fulltext"),
]

# Data queries that merely *mention* the DDL keywords.
NOT_DDL = [
    'MATCH (f:Function) WHERE f.source CONTAINS "CREATE INDEX" RETURN count(f) AS c',
    'MATCH (f:Function) WHERE f.source CONTAINS "CREATE FULLTEXT INDEX" RETURN count(f) AS c',
    "MATCH (f) WHERE f.name = 'CREATE CONSTRAINT' RETURN f",
    "MATCH (f) WHERE f.doc = 'DROP INDEX' RETURN f",
    "// CREATE INDEX in a comment\nMATCH (n) RETURN n",
    "/* CREATE CONSTRAINT */ MATCH (n) RETURN n",
    "MATCH (n) RETURN n",
    "MERGE (n:Function {name: 'CREATE INDEX'}) RETURN n",
    "MATCH (n:`CREATE INDEX`) RETURN n",
]


@pytest.mark.parametrize("query,kind", REAL_DDL)
def test_real_ddl_is_classified(query, kind):
    assert is_schema_ddl(query) is True
    assert ddl_kind(query) == kind


@pytest.mark.parametrize("query", NOT_DDL)
def test_data_queries_are_not_ddl(query):
    """A substring search over the whole query text also matched these words
    inside string literals, so an ordinary read query was silently replaced
    with `RETURN 1` — a fabricated value of the wrong shape, with no error:

        cgc query 'MATCH (f:Function) WHERE f.source CONTAINS "CREATE INDEX"
                   RETURN count(f) AS c'
        -> [ { "1": 1 } ]      instead of  [ { "c": 5 } ]

    `execute_cypher_query` is the designated expert fallback for agents, so an
    agent inspecting CGC's own schema code hits this directly.
    """
    assert is_schema_ddl(query) is False
    assert ddl_kind(query) is None


def test_strip_cypher_literals_preserves_length():
    query = "MATCH (n) WHERE n.x = 'abc' RETURN n"
    assert len(strip_cypher_literals(query)) == len(query)
    assert "abc" not in strip_cypher_literals(query)


def test_both_backends_use_the_anchored_classifier():
    from codegraphcontext.core import database_embedded_kuzu, database_falkordb

    kuzu_src = inspect.getsource(database_embedded_kuzu)
    falkor_src = inspect.getsource(database_falkordb)

    assert 'any(x in query.upper() for x in ["CREATE CONSTRAINT", "CREATE INDEX"])' not in kuzu_src
    assert "is_schema_ddl(query)" in kuzu_src
    assert 'if "CREATE FULLTEXT INDEX" in q_upper' not in falkor_src
    assert "ddl_kind(query)" in falkor_src


def test_nested_containment_carries_the_outer_line():
    """The nested-function CONTAINS write matched the outer function by name
    and path only. The parser already knew the enclosing definition's line
    (`_get_parent_context` returns name, type, line) but discarded it, so a
    file with two same-named functions — the same method on two classes, which
    is extremely common — got a false containment edge from each."""
    from codegraphcontext.tools.indexing.persistence import writer as writer_mod

    source = inspect.getsource(writer_mod)
    assert '"outer_line": outer_line' in source
    assert "row.outer_line < 0 OR outer.line_number = row.outer_line" in source


def test_python_parser_reports_the_enclosing_definition_line():
    from codegraphcontext.tools.languages import python as python_lang

    source = inspect.getsource(python_lang)
    assert "context, context_type, context_line = self._get_parent_context" in source
    assert '"context_line"' in source
    assert '"class_context_line"' in source
