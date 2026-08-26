"""#1605: relationship-writing UNWIND MERGEs use the deterministic row fallback.

Ladybug 0.11.x's MERGE pipeline can mis-bind rows without raising an exception.
This affects both node-MERGE and relationship-only batches, including CALLS,
CONTAINS, and INHERITS writes. Execute those batches per row for correctness.
"""
from pathlib import Path

import pytest

from codegraphcontext.core.database_ladybug import LadybugDBManager
from codegraphcontext.tools.indexing.persistence.writer import GraphWriter

ladybug = pytest.importorskip("ladybug")


@pytest.fixture()
def driver(tmp_path: Path):
    manager = LadybugDBManager(str(tmp_path / "db"))
    yield manager.get_driver()
    manager.close_driver()


def _seed_classes(session, names):
    for n in names:
        session.run(
            "MERGE (c:Class {name: $n, path: $p, line_number: $ln, occurrence_index: $oi})",
            n=n, p="/f.py", ln=1, oi=0,
        )


def test_node_merge_with_interleaved_repeated_key_stays_correct(driver):
    """The (A,P),(B,X),(C,P) shape that mis-binds when batched must keep
    falling back to per-row execution and produce correct endpoints."""
    batch = [
        {"child_name": "A", "parent_name": "P"},
        {"child_name": "B", "parent_name": "X"},
        {"child_name": "C", "parent_name": "P"},
    ]
    with driver.session() as s:
        _seed_classes(s, [r["child_name"] for r in batch])
        s.run(
            """
            UNWIND $batch AS row
            MATCH (child:Class {name: row.child_name, path: '/f.py'})
            MERGE (parent:ExternalClass {name: row.parent_name})
            MERGE (child)-[r:INHERITS]->(parent)
            """,
            batch=batch,
        )
        got = sorted(
            (r["c"], r["p"]) for r in s.run(
                "MATCH (c:Class)-[:INHERITS]->(p:ExternalClass) "
                "RETURN c.name AS c, p.name AS p"
            ).data()
        )
    assert got == [("A", "P"), ("B", "X"), ("C", "P")], got


def test_relationship_only_merge_uses_per_row_fallback(driver):
    """Relationship-only batches must avoid Ladybug's silent row mis-binding."""
    batch = [
        {"c": "A", "p": "P"},
        {"c": "B", "p": "X"},
        {"c": "C", "p": "P"},   # repeated parent key, non-adjacent
        {"c": "A", "p": "P"},   # duplicate pair
    ]
    with driver.session() as s:
        _seed_classes(s, {r["c"] for r in batch})
        for n in {r["p"] for r in batch}:
            s.run("MERGE (e:ExternalClass {name: $n})", n=n)

        executions = []
        orig = ladybug.Connection.execute

        def counting_execute(self, query, *a, **k):
            executions.append(str(query)[:60])
            return orig(self, query, *a, **k)

        ladybug.Connection.execute = counting_execute
        try:
            s.run(
                """
                UNWIND $batch AS row
                MATCH (child:Class {name: row.c, path: '/f.py'})
                MATCH (parent:ExternalClass {name: row.p})
                MERGE (child)-[r:INHERITS]->(parent)
                """,
                batch=batch,
            )
        finally:
            ladybug.Connection.execute = orig

        got = sorted(
            (r["c"], r["p"]) for r in s.run(
                "MATCH (c:Class)-[:INHERITS]->(p:ExternalClass) "
                "RETURN c.name AS c, p.name AS p"
            ).data()
        )

    assert got == [("A", "P"), ("B", "X"), ("C", "P")], got
    unique_pairs = {(row["c"], row["p"]) for row in batch}
    assert len(executions) == len(unique_pairs), (
        f"relationship-only UNWIND should execute once per unique input row, "
        f"ran {len(executions)} times for {len(unique_pairs)} unique rows: "
        f"{executions}"
    )


def test_file_to_function_calls_are_persisted(driver):
    with driver.session() as session:
        session.run(
            "MERGE (f:File {path: $path, name: $name})",
            path="/repo/caller.py",
            name="caller.py",
        )
        session.run(
            "MERGE (f:Function {name: $name, path: $path, line_number: $line, "
            "occurrence_index: 0, uid: $uid})",
            name="target",
            path="/repo/target.py",
            line=3,
            uid="/repo/target.py:target:3:0",
        )

    GraphWriter(driver).write_function_call_groups(
        file_to_fn=[
            {
                "type": "file",
                "caller_file_path": "/repo/caller.py",
                "called_name": "target",
                "called_file_path": "/repo/target.py",
                "called_line_number": 3,
                "called_context": "",
                "line_number": 8,
                "full_call_name": "target",
                "args": [],
                "confidence": 1.0,
                "resolution_tier": 1,
                "confidence_label": "EXACT",
            }
        ]
    )

    with driver.session() as session:
        assert (
            session.run(
                "MATCH (:File {path: '/repo/caller.py'})-[r:CALLS]->"
                "(:Function {name: 'target', path: '/repo/target.py'}) "
                "RETURN count(r) AS c"
            ).data()[0]["c"]
            == 1
        )
