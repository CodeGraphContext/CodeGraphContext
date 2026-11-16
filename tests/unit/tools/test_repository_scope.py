"""Check repository boundaries through the actual embedded Cypher queries."""

import pytest

from codegraphcontext.core.database_kuzu import KuzuDBManager
from codegraphcontext.tools.code_finder import CodeFinder
from codegraphcontext.tools.query_tool_languages.java_toolkit import JavaToolkit


@pytest.fixture
def sibling_repositories(tmp_path):
    pytest.importorskip("kuzu")
    manager = KuzuDBManager(str(tmp_path / "db"))
    try:
        paths = [
            (tmp_path / name / "app.py").as_posix() for name in ("repo", "repo-other")
        ]
        with manager.get_driver().session() as session:
            for path in paths:
                session.run(
                    "CREATE (file:File {path: $path, name: 'app.py', is_dependency: false}) "
                    "CREATE (fn:Function {uid: $path, path: $path, name: 'helper', "
                    "line_number: 1, is_dependency: false, cyclomatic_complexity: 2, "
                    "arg_types: ['token'], source: 'def helper(token): pass', "
                    "http_method: 'GET', http_path: '/status'}) "
                    "CREATE (file)-[:CONTAINS]->(fn) "
                    "MERGE (m:Module {name: 'os'}) CREATE (file)-[:IMPORTS]->(m)",
                    path=path,
                )
        yield CodeFinder(manager), (tmp_path / "repo").as_posix(), paths
    finally:
        manager.close_driver()


@pytest.mark.parametrize(
    ("method", "args"),
    [
        ("find_by_function_name", ("helper", False)),
        ("find_by_function_name", ("helper", True)),
        ("find_by_content", ("helper",)),
        ("find_functions_by_argument", ("token",)),
        ("find_most_complex_functions", ()),
        ("who_imports_module", ("os",)),
    ],
)
def test_repository_scope_excludes_shared_prefix_sibling(
    sibling_repositories, method, args
):
    finder, repo_path, paths = sibling_repositories
    search = getattr(finder, method)

    assert {row["path"] for row in search(*args)} == set(paths)
    for scope in (repo_path, repo_path + "/"):
        assert {row["path"] for row in search(*args, repo_path=scope)} == {paths[0]}


def test_java_endpoint_scope_excludes_shared_prefix_sibling(sibling_repositories):
    finder, repo_path, paths = sibling_repositories
    toolkit = JavaToolkit()._init_with(finder)

    assert {row["file"] for row in toolkit.find_spring_endpoints()} == set(paths)
    rows = toolkit.find_spring_endpoints(repo_path=repo_path)
    assert {row["file"] for row in rows} == {paths[0]}
