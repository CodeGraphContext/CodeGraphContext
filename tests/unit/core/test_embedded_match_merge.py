"""#1710: consecutive MATCH clauses inside UNWIND batches merge to comma-form.

LadybugDB's planner silently yields ZERO rows for
`UNWIND $b AS row MATCH (a:File {path: row.p}) MATCH (b:Function {…})` when
the first MATCH is an index-map lookup: each MATCH works alone, chained they
produce nothing, no error is raised — so downstream MERGEs quietly write no
edges. That was the parity gap's exact signature (every File-sourced CALLS
edge and five Struct CONTAINS edges missing on ladybug only, run after run).

The comma form `MATCH (a {…}), (b {…})` is semantically identical for
non-optional patterns and both engines plan it correctly, so the embedded
translation layer now rewrites adjacent MATCH clauses in UNWIND queries.
"""
from pathlib import Path

import pytest

from codegraphcontext.core.database_kuzu import KuzuDBManager

kuzu = pytest.importorskip("kuzu")


@pytest.fixture()
def driver(tmp_path: Path):
    manager = KuzuDBManager(str(tmp_path / "db"))
    yield manager.get_driver()
    manager.close_driver()


def _translate(driver, query, **params):
    with driver.session() as s:
        translated, _ = s._translate_query(query, params)
    return translated


UNWIND_DOUBLE_MATCH = """
    UNWIND $batch AS row
    MATCH (caller:File {path: row.caller_file_path})
    MATCH (called:Function {name: row.called_name, path: row.called_file_path})
    WHERE row.called_line_number <= 0 OR called.line_number = row.called_line_number
    MERGE (caller)-[c:CALLS {line_number: row.line_number}]->(called)
"""


def test_adjacent_matches_merge_to_comma_form(driver):
    translated = _translate(driver, UNWIND_DOUBLE_MATCH, batch=[{"caller_file_path": "/f.py"}])
    assert "}), " in translated.replace("\n", " ") or "}) , " in translated
    # exactly one MATCH keyword must remain
    assert translated.count("MATCH") == 1, translated


def test_triple_match_chain_fully_merges(driver):
    q = (
        "UNWIND $batch AS row "
        "MATCH (a:File {path: row.p}) "
        "MATCH (b:Function {name: row.n}) "
        "MATCH (c:Class {name: row.c}) "
        "RETURN count(*)"
    )
    translated = _translate(driver, q, batch=[{"p": "/f.py"}])
    assert translated.count("MATCH") == 1, translated


def test_where_between_matches_blocks_the_merge(driver):
    # Merging across an interposed WHERE would change which clause the
    # predicate binds to — that shape must stay untouched.
    q = (
        "UNWIND $batch AS row "
        "MATCH (outer:Function {name: row.outer}) "
        "WHERE row.outer_line < 0 OR outer.line_number = row.outer_line "
        "MATCH (inner:Function {name: row.inner_name}) "
        "MERGE (outer)-[:CONTAINS]->(inner)"
    )
    translated = _translate(driver, q, batch=[{"outer": "x"}])
    assert translated.count("MATCH") == 2, translated


def test_optional_match_is_never_merged(driver):
    q = (
        "UNWIND $batch AS row "
        "MATCH (a:File {path: row.p}) "
        "OPTIONAL MATCH (b:Function {name: row.n}) "
        "RETURN count(*)"
    )
    translated = _translate(driver, q, batch=[{"p": "/f.py"}])
    assert "OPTIONAL MATCH" in translated, translated


def test_non_unwind_queries_stay_untouched(driver):
    q = (
        "MATCH (a:File {path: $p}) "
        "MATCH (b:Function {name: $n}) "
        "RETURN count(*)"
    )
    translated = _translate(driver, q, p="/f.py", n="x")
    assert translated.count("MATCH") == 2, translated


class TestLadybugDoubleExecution:
    """LadybugDB state-dependently drops SOME rows of a batched rel-only
    UNWIND MERGE on first execution (no error raised); replaying the same
    idempotent batch immediately binds the stragglers. The compat layer
    therefore executes such batches twice on ladybug only."""

    REL_MERGE = (
        "UNWIND $batch AS row "
        "MATCH (a:Class {name: row.c}) "
        "MATCH (b:ExternalClass {name: row.p}) "
        "MERGE (a)-[r:INHERITS]->(b)"
    )

    def _run_counting(self, backend_id, query):
        from unittest.mock import MagicMock
        from codegraphcontext.core.database_embedded_kuzu import EmbeddedSessionWrapper

        conn = MagicMock()
        session = EmbeddedSessionWrapper(conn, backend_id=backend_id)
        session.run(query, batch=[{"c": "A", "p": "P"}])
        return conn.execute.call_count

    def test_ladybug_executes_rel_merge_batch_twice(self):
        assert self._run_counting("ladybugdb", self.REL_MERGE) == 2

    def test_kuzu_executes_rel_merge_batch_once(self):
        assert self._run_counting("kuzudb", self.REL_MERGE) == 1

    def test_ladybug_read_queries_execute_once(self):
        q = "UNWIND $batch AS row MATCH (a:Class {name: row.c}) RETURN count(a)"
        assert self._run_counting("ladybugdb", q) == 1


def test_merged_form_still_binds_rows_on_kuzu(driver):
    """End-to-end on the real engine: the rewritten comma-form must produce
    the same edges the two-MATCH form produced on kuzu before the rewrite."""
    with driver.session() as s:
        for name in ("A", "B"):
            s.run(
                "MERGE (c:Class {name: $n, path: $p, line_number: $ln, occurrence_index: $oi})",
                n=name, p="/f.py", ln=1, oi=0,
            )
            s.run("MERGE (e:ExternalClass {name: $n})", n=name + "_ext")
        s.run(
            """
            UNWIND $batch AS row
            MATCH (child:Class {name: row.c, path: '/f.py'})
            MATCH (parent:ExternalClass {name: row.p})
            MERGE (child)-[r:INHERITS]->(parent)
            """,
            batch=[{"c": "A", "p": "A_ext"}, {"c": "B", "p": "B_ext"}],
        )
        got = sorted(
            (r["c"], r["p"]) for r in s.run(
                "MATCH (c:Class)-[:INHERITS]->(p:ExternalClass) "
                "RETURN c.name AS c, p.name AS p"
            ).data()
        )
    assert got == [("A", "A_ext"), ("B", "B_ext")], got
