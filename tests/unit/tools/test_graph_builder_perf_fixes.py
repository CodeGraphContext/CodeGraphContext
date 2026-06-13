"""
Unit tests for performance and correctness fixes in graph_builder.py and watcher.py.

Covers Changes 2-11:
  - _resolve_function_call (V3 helper)
  - _create_all_function_calls (V3 UNWIND batching, label categorisation, skip_external)
  - add_file_to_graph (UNWIND batched writes, new repo_path_str param)
  - delete_repository_from_graph (batched, rels-first, orphan purge)
  - delete_relationship_links / delete_outgoing_calls_from_files / delete_inherits_for_files
  - watcher: all_file_data.clear() after initial scan
  - watcher: incremental _handle_modification calls delete_relationship_links
"""

import inspect
import sys
import pytest
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Minimal stubs for GraphBuilder dependencies
# ---------------------------------------------------------------------------

class _FakeResult:
    def __init__(self, rows=None):
        self._rows = rows or []

    def single(self):
        return self._rows[0] if self._rows else None

    def __iter__(self):
        return iter(self._rows)


class _RecordingSession:
    """Records every (query, kwargs) pair passed to .run()."""

    def __init__(self, responses: Optional[List[_FakeResult]] = None):
        self.calls: List[Dict] = []
        self._responses = list(responses or [])
        self._call_idx = 0

    def run(self, query: str, **kwargs):
        self.calls.append({"query": query, "kwargs": kwargs})
        if self._call_idx < len(self._responses):
            result = self._responses[self._call_idx]
        else:
            result = _FakeResult()
        self._call_idx += 1
        return result

    # context-manager support (used by GraphBuilder)
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class _FakeDriver:
    def __init__(self, session: _RecordingSession):
        self._session = session

    def session(self):
        return self._session


class _FakeDBManager:
    """Minimal stub that satisfies GraphWriter's backend detection."""

    def __init__(self, backend: str = "neo4j"):
        self._backend = backend

    def get_backend_type(self) -> str:
        return self._backend


def _make_graph_builder(session: Optional[_RecordingSession] = None,
                        backend: str = "neo4j"):
    """Return a GraphBuilder with a fake driver. Skips full __init__ setup."""
    from codegraphcontext.tools.graph_builder import GraphBuilder
    from codegraphcontext.tools.indexing.persistence.writer import GraphWriter

    gb = GraphBuilder.__new__(GraphBuilder)
    if session is None:
        session = _RecordingSession()
    gb.driver = _FakeDriver(session)
    dm = _FakeDBManager(backend)
    gb._writer = GraphWriter(gb.driver, db_manager=dm)
    gb.parsers = {}
    return gb, session


# ---------------------------------------------------------------------------
# 1. _resolve_function_call
# ---------------------------------------------------------------------------

class TestResolveFunctionCall:
    """Tests for the _resolve_function_call helper (Change 2)."""

    def _call(self, gb, call_dict, caller_path="/repo/a.py",
              local_names=None, local_imports=None, imports_map=None, skip_external=False):
        return gb._resolve_function_call(
            call_dict,
            caller_path,
            local_names or set(),
            local_imports or {},
            imports_map or {},
            skip_external,
        )

    def test_returns_none_for_builtin(self):
        gb, _ = _make_graph_builder()
        result = self._call(gb, {"name": "len", "line_number": 1, "context": None})
        assert result is None

    def test_resolves_local_function_call(self):
        gb, _ = _make_graph_builder()
        call_dict = {
            "name": "helper",
            "line_number": 5,
            "full_name": "helper",
            "args": [],
            "context": ("caller_fn", None, 3),
        }
        result = self._call(gb, call_dict, local_names={"helper"})
        assert result is not None
        assert result["called_name"] == "helper"
        assert result["called_file_path"] == "/repo/a.py"
        assert result["type"] == "function"

    def test_resolves_self_method_call(self):
        gb, _ = _make_graph_builder()
        call_dict = {
            "name": "run",
            "line_number": 10,
            "full_name": "self.run",
            "args": [],
            "context": ("caller_fn", None, 8),
        }
        result = self._call(gb, call_dict)
        assert result is not None
        assert result["called_file_path"] == "/repo/a.py"

    def test_resolves_via_imports_map(self):
        gb, _ = _make_graph_builder()
        call_dict = {
            "name": "parse",
            "line_number": 7,
            "full_name": "parse",
            "args": [],
            "context": ("caller_fn", None, 5),
        }
        imports_map = {"parse": ["/repo/parser.py"]}
        result = self._call(gb, call_dict, imports_map=imports_map)
        assert result is not None
        assert result["called_file_path"] == "/repo/parser.py"

    def test_resolves_aliased_import_to_original_symbol(self):
        gb, _ = _make_graph_builder()
        call_dict = {
            "name": "bar",
            "line_number": 4,
            "full_name": "bar",
            "args": [],
            "context": ("caller", None, 3),
        }
        imports_map = {"foo": ["/repo/module.ts"]}
        local_imports = {"bar": "foo"}

        result = self._call(
            gb,
            call_dict,
            local_imports=local_imports,
            imports_map=imports_map,
        )

        assert result is not None
        assert result["called_name"] == "foo"
        assert result["called_file_path"] == "/repo/module.ts"

    def test_skip_external_suppresses_unresolved(self):
        """When skip_external=True, calls that cannot be resolved should return None."""
        gb, _ = _make_graph_builder()
        call_dict = {
            "name": "spring_bean",
            "line_number": 12,
            "full_name": "spring_bean",
            "args": [],
            "context": ("my_fn", None, 10),
        }
        result = self._call(gb, call_dict, skip_external=True)
        assert result is None

    def test_skip_external_false_still_returns_something(self):
        """skip_external=False should NOT suppress unresolved calls."""
        gb, _ = _make_graph_builder()
        call_dict = {
            "name": "spring_bean",
            "line_number": 12,
            "full_name": "spring_bean",
            "args": [],
            "context": ("my_fn", None, 10),
        }
        result = self._call(gb, call_dict, skip_external=False)
        assert result is not None

    def test_file_type_returned_when_no_caller_context(self):
        gb, _ = _make_graph_builder()
        call_dict = {
            "name": "helper",
            "line_number": 1,
            "full_name": "helper",
            "args": [],
            "context": None,
        }
        result = self._call(gb, call_dict, local_names={"helper"})
        assert result is not None
        assert result["type"] == "file"


