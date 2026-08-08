# tests/unit/tools/test_writer_path_normalization.py
"""
Unit tests for cross-platform path normalization in GraphWriter.

Regression tests for https://github.com/CodeGraphContext/CodeGraphContext/issues/1080

Root cause: str(Path(...).resolve()) produces backslashes on Windows, causing
STARTS WITH queries in the graph DB to silently fail. All path writes and
prefix constructions must use forward slashes via Path.as_posix().
"""

from __future__ import annotations

import sys
from pathlib import Path, PureWindowsPath
from unittest.mock import MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Import the two helpers directly — they are module-level and pure functions,
# so we can test them without instantiating GraphWriter or touching a DB.
# ---------------------------------------------------------------------------
from codegraphcontext.tools.indexing.persistence.writer import (
    GraphWriter,
    _normalize_path,
    _normalize_prefix,
)


# ===========================================================================
# 1. Pure helper tests — no mocks needed
# ===========================================================================

class TestNormalizePath:
    """_normalize_path always returns a forward-slash absolute path string."""

    def test_forward_slash_path_unchanged(self, tmp_path):
        result = _normalize_path(tmp_path)
        assert "\\" not in result, "Forward-slash path should not contain backslashes"
        assert result == str(tmp_path).replace("\\", "/")

    def test_windows_style_backslash_path(self):
        """Simulate what str(Path(...).resolve()) returns on Windows."""
        windows_path = "D:\\WorkPlace\\AI\\MinerU\\pipeline\\complete_metadata.py"
        with patch("codegraphcontext.tools.indexing.persistence.writer.Path") as MockPath:
            mock_instance = MagicMock()
            mock_instance.resolve.return_value = mock_instance
            mock_instance.as_posix.return_value = "D:/WorkPlace/AI/MinerU/pipeline/complete_metadata.py"
            MockPath.return_value = mock_instance
            result = _normalize_path(windows_path)
        assert "\\" not in result
        assert result == "D:/WorkPlace/AI/MinerU/pipeline/complete_metadata.py"

    def test_returns_string(self, tmp_path):
        result = _normalize_path(tmp_path)
        assert isinstance(result, str)

    def test_path_object_input(self, tmp_path):
        """Accepts a Path object, not just a string."""
        result = _normalize_path(tmp_path)
        assert isinstance(result, str)
        assert "\\" not in result

    def test_string_input(self, tmp_path):
        """Accepts a plain string path."""
        result = _normalize_path(str(tmp_path))
        assert isinstance(result, str)
        assert "\\" not in result

    def test_resolves_relative_path(self):
        """Relative paths become absolute."""
        result = _normalize_path(".")
        assert Path(result).is_absolute()

    def test_no_trailing_slash(self, tmp_path):
        """_normalize_path does NOT add a trailing slash."""
        result = _normalize_path(tmp_path)
        assert not result.endswith("/")


class TestNormalizePrefix:
    """_normalize_prefix always ends with a single '/' and uses forward slashes."""

    def test_ends_with_forward_slash(self, tmp_path):
        result = _normalize_prefix(tmp_path)
        assert result.endswith("/")

    def test_no_backslashes(self, tmp_path):
        result = _normalize_prefix(tmp_path)
        assert "\\" not in result

    def test_is_normalize_path_plus_slash(self, tmp_path):
        assert _normalize_prefix(tmp_path) == _normalize_path(tmp_path) + "/"

    def test_starts_with_query_correctness(self, tmp_path):
        """
        Simulate the exact STARTS WITH scenario from issue #1080.

        A file stored with a normalized forward-slash path should match
        when we do `path STARTS WITH prefix` in the graph DB.
        """
        stored_file_path = _normalize_path(tmp_path / "pipeline" / "complete_metadata.py")
        repo_prefix = _normalize_prefix(tmp_path)

        # This is what the Cypher STARTS WITH does in Python string terms
        assert stored_file_path.startswith(repo_prefix), (
            f"STARTS WITH would fail!\n"
            f"  stored: {stored_file_path}\n"
            f"  prefix: {repo_prefix}"
        )

    def test_windows_backslash_does_not_match_without_fix(self):
        """
        Demonstrate the original bug: backslash path vs forward-slash prefix.
        This test documents WHY the fix is needed.
        """
        # What the old code produced on Windows (str(Path.resolve()))
        windows_stored = "D:\\WorkPlace\\AI\\MinerU\\pipeline\\complete_metadata.py"
        # What the old delete_repository_from_graph built as prefix
        old_prefix = "D:\\WorkPlace\\AI\\MinerU/" 

        # This is the bug — STARTS WITH would fail
        assert not windows_stored.startswith(old_prefix), (
            "This test documents the original bug. If this fails, "
            "the test itself is wrong."
        )

    def test_fix_resolves_the_bug(self):
        """
        With _normalize_path applied to both stored path and prefix,
        STARTS WITH now works correctly.
        """
        with patch("codegraphcontext.tools.indexing.persistence.writer.Path") as MockPath:
            # Simulate Windows resolve() returning backslashes
            def make_mock(p):
                m = MagicMock()
                m.resolve.return_value = m
                # as_posix normalizes to forward slashes
                path_str = str(p).replace("\\", "/")
                m.as_posix.return_value = path_str
                return m

            MockPath.side_effect = make_mock

            stored = _normalize_path("D:\\WorkPlace\\AI\\MinerU\\pipeline\\complete_metadata.py")
            prefix = _normalize_prefix("D:\\WorkPlace\\AI\\MinerU")

        assert stored.startswith(prefix), (
            f"Fix failed — STARTS WITH still broken:\n"
            f"  stored: {stored}\n"
            f"  prefix: {prefix}"
        )


