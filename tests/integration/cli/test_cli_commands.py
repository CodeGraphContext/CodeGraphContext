
import ast
import os
import sys
import types
from pathlib import Path
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console
from typer.testing import CliRunner

import codegraphcontext.cli.main as cli_main
from codegraphcontext.cli.main import app, _load_credentials

runner = CliRunner()


def _command_name_from_decorator(decorator: ast.Call, func_name: str) -> str:
    if decorator.args and isinstance(decorator.args[0], ast.Constant) and isinstance(decorator.args[0].value, str):
        return decorator.args[0].value

    for kw in decorator.keywords:
        if kw.arg == "name" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value

    return func_name.replace("_", "-")


def _inventory_from_main_source() -> dict[str, set[str]]:
    source = Path(cli_main.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    group_alias_to_name: dict[str, str] = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.Expr):
            continue
        call = node.value
        if not isinstance(call, ast.Call):
            continue
        if not isinstance(call.func, ast.Attribute):
            continue
        if call.func.attr != "add_typer":
            continue
        if not isinstance(call.func.value, ast.Name) or call.func.value.id != "app":
            continue
        if not call.args or not isinstance(call.args[0], ast.Name):
            continue

        group_alias = call.args[0].id
        for kw in call.keywords:
            if kw.arg == "name" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                group_alias_to_name[group_alias] = kw.value.value

    inventory: dict[str, set[str]] = {
        "root": set(),
        "mcp": set(),
        "neo4j": set(),
        "config": set(),
        "bundle": set(),
        "registry": set(),
        "find": set(),
        "analyze": set(),
    }

    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue

        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            if not isinstance(decorator.func, ast.Attribute):
                continue
            if decorator.func.attr != "command":
                continue
            if not isinstance(decorator.func.value, ast.Name):
                continue

            owner = decorator.func.value.id
            family = "root" if owner == "app" else group_alias_to_name.get(owner)
            if family is None:
                continue

            command_name = _command_name_from_decorator(decorator, node.name)
            inventory.setdefault(family, set()).add(command_name)

    return inventory


class _FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def run(self, query, **kwargs):
        if "MATCH (n:File)" in query:
            return [{"name": "main.py", "path": "repo/main.py", "is_dependency": False}]
        return [{"type": "Function", "name": "demo", "path": "repo/main.py", "line_number": 1, "is_dependency": False}]


class _FakeDriver:
    def session(self):
        return _FakeSession()


class _FakeDBManager:
    def get_driver(self):
        return _FakeDriver()

    def close_driver(self):
        return None


class _FakeGraphBuilder:
    def delete_repository_from_graph(self, _):
        return None