# ---------------------------------------------------------------------------
# 2. _create_all_function_calls  (V3 UNWIND batching)
# ---------------------------------------------------------------------------

class TestCreateAllFunctionCallsV3:
    """Tests for the V3 _create_all_function_calls method (Change 2)."""

    def _run(self, all_file_data, imports_map=None, file_class_lookup=None,
             skip_external_env="false"):
        session = _RecordingSession()
        gb, _ = _make_graph_builder(session)
        with patch("codegraphcontext.tools.indexing.resolution.calls.get_config_value",
                   return_value=skip_external_env):
            gb._create_all_function_calls(
                all_file_data,
                imports_map or {},
                file_class_lookup,
            )
        return session.calls

    def test_uses_unwind_queries(self):
        """All DB writes should use UNWIND (not individual MERGE per call)."""
        file_data = [{
            "path": "/repo/a.py",
            "functions": [{"name": "foo", "line_number": 1}],
            "classes": [],
            "imports": [],
            "function_calls": [{
                "name": "foo",
                "line_number": 5,
                "full_name": "foo",
                "args": [],
                "context": ("bar", None, 4),
            }],
        }]
        calls = self._run(file_data)
        queries = [c["query"] for c in calls]
        assert any("UNWIND" in q for q in queries), "Expected UNWIND queries"

    def test_uses_create_for_calls_rel_on_neo4j(self):
        """CALLS relationships should use CREATE on Neo4j — MERGE lock overhead
        makes large repos (35k+ edges) take 60-90 min; CREATE drops to seconds.
        All call paths delete existing CALLS before writing, so CREATE is safe."""
        file_data = [{
            "path": "/repo/a.py",
            "functions": [{"name": "foo", "line_number": 1}],
            "classes": [],
            "imports": [],
            "function_calls": [{
                "name": "foo",
                "line_number": 5,
                "full_name": "foo",
                "args": [],
                "context": ("bar", None, 4),
            }],
        }]
        calls = self._run(file_data)
        call_rels = [c["query"] for c in calls if "CALLS" in c["query"]]
        for q in call_rels:
            assert "CREATE" in q, f"Expected CREATE in CALLS query on Neo4j, got: {q[:120]}"
            assert "MERGE" not in q, f"Unexpected MERGE in CALLS query on Neo4j, got: {q[:120]}"

    def test_uses_merge_for_calls_rel_on_kuzudb(self):
        """CALLS relationships should keep MERGE on KuzuDB — its UNWIND fallback
        path can re-execute rows individually, making CREATE unsafe there."""
        file_data = [{
            "path": "/repo/a.py",
            "functions": [{"name": "foo", "line_number": 1}],
            "classes": [],
            "imports": [],
            "function_calls": [{
                "name": "foo",
                "line_number": 5,
                "full_name": "foo",
                "args": [],
                "context": ("bar", None, 4),
            }],
        }]
        session = _RecordingSession()
        gb, _ = _make_graph_builder(session, backend="kuzudb")
        with patch("codegraphcontext.tools.indexing.resolution.calls.get_config_value",
                   return_value="false"):
            gb._create_all_function_calls(file_data, {})
        call_rels = [c["query"] for c in session.calls if "CALLS" in c["query"]]
        for q in call_rels:
            assert "MERGE" in q, f"Expected MERGE in CALLS query on KuzuDB, got: {q[:120]}"

    def test_uses_merge_for_calls_rel_on_falkordb(self):
        """CALLS relationships should keep MERGE on FalkorDB."""
        file_data = [{
            "path": "/repo/a.py",
            "functions": [{"name": "foo", "line_number": 1}],
            "classes": [],
            "imports": [],
            "function_calls": [{
                "name": "foo",
                "line_number": 5,
                "full_name": "foo",
                "args": [],
                "context": ("bar", None, 4),
            }],
        }]
        session = _RecordingSession()
        gb, _ = _make_graph_builder(session, backend="falkordb")
        with patch("codegraphcontext.tools.indexing.resolution.calls.get_config_value",
                   return_value="false"):
            gb._create_all_function_calls(file_data, {})
        call_rels = [c["query"] for c in session.calls if "CALLS" in c["query"]]
        for q in call_rels:
            assert "MERGE" in q, f"Expected MERGE in CALLS query on FalkorDB, got: {q[:120]}"

    def test_calls_rel_identity_excludes_mutable_metadata(self):
        """CALLS confidence/tier should be written via SET, not baked into the
        relationship identity key — they must not appear before the SET clause."""
        file_data = [{
            "path": "/repo/a.py",
            "functions": [{"name": "foo", "line_number": 1}],
            "classes": [],
            "imports": [],
            "function_calls": [{
                "name": "foo",
                "line_number": 5,
                "full_name": "foo",
                "args": [],
                "context": ("bar", None, 4),
                "confidence": 0.9,
                "resolution_tier": 1,
            }],
        }]
        calls = self._run(file_data)
        call_write = next(c for c in calls if "CALLS" in c["query"])
        # Split on whichever keyword was used (CREATE on Neo4j, MERGE on others)
        keyword = "CREATE" if "CREATE" in call_write["query"] else "MERGE"
        rel_clause = call_write["query"].split(keyword, 1)[1].split("SET", 1)[0]

        assert "confidence" not in rel_clause
        assert "resolution_tier" not in rel_clause
        assert "SET call.confidence = row.confidence" in call_write["query"]
        assert "call.resolution_tier = row.resolution_tier" in call_write["query"]

    def test_function_call_writes_use_precise_target_filters(self):
        """CALLS writes should use target line/context hints when resolution provides them."""
        file_data = [{
            "path": "/repo/a.py",
            "functions": [
                {"name": "caller_fn", "line_number": 1, "args": []},
                {"name": "callee", "line_number": 10, "args": ["value"]},
                {"name": "callee", "line_number": 20, "args": ["value", "flag"]},
            ],
            "classes": [],
            "imports": [],
            "function_calls": [{
                "name": "callee",
                "line_number": 5,
                "full_name": "callee",
                "args": ["value", "true"],
                "context": ("caller_fn", None, 1),
            }],
        }]

        calls = self._run(file_data)
        call_write = next(c for c in calls if "CALLS" in c["query"])

        assert "called.line_number = row.called_line_number" in call_write["query"]
        assert "called.context = row.called_context" in call_write["query"]
        assert call_write["kwargs"]["batch"][0]["called_line_number"] == 20
        assert call_write["kwargs"]["batch"][0]["called_context"] == ""

    def test_function_call_batch_normalization_preserves_falsy_filters(self):
        """Valid call rows are passed through to the driver batch as-is."""
        from codegraphcontext.tools.indexing.persistence.writer import GraphWriter

        session = _RecordingSession()
        writer = GraphWriter(_FakeDriver(session))
        writer.write_function_call_groups(
            [
                {
                    "type": "function",
                    "caller_name": "caller",
                    "caller_file_path": "/repo/a.py",
                    "caller_line_number": 1,
                    "called_name": "callee",
                    "called_file_path": "/repo/a.py",
                    "called_line_number": 0,
                    "called_context": "",
                    "line_number": 5,
                    "args": [],
                    "full_call_name": "callee",
                },
            ],
        )

        call_write = next(c for c in session.calls if "CALLS" in c["query"])
        assert len(call_write["kwargs"]["batch"]) == 1
        assert call_write["kwargs"]["batch"][0]["called_line_number"] == 0
        assert call_write["kwargs"]["batch"][0]["called_context"] == ""

    def test_empty_file_data_writes_nothing(self):
        calls = self._run([])
        call_rels = [c for c in calls if "CALLS" in c.get("query", "")]
        assert call_rels == []

    def test_file_class_lookup_supplemented_from_file_data(self):
        """External file_class_lookup is supplemented with classes from all_file_data."""
        file_data = [{
            "path": "/repo/b.py",
            "functions": [],
            "classes": [{"name": "MyClass"}],
            "imports": [],
            "function_calls": [],
        }]
        external_lookup = {"/repo/other.py": {"OtherClass"}}
        session = _RecordingSession()
        gb, _ = _make_graph_builder(session)
        with patch("codegraphcontext.tools.indexing.resolution.calls.get_config_value",
                   return_value="false"):
            gb._create_all_function_calls(file_data, {}, external_lookup)
        resolved_b = Path("/repo/b.py").resolve().as_posix()
        assert resolved_b in external_lookup
        assert "MyClass" in external_lookup[resolved_b]

    def test_label_specific_queries_used(self):
        """Queries should reference specific labels like Function, Class, File — not generic nodes."""
        file_data = [{
            "path": "/repo/a.py",
            "functions": [{"name": "caller_fn", "line_number": 1}],
            "classes": [],
            "imports": [],
            "function_calls": [{
                "name": "callee",
                "line_number": 3,
                "full_name": "callee",
                "args": [],
                "context": ("caller_fn", None, 2),
            }],
        }]
        calls = self._run(file_data)
        call_queries = [c["query"] for c in calls if "CALLS" in c.get("query", "")]
        labels_found = any(
            ":Function" in q or ":Class" in q or ":File" in q
            for q in call_queries
        )
        assert labels_found, "Expected label-specific MATCH in CALLS queries"


