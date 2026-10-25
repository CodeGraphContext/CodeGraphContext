"""Tests for the Scala parser's parameter-name extraction.

Scala parameter types can contain commas (``Map[String, Int]``, tuple and
function types), so splitting a parameter list on every comma produced bogus
parameter names such as ``Int]``. These tests pin the nesting-aware behaviour.
"""
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.languages.scala import ScalaTreeSitterParser
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager


@pytest.fixture(scope="module")
def parser():
    manager = get_tree_sitter_manager()
    wrapper = MagicMock()
    wrapper.language_name = "scala"
    wrapper.language = manager.get_language_safe("scala")
    wrapper.parser = manager.create_parser("scala")
    return ScalaTreeSitterParser(wrapper)


@pytest.fixture(scope="module")
def splitter():
    """A parser instance for the pure-text helpers, which need no tree-sitter."""
    return ScalaTreeSitterParser(MagicMock())


@pytest.mark.parametrize(
    "params_text, expected",
    [
        # simple cases
        ("()", []),
        ("", []),
        ("(a: Int)", ["a"]),
        ("(a: Int, b: String)", ["a", "b"]),
        # commas inside type arguments
        ("(m: Map[String, Int], n: Int)", ["m", "n"]),
        ("(e: Either[String, Int], f: Option[List[Int]])", ["e", "f"]),
        ("(m: Map[String, Map[Int, List[String]]], z: Int)", ["m", "z"]),
        # commas inside tuple and function types
        ("(f: (Int, String) => Boolean, x: Int)", ["f", "x"]),
        ("(t: (Int, String), u: Long)", ["t", "u"]),
        # a trailing function type must keep its closing paren
        ("(x: Int, f: Int => (Int, Int))", ["x", "f"]),
        # modifiers and annotations are dropped, only the name remains
        ("(implicit ev: Ordering[A], b: Int)", ["ev", "b"]),
        ("(@deprecated x: Int, y: Int)", ["x", "y"]),
        # default values, including commas inside literals
        ("(a: Int = 5, b: String = \"x,y\")", ["a", "b"]),
        ("(sep: Char = ',', n: Int = 1)", ["sep", "n"]),
        ("(xs: List[Int] = List(1, 2, 3), n: Int)", ["xs", "n"]),
        # by-name parameter: the '>' of '=>' must not unbalance anything
        ("(cond: => Boolean, msg: Map[String, Int])", ["cond", "msg"]),
    ],
)
def test_extract_parameter_names(splitter, params_text, expected):
    assert splitter._extract_parameter_names(params_text) == expected


def test_split_parameters_keeps_nested_commas_together(splitter):
    assert splitter._split_parameters("(m: Map[String, Int], n: Int)") == [
        "m: Map[String, Int]",
        "n: Int",
    ]


def test_extracted_names_are_never_fragments_of_a_type(splitter):
    """Regression: the old comma split yielded 'Int]' and 'String) => Boolean'."""
    names = splitter._extract_parameter_names(
        "(m: Map[String, Int], f: (Int, String) => Boolean)"
    )
    assert names == ["m", "f"]
    assert not any(c in name for name in names for c in "[]()=> ")


def _parse(parser, source: str) -> dict:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".scala", delete=False, encoding="utf-8"
    ) as f:
        f.write(source)
        tmp = Path(f.name)
    try:
        result = parser.parse(tmp)
    finally:
        tmp.unlink(missing_ok=True)
    assert isinstance(result, dict)
    return result


def test_parse_records_clean_parameters_for_generic_types(parser):
    src = """\
object Service {
  def simple(a: Int, b: String): Int = a

  def generic(m: Map[String, Int], n: Int): Int = n

  def higherOrder(f: (Int, String) => Boolean, x: Int): Boolean = f(x, "a")
}
"""
    result = _parse(parser, src)
    by_name = {fn["name"]: fn for fn in result["functions"]}

    assert by_name["simple"]["parameters"] == ["a", "b"]
    assert by_name["generic"]["parameters"] == ["m", "n"]
    assert by_name["higherOrder"]["parameters"] == ["f", "x"]
    # 'args' mirrors 'parameters' for consumers that read either key.
    assert by_name["generic"]["args"] == ["m", "n"]
