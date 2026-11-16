from types import SimpleNamespace

import pytest

from codegraphcontext.tools.languages.python import PythonTreeSitterParser
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager


@pytest.fixture
def parser():
    manager = get_tree_sitter_manager()
    return PythonTreeSitterParser(SimpleNamespace(language_name="python", language=manager.get_language_safe("python"), parser=manager.create_parser("python")))


@pytest.mark.parametrize("definition", ["def endpoint(): pass", "class Endpoint: pass"])
def test_bare_decorator_has_an_implicit_call_from_module(parser, tmp_path, definition):
    path = tmp_path / "decorators.py"
    path.write_text("def route(value): return value\n@route\n" + definition + "\n")
    parsed = parser.parse(path)
    calls = [c for c in parsed["function_calls"] if c["name"] == "route"]
    assert len(calls) == 1
    assert calls[0]["context"] == ("<module>", "module", 1)
    assert calls[0]["line_number"] == 2
    assert calls[0]["args"] == ["endpoint" if definition.startswith("def") else "Endpoint"]


def test_decorator_factory_is_not_duplicated(parser, tmp_path):
    path = tmp_path / "decorators.py"
    path.write_text('def factory(x): return lambda f: f\n@factory("x")\ndef endpoint(): pass\n')
    parsed = parser.parse(path)
    assert len([c for c in parsed["function_calls"] if c["name"] == "factory"]) == 1


def test_nested_definition_invokes_decorator_from_enclosing_function(parser, tmp_path):
    path = tmp_path / "decorators.py"
    path.write_text("def outer():\n    @route\n    def inner(): pass\n    return inner\n")
    parsed = parser.parse(path)
    call = next(c for c in parsed["function_calls"] if c["name"] == "route")
    assert call["context"] == ("outer", "function_definition", 1)