# ---------------------------------------------------------------------------
# 3. add_file_to_graph — new repo_path_str param + UNWIND writes
# ---------------------------------------------------------------------------

class TestAddFileToGraph:
    """Tests for the batched add_file_to_graph method (Change 7)."""

    def test_accepts_repo_path_str_kwarg(self):
        """Should accept the new repo_path_str parameter without error."""
        from codegraphcontext.tools.graph_builder import GraphBuilder
        sig = inspect.signature(GraphBuilder.add_file_to_graph)
        assert "repo_path_str" in sig.parameters

    def test_repo_path_str_is_optional(self):
        """repo_path_str should have a default value (None)."""
        from codegraphcontext.tools.graph_builder import GraphBuilder
        sig = inspect.signature(GraphBuilder.add_file_to_graph)
        param = sig.parameters["repo_path_str"]
        assert param.default is None

    def test_writes_use_unwind(self):
        """Node writes should use UNWIND (not individual per-item MERGE)."""
        session = _RecordingSession(responses=[_FakeResult()])
        gb, _ = _make_graph_builder(session)
        file_data = {
            "path": "/repo/a.py",
            "lang": "python",
            "is_dependency": False,
            "functions": [{"name": "foo", "line_number": 1, "cyclomatic_complexity": 1, "args": []}],
            "classes": [],
            "variables": [],
            "imports": [],
            "function_calls": [],
        }
        gb.add_file_to_graph(file_data, "my_repo", {}, repo_path_str="/repo")
        queries = [c["query"] for c in session.calls]
        assert any("UNWIND" in q for q in queries), "Expected UNWIND batch writes"

    def test_class_function_contains_uses_class_context_line(self):
        """Same-named nested classes in one file should not all own every method."""
        session = _RecordingSession(responses=[_FakeResult()])
        gb, _ = _make_graph_builder(session)
        file_data = {
            "path": "/repo/A.kt",
            "lang": "kotlin",
            "is_dependency": False,
            "functions": [
                {
                    "name": "run",
                    "line_number": 3,
                    "args": [],
                    "class_context": "Worker",
                    "class_context_line": 2,
                },
                {
                    "name": "run",
                    "line_number": 8,
                    "args": [],
                    "class_context": "Worker",
                    "class_context_line": 7,
                },
            ],
            "classes": [
                {"name": "Worker", "line_number": 2},
                {"name": "Worker", "line_number": 7},
            ],
            "variables": [],
            "imports": [],
            "function_calls": [],
        }
        gb.add_file_to_graph(file_data, "my_repo", {}, repo_path_str="/repo")

        class_fn_call = next(
            c
            for c in session.calls
            if "MATCH (c:Class" in c["query"] and "MERGE (c)-[:CONTAINS]->(fn)" in c["query"]
        )
        assert "c.line_number = row.class_line" in class_fn_call["query"]
        assert class_fn_call["kwargs"]["batch"] == [
            {"class_name": "Worker", "class_line": 2, "func_name": "run", "func_line": 3},
            {"class_name": "Worker", "class_line": 7, "func_name": "run", "func_line": 8},
        ]

    def test_non_javascript_import_rows_are_schema_complete(self):
        """Imports without full_import_name/source parity should not break Kuzu UNWIND."""
        session = _RecordingSession(responses=[_FakeResult()])
        gb, _ = _make_graph_builder(session)
        file_data = {
            "path": "/repo/main.go",
            "lang": "go",
            "is_dependency": False,
            "functions": [],
            "classes": [],
            "variables": [],
            "imports": [
                {
                    "name": "fmt",
                    "source": "fmt",
                    "alias": None,
                    "line_number": 3,
                    "lang": "go",
                }
            ],
            "function_calls": [],
        }

        gb.add_file_to_graph(file_data, "my_repo", {}, repo_path_str="/repo")

        import_call = next(
            c for c in session.calls
            if "MERGE (f)-[r:IMPORTS {line_number: row.line_number}]->(m)" in c["query"]
        )
        assert "m.alias" not in import_call["query"]
        assert import_call["kwargs"]["batch"] == [
            {
                "name": "fmt",
                "full_import_name": "fmt",
                "imported_name": "fmt",
                "alias": None,
                "line_number": 3,
                "lang": "go",
            }
        ]

    def test_import_module_metadata_preserves_existing_node_values(self):
        """Repeated imports of the same module should not overwrite node metadata."""
        session = _RecordingSession(responses=[_FakeResult()])
        gb, _ = _make_graph_builder(session)
        file_data = {
            "path": "/repo/generics.rs",
            "lang": "rust",
            "is_dependency": False,
            "functions": [],
            "classes": [],
            "variables": [],
            "imports": [
                {
                    "name": "Display",
                    "full_import_name": "use std::fmt::{Debug, Display};",
                    "line_number": 3,
                    "alias": None,
                }
            ],
            "function_calls": [],
        }

        gb.add_file_to_graph(file_data, "my_repo", {}, repo_path_str="/repo")

        import_call = next(
            c
            for c in session.calls
            if "MERGE (f)-[r:IMPORTS {line_number: row.line_number}]->(m)" in c["query"]
        )
        assert "m.lang = coalesce(m.lang, row.lang)" in import_call["query"]
        assert "m.full_import_name = coalesce(m.full_import_name, row.full_import_name)" in import_call["query"]
        assert "r.full_import_name = row.full_import_name" in import_call["query"]

    def test_duplicate_import_metadata_uses_stable_canonical_order(self):
        """Shared Rust module nodes should prefer stable, descriptive import metadata."""
        session = _RecordingSession(responses=[_FakeResult()])
        gb, _ = _make_graph_builder(session)
        file_data = {
            "path": "/repo/modules.rs",
            "lang": "rust",
            "is_dependency": False,
            "functions": [],
            "classes": [],
            "variables": [],
            "imports": [
                {
                    "name": "Rectangle",
                    "full_import_name": "use super::shapes::{Circle, Rectangle};",
                    "line_number": 37,
                    "alias": None,
                },
                {
                    "name": "*",
                    "full_import_name": "pub use super::geometry::shapes::*;",
                    "line_number": 98,
                    "alias": None,
                },
                {
                    "name": "Rectangle",
                    "full_import_name": "pub use super::geometry::shapes::Rectangle;",
                    "line_number": 77,
                    "alias": None,
                },
                {
                    "name": "*",
                    "full_import_name": "use super::*;",
                    "line_number": 104,
                    "alias": None,
                },
            ],
            "function_calls": [],
        }

        gb.add_file_to_graph(file_data, "my_repo", {}, repo_path_str="/repo")

        import_call = next(
            c
            for c in session.calls
            if "MERGE (f)-[r:IMPORTS {line_number: row.line_number}]->(m)" in c["query"]
        )
        batch = import_call["kwargs"]["batch"]
        assert [row["full_import_name"] for row in batch] == [
            "use super::*;",
            "pub use super::geometry::shapes::*;",
            "pub use super::geometry::shapes::Rectangle;",
            "use super::shapes::{Circle, Rectangle};",
        ]


