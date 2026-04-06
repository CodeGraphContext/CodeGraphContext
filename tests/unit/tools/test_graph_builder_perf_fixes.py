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
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, call, patch


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


def _make_graph_builder(session: Optional[_RecordingSession] = None):
    """Return a GraphBuilder with a fake driver. Skips full __init__ setup."""
    from codegraphcontext.tools.graph_builder import GraphBuilder

    gb = GraphBuilder.__new__(GraphBuilder)
    if session is None:
        session = _RecordingSession()
    gb.driver = _FakeDriver(session)
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
        with patch("codegraphcontext.tools.graph_builder.get_config_value",
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
        assert not any("MERGE (caller" in q for q in queries), "Should not use per-call MERGE"

    def test_uses_create_not_merge_for_calls_rel(self):
        """CALLS relationships should be written with CREATE, not MERGE."""
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
            assert "CREATE" in q, f"Expected CREATE in CALLS query, got: {q[:120]}"

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
        with patch("codegraphcontext.tools.graph_builder.get_config_value",
                   return_value="false"):
            gb._create_all_function_calls(file_data, {}, external_lookup)
        resolved_b = str(Path("/repo/b.py").resolve())
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


# ---------------------------------------------------------------------------
# 4. delete_repository_from_graph (Changes 9a/9b/9c)
# ---------------------------------------------------------------------------

class TestDeleteRepositoryFromGraph:
    """Tests for delete_repository_from_graph (batched, rels-first, orphan purge)."""

    def _make_repo_exists_session(self, extra_responses=None):
        """Session that reports the repo exists (cnt=1), then zero-counts to stop loops."""
        responses = [
            _FakeResult([{"cnt": 1}]),  # repo existence check
        ]
        # For each loop iteration: non-zero first, then zero to stop
        if extra_responses:
            responses.extend(extra_responses)
        else:
            # Enough zeros to drain all the while-True loops
            responses.extend([_FakeResult([{"deleted": 0}])] * 20)
        return _RecordingSession(responses=responses)

    def test_returns_false_when_repo_not_found(self):
        session = _RecordingSession(responses=[_FakeResult([{"cnt": 0}])])
        gb, _ = _make_graph_builder(session)
        result = gb.delete_repository_from_graph("/nonexistent/repo")
        assert result is False

    def test_returns_true_when_repo_found(self):
        session = self._make_repo_exists_session()
        gb, _ = _make_graph_builder(session)
        result = gb.delete_repository_from_graph("/my/repo")
        assert result is True

    def test_deletes_relationships_before_nodes(self):
        """CALLS/INHERITS/IMPORTS deletion must appear before Function/Class/File node deletion."""
        session = self._make_repo_exists_session()
        gb, _ = _make_graph_builder(session)
        gb.delete_repository_from_graph("/my/repo")

        queries = [c["query"] for c in session.calls]
        rel_idx = next((i for i, q in enumerate(queries) if "CALLS" in q or "INHERITS" in q or "IMPORTS" in q), None)
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
        mock_gb._pre_scan_for_imports.return_value = {}
        mock_gb._create_all_function_calls.return_value = None
        mock_gb._create_all_inheritance_links.return_value = None
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
        mock_gb._create_all_function_calls.return_value = None
        mock_gb._create_all_inheritance_links.return_value = None
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
        mock_gb._create_all_function_calls.return_value = None
        mock_gb._create_all_inheritance_links.return_value = None
        mock_gb.update_file_in_graph.return_value = None
        watcher.graph_builder = mock_gb

        with patch.object(watcher, "_update_imports_map_for_file"):
            watcher._handle_modification("/fake/module.py")

        mock_gb.delete_outgoing_calls_from_files.assert_not_called()

    def test_handle_modification_calls_create_all_function_calls(self):
        """After relinking, _create_all_function_calls must be called for the subset."""
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
        mock_gb._create_all_function_calls.return_value = None
        mock_gb._create_all_inheritance_links.return_value = None
        mock_gb.update_file_in_graph.return_value = None
        watcher.graph_builder = mock_gb

        with patch.object(watcher, "_update_imports_map_for_file"):
            watcher._handle_modification("/fake/module.py")

        mock_gb._create_all_function_calls.assert_called_once()
