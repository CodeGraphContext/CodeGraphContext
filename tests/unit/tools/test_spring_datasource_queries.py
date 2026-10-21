import os
from types import SimpleNamespace

import pytest

from codegraphcontext.core.database_kuzu import KuzuDBManager
from codegraphcontext.core.database_ladybug import LadybugDBManager
from codegraphcontext.tools.handlers.analysis_handlers import (
    find_datasource_nodes, find_java_spring_beans, find_java_spring_endpoints,
)
from codegraphcontext.tools.indexing.persistence.writer import GraphWriter
from codegraphcontext.tools.languages.java import JavaTreeSitterParser
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager


@pytest.fixture
def graph(tmp_path, monkeypatch):
    # Run each native engine in a separate process: their C++ symbols collide.
    manager_type = LadybugDBManager if os.getenv("CGC_TEST_EMBEDDED_BACKEND") == "ladybugdb" else KuzuDBManager
    pytest.importorskip(manager_type.BACKEND_SPEC.python_module)
    monkeypatch.setenv("CGC_EMBEDDED_BUFFER_POOL_MB", "1024")
    manager = manager_type(str(tmp_path / "db"))
    driver = manager.get_driver()
    yield manager, GraphWriter(driver, manager), SimpleNamespace(driver=driver)
    manager.close_driver()


@pytest.mark.parametrize("method_path,prefix,expected", [
    ('"/hello"', '"/api"', "/api/hello"),
    ('"hello"', '"/api/"', "/api/hello"),
    ("", '"/api"', "/api"),
])
def test_spring_parser_writer_and_query_agree(graph, tmp_path, method_path, prefix, expected):
    manager, writer, finder = graph
    source = tmp_path / "Demo.java"
    source.write_text(f'''@RestController @RequestMapping({prefix})
class Demo {{ @GetMapping({method_path}) public String hello() {{ return "ok"; }} }}
@Service class ServiceBean {{}}
''')
    ts = get_tree_sitter_manager()
    parser = JavaTreeSitterParser(SimpleNamespace(language_name="java", language=ts.get_language_safe("java"), parser=ts.create_parser("java")))
    parsed = parser.parse(source)
    parsed["repo_path"] = str(tmp_path)
    writer.add_repository_to_graph(tmp_path)
    writer.add_file_to_graph(parsed, tmp_path.name, {}, str(tmp_path))
    endpoint = find_java_spring_endpoints(finder, http_method="GET", path_pattern="/api")
    assert endpoint["success"] is True
    assert [(r["handler"], r["path"]) for r in endpoint["endpoints"]] == [("hello", expected)]
    beans = find_java_spring_beans(finder, stereotype="SERVICE")
    assert beans["success"] is True
    assert [(r["name"], r["stereotype"]) for r in beans["beans"]] == [("ServiceBean", "SERVICE")]


def test_empty_datasource_graph_and_all_filters(graph):
    _, _, finder = graph
    for kind in (None, "mysql", "cassandra", "redis"):
        result = find_datasource_nodes(finder, **({"kind": kind} if kind else {}))
        assert result == {"success": True, "datasources": [], "count": 0}


def test_populated_datasource_graph_filters_order_and_columns(graph):
    _, writer, finder = graph
    for name in ("zeta", "alpha"):
        writer.write_datasource_graph({
            "datasource": {"name": name, "kind": "mysql", "host": "localhost", "env": "test"},
            "tables": [{"fqn": name + ".users", "name": "users", "datasource_name": name}],
            "columns": [{"name": "id", "table_fqn": name + ".users", "type": "INT", "nullable": False, "datasource_name": name, "is_primary_key": True}],
        })
    result = find_datasource_nodes(finder, include_columns=True)
    assert result["success"] is True
    assert [r["datasource"] for r in result["datasources"]] == ["alpha", "zeta"]
    assert result["datasources"][0]["columns"]["alpha.users"][0]["name"] == "id"
    assert find_datasource_nodes(finder, kind="redis")["datasources"] == []
    assert find_datasource_nodes(finder, name="alpha")["count"] == 1
