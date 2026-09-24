"""#1658: `Type::method()` calls resolve to the right impl — end to end.

Three pieces assembled across #1657 and #1510 make this work: impl methods
carry class_context (populating class_method_index), scoped calls carry their
receiver in inferred_obj_type (routing into method_target_for_type), and the
writer's called-context clause matches module/class context so the resolved
edge actually lands. This test pins the whole chain on a real embedded
database, including the two failure modes that used to occur: same-named
constructors binding to the wrong impl, and external types (Arc::new)
mis-binding to an unrelated local `new`.
"""
import asyncio
from pathlib import Path

import pytest

from codegraphcontext.core.database_kuzu import KuzuDBManager
from codegraphcontext.tools.graph_builder import GraphBuilder

kuzu = pytest.importorskip("kuzu")


class _DBM:
    def __init__(self, driver):
        self._driver = driver

    def get_driver(self, graph_name=None):
        return self._driver

    def get_backend_type(self):
        return "kuzudb"


class _JM:
    def update_job(self, *a, **k):
        pass


def test_scoped_constructor_calls_resolve_to_their_own_impl(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "lib.rs").write_text(
        "use std::sync::Arc;\n"
        "struct Worker;\n"
        "impl Worker { fn new() -> Worker { Worker } }\n"
        "struct Pool;\n"
        "impl Pool { fn new() -> Pool { Pool } }\n"
        "fn main() {\n"
        "    let w = Worker::new();\n"
        "    let p = Pool::new();\n"
        "    let a = Arc::new(1);\n"
        "}\n",
        encoding="utf-8",
    )
    manager = KuzuDBManager(str(tmp_path / "db"))
    driver = manager.get_driver()
    try:
        gb = GraphBuilder(_DBM(driver), _JM(), asyncio.new_event_loop())
        asyncio.new_event_loop().run_until_complete(
            gb.build_graph_from_path_async(repo, is_dependency=False)
        )
        with driver.session() as s:
            rows = s.run(
                "MATCH (a:Function)-[r:CALLS|HEURISTIC_CALLS]->(b:Function) "
                "RETURN a.name AS caller, b.name AS callee, b.class_context AS owner"
            ).data()
        edges = {(r["caller"], r["callee"], r["owner"]) for r in rows}
        # Same-named constructors resolve to their OWN impl...
        assert ("main", "new", "Worker") in edges
        assert ("main", "new", "Pool") in edges
        # ...and the external Arc::new does not mis-bind to a local `new`.
        assert len([e for e in edges if e[1] == "new"]) == 2
    finally:
        manager.close_driver()