# ---------------------------------------------------------------------------
# 4. delete_repository_from_graph (Changes 9a/9b/9c)
# ---------------------------------------------------------------------------

class _DeleteRepoSession(_RecordingSession):
    """RecordingSession that intercepts label-discovery queries and
    returns a fixed label list without consuming a slot in the responses
    queue, so positional fixtures stay focused on deletion counts and
    aren't disturbed by the label-discovery query in the implementation.

    Supports both Neo4j (``CALL db.labels()``) and KuzuDB/LadybugDB
    (``MATCH (n) RETURN DISTINCT label(n)``) discovery patterns."""

    def __init__(self, labels, responses=None):
        super().__init__(responses=responses)
        self._labels = list(labels)

    def run(self, query: str, **kwargs):
        self.calls.append({"query": query, "kwargs": kwargs})
        if "db.labels()" in query:
            return _FakeResult([{"label": lbl} for lbl in self._labels])
        if "RETURN DISTINCT label(n)" in query:
            return _FakeResult([[lbl] for lbl in self._labels])
        if self._call_idx < len(self._responses):
            result = self._responses[self._call_idx]
        else:
            result = _FakeResult()
        self._call_idx += 1
        return result


class TestDeleteRepositoryFromGraph:
    """Tests for delete_repository_from_graph (batched, rels-first, orphan purge)."""

    # Default set of labels returned by the mocked `CALL db.labels()` --
    # covers the labels the existing assertions still expect to see in
    # node-deletion queries (Function, Class, File) while including one
    # previously-leaking label (Variable) so the test reflects the bug
    # this PR is closing.
    _DEFAULT_DB_LABELS = ["Class", "File", "Function", "Variable"]

    def _make_repo_exists_session(self, extra_responses=None, db_labels=None):
        """Session that reports the repo exists (cnt=1), then zero-counts to stop loops."""
        labels = db_labels if db_labels is not None else self._DEFAULT_DB_LABELS
        responses = [
            _FakeResult([{"cnt": 1}]),  # repo existence check
        ]
        # For each loop iteration: non-zero first, then zero to stop
        if extra_responses:
            responses.extend(extra_responses)
        else:
            # Enough zeros to drain all the while-True loops
            responses.extend([_FakeResult([{"deleted": 0}])] * 20)
        return _DeleteRepoSession(labels=labels, responses=responses)

    def test_returns_false_when_repo_not_found(self):
        # Provide two failure responses: one for normalized path, one for fallback
        session = _RecordingSession(responses=[
            _FakeResult([{"cnt": 0}]),  # normalized path (forward-slash)
            _FakeResult([{"cnt": 0}]),  # fallback path (original)
        ])
        gb, _ = _make_graph_builder(session)
        result = gb.delete_repository_from_graph("/nonexistent/repo")
        assert result is False

    def test_returns_true_when_repo_found(self):
        session = self._make_repo_exists_session()
        gb, _ = _make_graph_builder(session)
        result = gb.delete_repository_from_graph("/my/repo")
        assert result is True

    def test_purges_dangling_pathless_modules(self):
        """Pathless Module nodes (C #includes) must be removed after repo delete."""
        session = self._make_repo_exists_session()
        gb, writer = _make_graph_builder(session)
        gb.delete_repository_from_graph("/my/repo")

        queries = [c["query"] for c in session.calls]
        assert any(
            "Module" in q and "IMPORTS|INCLUDES" in q and "DETACH DELETE" in q
            for q in queries
        ), "Expected dangling Module purge after repository deletion"

    def test_deletes_relationships_before_nodes(self):
        """CALLS/INHERITS/IMPORTS/INCLUDES deletion must appear before Function/Class/File node deletion."""
        session = self._make_repo_exists_session()
        gb, _ = _make_graph_builder(session)
        gb.delete_repository_from_graph("/my/repo")

        queries = [c["query"] for c in session.calls]
        rel_idx = next(
            (i for i, q in enumerate(queries)
             if any(rt in q for rt in ("CALLS", "INHERITS", "IMPORTS", "INCLUDES"))),
            None,
        )
        node_idx = next((i for i, q in enumerate(queries) if any(f"MATCH (n:{lbl})" in q for lbl in ("Function", "Class", "File"))), None)

        assert rel_idx is not None, "No relationship deletion query found"
        assert node_idx is not None, "No node deletion query found"
        assert rel_idx < node_idx, "Relationships should be deleted before nodes"

    def test_uses_starts_with_prefix_for_scope(self):
        """Queries should scope deletion to the repository path prefix."""
        session = self._make_repo_exists_session()
        gb, _ = _make_graph_builder(session)
        gb.delete_repository_from_graph("/my/repo")

        queries = [c["query"] for c in session.calls]
        assert any("STARTS WITH" in q for q in queries), "Expected STARTS WITH path scoping"

    def test_batched_delete_uses_limit(self):
        """Deletion should use LIMIT to batch and avoid cartesian explosion."""
        session = self._make_repo_exists_session()
        gb, _ = _make_graph_builder(session)
        gb.delete_repository_from_graph("/my/repo")

        queries = [c["query"] for c in session.calls]
        assert any("LIMIT" in q for q in queries), "Expected LIMIT in batch delete queries"

    def test_deletes_repository_node_itself(self):
        session = self._make_repo_exists_session()
        gb, _ = _make_graph_builder(session)
        gb.delete_repository_from_graph("/my/repo")

        queries = [c["query"] for c in session.calls]
        assert any("Repository" in q and ("DELETE" in q or "DETACH DELETE" in q) for q in queries)

    def test_purges_labels_discovered_dynamically(self):
        """Should DETACH DELETE every label that `CALL db.labels()` reports,
        not a hardcoded subset -- otherwise nodes from any newly-added
        indexer label leak as orphans on `delete_repository`.

        Regression test for: pre-fix, the function iterated a fixed tuple
        of (Function, Class, Interface, ..., DbTable). When the indexer
        learned a new label, every `delete_repository` call against that
        repo would leave the new label's nodes behind. The fix uses
        `CALL db.labels()` so the per-label cleanup loop is self-
        maintaining.
        """
        # Mock db.labels() returning a label that doesn't exist in any
        # hardcoded list anywhere in this codebase -- proves the loop
        # responds to whatever the running Neo4j actually contains.
        session = self._make_repo_exists_session(
            db_labels=["Function", "Class", "File", "SomeFutureLabelTheIndexerMightAdd"]
        )
        gb, _ = _make_graph_builder(session)
        gb.delete_repository_from_graph("/my/repo")

        queries = [c["query"] for c in session.calls]
        assert any(
            "SomeFutureLabelTheIndexerMightAdd" in q and "DETACH DELETE" in q
            for q in queries
        ), (
            "Expected a DETACH DELETE query targeting every label returned by "
            "`CALL db.labels()`, including labels not in any hardcoded list."
        )

    def test_calls_db_labels_after_existence_check(self):
        """Label discovery should happen exactly once, after the repo
        existence check passes, before any per-label deletion loops."""
        session = self._make_repo_exists_session()
        gb, _ = _make_graph_builder(session)
        gb.delete_repository_from_graph("/my/repo")

        queries = [c["query"] for c in session.calls]
        labels_call_idx = next(
            (i for i, q in enumerate(queries) if "db.labels()" in q), None
        )
        existence_idx = next(
            (i for i, q in enumerate(queries) if "MATCH (r:Repository {path: $path})" in q and "count(r)" in q),
            None,
        )
        node_delete_idx = next(
            (i for i, q in enumerate(queries) if "DETACH DELETE n" in q), None
        )
        assert labels_call_idx is not None, "Expected exactly one `CALL db.labels()` query"
        assert existence_idx is not None, "Expected the repo existence check"
        assert node_delete_idx is not None, "Expected at least one DETACH DELETE for nodes"
        assert existence_idx < labels_call_idx < node_delete_idx, (
            "db.labels() must come after existence check and before per-label deletion"
        )

    def test_finds_repo_with_unix_path(self):
        """A Unix path supplied to delete_repository_from_graph should resolve
        correctly and find the repository in the existence check."""
        session = _DeleteRepoSession(
            labels=self._DEFAULT_DB_LABELS,
            responses=[
                _FakeResult([{"cnt": 1}]),
                *([_FakeResult([{"deleted": 0}])] * 20),
            ],
        )
        gb, _ = _make_graph_builder(session)
        result = gb.delete_repository_from_graph("/home/user/my-repo")
        assert result is True

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific backslash path regression test")
    def test_finds_repo_stored_with_backslash_path(self):
        """Fallback should find a Repository stored with Windows backslash paths."""
        session = _RecordingSession(responses=[
            _FakeResult([{"cnt": 0}]),   # normalized (forward-slash) fails
            _FakeResult([{"cnt": 1}]),   # fallback (original backslash) succeeds
            *([_FakeResult([{"deleted": 0}])] * 20),  # drain loops
        ])
        gb, _ = _make_graph_builder(session)
        result = gb.delete_repository_from_graph("C:\\Users\\test\\repo")
        assert result is True

    def test_deletion_queries_use_forward_slash_paths(self):
        """All deletion queries must use forward-slash normalised paths so that
        STARTS WITH scoping works correctly across platforms (issue #1080)."""
        session = _DeleteRepoSession(
            labels=self._DEFAULT_DB_LABELS,
            responses=[
                _FakeResult([{"cnt": 1}]),
                *([_FakeResult([{"deleted": 0}])] * 20),
            ],
        )
        gb, _ = _make_graph_builder(session)
        gb.delete_repository_from_graph("/home/user/my-repo")

        for c in session.calls:
            if "STARTS WITH" in c["query"] or "DETACH DELETE" in c["query"]:
                for key in ("prefix", "path"):
                    val = c["kwargs"].get(key, "")
                    if val:
                        assert "\\" not in val, \
                            f"Backslash in ${key} kwarg — path must be normalised: {val!r}"
                        assert "/" in val, \
                            f"Expected forward-slash path in ${key}, got: {val!r}"


