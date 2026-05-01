from pathlib import Path

import pytest

from codegraphcontext.tools.languages.dart import DartTreeSitterParser
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager


pytest.importorskip("tree_sitter_language_pack")


@pytest.fixture
def dart_parser():
    manager = get_tree_sitter_manager()
    if not manager.is_language_available("dart"):
        pytest.skip("Dart tree-sitter grammar is not available in this environment")

    class Wrapper:
        language_name = "dart"

    wrapper = Wrapper()
    wrapper.language = manager.get_language_safe("dart")
    wrapper.parser = manager.create_parser("dart")
    return DartTreeSitterParser(wrapper)


def test_dart_extracts_chained_and_top_level_calls(dart_parser, tmp_path: Path):
    source = """
class Foo {
  void doIt() {
    print('hi');
    other.callMe(1);
  }
}

void topLevel() {
  print('top');
  list.where((x) => x > 0).toList();
}
"""
    path = tmp_path / "test_dart.dart"
    path.write_text(source, encoding="utf-8")

    result = dart_parser.parse(path)

    calls = result["function_calls"]
    assert [call["name"] for call in calls] == ["print", "callMe", "print", "where", "toList"]
    assert [call["context"][0] for call in calls] == [
        "doIt",
        "doIt",
        "topLevel",
        "topLevel",
        "topLevel",
    ]
    assert all(call["context"][1] == "function_signature" for call in calls)