class _FakeCodeFinder:
    def find_by_function_name(self, *_args, **_kwargs):
        return [{"name": "foo", "path": "repo/main.py", "line_number": 2, "is_dependency": False}]

    def find_by_class_name(self, *_args, **_kwargs):
        return [{"name": "Foo", "path": "repo/main.py", "line_number": 3, "is_dependency": False}]

    def find_by_variable_name(self, *_args, **_kwargs):
        return [{"name": "value", "path": "repo/main.py", "line_number": 4, "context": "module", "is_dependency": False}]

    def find_by_module_name(self, *_args, **_kwargs):
        return [{"name": "repo.module", "path": "repo/module.py", "line_number": 1, "is_dependency": False}]

    def find_imports(self, *_args, **_kwargs):
        return [{"alias": "json", "imported_name": "json", "path": "repo/main.py", "line_number": 1, "is_dependency": False}]

    def find_by_type(self, *_args, **_kwargs):
        return [{"name": "foo", "path": "repo/main.py", "line_number": 2, "is_dependency": False}]

    def find_by_content(self, *_args, **_kwargs):
        return [{"name": "foo", "type": "Function", "path": "repo/main.py", "line_number": 2}]

    def find_functions_by_decorator(self, *_args, **_kwargs):
        return [{"function_name": "foo", "path": "repo/main.py", "line_number": 2, "decorators": ["route"]}]

    def find_functions_by_argument(self, *_args, **_kwargs):
        return [{"function_name": "foo", "path": "repo/main.py", "line_number": 2}]

    def what_does_function_call(self, *_args, **_kwargs):
        return [{"called_function": "bar", "called_file_path": "repo/main.py", "called_line_number": 10, "called_is_dependency": False}]

    def who_calls_function(self, *_args, **_kwargs):
        return [{"caller_function": "main", "caller_file_path": "repo/main.py", "caller_line_number": 1, "caller_is_dependency": False}]

    def find_function_call_chain(self, *_args, **_kwargs):
        return [{
            "chain_length": 2,
            "function_chain": [
                {"name": "main", "path": "repo/main.py", "line_number": 1},
                {"name": "foo", "path": "repo/main.py", "line_number": 2},
            ],
            "call_details": [{"call_line": 1, "args": ["x"]}],
        }]

    def find_module_dependencies(self, *_args, **_kwargs):
        return {
            "importers": [{"importer_file_path": "repo/main.py", "import_line_number": 1}],
            "imports": [{"imported_module": "json", "import_line_number": 1}],
        }

    def find_class_hierarchy(self, *_args, **_kwargs):
        return {
            "parent_classes": [{"parent_class": "Base", "parent_file_path": "repo/base.py", "parent_line_number": 1}],
            "child_classes": [{"child_class": "Derived", "child_file_path": "repo/main.py", "child_line_number": 2}],
            "methods": [{"method_name": "run", "method_args": "self"}],
        }

    def get_cyclomatic_complexity(self, *_args, **_kwargs):
        return {"complexity": 3, "path": "repo/main.py", "line_number": 2}

    def find_most_complex_functions(self, *_args, **_kwargs):
        return [{"function_name": "complex", "complexity": 12, "path": "repo/main.py", "line_number": 20}]

    def find_dead_code(self, *_args, **_kwargs):
        return {
            "potentially_unused_functions": [{"function_name": "unused", "path": "repo/main.py", "line_number": 30}],
            "note": "Static approximation",
        }

    def find_function_overrides(self, *_args, **_kwargs):
        return [{"class_name": "Derived", "function_name": "run", "class_file_path": "repo/main.py", "function_line_number": 20}]

    def find_variable_usage_scope(self, *_args, **_kwargs):
        return {
            "instances": [{
                "scope_type": "function",
                "scope_name": "foo",
                "path": "repo/main.py",
                "line_number": 2,
                "variable_value": "1",
            }]
        }

    def list_indexed_repositories(self):
        return [{"name": "repo", "path": "repo"}]


@pytest.fixture
def kuzudb_env():
    env = {
        "DEFAULT_DATABASE": "kuzudb",
        "DATABASE_TYPE": "kuzudb",
        "CGC_RUNTIME_DB_TYPE": "kuzudb",
    }
    with patch.dict(os.environ, env, clear=False):
        yield


