"""Visual previews should select the same graph rows after a reindex."""

import inspect

import pytest

from codegraphcontext.cli import visualizer
from codegraphcontext.core.database_kuzu import KuzuDBManager


@pytest.fixture(scope="module")
def indexed_graphs(tmp_path_factory):
    pytest.importorskip("kuzu")
    databases = []
    for prefix, order in (
        ("forward", range(200)),
        ("reverse", range(199, -1, -1)),
    ):
        root = tmp_path_factory.mktemp(prefix)
        databases.append(str(root / "db"))
        manager = KuzuDBManager(databases[-1])
        try:
            paths = [f"/repo/source_{index:03d}.py" for index in order]
            with manager.get_driver().session() as session:
                session.run(
                    "CREATE (:Function {uid: 'target', name: 'target', "
                    "path: '/repo/target.py', line_number: 1})"
                )
                session.run("CREATE (:Module {name: 'target_module'})")
                session.run(
                    "CREATE (:Class {uid: 'base', name: 'Base', "
                    "path: '/repo/base.py', line_number: 1})"
                )
                session.run(
                    "UNWIND $paths AS path "
                    "MATCH (target:Function {uid: 'target'}) "
                    "MATCH (module:Module {name: 'target_module'}) "
                    "MATCH (base:Class {uid: 'base'}) "
                    "CREATE (file:File {path: path, name: 'source.py'}) "
                    "CREATE (handler:Function {uid: path, name: 'handler', "
                    "path: path, line_number: 3}) "
                    "CREATE (owner:Class {uid: path, name: 'Service', "
                    "path: path, line_number: 1}) "
                    "CREATE (handler)-[:CALLS {line_number: 4}]->(target) "
                    "CREATE (target)-[:CALLS {line_number: 2}]->(handler) "
                    "CREATE (owner)-[:CONTAINS]->(handler) "
                    "CREATE (file)-[:IMPORTS {line_number: 1}]->(module) "
                    "CREATE (owner)-[:INHERITS]->(base)",
                    paths=paths,
                )
        finally:
            manager.close_driver()
    return databases


@pytest.mark.parametrize(
    ("render", "term", "options", "column", "limit"),
    [
        (visualizer.visualize_search_results, "handler", {}, "n", 80),
        (
            visualizer.visualize_search_results,
            "hand",
            {"search_type": "pattern"},
            "n",
            80,
        ),
        (visualizer.visualize_search_results, "File", {"search_type": "type"}, "n", 80),
        (
            visualizer.visualize_call_graph,
            "target",
            {"direction": "incoming"},
            "n",
            120,
        ),
        (visualizer.visualize_call_graph, "target", {}, "m", 120),
        (visualizer.visualize_overrides, "handler", {}, "n", 120),
        (visualizer.visualize_dependencies, "target_module", {}, "n", 120),
        (visualizer.visualize_inheritance_tree, "Base", {}, "n", 120),
    ],
)
def test_visualization_limit_is_independent_of_index_order(
    indexed_graphs, monkeypatch, render, term, options, column, limit
):
    queries = []
    monkeypatch.setattr(visualizer, "_launch_visualizer", queries.append)
    render([], term, **options)
    expected = [f"/repo/source_{index:03d}.py" for index in range(limit)]
    observed = []
    for path in indexed_graphs:
        manager = KuzuDBManager(path)
        try:
            with manager.get_driver().session() as session:
                rows = session.run(queries[0]).data()
                paths = [row[column]["path"] for row in rows]
                if render is visualizer.visualize_inheritance_tree:
                    # UNION output order is backend-defined; compare the drawn set.
                    paths.sort()
                observed.append(paths)
        finally:
            manager.close_driver()
    assert observed[0] == observed[1]
    assert observed[0] == expected


def test_call_chain_has_order_by_before_limit():
    """visualize_call_chain was missing ORDER BY before LIMIT 200 (#1865).

    The path-unwind pattern returns one row per hop across every discovered
    path.  Without ORDER BY the hop order depends on insertion order, so the
    same two-function chain produces different subgraphs after a re-index.
    This test is source-based so it runs without a database.
    """
    src = inspect.getsource(visualizer.visualize_call_chain)
    assert "ORDER BY" in src, "visualize_call_chain must have an ORDER BY clause"
    order_pos = src.index("ORDER BY")
    limit_pos = src.index("LIMIT 200")
    assert order_pos < limit_pos, "ORDER BY must appear before LIMIT 200"