# ===========================================================================
# 2. GraphWriter method tests — mock the DB session
# ===========================================================================

def _make_writer() -> tuple[GraphWriter, MagicMock]:
    """Return a GraphWriter with a fully mocked driver and db_manager."""
    # Limit spec so execute_write_operation invokes work_fn(session) directly.
    mock_session = MagicMock(spec=["run", "__enter__", "__exit__"])
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_session.run.return_value = MagicMock(single=MagicMock(return_value=None))

    mock_driver = MagicMock()
    mock_driver.session.return_value = mock_session

    mock_db_manager = MagicMock()
    mock_db_manager.get_backend_type.return_value = "neo4j"

    writer = GraphWriter(driver=mock_driver, db_manager=mock_db_manager)
    return writer, mock_session


def _make_writer_with_delete_mocks() -> tuple[GraphWriter, MagicMock]:
    """
    Return a GraphWriter with a mocked driver that returns proper values
    for delete_repository_from_graph:
      - 1st call (existence check) -> {"cnt": 1}
      - subsequent calls (DELETE queries) -> {"deleted": 0}
    """
    writer, session = _make_writer()
    call_counter = iter([{"cnt": 1}])

    def _side_effect(*_a, **_kw):
        try:
            r = next(call_counter)
        except StopIteration:
            r = {"deleted": 0}
        return MagicMock(single=MagicMock(return_value=r))

    session.run.side_effect = _side_effect
    return writer, session


class TestAddRepositoryToGraph:
    def test_stored_path_uses_forward_slashes(self, tmp_path):
        writer, session = _make_writer()
        writer.add_repository_to_graph(tmp_path)

        # Find the MERGE call and check the path parameter
        merge_call = session.run.call_args_list[0]
        stored_path = merge_call.kwargs.get("path") or merge_call.args[1] if len(merge_call.args) > 1 else None
        # Also try keyword args pattern
        all_kwargs = {}
        for c in session.run.call_args_list:
            all_kwargs.update(c.kwargs)

        path_value = all_kwargs.get("path", "")
        assert "\\" not in path_value, f"Path stored with backslashes: {path_value}"

    def test_stored_path_is_absolute(self, tmp_path):
        writer, session = _make_writer()
        writer.add_repository_to_graph(tmp_path)

        all_kwargs = {}
        for c in session.run.call_args_list:
            all_kwargs.update(c.kwargs)
        path_value = all_kwargs.get("path", "")
        assert path_value  # not empty
        assert path_value[0] in ("/", "~") or (len(path_value) > 2 and path_value[1] == ":"), \
            f"Path should be absolute: {path_value}"


class TestDeleteRepositoryFromGraph:
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific backslash path regression test")
    def test_normalized_path_used_for_lookup(self, tmp_path):
        """delete_repository_from_graph normalizes before querying."""
        writer, session, *_ = _make_writer_with_delete_mocks()

        # Make label discovery return empty to short-circuit node deletion loop
        writer._get_all_node_labels = MagicMock(return_value=[])

        windows_style = str(tmp_path).replace("/", "\\")
        writer.delete_repository_from_graph(windows_style)

        # The first session.run call is the existence check — path must have no backslashes
        first_call_kwargs = session.run.call_args_list[0].kwargs
        queried_path = first_call_kwargs.get("path", "")
        assert "\\" not in queried_path, (
            f"delete_repository_from_graph passed backslash path to DB: {queried_path}"
        )

    def test_prefix_uses_forward_slash(self, tmp_path):
        """The STARTS WITH prefix must end with '/' not '\\'."""
        writer, session, *_ = _make_writer_with_delete_mocks()
        writer._get_all_node_labels = MagicMock(return_value=[])

        writer.delete_repository_from_graph(str(tmp_path))

        # Find any call that passes a 'prefix' kwarg
        prefix_values = [
            c.kwargs["prefix"]
            for c in session.run.call_args_list
            if "prefix" in c.kwargs
        ]
        assert prefix_values, "No STARTS WITH prefix was passed to DB"
        for pv in prefix_values:
            assert pv.endswith("/"), f"Prefix does not end with '/': {pv}"
            assert "\\" not in pv, f"Prefix contains backslash: {pv}"

    def test_returns_false_for_nonexistent_repo(self, tmp_path):
        writer, session = _make_writer()
        session.run.return_value.single.return_value = {"cnt": 0}

        result = writer.delete_repository_from_graph(str(tmp_path))
        assert result is False


