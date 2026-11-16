from types import SimpleNamespace

import pytest

from codegraphcontext.tools.languages.python import PythonTreeSitterParser
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager


@pytest.fixture(scope="module")
def parser():
    manager = get_tree_sitter_manager()
    return PythonTreeSitterParser(SimpleNamespace(
        language_name="python", language=manager.get_language_safe("python"),
        parser=manager.create_parser("python"),
    ))


@pytest.mark.parametrize("body,expected", [
    ("return 1", 1),
    ("if x:\n    return 1\nelif y:\n    return 2\nelse:\n    return 3", 3),
    ("return 1 if x else 2", 2),
    ("return 1 if x else 2 if y else 3", 3),
    ("def inner():\n    if x:\n        return 1\nreturn inner", 1),
    ("g = lambda: 1 if x else 2\nreturn g", 1),
    ("class Inner:\n    def method(self):\n        if x:\n            return 1\nreturn Inner", 1),
    ("if x:\n    def inner():\n        if y:\n            return 1\nreturn 2", 2),
    ("for x in xs:\n    if x:\n        return x\nreturn None", 3),
])
def test_complexity_has_independent_per_function_oracle(parser, tmp_path, body, expected):
    path = tmp_path / "fixture.py"
    path.write_text("def outer():\n" + "\n".join("    " + line for line in body.splitlines()) + "\n")
    result = parser.parse(path)
    outer = next(f for f in result["functions"] if f["name"] == "outer")
    assert outer["cyclomatic_complexity"] == expected
    for function in result["functions"]:
        if function["name"] in {"inner", "method"}:
            assert function["cyclomatic_complexity"] == 2
