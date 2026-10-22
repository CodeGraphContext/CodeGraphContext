"""#599: attach a watcher to a fresh embedded database without indexing first."""

import asyncio
import time

import pytest

from codegraphcontext.core.database_ladybug import LadybugDBManager
from codegraphcontext.core.database_embedded_kuzu import EmbeddedSessionWrapper
from codegraphcontext.core.jobs import JobManager
from codegraphcontext.core import watcher as watcher_module
from codegraphcontext.core.watcher import CodeWatcher
from codegraphcontext.tools.graph_builder import GraphBuilder


def _wait_until(predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return predicate()


@pytest.mark.integration
@pytest.mark.parametrize("use_polling", [False, True], ids=["native", "polling"])
@pytest.mark.parametrize(
    ("perform_initial_scan", "sync_on_start"),
    [(False, False), (False, True), (True, False)],
    ids=["events-only", "startup-sync", "initial-scan"],
)
def test_watch_first_initializes_repository_before_live_events(
    tmp_path, monkeypatch, use_polling, perform_initial_scan, sync_on_start
):
    pytest.importorskip("ladybug")
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

    monkeypatch.setattr(watcher_module.threading, "Timer", track_timer)
    try:
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


@pytest.mark.integration
@pytest.mark.parametrize("perform_initial_scan", [False, True])
def test_watch_attachment_preserves_metadata_unless_scanning(
    tmp_path, perform_initial_scan
):
    pytest.importorskip("ladybug")
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


@pytest.mark.integration
def test_watch_registration_preserves_a_concurrent_index_write(tmp_path, monkeypatch):
    pytest.importorskip("ladybug")
    repo = tmp_path / "repo"
    repo.mkdir()
    manager = LadybugDBManager(str(tmp_path / "db"))
    loop = asyncio.new_event_loop()
    try:
        builder = GraphBuilder(manager, JobManager(), loop)
        monkeypatch.setattr(
            "codegraphcontext.tools.indexing.persistence.writer.get_repo_commit_hash",
            lambda _path: "watch-commit",
        )
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

        monkeypatch.setattr(EmbeddedSessionWrapper, "run", interleaved_run)
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
