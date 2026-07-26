from pathlib import Path, PureWindowsPath
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from codegraphcontext.cli import cli_helpers
from codegraphcontext.core.watcher import CodeWatcher, RepositoryEventHandler
from codegraphcontext.tools.handlers import watcher_handlers
from codegraphcontext.tools.indexing.persistence.writer import GraphWriter


def test_startup_sync_reconciles_current_and_deleted_files(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    changed_file = repo / "changed.py"
    added_file = repo / "added.py"
    changed_file.write_text("def changed(): pass\n", encoding="utf-8")
    added_file.write_text("def added(): pass\n", encoding="utf-8")
    stale_path = str((repo / "deleted.py").resolve())

    graph_builder = MagicMock()
    graph_builder.parsers = {".py": "python"}
    graph_builder.get_repo_file_paths.return_value = {
        str(changed_file.resolve()),
        stale_path,
    }
    graph_builder.pre_scan_imports.return_value = {}
    graph_builder.update_file_in_graph.side_effect = lambda path, *_args: {
        "path": str(path.resolve()),
        "functions": [],
    }

    with patch.object(
        RepositoryEventHandler,
        "_iter_supported_files",
        return_value=[changed_file, added_file],
    ):
        handler = RepositoryEventHandler(
            graph_builder,
            repo,
            perform_initial_scan=False,
            sync_on_start=True,
        )

    graph_builder.delete_file_from_graph.assert_called_once_with(stale_path)
    graph_builder.update_file_in_graph.assert_has_calls(
        [
            call(changed_file, repo.resolve(), handler.imports_map),
            call(added_file, repo.resolve(), handler.imports_map),
        ]
    )
    assert graph_builder.update_file_in_graph.call_count == 2
    refreshed_paths = {
        str(changed_file.resolve()),
        str(added_file.resolve()),
    }
    assert set(graph_builder.delete_outgoing_calls_from_files.call_args.args[0]) == refreshed_paths
    assert set(graph_builder.delete_inherits_for_files.call_args.args[0]) == refreshed_paths
    graph_builder.link_function_calls.assert_called_once()
    graph_builder.link_inheritance.assert_called_once()


def test_startup_sync_does_not_delete_windows_paths_that_are_still_on_disk(tmp_path: Path):
    class WindowsFilePath:
        def __init__(self, path: str):
            self.path = PureWindowsPath(path)

        def resolve(self) -> PureWindowsPath:
            return self.path

    current_file = WindowsFilePath("C:/repo/src/app.py")
    graph_builder = MagicMock()
    graph_builder.get_repo_file_paths.return_value = {"C:/repo/src/app.py"}
    graph_builder.pre_scan_imports.return_value = {}
    graph_builder.update_file_in_graph.return_value = None

    handler = RepositoryEventHandler.__new__(RepositoryEventHandler)
    handler.repo_path = tmp_path
    handler.graph_builder = graph_builder
    handler.imports_map = {}

    with patch.object(RepositoryEventHandler, "_iter_supported_files", return_value=[current_file]):
        handler.synchronize_with_disk()

    graph_builder.delete_file_from_graph.assert_not_called()


def test_code_watcher_forwards_startup_sync_option(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    graph_builder = MagicMock()
    watcher = CodeWatcher.__new__(CodeWatcher)
    watcher.graph_builder = graph_builder
    watcher.observer = MagicMock()
    watcher.watched_paths = set()
    watcher.watches = {}
    watcher.handlers = {}

    with patch("codegraphcontext.core.watcher.RepositoryEventHandler") as handler_cls:
        watcher.watch_directory(
            str(repo),
            perform_initial_scan=False,
            sync_on_start=True,
        )

    handler_cls.assert_called_once_with(
        graph_builder,
        repo.resolve(),
        perform_initial_scan=False,
        sync_on_start=True,
        cgcignore_path=None,
    )


@pytest.mark.parametrize("sync_on_start", [False, True])
def test_cli_watch_helper_startup_sync_is_explicit_for_indexed_repo(tmp_path: Path, sync_on_start: bool):
    repo = tmp_path / "repo"
    repo.mkdir()
    db_manager = MagicMock()
    graph_builder = MagicMock()
    code_finder = MagicMock()
    code_finder.list_indexed_repositories.return_value = [{"path": str(repo)}]
    watcher = MagicMock()

    class StopAfterAttach:
        def wait(self):
            raise KeyboardInterrupt

    with (
        patch.object(
            cli_helpers,
            "_initialize_services",
            return_value=(db_manager, graph_builder, code_finder, SimpleNamespace(cgcignore_path=None)),
        ),
        patch("codegraphcontext.core.watcher.CodeWatcher", return_value=watcher),
        patch("threading.Event", return_value=StopAfterAttach()),
    ):
        if sync_on_start:
            cli_helpers.watch_helper(str(repo), sync_on_start=True)
        else:
            cli_helpers.watch_helper(str(repo))

    watcher.watch_directory.assert_called_once_with(
        str(repo.resolve()),
        perform_initial_scan=False,
        sync_on_start=sync_on_start,
        cgcignore_path=None,
    )


def test_repo_file_paths_are_scoped_to_repository_root(tmp_path: Path):
    repo = tmp_path / "repo"
    indexed_path = str((repo / "src" / "app.py").resolve())
    session = MagicMock()
    session.run.return_value = [{"p": indexed_path}, {"p": None}]
    driver = MagicMock()
    driver.session.return_value.__enter__.return_value = session

    paths = GraphWriter(driver).get_repo_file_paths(repo)

    assert paths == {indexed_path}
    query = session.run.call_args.args[0]
    assert "MATCH (f:File)" in query
    assert session.run.call_args.kwargs["prefix"] == str(repo.resolve()) + "/"


def test_mcp_watcher_syncs_already_indexed_repository(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    code_watcher = MagicMock()
    code_watcher.watched_paths = set()

    with (
        patch.object(watcher_handlers, "is_path_allowed", return_value=True),
        patch.object(watcher_handlers, "any_repo_matches_path", return_value=True),
    ):
        result = watcher_handlers.watch_directory(
            code_watcher,
            list_repositories_func=lambda: {"repositories": [{"path": str(repo)}]},
            add_code_func=MagicMock(),
            path=str(repo),
        )

    assert result["success"] is True
    code_watcher.watch_directory.assert_called_once_with(
        str(repo.resolve()),
        perform_initial_scan=False,
        sync_on_start=True,
    )
