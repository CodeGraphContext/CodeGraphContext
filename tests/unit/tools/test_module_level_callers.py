"""Caller lookup must include module-level code even without context (#1850)."""

from types import SimpleNamespace

import pytest

from codegraphcontext.core.database_kuzu import KuzuDBManager
from codegraphcontext.tools.code_finder import CodeFinder

pytest.importorskip("kuzu")

TARGETS = ["Badge", "Widget", "HeuristicBadge", "HeuristicWidget"]


@pytest.fixture(scope="module")
def call_graph(tmp_path_factory):
    root = tmp_path_factory.mktemp("module_callers")
    repo = root / "repo"
    target_path = (repo / "target.ts").as_posix()
    source_path = (repo / "boot.ts").as_posix()
    manager = KuzuDBManager(str(root / "db"))
    driver = manager.get_driver()
    adapter = SimpleNamespace(
        get_driver=lambda graph_name=None: driver, get_backend_type=lambda: "kuzudb"
    )
    try:
        with driver.session() as session:
            session.run(
                "CREATE (:File {name: 'boot.ts', path: $path, is_dependency: false})",
                path=source_path,
            )
            for label, name in (("Function", "start"), ("Class", "Launcher")):
                session.run(
                    f"CREATE (:{label} {{uid: $name, name: $name, path: $path, "
                    "line_number: 3, is_dependency: false})",
                    name=name,
                    path=source_path,
                )
            session.run(
                "CREATE (:Function {uid: 'contained', name: 'contained', "
                "line_number: 5, is_dependency: false})"
            )
            session.run(
                "MATCH (f:File {path: $path}), (c:Function {uid: 'contained'}) "
                "CREATE (f)-[:CONTAINS]->(c)",
                path=source_path,
            )
            session.run(
                "CREATE (:File {name: 'outside.ts', path: $path, is_dependency: false})",
                path=(root / "repo-other" / "outside.ts").as_posix(),
            )
            for label, target, edge in (
                ("Function", "Badge", "CALLS"),
                ("Class", "Widget", "CALLS"),
                ("Function", "HeuristicBadge", "HEURISTIC_CALLS"),
                ("Class", "HeuristicWidget", "HEURISTIC_CALLS"),
            ):
                session.run(
                    f"CREATE (:{label} {{uid: $name, name: $name, path: $path, "
                    "line_number: 10, is_dependency: false})",
                    name=target,
                    path=target_path,
                )
                for caller_label in ("File", "Function", "Class"):
                    session.run(
                        f"MATCH (c:{caller_label}), (t:{label} {{name: $name}}) "
                        "WHERE c.name IN ['boot.ts', 'start', 'Launcher', 'contained', 'outside.ts'] "
                        f"CREATE (c)-[:{edge} {{line_number: 7, args: ['value']}}]->(t)",
                        name=target,
                    )
        yield CodeFinder(adapter), repo, target_path, source_path
    finally:
        manager.close_driver()


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("context", ["none", "exact", "fallback"])
def test_callers_include_files_classes_and_contained_functions(
    call_graph, target, context
):
    finder, _, target_path, source_path = call_graph
    path = {"none": None, "exact": target_path, "fallback": target_path + ".missing"}[
        context
    ]
    rows = finder.who_calls_function(target, path=path)
    assert {row["caller_function"] for row in rows} == {
        "boot.ts",
        "start",
        "Launcher",
        "contained",
        "outside.ts",
    }
    assert len(rows) == 5
    for row in rows:
        assert row["target_file_path"] == target_path
        assert row["call_line_number"] == 7
        assert row["call_args"] == ["value"]
        if row["caller_function"] != "outside.ts":
            assert row["caller_file_path"] == source_path


@pytest.mark.parametrize("target", TARGETS)
def test_default_callers_preserve_scope_and_limits(call_graph, target):
    finder, repo, target_path, _ = call_graph
    rows = finder.who_calls_function(target, repo_path=str(repo))
    assert {row["caller_function"] for row in rows} == {"boot.ts", "start", "Launcher"}
    exact_rows = finder.who_calls_function(
        target, path=target_path, repo_path=str(repo)
    )
    assert sorted(rows, key=lambda row: row["caller_function"]) == sorted(
        exact_rows, key=lambda row: row["caller_function"]
    )
    limited = finder.who_calls_function(target, repo_path=str(repo), limit=2)
    assert len(limited) == 2
    assert all(row in rows for row in limited)
    assert finder.who_calls_function(target, limit=0) == []


def test_find_callers_default_route_returns_module_level_calls(call_graph, monkeypatch):
    finder, repo, _, source_path = call_graph
    monkeypatch.setenv("TOOL_RESULT_LIMITS", '{"find_callers": 20}')
    result = finder.analyze_code_relationships(
        "find_callers", "Badge", repo_path=str(repo)
    )
    assert result["truncated"] is False
    assert {row["caller_function"] for row in result["results"]} == {
        "boot.ts",
        "start",
        "Launcher",
    }
    assert all(row["caller_file_path"] == source_path for row in result["results"])
    monkeypatch.setenv("TOOL_RESULT_LIMITS", '{"find_callers": 2}')
    result = finder.analyze_code_relationships(
        "find_callers", "Badge", repo_path=str(repo)
    )
    assert result["truncated"] is True
    assert result["result_limit"] == 2
    assert len(result["results"]) == 2