class TestDeleteFileFromGraph:
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific backslash path regression test")
    def test_normalized_path_used(self, tmp_path):
        writer, session = _make_writer()
        # Mock the parents query to return empty
        session.run.return_value.__iter__ = MagicMock(return_value=iter([]))

        test_file = tmp_path / "src" / "myfile.py"
        windows_path = str(test_file).replace("/", "\\")
        writer.delete_file_from_graph(windows_path)

        first_call_kwargs = session.run.call_args_list[0].kwargs
        queried_path = first_call_kwargs.get("path", "")
        assert "\\" not in queried_path


class TestGetRepoClassLookup:
    def test_prefix_uses_forward_slash(self, tmp_path):
        writer, session = _make_writer()
        session.run.return_value.__iter__ = MagicMock(return_value=iter([]))

        writer.get_repo_class_lookup(tmp_path)

        first_call_kwargs = session.run.call_args_list[0].kwargs
        prefix = first_call_kwargs.get("prefix", "")
        assert prefix.endswith("/"), f"Prefix should end with '/': {prefix}"
        assert "\\" not in prefix, f"Prefix contains backslash: {prefix}"


class TestDeleteRelationshipLinks:
    def test_prefix_uses_forward_slash(self, tmp_path):
        writer, session = _make_writer()
        session.run.return_value.single.return_value = {"cnt": 0}

        writer.delete_relationship_links(tmp_path)

        all_prefixes = [
            c.kwargs["prefix"]
            for c in session.run.call_args_list
            if "prefix" in c.kwargs
        ]
        assert all_prefixes, "No prefix passed to DB"
        for p in all_prefixes:
            assert "\\" not in p, f"Backslash in prefix: {p}"
            assert p.endswith("/"), f"Prefix missing trailing slash: {p}"


class TestAddMinimalFileNode:
    def test_stored_paths_use_forward_slashes(self, tmp_path):
        writer, session = _make_writer()

        file_path = tmp_path / "src" / "main.py"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.touch()

        writer.add_minimal_file_node(file_path, tmp_path)

        for c in session.run.call_args_list:
            for key in ("file_path", "repo_path", "current_path", "parent_path"):
                val = c.kwargs.get(key, "")
                if val:
                    assert "\\" not in val, (
                        f"Backslash found in '{key}' param: {val}"
                    )


# ===========================================================================
# 3. Integration-style: end-to-end path consistency check
# ===========================================================================

class TestPathConsistencyEndToEnd:
    """
    Verify that the path written by add_repository_to_graph is the same
    format used by delete_repository_from_graph for its existence check.
    Without _normalize_path, these would differ on Windows.
    """

    def test_write_and_delete_use_same_path_format(self, tmp_path):
        writer, session = _make_writer()

        # Intercept driver.session() via the context manager instead of side_effect
        captured_write_paths = []

        def capture_write(original_session_run, query, **kwargs):
            if "path" in kwargs:
                captured_write_paths.append(kwargs["path"])
            return original_session_run(query, **kwargs)

        # Patch the writer's own session, not session.run's side_effect
        original_session_run = session.run
        session.run = lambda query, **kwargs: capture_write(original_session_run, query, **kwargs)

        writer.add_repository_to_graph(tmp_path)
        assert captured_write_paths, "No path was written to DB"
        written_path = captured_write_paths[0]

        # Now simulate delete — set up properly scoped mocks
        writer2, session2 = _make_writer()
        delete_call_counter = iter([{"cnt": 1}])
        def _delete_side_effect(*_a, **_kw):
            try:
                r = next(delete_call_counter)
            except StopIteration:
                r = {"deleted": 0}
            return MagicMock(single=MagicMock(return_value=r))
        session2.run.side_effect = _delete_side_effect
        writer2._get_all_node_labels = MagicMock(return_value=[])

        captured_delete_paths = []
        original_session_run2 = session2.run
        session2.run = lambda query, **kwargs: (
            captured_delete_paths.append(kwargs["path"]) or
            original_session_run2(query, **kwargs)
            if "path" in kwargs else
            original_session_run2(query, **kwargs)
        )

        writer2.delete_repository_from_graph(str(tmp_path))

        assert captured_delete_paths, "No path was queried during delete"
        queried_path = captured_delete_paths[0]

        assert written_path == queried_path, (
            f"Path format mismatch between write and delete!\n"
            f"  written:  {written_path}\n"
            f"  queried:  {queried_path}\n"
            "This would cause STARTS WITH to silently fail on Windows."
        )