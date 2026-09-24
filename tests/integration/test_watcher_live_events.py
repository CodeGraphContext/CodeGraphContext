"""End-to-end live watcher: real watchdog events → debounce → graph updates.

The startup-sync and handler internals are unit-tested; this covers the one
path nothing exercised — actual filesystem events driving incremental
updates on a real embedded database.
"""
import asyncio
import time
from pathlib import Path

import pytest

from codegraphcontext.core.database_kuzu import KuzuDBManager
from codegraphcontext.core.watcher import CodeWatcher
from codegraphcontext.tools.graph_builder import GraphBuilder

kuzu = pytest.importorskip("kuzu")


class _DBM:
    def __init__(self, d): self._d = d
    def get_driver(self, graph_name=None): return self._d
    def get_backend_type(self): return "kuzudb"


class _JM:
    def update_job(self, *a, **k): pass


def _wait_until(predicate, timeout=30.0, interval=0.5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def test_watcher_applies_modify_create_and_delete(tmp_path: Path):
    repo = tmp_path / "repo"; repo.mkdir()
    (repo / "a.py").write_text("def one():\n    pass\n", encoding="utf-8")

    manager = KuzuDBManager(str(tmp_path / "db"))
    driver = manager.get_driver()
    gb = GraphBuilder(_DBM(driver), _JM(), asyncio.new_event_loop())
    asyncio.new_event_loop().run_until_complete(
        gb.build_graph_from_path_async(repo, is_dependency=False)
    )

    def funcs():
        with driver.session() as s:
            return sorted(
                r["n"] for r in s.run(
                    "MATCH (f:Function) WHERE f.name <> '<module>' RETURN f.name AS n"
                ).data()
            )

    assert funcs() == ["one"]

    watcher = CodeWatcher(gb)
    watcher.watch_directory(str(repo), perform_initial_scan=False)
    watcher.start()
    try:
        (repo / "a.py").write_text(
            "def one():\n    pass\n\ndef two():\n    return 1\n", encoding="utf-8"
        )
        assert _wait_until(lambda: "two" in funcs()), (
            f"modify event never reached the graph: {funcs()}"
        )

        (repo / "b.py").write_text("def three():\n    return 3\n", encoding="utf-8")
        assert _wait_until(lambda: "three" in funcs()), (
            f"create event never reached the graph: {funcs()}"
        )

        (repo / "b.py").unlink()
        assert _wait_until(lambda: "three" not in funcs()), (
            f"delete event never reached the graph: {funcs()}"
        )

        assert funcs() == ["one", "two"]
    finally:
        watcher.stop()
        manager.close_driver()