# ---------------------------------------------------------------------------
# 5. delete_relationship_links / delete_outgoing_calls / delete_inherits
# ---------------------------------------------------------------------------

class TestDeleteRelationshipHelpers:
    """Tests for the relationship-deletion helpers (Changes 5/6)."""

    def test_delete_relationship_links_runs_query(self):
        session = _RecordingSession(responses=[_FakeResult([{"cnt": 0}])])
        gb, _ = _make_graph_builder(session)
        gb.delete_relationship_links(Path("/repo"))
        assert len(session.calls) >= 1

    def test_delete_outgoing_calls_from_files(self):
        session = _RecordingSession(responses=[_FakeResult([{"cnt": 5}])])
        gb, _ = _make_graph_builder(session)
        gb.delete_outgoing_calls_from_files(["/repo/a.py", "/repo/b.py"])
        assert len(session.calls) == 1
        q = session.calls[0]["query"]
        assert "CALLS" in q
        assert "DELETE" in q

    def test_delete_outgoing_calls_passes_paths(self):
        session = _RecordingSession(responses=[_FakeResult([{"cnt": 0}])])
        gb, _ = _make_graph_builder(session)
        paths = ["/repo/a.py", "/repo/b.py"]
        gb.delete_outgoing_calls_from_files(paths)
        kwargs = session.calls[0]["kwargs"]
        assert "paths" in kwargs
        assert set(kwargs["paths"]) == set(paths)

    def test_delete_inherits_for_files(self):
        session = _RecordingSession(responses=[_FakeResult([{"cnt": 3}])])
        gb, _ = _make_graph_builder(session)
        gb.delete_inherits_for_files(["/repo/a.py"])
        assert len(session.calls) == 1
        q = session.calls[0]["query"]
        assert "INHERITS" in q
        assert "DELETE" in q


