"""
Regression tests for two FalkorDB + watcher bugs fixed together:

Bug 1 — schema.py: CREATE CONSTRAINT sent to FalkorDB backends
    FalkorDB has a null-pointer crash (SEGV) in EnforceUniqueEntity when
    composite UNIQUE constraints are created alongside batched UNWIND…MERGE.
    Fix: skip all CREATE CONSTRAINT statements when backend_type starts with
    "falkordb" (covers both embedded "falkordb" and remote "falkordb-remote").

Bug 2 — graph_builder.py update_file_in_graph: generic files silently dropped
    parse_file() returns {"error": "Generic file type …", "unsupported": False}
    for .md, .yml, .json, etc.  The watcher's update_file_in_graph() checked
    only `"error" not in file_data`, so generic files were logged as errors and
    returned None — the add_minimal_file_node() path was never reached.
    Fix: mirror pipeline.py logic — call add_minimal_file_node when
    "error" in file_data and not file_data.get("unsupported").
"""

from pathlib import Path
from unittest.mock import MagicMock, call, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _RecordingSession:
    """Records every query string passed to .run()."""

    def __init__(self):
        self.queries: list[str] = []

    def run(self, query: str, **_kwargs):
        self.queries.append(query)
        return MagicMock(result_set=[])

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class _FakeDriver:
    def __init__(self, session: _RecordingSession):
        self._session = session

    def session(self):
        return self._session


def _make_db_manager(backend_type: str):
    m = MagicMock()
    m.get_backend_type.return_value = backend_type
    return m


# ---------------------------------------------------------------------------
# Bug 1: schema.py — CREATE CONSTRAINT must not be sent to FalkorDB backends
# ---------------------------------------------------------------------------

class TestCreateGraphSchemaFalkorDB:

    def _run_schema(self, backend_type: str):
        from codegraphcontext.tools.indexing.schema import create_graph_schema

        session = _RecordingSession()
        driver = _FakeDriver(session)
        db_manager = _make_db_manager(backend_type)
        create_graph_schema(driver, db_manager)
        return session.queries

    def test_embedded_falkordb_sends_no_create_constraint(self):
        """Backend 'falkordb' (embedded Lite) must not receive CREATE CONSTRAINT."""
        queries = self._run_schema("falkordb")
        constraint_queries = [q for q in queries if "CREATE CONSTRAINT" in q]
        assert constraint_queries == [], (
            f"Expected no CREATE CONSTRAINT for 'falkordb', got: {constraint_queries}"
        )

    def test_remote_falkordb_sends_no_create_constraint(self):
        """Backend 'falkordb-remote' must not receive CREATE CONSTRAINT.

        This was the primary regression: the original guard used
        `backend_type == 'falkordb'` (strict equality), so 'falkordb-remote'
        was not matched and CONSTRAINT statements were sent — crashing the server.
        """
        queries = self._run_schema("falkordb-remote")
        constraint_queries = [q for q in queries if "CREATE CONSTRAINT" in q]
        assert constraint_queries == [], (
            f"Expected no CREATE CONSTRAINT for 'falkordb-remote', got: {constraint_queries}"
        )

    def test_neo4j_sends_create_constraint(self):
        """Neo4j backend must still receive CREATE CONSTRAINT statements."""
        queries = self._run_schema("neo4j")
        constraint_queries = [q for q in queries if "CREATE CONSTRAINT" in q]
        assert len(constraint_queries) > 0, "Expected CREATE CONSTRAINT queries for neo4j"

    def test_embedded_falkordb_still_sends_create_index(self):
        """Indices are always sent — they are what makes MERGE deduplication work."""
        queries = self._run_schema("falkordb")
        index_queries = [q for q in queries if "CREATE INDEX" in q]
        assert len(index_queries) > 0, "Expected CREATE INDEX queries for 'falkordb'"

    def test_remote_falkordb_still_sends_create_index(self):
        """Indices are always sent for 'falkordb-remote' too."""
        queries = self._run_schema("falkordb-remote")
        index_queries = [q for q in queries if "CREATE INDEX" in q]
        assert len(index_queries) > 0, "Expected CREATE INDEX queries for 'falkordb-remote'"


# ---------------------------------------------------------------------------
# Bug 2: update_file_in_graph — generic files must reach add_minimal_file_node
# ---------------------------------------------------------------------------

