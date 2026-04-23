"""Watcher threading: graph_name pinned at watch time propagates to every
subsequent graph_builder call the watcher issues.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from codegraphcontext.core.watcher import CodeWatcher, RepositoryEventHandler


def test_repository_event_handler_stores_graph_name():
    mock_gb = MagicMock()
    mock_gb.parsers = {}
    handler = RepositoryEventHandler(
        mock_gb, Path("/fake"), perform_initial_scan=False, graph_name="tenant_a"
    )
    assert handler.graph_name == "tenant_a"


def test_repository_event_handler_default_graph_name_is_none():
    mock_gb = MagicMock()
    mock_gb.parsers = {}
    handler = RepositoryEventHandler(mock_gb, Path("/fake"), perform_initial_scan=False)
    assert handler.graph_name is None


def test_initial_scan_forwards_graph_name_to_link_calls():
    """_initial_scan links via graph_builder and must pass its graph_name."""
    handler = RepositoryEventHandler.__new__(RepositoryEventHandler)
    handler.all_file_data = []
    handler.imports_map = {}
    handler.repo_path = Path("/fake")
    handler.graph_name = "tenant_b"

    mock_gb = MagicMock()
    mock_gb.parsers = {}
    mock_gb.pre_scan_imports.return_value = {}
    handler.graph_builder = mock_gb

    with patch.object(Path, "rglob", return_value=[]):
        handler._initial_scan()

    mock_gb.link_function_calls.assert_called_once()
    assert mock_gb.link_function_calls.call_args.kwargs.get("graph_name") == "tenant_b"
    mock_gb.link_inheritance.assert_called_once()
    assert mock_gb.link_inheritance.call_args.kwargs.get("graph_name") == "tenant_b"


def test_handle_modification_forwards_graph_name_to_every_builder_call():
    """Every graph_builder method invoked during _handle_modification must
    receive the handler's bound graph_name. This guards against future edits
    that add new graph_builder calls but forget to forward graph_name."""
    handler = RepositoryEventHandler.__new__(RepositoryEventHandler)
    handler.all_file_data = []
    handler.imports_map = {}
    handler.repo_path = Path("/fake")
    handler.graph_name = "tenant_c"

    mock_gb = MagicMock()
    mock_gb.parsers = {".py": None}
    # Return at least one affected caller and inheritor to exercise delete paths.
    mock_gb.get_caller_file_paths.return_value = {"/fake/caller.py"}
    mock_gb.get_inheritance_neighbor_paths.return_value = {"/fake/inh.py"}
    mock_gb.get_repo_class_lookup.return_value = {}
    handler.graph_builder = mock_gb

    with patch.object(handler, "_update_imports_map_for_file"):
        handler._handle_modification("/fake/module.py")

    # Collect every graph_builder method that was called and inspect its kwargs.
    relevant = [
        "get_caller_file_paths",
        "get_inheritance_neighbor_paths",
        "update_file_in_graph",
        "delete_outgoing_calls_from_files",
        "delete_inherits_for_files",
        "get_repo_class_lookup",
        "link_function_calls",
        "link_inheritance",
    ]
    for method_name in relevant:
        method_mock = getattr(mock_gb, method_name)
        assert method_mock.called, f"{method_name} should be invoked"
        for call in method_mock.call_args_list:
            assert call.kwargs.get("graph_name") == "tenant_c", (
                f"{method_name} was called without graph_name='tenant_c': {call}"
            )


def test_code_watcher_forwards_graph_name_to_handler():
    """CodeWatcher.watch_directory must construct the handler with the given graph."""
    mock_gb = MagicMock()
    mock_gb.parsers = {}

    watcher = CodeWatcher.__new__(CodeWatcher)
    watcher.graph_builder = mock_gb
    watcher.watched_paths = set()
    watcher.watches = {}
    watcher.observer = MagicMock()

    with patch(
        "codegraphcontext.core.watcher.RepositoryEventHandler"
    ) as mock_handler_cls:
        mock_handler_cls.return_value = MagicMock()
        watcher.watch_directory("/fake/path", perform_initial_scan=False, graph_name="tenant_d")

    # Verify the handler was constructed with graph_name="tenant_d".
    assert mock_handler_cls.called
    call = mock_handler_cls.call_args
    assert call.kwargs.get("graph_name") == "tenant_d"


def test_code_watcher_default_graph_name_is_none():
    mock_gb = MagicMock()
    mock_gb.parsers = {}

    watcher = CodeWatcher.__new__(CodeWatcher)
    watcher.graph_builder = mock_gb
    watcher.watched_paths = set()
    watcher.watches = {}
    watcher.observer = MagicMock()

    with patch(
        "codegraphcontext.core.watcher.RepositoryEventHandler"
    ) as mock_handler_cls:
        mock_handler_cls.return_value = MagicMock()
        watcher.watch_directory("/fake/path", perform_initial_scan=False)

    assert mock_handler_cls.call_args.kwargs.get("graph_name") is None