@pytest.fixture
def cli_test_stubs(monkeypatch, tmp_path):
    monkeypatch.setattr(cli_main.config_manager, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cli_main.config_manager, "CONFIG_FILE", tmp_path / "config.json")

    monkeypatch.setattr(cli_main, "_load_credentials", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli_main, "configure_mcp_client", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli_main, "run_neo4j_setup_wizard", lambda *_args, **_kwargs: None)

    monkeypatch.setattr(cli_main, "index_helper", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli_main, "add_package_helper", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli_main, "list_repos_helper", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli_main, "delete_helper", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli_main, "cypher_helper", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli_main, "cypher_helper_visual", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli_main, "visualize_helper", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli_main, "reindex_helper", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli_main, "clean_helper", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli_main, "stats_helper", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli_main, "watch_helper", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli_main, "unwatch_helper", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli_main, "list_watching_helper", lambda *_args, **_kwargs: None)

    fake_db = _FakeDBManager()
    monkeypatch.setattr(cli_main, "_initialize_services", lambda *_args, **_kwargs: (fake_db, _FakeGraphBuilder(), _FakeCodeFinder()))
    monkeypatch.setattr(cli_main.DatabaseManager, "test_connection", staticmethod(lambda *_args, **_kwargs: (True, None)))
    monkeypatch.setattr(cli_main.typer, "confirm", lambda *_args, **_kwargs: True)

    class _FakeMCPServer:
        def __init__(self, *_args, **_kwargs):
            self.tools = {
                "demo": {"name": "demo.tool", "description": "demo"},
            }

        async def run(self):
            return None

        def shutdown(self):
            return None

    monkeypatch.setattr(cli_main, "MCPServer", _FakeMCPServer)

    downloaded_bundle = tmp_path / "downloaded.cgc"
    downloaded_bundle.write_text("bundle", encoding="utf-8")

    registry_module = types.ModuleType("codegraphcontext.cli.registry_commands")
    registry_module.list_bundles = lambda *_args, **_kwargs: None
    registry_module.search_bundles = lambda *_args, **_kwargs: None
    registry_module.download_bundle = lambda *_args, **_kwargs: str(downloaded_bundle)
    registry_module.request_bundle = lambda *_args, **_kwargs: None
    monkeypatch.setitem(sys.modules, "codegraphcontext.cli.registry_commands", registry_module)

    bundle_module = types.ModuleType("codegraphcontext.core.cgc_bundle")

    class _FakeCGCBundle:
        def __init__(self, _db_manager):
            pass

        def export_to_bundle(self, *_args, **_kwargs):
            return True, "Bundle exported"

        def import_from_bundle(self, *_args, **_kwargs):
            return True, "Bundle imported"

    bundle_module.CGCBundle = _FakeCGCBundle
    monkeypatch.setitem(sys.modules, "codegraphcontext.core.cgc_bundle", bundle_module)

    return {
        "bundle_file": downloaded_bundle,
        "bundle_export": tmp_path / "exported.cgc",
    }


def _matrix_command_set(entries: list[list[str]]) -> set[tuple[str, str]]:
    families = set(_inventory_from_main_source().keys()) - {"root"}
    covered: set[tuple[str, str]] = set()
    for args in entries:
        if args[0] in families:
            covered.add((args[0], args[1]))
        else:
            covered.add(("root", args[0]))
    return covered


def test_cli_inventory_grouped_from_source():
    inventory = _inventory_from_main_source()

    assert {"root", "mcp", "neo4j", "config", "bundle", "registry", "find", "analyze"}.issubset(set(inventory.keys()))
    assert inventory["mcp"] == {"setup", "start", "tools"}
    assert inventory["neo4j"] == {"setup"}
    assert inventory["config"] == {"show", "set", "reset", "db"}
    assert inventory["bundle"] == {"export", "import", "load"}
    assert inventory["registry"] == {"list", "search", "download", "request"}
    assert inventory["find"] == {"name", "pattern", "type", "variable", "content", "decorator", "argument"}
    assert inventory["analyze"] == {"calls", "callers", "chain", "deps", "tree", "complexity", "dead-code", "overrides", "variable"}
    if "context" in inventory:
        assert inventory["context"] == {"list", "create", "delete", "mode", "default"}


