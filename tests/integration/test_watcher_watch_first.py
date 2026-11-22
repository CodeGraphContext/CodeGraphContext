"""#599: attach a watcher to a fresh embedded database without indexing first.

Every case opens Ladybug, so each one runs in its own interpreter: the fast
suite already holds Kuzu in the pytest process, and the two embedded native
libraries must never share one (see ``tests/conftest.py``). The pytest tests
only spawn this file as a script; nothing here imports an engine in-process.
"""

import asyncio
import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest import mock

import pytest


def _wait_until(predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return predicate()


def _live_events_case(tmp_path, use_polling, perform_initial_scan, sync_on_start):
    from codegraphcontext.core import watcher as watcher_module
    from codegraphcontext.core.database_ladybug import LadybugDBManager
    from codegraphcontext.core.jobs import JobManager
    from codegraphcontext.core.watcher import CodeWatcher
    from codegraphcontext.tools.graph_builder import GraphBuilder

    repo = tmp_path / "Mixed Case Repo"
    source_dir = repo / "Source Dir"
    source_dir.mkdir(parents=True)
    source = source_dir / "Example.py"
    db_path = tmp_path / "fresh-db"
    assert not db_path.exists()

    manager = LadybugDBManager(str(db_path))
    loop = asyncio.new_event_loop()
    watcher = None
    timers = []
    timer_class = watcher_module.threading.Timer

    def track_timer(*args, **kwargs):
        timer = timer_class(*args, **kwargs)
        timers.append(timer)
        return timer

    try:
        with mock.patch.object(watcher_module.threading, "Timer", track_timer):
            builder = GraphBuilder(manager, JobManager(), loop)
            driver = builder.driver

            def rows(query, **params):
                with driver.session() as session:
                    return session.run(query, **params).data()

            # These queries also prove the embedded schema exists before any event.
            assert rows("MATCH (r:Repository) RETURN r.path AS path") == []
            assert rows("MATCH (f:File) RETURN f.path AS path") == []
            assert rows("MATCH (f:Function) RETURN f.name AS name") == []

            watcher = CodeWatcher(builder, use_polling=use_polling)
            watcher.start()
            watcher.watch_directory(
                str(repo),
                perform_initial_scan=perform_initial_scan,
                sync_on_start=sync_on_start,
            )
            handler = watcher.handlers[str(repo.resolve())]
            handler.debounce_interval = 0.05
            assert rows("MATCH (r:Repository) RETURN r.path AS path") == [
                {"path": repo.resolve().as_posix()}
            ]

            def functions():
                # Orphan File/Function nodes must not satisfy the assertion: the
                # missing Repository used to leave live updates outside the graph's
                # repository hierarchy even when parsing appeared to succeed.
                return sorted(
                    row["name"]
                    for row in rows(
                        "MATCH (r:Repository {path: $repo})-[:CONTAINS]->(:Directory)"
                        "-[:CONTAINS]->(f:File {path: $file})-[:CONTAINS]->(fn:Function) "
                        "WHERE fn.name <> '<module>' RETURN fn.name AS name",
                        repo=repo.resolve().as_posix(),
                        file=source.resolve().as_posix(),
                    )
                )

            source.write_text("def created():\n    return 1\n", encoding="utf-8")
            assert _wait_until(lambda: functions() == ["created"]), functions()

            # Graph writes can become visible before the same handler finishes
            # re-reading the file for relationship linking. This test exercises
            # sequential create/modify/delete, not concurrent reader interruption:
            # wait for that owned update before each next mutation. Windows denies
            # unlinking an open reader; graph visibility alone is not quiescence.
            assert handler._update_lock.acquire(timeout=5), "previous update did not finish"
            try:
                source.write_text("def modified():\n    return 2\n", encoding="utf-8")
            finally:
                handler._update_lock.release()
            assert _wait_until(lambda: functions() == ["modified"]), functions()

            assert handler._update_lock.acquire(timeout=5), "previous update did not finish"
            try:
                source.unlink()
            finally:
                handler._update_lock.release()
            assert _wait_until(
                lambda: (
                    rows("MATCH (f:File) RETURN f.path AS path") == []
                    and rows("MATCH (f:Function) RETURN f.name AS name") == []
                )
            )
            assert rows("MATCH (r:Repository) RETURN r.path AS path") == [
                {"path": repo.resolve().as_posix()}
            ]
    finally:
        if watcher is not None:
            # Stop dispatch first so no new timer can be enqueued during
            # teardown. A fired timer is no longer in handler.timers, so retain
            # and join every test-owned timer, including queued/active updates.
            if watcher.observer.is_alive():
                watcher.observer.stop()
                watcher.observer.join(timeout=10)
                assert not watcher.observer.is_alive()
            watcher.stop()
        for timer in timers:
            timer.cancel()
        for timer in timers:
            timer.join(timeout=30)
            assert not timer.is_alive()
        manager.close_driver()
        loop.close()


def _metadata_case(tmp_path, perform_initial_scan):
    from codegraphcontext.core.database_ladybug import LadybugDBManager
    from codegraphcontext.core.jobs import JobManager
    from codegraphcontext.core.watcher import CodeWatcher
    from codegraphcontext.tools.graph_builder import GraphBuilder

    repo = tmp_path / "repo"
    repo.mkdir()
    manager = LadybugDBManager(str(tmp_path / "db"))
    loop = asyncio.new_event_loop()
    watcher = None
    try:
        builder = GraphBuilder(manager, JobManager(), loop)
        builder.add_repository_to_graph(repo, is_dependency=True)
        with builder.driver.session() as session:
            session.run(
                "MATCH (r:Repository) SET r.indexed_at = $indexed_at, r.commit_hash = $commit_hash",
                indexed_at="previous-index-time",
                commit_hash="previous-index-commit",
            )
            query = (
                "MATCH (r:Repository) RETURN r.path AS path, "
                "r.indexed_at AS indexed_at, r.commit_hash AS commit_hash, "
                "r.is_dependency AS is_dependency"
            )
            before = session.run(query).data()
        watcher = CodeWatcher(builder, use_polling=True)
        watcher.watch_directory(str(repo), perform_initial_scan=perform_initial_scan)
        with builder.driver.session() as session:
            after = session.run(query).data()
        if perform_initial_scan:
            assert after[0]["indexed_at"] != before[0]["indexed_at"]
            assert after[0]["is_dependency"] is False
        else:
            assert after == before
    finally:
        if watcher is not None:
            watcher.stop()
        manager.close_driver()
        loop.close()


def _concurrent_index_write_case(tmp_path):
    from codegraphcontext.core.database_embedded_kuzu import EmbeddedSessionWrapper
    from codegraphcontext.core.database_ladybug import LadybugDBManager
    from codegraphcontext.core.jobs import JobManager
    from codegraphcontext.tools.graph_builder import GraphBuilder

    repo = tmp_path / "repo"
    repo.mkdir()
    manager = LadybugDBManager(str(tmp_path / "db"))
    loop = asyncio.new_event_loop()
    try:
        builder = GraphBuilder(manager, JobManager(), loop)
        original_run = EmbeddedSessionWrapper.run
        pending_index = True

        def interleaved_run(session, query, *args, **kwargs):
            nonlocal pending_index
            # The index wins immediately before the watcher's repository write.
            # A separate existence read followed by an unconditional MERGE/SET
            # would overwrite these values despite having observed no node.
            if pending_index and "MERGE (r:Repository" in query:
                pending_index = False
                builder.add_repository_to_graph(repo, is_dependency=True)
                with builder.driver.session() as index_session:
                    original_run(
                        index_session,
                        "MATCH (r:Repository) SET r.name = $name, "
                        "r.indexed_at = $indexed_at, r.commit_hash = $commit_hash",
                        name="indexed-name",
                        indexed_at="index-time",
                        commit_hash="index-commit",
                    )
            return original_run(session, query, *args, **kwargs)

        with mock.patch(
            "codegraphcontext.tools.indexing.persistence.writer.get_repo_commit_hash",
            lambda _path: "watch-commit",
        ), mock.patch.object(EmbeddedSessionWrapper, "run", interleaved_run):
            builder.add_repository_to_graph(repo, preserve_existing=True)
        assert not pending_index
        with builder.driver.session() as session:
            assert session.run(
                "MATCH (r:Repository) RETURN r.name AS name, r.indexed_at AS indexed_at, "
                "r.commit_hash AS commit_hash, r.is_dependency AS is_dependency"
            ).data() == [
                {
                    "name": "indexed-name",
                    "indexed_at": "index-time",
                    "commit_hash": "index-commit",
                    "is_dependency": True,
                }
            ]
    finally:
        manager.close_driver()
        loop.close()


_CASES = {
    "live_events": _live_events_case,
    "metadata": _metadata_case,
    "concurrent_index_write": _concurrent_index_write_case,
}


def _run_case(tmp_path, case, *args):
    if importlib.util.find_spec("ladybug") is None:
        pytest.skip("ladybug is not installed")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(Path(__file__).resolve().parents[2] / "src"), env.get("PYTHONPATH")) if p
    )
    result = subprocess.run(
        [sys.executable, __file__, case, str(tmp_path), *map(str, args)],
        env=env,
        capture_output=True,
        text=True,
        timeout=240,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.integration
@pytest.mark.parametrize("use_polling", [False, True], ids=["native", "polling"])
@pytest.mark.parametrize(
    ("perform_initial_scan", "sync_on_start"),
    [(False, False), (False, True), (True, False)],
    ids=["events-only", "startup-sync", "initial-scan"],
)
def test_watch_first_initializes_repository_before_live_events(
    tmp_path, use_polling, perform_initial_scan, sync_on_start
):
    _run_case(tmp_path, "live_events", use_polling, perform_initial_scan, sync_on_start)


@pytest.mark.integration
@pytest.mark.parametrize("perform_initial_scan", [False, True])
def test_watch_attachment_preserves_metadata_unless_scanning(tmp_path, perform_initial_scan):
    _run_case(tmp_path, "metadata", perform_initial_scan)


@pytest.mark.integration
def test_watch_registration_preserves_a_concurrent_index_write(tmp_path):
    _run_case(tmp_path, "concurrent_index_write")


if __name__ == "__main__":
    case, case_tmp_path, *flags = sys.argv[1:]
    _CASES[case](Path(case_tmp_path), *(flag == "True" for flag in flags))
