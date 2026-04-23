"""Handler-level plumbing for the graph_name MCP parameter.

Verifies that when an MCP tool call carries a graph_name, that value reaches
``db_manager.get_driver(graph_name=...)``. Also verifies omission falls back
to the env default.
"""

from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.code_finder import CodeFinder
from codegraphcontext.tools.handlers import (
    analysis_handlers,
    indexing_handlers,
    management_handlers,
    query_handlers,
    watcher_handlers,
)


def _make_code_finder():
    db_manager = MagicMock()
    db_manager.get_backend_type.return_value = "neo4j"
    driver = MagicMock()
    session = MagicMock()
    # The manager proxies .get_driver(...).session() — stub both levels.
    db_manager.get_driver.return_value = driver
    driver.session.return_value.__enter__.return_value = session
    driver.session.return_value.__exit__.return_value = None
    # session.run(...) returns a mock that supports .data() / .single()
    result = MagicMock()
    result.data.return_value = []
    result.single.return_value = None
    session.run.return_value = result
    return CodeFinder(db_manager), db_manager


def test_find_code_forwards_graph_name_to_get_driver():
    finder, db_manager = _make_code_finder()
    analysis_handlers.find_code(finder, query="foo", graph_name="tenant_a")
    # Every get_driver call on this path should carry graph_name="tenant_a".
    for call in db_manager.get_driver.call_args_list:
        assert call.kwargs.get("graph_name") == "tenant_a", (
            f"Expected graph_name='tenant_a' on every get_driver call, got {call}"
        )
    assert db_manager.get_driver.called


def test_find_code_without_graph_name_uses_none():
    finder, db_manager = _make_code_finder()
    analysis_handlers.find_code(finder, query="foo")
    for call in db_manager.get_driver.call_args_list:
        assert call.kwargs.get("graph_name") is None


def test_analyze_code_relationships_forwards_graph_name():
    finder, db_manager = _make_code_finder()
    analysis_handlers.analyze_code_relationships(
        finder,
        query_type="find_callers",
        target="my_func",
        graph_name="tenant_b",
    )
    for call in db_manager.get_driver.call_args_list:
        assert call.kwargs.get("graph_name") == "tenant_b"


def test_execute_cypher_query_forwards_graph_name():
    db_manager = MagicMock()
    driver = MagicMock()
    session = MagicMock()
    db_manager.get_driver.return_value = driver
    driver.session.return_value.__enter__.return_value = session
    driver.session.return_value.__exit__.return_value = None
    session.run.return_value = []

    query_handlers.execute_cypher_query(
        db_manager,
        cypher_query="MATCH (n) RETURN n LIMIT 1",
        graph_name="tenant_c",
    )
    db_manager.get_driver.assert_called_with(graph_name="tenant_c")


def test_execute_cypher_query_without_graph_name_passes_none():
    db_manager = MagicMock()
    driver = MagicMock()
    session = MagicMock()
    db_manager.get_driver.return_value = driver
    driver.session.return_value.__enter__.return_value = session
    driver.session.return_value.__exit__.return_value = None
    session.run.return_value = []

    query_handlers.execute_cypher_query(
        db_manager, cypher_query="MATCH (n) RETURN n LIMIT 1"
    )
    db_manager.get_driver.assert_called_with(graph_name=None)


# ---------------------------------------------------------------------------
# Remaining analysis_handlers (sweep)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "handler_call",
    [
        lambda f, **k: analysis_handlers.find_dead_code(f, **k),
        lambda f, **k: analysis_handlers.calculate_cyclomatic_complexity(
            f, function_name="foo", **k
        ),
        lambda f, **k: analysis_handlers.find_most_complex_functions(f, **k),
    ],
    ids=["find_dead_code", "calculate_cyclomatic_complexity", "find_most_complex_functions"],
)
def test_remaining_analysis_handlers_forward_graph_name(handler_call):
    finder, db_manager = _make_code_finder()
    handler_call(finder, graph_name="tenant_x")
    # Some code paths (e.g. get_cyclomatic_complexity) may short-circuit before
    # hitting a session. Only validate calls that *did* occur; require there's
    # at least one with the right graph_name.
    observed = [c.kwargs.get("graph_name") for c in db_manager.get_driver.call_args_list]
    assert observed, "Handler should have opened at least one session"
    for gn in observed:
        assert gn == "tenant_x"


# ---------------------------------------------------------------------------
# management_handlers
# ---------------------------------------------------------------------------


def test_list_indexed_repositories_forwards_graph_name():
    finder, db_manager = _make_code_finder()
    management_handlers.list_indexed_repositories(finder, graph_name="tenant_y")
    for call in db_manager.get_driver.call_args_list:
        assert call.kwargs.get("graph_name") == "tenant_y"


def test_delete_repository_forwards_graph_name_to_builder():
    mock_builder = MagicMock()
    mock_builder.delete_repository_from_graph.return_value = True
    management_handlers.delete_repository(
        mock_builder, repo_path="/some/repo", graph_name="tenant_z"
    )
    mock_builder.delete_repository_from_graph.assert_called_once_with(
        "/some/repo", graph_name="tenant_z"
    )


def test_get_repository_stats_forwards_graph_name():
    finder, db_manager = _make_code_finder()
    # Prime the session's .single() so the repo-exists check short-circuits gracefully.
    session_ctx = db_manager.get_driver.return_value.session.return_value.__enter__.return_value
    session_ctx.run.return_value.single.return_value = None
    management_handlers.get_repository_stats(
        finder, repo_path="/some/repo", graph_name="tenant_q"
    )
    db_manager.get_driver.assert_called_with(graph_name="tenant_q")


