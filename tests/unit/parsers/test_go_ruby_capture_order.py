"""Go/Ruby parser consumers that matched captures to containers by position.

* Go ``_find_interfaces`` / ``_find_structs`` keyed a type by its enclosing
  ``type_declaration``: a grouped ``type ( A …; B … )`` collapsed its
  interfaces into one and gave every struct the first spec's embedded bases;
  an interface entry also depended on which capture of it arrived first.
* Ruby functions/modules/imports matched @name captures to the first
  container whose byte range holds them: a nested ``def`` renamed its
  enclosing method and vanished.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser


def _parse(lang: str, tmp_path: Path, name: str, source: str) -> dict:
    path = tmp_path / name
    path.write_text(source, encoding="utf-8")
    return TreeSitterParser(lang).parse(path, False)


# ── order independence under a permuted capture order ────────────────────────

@pytest.fixture
def reversed_captures(monkeypatch):
    """Run a language module's queries with the capture order reversed."""
    from codegraphcontext.utils.tree_sitter_manager import execute_query as real

    def patch(module):
        monkeypatch.setattr(module, "execute_query", lambda *a, **k: list(reversed(real(*a, **k))))
    return patch


GO_INTERFACES = '''package shapes

type Shape interface {
    Area() float64
    Perimeter() float64
}

type Named interface {
    Shape
    Name() string
}
'''


def _interfaces(result):
    return sorted((i["name"], tuple(sorted(i["methods"])), tuple(i["bases"])) for i in result["interfaces"])


def test_go_interfaces_do_not_depend_on_capture_order(tmp_path, reversed_captures):
    from codegraphcontext.tools.languages import go

    expected = _interfaces(_parse("go", tmp_path, "shapes.go", GO_INTERFACES))
    assert [name for name, _, _ in expected] == ["Named", "Shape"]
    reversed_captures(go)
    assert _interfaces(_parse("go", tmp_path, "shapes2.go", GO_INTERFACES)) == expected


GO_GROUPED = '''package shapes

type (
    Reader interface {
        Read() int
    }
    Writer interface {
        Write(n int)
    }
)

type Base struct{}
type Other struct{}

type (
    First struct {
        Base
        x int
    }
    Second struct {
        Other
    }
)
'''


def test_go_grouped_type_declarations_are_one_type_each(tmp_path):
    """`type ( A …; B … )` declares two types: keying by the type_declaration collapsed
    the interfaces to one and gave every struct the first spec's embedded bases."""
    result = _parse("go", tmp_path, "grouped.go", GO_GROUPED)
    interfaces = sorted((i["name"], tuple(i["methods"]), i["line_number"]) for i in result["interfaces"])
    assert interfaces == [("Reader", ("Read",), 4), ("Writer", ("Write",), 7)]
    structs = {c["name"]: (tuple(c["bases"]), c["line_number"]) for c in result["structs"]}
    assert structs["First"] == (("Base",), 16)
    assert structs["Second"] == (("Other",), 20)
    assert structs["Base"] == ((), 12)        # a single declaration keeps its `type` line


RUBY_NESTED = '''module Outer
  module Inner
    class Thing
      def outer_method
        def inner_method
          1
        end
        inner_method
      end

      def self.build
        new
      end
    end
  end
end

require "json"
load "tasks.rb"
'''


def _ruby_shape(result):
    return (
        sorted((f["name"], f["line_number"]) for f in result["functions"]),
        sorted((m["name"], m["line_number"]) for m in result.get("modules", [])),
        sorted((i["name"], i["line_number"]) for i in result["imports"]),
    )


def test_ruby_nested_definitions_keep_their_own_names(tmp_path):
    functions, modules, imports = _ruby_shape(_parse("ruby", tmp_path, "thing.rb", RUBY_NESTED))
    assert functions == [("build", 11), ("inner_method", 5), ("outer_method", 4)]
    assert modules == [("Inner", 2), ("Outer", 1)]
    assert [line for _, line in imports] == [18, 19]


def test_ruby_parse_does_not_depend_on_capture_order(tmp_path, reversed_captures):
    from codegraphcontext.tools.languages import ruby

    expected = _ruby_shape(_parse("ruby", tmp_path, "thing.rb", RUBY_NESTED))
    reversed_captures(ruby)
    assert _ruby_shape(_parse("ruby", tmp_path, "thing2.rb", RUBY_NESTED)) == expected