def test_all_canonical_cli_commands_run_with_kuzudb(kuzudb_env, cli_test_stubs):
    bundle_file = str(cli_test_stubs["bundle_file"])
    bundle_export = str(cli_test_stubs["bundle_export"])

    command_matrix = [
        ["mcp", "setup"],
        ["mcp", "start"],
        ["mcp", "tools"],
        ["neo4j", "setup"],
        ["config", "show"],
        ["config", "set", "MAX_FILE_SIZE_MB", "11"],
        ["config", "reset"],
        ["config", "db", "kuzudb"],
        ["bundle", "export", bundle_export],
        ["bundle", "import", bundle_file],
        ["bundle", "load", bundle_file],
        ["registry", "list"],
        ["registry", "search", "numpy"],
        ["registry", "download", "numpy"],
        ["registry", "request", "https://github.com/example/repo"],
        ["doctor"],
        ["start"],
        ["index", "."],
        ["clean"],
        ["stats"],
        ["delete", "."],
        ["visualize"],
        ["list"],
        ["add-package", "requests", "python"],
        ["watch", "."],
        ["unwatch", "."],
        ["watching"],
        ["find", "name", "foo"],
        ["find", "pattern", "foo"],
        ["find", "type", "function"],
        ["find", "variable", "value"],
        ["find", "content", "foo"],
        ["find", "decorator", "route"],
        ["find", "argument", "user_id"],
        ["analyze", "calls", "foo"],
        ["analyze", "callers", "foo"],
        ["analyze", "chain", "main", "foo"],
        ["analyze", "deps", "json"],
        ["analyze", "tree", "Foo"],
        ["analyze", "complexity"],
        ["analyze", "dead-code"],
        ["analyze", "overrides", "run"],
        ["analyze", "variable", "value"],
        ["query", "MATCH (n) RETURN n LIMIT 1"],
        ["cypher", "MATCH (n) RETURN n LIMIT 1"],
        ["i", "."],
        ["ls"],
        ["rm", "."],
        ["v", "."],
        ["w", "."],
        ["help"],
        ["version"],
        ["m"],
        ["n"],
        ["export", bundle_export],
        ["load", bundle_file],
    ]

    source_inventory = _inventory_from_main_source()
    if "context" in source_inventory:
        command_matrix.extend(
            [
                ["context", "list"],
                ["context", "create", "ci-context"],
                ["context", "delete", "ci-context"],
                ["context", "mode", "single"],
                ["context", "default", "ci-context"],
            ]
        )

    expected_inventory = source_inventory
    expected_set = {(family, name) for family, names in expected_inventory.items() for name in names}
    assert _matrix_command_set(command_matrix) == expected_set

    for args in command_matrix:
        result = runner.invoke(app, ["--database", "kuzudb", *args])
        assert result.exit_code == 0, f"command failed: {' '.join(args)}\n{result.output}"
        assert result.exception is None, f"exception raised for {' '.join(args)}"
        assert "Traceback" not in result.output


def test_config_db_rejects_invalid_backend_with_clear_error(kuzudb_env):
    result = runner.invoke(app, ["config", "db", "invalid-backend"])

    assert result.exit_code == 1
    assert "Invalid backend" in result.output
    assert "kuzudb" in result.output


def test_config_show_with_empty_config_does_not_crash(monkeypatch, tmp_path):
    monkeypatch.setattr(cli_main.config_manager, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cli_main.config_manager, "CONFIG_FILE", tmp_path / "config.json")

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0
    assert "Configuration Settings" in result.output


def test_find_content_falkordb_known_limitation_message(monkeypatch):
    class _FakeFalkorDBManager:
        def close_driver(self):
            return None

    class _FailingFinder:
        def find_by_content(self, _query):
            raise Exception("CALL db.index.fulltext.queryNodes is unsupported")

    monkeypatch.setattr(cli_main, "_load_credentials", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        cli_main,
        "_initialize_services",
        lambda *_args, **_kwargs: (_FakeFalkorDBManager(), _FakeGraphBuilder(), _FailingFinder()),
    )

    result = runner.invoke(app, ["--database", "falkordb", "find", "content", "foo"])

    assert result.exit_code == 0
    assert "Full-text search is not supported on FalkorDB" in result.output
    assert "cgc find pattern" in result.output


