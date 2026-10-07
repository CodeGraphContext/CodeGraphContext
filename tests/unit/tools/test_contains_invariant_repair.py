"""
Unit tests for the post-index File->CONTAINS invariant check and repair.

Regression target: on FalkorDB Lite, a property index created while parallel
workers are still writing can end up empty but operational. Every Cypher
predicate routed through that index then silently matches zero rows, which
made the per-file `MATCH (f:File) MATCH (n:Function {...occurrence_index...})
MERGE (f)-[:CONTAINS]->(n)` linking pass write nothing — while node creation
itself succeeded. `cgc stats <repo>` reported 0 functions/classes because the
scoped counters traverse Repository-[:CONTAINS*]->Function.

The fix adds GraphWriter.repair_missing_contains_links(repo_path): after
indexing, if a label has symbol nodes under the repo prefix but zero
File-[:CONTAINS]->symbol edges, warn and back-fill the edges from the
already-stored `path` property.
"""

from tests.unit.tools.test_graph_builder_perf_fixes import (
    _FakeDBManager,
    _FakeDriver,
    _FakeResult,
    _RecordingSession,
)


def _make_writer(responses=None):
    from codegraphcontext.tools.indexing.persistence.writer import GraphWriter

    session = _RecordingSession(responses=responses or [])
    driver = _FakeDriver(session)
    writer = GraphWriter(driver, db_manager=_FakeDBManager(driver, backend="falkordb"))
    return writer, session


def _count(n):
    return _FakeResult([{"c": n}])


class TestRepairMissingContainsLinks:
    """Invariant: symbols stored under the repo must be CONTAINS-linked to their File."""

    def _violation_responses(self):
        # Per label: symbols count, linked count, backfill result.
        return [
            _count(12), _count(0), _FakeResult(),   # Function: 12 nodes, 0 links
            _count(3), _count(0), _FakeResult(),    # Class: violation
            _count(40), _count(0), _FakeResult(),   # Variable: violation
        ]

    def test_backfills_every_label_that_is_unlinked(self):
        writer, session = _make_writer(self._violation_responses())
        repaired = writer.repair_missing_contains_links("/repo")

        backfills = [
            c for c in session.calls
            if "MERGE (f)-[:CONTAINS]->(n)" in c["query"]
        ]
        assert len(backfills) == 3, "Expected one back-fill MERGE per violating label"
        for label in ("Function", "Class", "Variable"):
            assert any(c["query"].count(f":{label}") >= 1 for c in backfills), (
                f"Expected a back-fill query touching {label}"
            )
        assert repaired == {"Function": 12, "Class": 3, "Variable": 40}

    def test_backfill_is_path_scoped_and_pairwise(self):
        """The repair must join File and symbol on the stored path property,
        scoped to the repository prefix — not link symbols across repos."""
        writer, session = _make_writer(self._violation_responses())
        writer.repair_missing_contains_links("/repo")

        backfill = next(
            c for c in session.calls if "MERGE (f)-[:CONTAINS]->(n)" in c["query"]
        )
        assert "STARTS WITH $repo_path" in backfill["query"]
        assert "n.path = f.path" in backfill["query"]
        assert backfill["kwargs"]["repo_path"].rstrip("/") == "/repo"

    def test_healthy_graph_writes_nothing(self):
        responses = [
            _count(12), _count(12),   # Function: fully linked
            _count(3), _count(3),     # Class: fully linked
            _count(40), _count(40),   # Variable: fully linked
        ]
        writer, session = _make_writer(responses)
        repaired = writer.repair_missing_contains_links("/repo")

        assert not any("MERGE" in c["query"] for c in session.calls)
        assert repaired == {}

    def test_empty_repo_is_a_noop(self):
        responses = [_count(0)] * 6
        writer, session = _make_writer(responses)
        repaired = writer.repair_missing_contains_links("/repo")

        assert not any("MERGE" in c["query"] for c in session.calls)
        assert repaired == {}

    def test_partial_linking_is_left_alone(self):
        """If any File->CONTAINS edge exists for a label the linking pass ran
        at least partly; blanket back-fill would mask a different bug."""
        responses = [
            _count(12), _count(5),    # Function: partially linked
            _count(3), _count(3),
            _count(40), _count(40),
        ]
        writer, session = _make_writer(responses)
        repaired = writer.repair_missing_contains_links("/repo")

        assert not any("MERGE (f)-[:CONTAINS]->(n)" in c["query"] for c in session.calls)
        assert repaired == {}


class TestPipelineWiresRepair:
    """The post-processing phase must actually invoke the invariant check."""

    def test_pipeline_calls_repair_after_linking_passes(self):
        import inspect

        from codegraphcontext.tools.indexing import pipeline

        source = inspect.getsource(pipeline)
        assert "repair_missing_contains_links" in source, (
            "pipeline.py must run the File->CONTAINS invariant check after "
            "the post-processing linking passes"
        )