# ---------------------------------------------------------------------------
# 6. GraphBuilder method existence checks (structural tests)
# ---------------------------------------------------------------------------

class TestGraphBuilderMethodsExist:
    """Smoke tests confirming all new/changed methods are present."""

    def test_resolve_function_call_exists(self):
        from codegraphcontext.tools.graph_builder import GraphBuilder
        assert callable(getattr(GraphBuilder, "_resolve_function_call", None))

    def test_create_all_function_calls_exists(self):
        from codegraphcontext.tools.graph_builder import GraphBuilder
        assert callable(getattr(GraphBuilder, "_create_all_function_calls", None))

    def test_delete_outgoing_calls_from_files_exists(self):
        from codegraphcontext.tools.graph_builder import GraphBuilder
        assert callable(getattr(GraphBuilder, "delete_outgoing_calls_from_files", None))

    def test_delete_inherits_for_files_exists(self):
        from codegraphcontext.tools.graph_builder import GraphBuilder
        assert callable(getattr(GraphBuilder, "delete_inherits_for_files", None))

    def test_get_caller_file_paths_exists(self):
        from codegraphcontext.tools.graph_builder import GraphBuilder
        assert callable(getattr(GraphBuilder, "get_caller_file_paths", None))

    def test_get_inheritance_neighbor_paths_exists(self):
        from codegraphcontext.tools.graph_builder import GraphBuilder
        assert callable(getattr(GraphBuilder, "get_inheritance_neighbor_paths", None))

    def test_get_repo_class_lookup_exists(self):
        from codegraphcontext.tools.graph_builder import GraphBuilder
        assert callable(getattr(GraphBuilder, "get_repo_class_lookup", None))