def test_load_bundle_constructs_cgc_bundle_with_graph_name():
    finder, db_manager = _make_code_finder()
    with pytest.MonkeyPatch.context() as mp:
        # Stub CGCBundle so we can assert it was constructed with graph_name.
        captured = {}

        class _StubBundle:
            def __init__(self, db_manager, graph_name=None):
                captured["db_manager"] = db_manager
                captured["graph_name"] = graph_name

            def import_from_bundle(self, bundle_path, clear_existing):
                return False, "stub"

        mp.setattr("codegraphcontext.core.cgc_bundle.CGCBundle", _StubBundle)
        # Also short-circuit the file-existence path by giving a fake local file.
        import pathlib

        fake_bundle = pathlib.Path("/tmp/__never_exists__.cgc")
        mp.setattr(pathlib.Path, "exists", lambda self: self == fake_bundle)
        management_handlers.load_bundle(
            finder, bundle_name=str(fake_bundle), graph_name="tenant_w"
        )

    assert captured.get("graph_name") == "tenant_w"


# ---------------------------------------------------------------------------
# indexing_handlers
# ---------------------------------------------------------------------------


def test_add_code_to_graph_threads_graph_name(tmp_path, monkeypatch):
    """graph_name must flow to list_repos_func, job creation, and build_graph_from_path_async."""
    # We need a real path so the handler doesn't short-circuit on 'path_not_found'.
    real_path = tmp_path
    list_calls = []

    def fake_list_repos(graph_name=None):
        list_calls.append(graph_name)
        return {"repositories": []}

    mock_builder = MagicMock()
    mock_builder.estimate_processing_time.return_value = (0, 0.0)

    # Capture arguments the coroutine was built with (don't await it).
    coro_capture = {}

    def fake_build_graph(*args, **kwargs):
        coro_capture["args"] = args
        coro_capture["kwargs"] = kwargs
        # Return a synchronous sentinel — the real scheduler isn't running, so
        # no coroutine needs to be awaited.
        return object()

    mock_builder.build_graph_from_path_async.side_effect = fake_build_graph

    mock_job_manager = MagicMock()
    mock_job_manager.create_job.return_value = "jid-1"

    # Replace run_coroutine_threadsafe to avoid needing a running loop.
    monkeypatch.setattr(
        "codegraphcontext.tools.handlers.indexing_handlers.asyncio.run_coroutine_threadsafe",
        lambda coro, loop: None,
    )

    result = indexing_handlers.add_code_to_graph(
        mock_builder, mock_job_manager, None, fake_list_repos,
        path=str(real_path), graph_name="tenant_idx",
    )

    assert result["success"] is True
    assert list_calls == ["tenant_idx"]
    mock_job_manager.create_job.assert_called_once()
    assert mock_job_manager.create_job.call_args.kwargs.get("graph_name") == "tenant_idx"
    mock_builder.build_graph_from_path_async.assert_called_once()
    assert (
        coro_capture["kwargs"].get("graph_name") == "tenant_idx"
    ), f"Got {coro_capture}"


def test_add_package_to_graph_threads_graph_name(monkeypatch):
    list_calls = []

    def fake_list_repos(graph_name=None):
        list_calls.append(graph_name)
        return {"repositories": []}

    mock_builder = MagicMock()
    mock_builder.estimate_processing_time.return_value = (0, 0.0)

    coro_capture = {}

    def fake_build_graph(*args, **kwargs):
        coro_capture["kwargs"] = kwargs
        return object()

    mock_builder.build_graph_from_path_async.side_effect = fake_build_graph

    mock_job_manager = MagicMock()
    mock_job_manager.create_job.return_value = "jid-2"

    # Pretend the package resolves to an existing path.
    import os
    monkeypatch.setattr(
        "codegraphcontext.tools.handlers.indexing_handlers.get_local_package_path",
        lambda name, lang: "/tmp",
    )
    monkeypatch.setattr(os.path, "exists", lambda p: True)
    monkeypatch.setattr(
        "codegraphcontext.tools.handlers.indexing_handlers.asyncio.run_coroutine_threadsafe",
        lambda coro, loop: None,
    )

    indexing_handlers.add_package_to_graph(
        mock_builder, mock_job_manager, None, fake_list_repos,
        package_name="requests", language="python", graph_name="tenant_pkg",
    )

    assert list_calls == ["tenant_pkg"]
    assert mock_job_manager.create_job.call_args.kwargs.get("graph_name") == "tenant_pkg"
    assert coro_capture["kwargs"].get("graph_name") == "tenant_pkg"


# ---------------------------------------------------------------------------
# watcher_handlers.watch_directory
# ---------------------------------------------------------------------------


def test_watch_directory_handler_forwards_graph_name_everywhere(tmp_path):
    """watch_directory must forward graph_name to list_repos_func, add_code_func,
    AND code_watcher.watch_directory."""
    real_dir = tmp_path

    list_calls = []

    def fake_list_repos(graph_name=None):
        list_calls.append(graph_name)
        return {"repositories": []}  # not indexed → triggers add_code_func

    add_code_calls = []

    def fake_add_code(**kwargs):
        add_code_calls.append(kwargs)
        return {"success": True, "job_id": "jid-3"}

    mock_watcher = MagicMock()
    mock_watcher.watched_paths = set()

    watcher_handlers.watch_directory(
        mock_watcher, fake_list_repos, fake_add_code,
        path=str(real_dir), graph_name="tenant_watch",
    )

    assert list_calls == ["tenant_watch"]
    assert add_code_calls and add_code_calls[0].get("graph_name") == "tenant_watch"
    mock_watcher.watch_directory.assert_called_once()
    assert mock_watcher.watch_directory.call_args.kwargs.get("graph_name") == "tenant_watch"
