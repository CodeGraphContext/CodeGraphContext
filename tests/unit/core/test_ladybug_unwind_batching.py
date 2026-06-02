"""#1605: relationship-only UNWIND MERGEs batch; node-MERGE shapes fall back.

Ladybug 0.11.3's MERGE pipeline mis-binds when a merged node's key repeats
non-adjacently in one UNWIND batch: in [(A,P), (B,X), (C,P)] the C row binds
to X's node instead of re-matching P. Relationship-only MERGEs do not exhibit
the bug, so the forced per-row fallback is now scoped to queries that MERGE a
node inside the UNWIND — everything else batches, which removes most of the
per-row planner overhead.
"""
from pathlib import Path

import pytest

from codegraphcontext.core.database_ladybug import LadybugDBManager

kuzu = pytest.importorskip("kuzu")


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


def test_relationship_only_merge_batches_in_one_execution(driver):
    """A MATCH…MATCH…MERGE-rel UNWIND must reach the engine once for the whole
    batch (not once per row) and still bind every endpoint correctly, even
    with interleaved repeated endpoint keys and duplicate pairs."""
    import codegraphcontext.core.database_embedded_kuzu as dek

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
        orig = kuzu.Connection.execute

        def counting_execute(self, query, *a, **k):
            executions.append(str(query)[:60])
            return orig(self, query, *a, **k)

        kuzu.Connection.execute = counting_execute
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
            kuzu.Connection.execute = orig

        got = sorted(
            (r["c"], r["p"]) for r in s.run(
                "MATCH (c:Class)-[:INHERITS]->(p:ExternalClass) "
                "RETURN c.name AS c, p.name AS p"
            ).data()
        )

    assert got == [("A", "P"), ("B", "X"), ("C", "P")], got
    assert len(executions) == 1, (
        f"relationship-only UNWIND should execute once for the whole batch, "
        f"ran {len(executions)}: {executions}"
    )