# ---------------------------------------------------------------------------
# 7. cli_helpers — variable-length CONTAINS (Change 3)
# ---------------------------------------------------------------------------

class TestCliHelpersContainsFix:
    """Change 3: [:CONTAINS] -> [:CONTAINS*] in indexed path query."""

    def test_index_helper_uses_variable_length_contains(self):
        import inspect
        from codegraphcontext.cli import cli_helpers
        source = inspect.getsource(cli_helpers)
        # Should use variable-length CONTAINS* (not fixed [:CONTAINS])
        assert "[:CONTAINS*]" in source or "CONTAINS*" in source, \
            "cli_helpers should use variable-length [:CONTAINS*] for directory hierarchy"

    def test_index_helper_does_not_use_fixed_contains_only(self):
        """Make sure the old single-hop [:CONTAINS] without * is not used for the indexed check."""
        import inspect
        from codegraphcontext.cli import cli_helpers
        source = inspect.getsource(cli_helpers)
        # The source should contain CONTAINS* somewhere (our fix)
        assert "CONTAINS*" in source


# ---------------------------------------------------------------------------
# 8. Watcher — all_file_data.clear() after initial scan (Change 4)
# ---------------------------------------------------------------------------

class TestWatcherMemoryClear:
    """Change 4: all_file_data.clear() after the linking pass in _initial_scan."""

    def test_initial_scan_clears_all_file_data(self):
        import inspect
        from codegraphcontext.core.watcher import RepositoryEventHandler
        source = inspect.getsource(RepositoryEventHandler._initial_scan)
        assert "all_file_data.clear()" in source, \
            "RepositoryEventHandler._initial_scan must call all_file_data.clear() after linking"

    def test_all_file_data_is_empty_after_initial_scan(self):
        """Simulate _initial_scan: after the call, self.all_file_data must be empty."""
        from codegraphcontext.core.watcher import RepositoryEventHandler

        watcher = RepositoryEventHandler.__new__(RepositoryEventHandler)
        watcher.all_file_data = []
        watcher.repo_path = Path("/fake")
        watcher.imports_map = {}

        mock_gb = MagicMock()
        mock_gb.parsers = {}
        mock_gb.pre_scan_imports.return_value = {}
        mock_gb.link_function_calls.return_value = None
        mock_gb.link_inheritance.return_value = None
        watcher.graph_builder = mock_gb

        # Patch rglob to return empty list (no files to scan)
        with patch.object(Path, "rglob", return_value=[]):
            watcher._initial_scan()

        assert watcher.all_file_data == [], \
            "all_file_data should be empty after _initial_scan completes"