class TestNeo4jDatabaseNameCLI:
    """Integration tests for NEO4J_DATABASE display in CLI commands."""

    @patch("codegraphcontext.cli.main.config_manager")
    @patch("codegraphcontext.core.database.DatabaseManager.test_connection")
    def test_doctor_passes_database_to_test_connection(self, mock_test_conn, mock_config_mgr):
        """Test that the doctor command passes NEO4J_DATABASE to test_connection."""
        mock_config_mgr.load_config.return_value = {"DEFAULT_DATABASE": "neo4j"}
        mock_config_mgr.CONFIG_FILE = MagicMock()
        mock_config_mgr.CONFIG_FILE.exists.return_value = True
        mock_config_mgr.validate_config_value.return_value = (True, None)
        mock_test_conn.return_value = (True, None)

        env = {
            "NEO4J_URI": "bolt://localhost:7687",
            "NEO4J_USERNAME": "neo4j",
            "NEO4J_PASSWORD": "password",
            "NEO4J_DATABASE": "mydb",
            "DEFAULT_DATABASE": "neo4j",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch("codegraphcontext.cli.main._load_credentials"):
                runner.invoke(app, ["doctor"])

        mock_test_conn.assert_called_once_with(
            "bolt://localhost:7687", "neo4j", "password", database="mydb"
        )

    @patch("codegraphcontext.cli.main.find_dotenv", return_value=None)
    @patch("codegraphcontext.cli.main.config_manager")
    def test_load_credentials_displays_database_name(self, mock_config_mgr, _mock_find_dotenv, monkeypatch, tmp_path):
        """Test _load_credentials prints database name when NEO4J_DATABASE is set."""
        mock_config_mgr.ensure_config_dir.return_value = None

        env = {
            "NEO4J_URI": "bolt://localhost:7687",
            "NEO4J_USERNAME": "neo4j",
            "NEO4J_PASSWORD": "password",
            "NEO4J_DATABASE": "mydb",
            "DEFAULT_DATABASE": "neo4j",
        }
        monkeypatch.chdir(tmp_path)
        clean_env = {
            k: v for k, v in os.environ.items()
            if k not in {
                "DEFAULT_DATABASE",
                "DATABASE_TYPE",
                "CGC_RUNTIME_DB_TYPE",
                "NEO4J_URI",
                "NEO4J_USERNAME",
                "NEO4J_PASSWORD",
                "NEO4J_DATABASE",
            }
        }
        clean_env.update(env)
        with patch.dict(os.environ, clean_env, clear=True):
            output = StringIO()
            with patch("codegraphcontext.cli.main.console", Console(file=output, force_terminal=False)):
                _load_credentials()

            printed = output.getvalue()
            assert "Using database: Neo4j (database: mydb)" in printed

    @patch("codegraphcontext.cli.main.find_dotenv", return_value=None)
    @patch("codegraphcontext.cli.main.config_manager")
    def test_load_credentials_no_database_name(self, mock_config_mgr, _mock_find_dotenv, monkeypatch, tmp_path):
        """Test _load_credentials prints Neo4j without database when NEO4J_DATABASE is not set."""
        mock_config_mgr.ensure_config_dir.return_value = None

        env = {
            "NEO4J_URI": "bolt://localhost:7687",
            "NEO4J_USERNAME": "neo4j",
            "NEO4J_PASSWORD": "password",
            "DEFAULT_DATABASE": "neo4j",
        }
        monkeypatch.chdir(tmp_path)
        clean_env = {
            k: v for k, v in os.environ.items()
            if k not in {
                "DEFAULT_DATABASE",
                "DATABASE_TYPE",
                "CGC_RUNTIME_DB_TYPE",
                "NEO4J_URI",
                "NEO4J_USERNAME",
                "NEO4J_PASSWORD",
                "NEO4J_DATABASE",
            }
        }
        clean_env.update(env)
        with patch.dict(os.environ, clean_env, clear=True):
            output = StringIO()
            with patch("codegraphcontext.cli.main.console", Console(file=output, force_terminal=False)):
                _load_credentials()

            printed = output.getvalue()
            assert "Using database: Neo4j" in printed
            assert "(database:" not in printed


def test_load_credentials_displays_kuzudb_backend(monkeypatch, tmp_path):
    monkeypatch.setattr(cli_main, "find_dotenv", lambda **_kwargs: None)
    monkeypatch.setattr(cli_main.config_manager, "ensure_config_dir", lambda *_args, **_kwargs: None)

    monkeypatch.chdir(tmp_path)
    clean_env = {
        k: v for k, v in os.environ.items()
        if k not in {
            "DEFAULT_DATABASE",
            "DATABASE_TYPE",
            "CGC_RUNTIME_DB_TYPE",
            "NEO4J_URI",
            "NEO4J_USERNAME",
            "NEO4J_PASSWORD",
            "NEO4J_DATABASE",
        }
    }
    clean_env["DEFAULT_DATABASE"] = "kuzudb"
    with patch.dict(os.environ, clean_env, clear=True):
        output = StringIO()
        with patch("codegraphcontext.cli.main.console", Console(file=output, force_terminal=False)):
            _load_credentials()

        assert "Using database: KùzuDB" in output.getvalue()