class TestUpdateFileInGraphGenericFiles:
    """
    update_file_in_graph is the watcher's incremental update path.
    Before the fix, generic files (.md, .yml, .json, .cfg, etc.) were silently
    dropped: parse_file() returned {"error": ..., "unsupported": False} and the
    method logged an error then returned None, never calling add_minimal_file_node.
    """

    def _make_graph_builder_stub(self):
        """Build a minimal GraphBuilder stub with the real update_file_in_graph method."""
        from codegraphcontext.tools.graph_builder import GraphBuilder
        from codegraphcontext.tools.indexing.persistence.writer import GraphWriter

        session = _RecordingSession()
        driver = _FakeDriver(session)

        gb = GraphBuilder.__new__(GraphBuilder)
        gb.driver = driver
        gb._writer = GraphWriter(driver)
        gb.parsers = {}
        gb.generic_extensions = {".md", ".yml", ".yaml", ".json", ".toml", ".cfg", ".txt"}
        gb.generic_filenames = {"Makefile", "Dockerfile", ".gitignore"}
        return gb

    def test_generic_file_calls_add_minimal_file_node(self, tmp_path):
        """A .md file must trigger add_minimal_file_node, not be silently dropped."""
        gb = self._make_graph_builder_stub()
        readme = tmp_path / "README.md"
        readme.write_text("# Hello")

        generic_result = {"path": str(readme), "error": "Generic file type .md", "unsupported": False}

        with (
            patch.object(gb, "delete_file_from_graph"),
            patch.object(gb, "parse_file", return_value=generic_result),
            patch.object(gb, "add_file_to_graph") as mock_add_full,
            patch.object(gb, "add_minimal_file_node") as mock_add_minimal,
        ):
            result = gb.update_file_in_graph(readme, tmp_path, imports_map={})

        mock_add_minimal.assert_called_once_with(readme, tmp_path)
        mock_add_full.assert_not_called()
        assert result == generic_result

    def test_unsupported_file_is_still_skipped(self, tmp_path):
        """A truly unsupported extension (unsupported=True) must NOT call add_minimal_file_node."""
        gb = self._make_graph_builder_stub()
        weird = tmp_path / "binary.xyz"
        weird.write_bytes(b"\x00\x01")

        unsupported_result = {"path": str(weird), "error": "No parser for .xyz", "unsupported": True}

        with (
            patch.object(gb, "delete_file_from_graph"),
            patch.object(gb, "parse_file", return_value=unsupported_result),
            patch.object(gb, "add_file_to_graph") as mock_add_full,
            patch.object(gb, "add_minimal_file_node") as mock_add_minimal,
        ):
            result = gb.update_file_in_graph(weird, tmp_path, imports_map={})

        mock_add_minimal.assert_not_called()
        mock_add_full.assert_not_called()
        assert result is None

    def test_code_file_calls_add_file_to_graph(self, tmp_path):
        """A parseable code file must still go through add_file_to_graph (not minimal)."""
        gb = self._make_graph_builder_stub()
        source = tmp_path / "main.py"
        source.write_text("def hello(): pass")

        code_result = {"path": str(source), "functions": [{"name": "hello"}]}

        with (
            patch.object(gb, "delete_file_from_graph"),
            patch.object(gb, "parse_file", return_value=code_result),
            patch.object(gb, "add_file_to_graph") as mock_add_full,
            patch.object(gb, "add_minimal_file_node") as mock_add_minimal,
        ):
            result = gb.update_file_in_graph(source, tmp_path, imports_map={})

        mock_add_full.assert_called_once()
        mock_add_minimal.assert_not_called()
        assert result == code_result

    def test_deleted_file_returns_deleted_sentinel(self, tmp_path):
        """A file that no longer exists on disk must return the deleted sentinel."""
        gb = self._make_graph_builder_stub()
        gone = tmp_path / "gone.py"
        # Deliberately NOT created — it doesn't exist

        with (
            patch.object(gb, "delete_file_from_graph"),
            patch.object(gb, "add_file_to_graph") as mock_add_full,
            patch.object(gb, "add_minimal_file_node") as mock_add_minimal,
        ):
            result = gb.update_file_in_graph(gone, tmp_path, imports_map={})

        mock_add_full.assert_not_called()
        mock_add_minimal.assert_not_called()
        assert result == {"deleted": True, "path": str(gone.resolve())}

    @staticmethod
    def _generic_extensions_sample():
        return [".md", ".yml", ".yaml", ".json", ".cfg", ".txt", ".toml"]

    def test_all_generic_extensions_reach_minimal_node(self, tmp_path):
        """Parametric check: every generic extension must reach add_minimal_file_node."""
        gb = self._make_graph_builder_stub()

        for ext in self._generic_extensions_sample():
            f = tmp_path / f"file{ext}"
            f.write_text("content")
            generic_result = {
                "path": str(f),
                "error": f"Generic file type {ext}",
                "unsupported": False,
            }

            with (
                patch.object(gb, "delete_file_from_graph"),
                patch.object(gb, "parse_file", return_value=generic_result),
                patch.object(gb, "add_file_to_graph"),
                patch.object(gb, "add_minimal_file_node") as mock_minimal,
            ):
                gb.update_file_in_graph(f, tmp_path, imports_map={})

            assert mock_minimal.called, f"add_minimal_file_node not called for {ext}"