# ---------------------------------------------------------------------------
# 9. Watcher — incremental _handle_modification calls helpers (Changes 5/6)
# ---------------------------------------------------------------------------

class TestWatcherIncrementalHandleModification:
    """Change 5/6: _handle_modification uses incremental O(k) relinking."""

    def test_handle_modification_calls_delete_outgoing(self):
        """When callers exist, delete_outgoing_calls_from_files must be called."""
        from codegraphcontext.core.watcher import RepositoryEventHandler

        watcher = RepositoryEventHandler.__new__(RepositoryEventHandler)
        watcher.all_file_data = []
        watcher.imports_map = {}
        watcher.repo_path = Path("/fake")

        mock_gb = MagicMock()
        mock_gb.parsers = {".py": None}
        mock_gb.get_caller_file_paths.return_value = {"/fake/caller.py"}
        mock_gb.get_inheritance_neighbor_paths.return_value = set()
        mock_gb.get_repo_class_lookup.return_value = {}
        mock_gb.link_function_calls.return_value = None
        mock_gb.link_inheritance.return_value = None
        mock_gb.update_file_in_graph.return_value = None
        watcher.graph_builder = mock_gb

        with patch.object(watcher, "_update_imports_map_for_file"):
            watcher._handle_modification("/fake/module.py")

        mock_gb.delete_outgoing_calls_from_files.assert_called_once()

    def test_handle_modification_skips_delete_when_no_callers(self):
        """When no callers exist, delete_outgoing_calls_from_files must NOT be called."""
        from codegraphcontext.core.watcher import RepositoryEventHandler

        watcher = RepositoryEventHandler.__new__(RepositoryEventHandler)
        watcher.all_file_data = []
        watcher.imports_map = {}
        watcher.repo_path = Path("/fake")

        mock_gb = MagicMock()
        mock_gb.parsers = {".py": None}
        mock_gb.get_caller_file_paths.return_value = set()
        mock_gb.get_inheritance_neighbor_paths.return_value = set()
        mock_gb.get_repo_class_lookup.return_value = {}
        mock_gb.link_function_calls.return_value = None
        mock_gb.link_inheritance.return_value = None
        mock_gb.update_file_in_graph.return_value = None
        watcher.graph_builder = mock_gb

        with patch.object(watcher, "_update_imports_map_for_file"):
            watcher._handle_modification("/fake/module.py")

        mock_gb.delete_outgoing_calls_from_files.assert_not_called()

    def test_handle_modification_calls_create_all_function_calls(self):
        """After relinking, link_function_calls must be called for the subset."""
        from codegraphcontext.core.watcher import RepositoryEventHandler

        watcher = RepositoryEventHandler.__new__(RepositoryEventHandler)
        watcher.all_file_data = []
        watcher.imports_map = {}
        watcher.repo_path = Path("/fake")

        mock_gb = MagicMock()
        mock_gb.parsers = {".py": None}
        mock_gb.get_caller_file_paths.return_value = set()
        mock_gb.get_inheritance_neighbor_paths.return_value = set()
        mock_gb.get_repo_class_lookup.return_value = {}
        mock_gb.link_function_calls.return_value = None
        mock_gb.link_inheritance.return_value = None
        mock_gb.update_file_in_graph.return_value = None
        watcher.graph_builder = mock_gb

        with patch.object(watcher, "_update_imports_map_for_file"):
            watcher._handle_modification("/fake/module.py")

        mock_gb.link_function_calls.assert_called_once()


class TestWriteOrmMappingsDatasourceName:
    """Regression test for bug: DbTable.datasource_name is null when write_query_links
    creates the DbTable node before write_orm_mappings runs (ON CREATE SET is a no-op
    on an existing node). Fix: add ON MATCH SET with COALESCE guard.
    """

    def _make_writer(self):
        from codegraphcontext.tools.indexing.persistence.writer import GraphWriter
        mock_driver = MagicMock()
        mock_session = MagicMock(spec=["run", "__enter__", "__exit__"])
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_driver.session.return_value = mock_session
        writer = GraphWriter.__new__(GraphWriter)
        writer.driver = mock_driver
        writer._db_manager = None
        return writer, mock_session

    def test_on_match_set_present_in_write_orm_mappings(self):
        """write_orm_mappings Cypher must include ON MATCH SET so datasource_name
        is back-filled on DbTable nodes created by write_query_links."""
        import inspect
        from codegraphcontext.tools.indexing.persistence.writer import GraphWriter
        src = inspect.getsource(GraphWriter.write_orm_mappings)
        assert "ON MATCH SET" in src, (
            "write_orm_mappings is missing ON MATCH SET — DbTable.datasource_name will be "
            "null when the node was created by write_query_links before write_orm_mappings runs"
        )
        assert "COALESCE" in src, (
            "ON MATCH SET must use COALESCE to avoid overwriting a datasource_name already set"
        )

    def test_orm_batch_sets_datasource_name_on_existing_node(self):
        """write_orm_mappings must emit an ON MATCH SET clause that populates
        datasource_name even when the DbTable node pre-exists."""
        writer, mock_session = self._make_writer()
        orm_batch = [{
            "kind": "class_table",
            "class_name": "WhiteListDB",
            "class_path": "/repo/WhiteListDB.java",
            "orm_table": "whitelist",
            "datastore": "cassandra",
            "line_number": 9,
        }]
        writer.write_orm_mappings(orm_batch)
        assert mock_session.run.called
        query = mock_session.run.call_args[0][0]
        assert "ON MATCH SET" in query
        assert "COALESCE" in query
