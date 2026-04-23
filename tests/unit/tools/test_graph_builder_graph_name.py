"""Coverage for the graph_name plumbing internal to GraphBuilder and GraphWriter.

Focus areas:
- ``GraphWriter._session()`` calls ``db_manager.get_driver(graph_name=self.graph_name)``.
- ``GraphBuilder._writer_for(graph_name)`` returns a writer bound to that graph.
- ``GraphBuilder.create_schema`` is memoized per graph_name (default + each override
  runs exactly once even when called repeatedly).
"""

import threading
from unittest.mock import MagicMock, patch

from codegraphcontext.tools.graph_builder import GraphBuilder
from codegraphcontext.tools.indexing.persistence.writer import GraphWriter


def _bare_graph_builder():
    """Construct a GraphBuilder instance without triggering the real __init__."""
    gb = GraphBuilder.__new__(GraphBuilder)
    gb.db_manager = MagicMock()
    gb.db_manager.get_backend_type.return_value = "neo4j"
    gb.job_manager = MagicMock()
    gb.loop = None
    gb.parsers = {}
    gb._parsed_cache = {}
    gb._schema_created = set()
    gb._schema_lock = threading.Lock()
    return gb


# ---------------------------------------------------------------------------
# GraphWriter
# ---------------------------------------------------------------------------


def test_graph_writer_stores_db_manager_and_graph_name():
    db_manager = MagicMock()
    writer = GraphWriter(db_manager, graph_name="t1")
    assert writer.db_manager is db_manager
    assert writer.graph_name == "t1"


def test_graph_writer_default_graph_name_is_none():
    db_manager = MagicMock()
    writer = GraphWriter(db_manager)
    assert writer.graph_name is None


def test_graph_writer_session_uses_bound_graph_name():
    db_manager = MagicMock()
    driver = MagicMock()
    db_manager.get_driver.return_value = driver

    writer = GraphWriter(db_manager, graph_name="t2")
    writer._session()

    db_manager.get_driver.assert_called_with(graph_name="t2")
    driver.session.assert_called_once_with()


def test_graph_writer_session_with_none_passes_none():
    db_manager = MagicMock()
    driver = MagicMock()
    db_manager.get_driver.return_value = driver

    writer = GraphWriter(db_manager)
    writer._session()

    db_manager.get_driver.assert_called_with(graph_name=None)


# ---------------------------------------------------------------------------
# GraphBuilder._writer_for
# ---------------------------------------------------------------------------


def test_writer_for_returns_writer_bound_to_requested_graph():
    gb = _bare_graph_builder()
    # Pre-mark schema so create_schema doesn't issue DDL.
    gb._schema_created.add("tenant_a")

    writer = gb._writer_for("tenant_a")

    assert isinstance(writer, GraphWriter)
    assert writer.graph_name == "tenant_a"
    assert writer.db_manager is gb.db_manager


def test_writer_for_none_returns_writer_with_none_graph_name():
    gb = _bare_graph_builder()
    gb._schema_created.add("")

    writer = gb._writer_for(None)
    assert writer.graph_name is None


def test_writer_for_invokes_create_schema_for_that_graph():
    """First call to _writer_for(graph_name) must ensure schema is created."""
    gb = _bare_graph_builder()
    with patch(
        "codegraphcontext.tools.graph_builder.create_graph_schema"
    ) as mock_schema:
        gb._writer_for("tenant_b")
        mock_schema.assert_called_once_with(gb.db_manager, graph_name="tenant_b")


# ---------------------------------------------------------------------------
# create_schema memoization
# ---------------------------------------------------------------------------


def test_create_schema_runs_once_per_graph_name():
    gb = _bare_graph_builder()
    with patch(
        "codegraphcontext.tools.graph_builder.create_graph_schema"
    ) as mock_schema:
        gb.create_schema("graph_x")
        gb.create_schema("graph_x")
        gb.create_schema("graph_x")
        # Only the first call issues DDL; the rest are no-ops.
        assert mock_schema.call_count == 1


def test_create_schema_runs_separately_per_distinct_graph():
    gb = _bare_graph_builder()
    with patch(
        "codegraphcontext.tools.graph_builder.create_graph_schema"
    ) as mock_schema:
        gb.create_schema("graph_x")
        gb.create_schema("graph_y")
        gb.create_schema("graph_x")  # already done
        gb.create_schema(None)        # default bucket
        gb.create_schema(None)        # already done
        assert mock_schema.call_count == 3
        # Verify each distinct graph was addressed.
        called_names = [c.kwargs["graph_name"] for c in mock_schema.call_args_list]
        assert set(called_names) == {"graph_x", "graph_y", None}


# ---------------------------------------------------------------------------
# Facade methods thread graph_name through to the writer
# ---------------------------------------------------------------------------


def test_facade_methods_pass_graph_name_to_writer_for():
    """Smoke-test the facade layer: every GraphBuilder method that touches the
    writer should route through _writer_for with the caller's graph_name."""
    gb = _bare_graph_builder()
    gb._schema_created.add("tenant_c")  # skip DDL

    with patch.object(gb, "_writer_for") as mock_writer_for:
        mock_writer_for.return_value = MagicMock()

        gb.add_repository_to_graph("/repo", graph_name="tenant_c")
        gb.delete_file_from_graph("/some/path", graph_name="tenant_c")
        gb.delete_repository_from_graph("/repo", graph_name="tenant_c")

        for call in mock_writer_for.call_args_list:
            # _writer_for takes graph_name as positional first arg
            assert call.args[0] == "tenant_c" or call.kwargs.get("graph_name") == "tenant_c"
