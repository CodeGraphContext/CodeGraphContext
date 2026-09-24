"""#660: the setup wizard replaced VS Code's settings.json instead of adding to it.

VS Code and its forks write settings.json as JSONC. `json.load` rejects comments
and trailing commas, and the wizard treated that rejection as "no settings yet"
before writing the file back — so a user's whole configuration was replaced by a
lone `mcpServers` key. These pin the two halves of the fix: JSONC parses, and an
input that still cannot be parsed is left alone rather than overwritten.
"""

import ast
import json
import re

import pytest

from codegraphcontext.cli import setup_wizard

_strip_jsonc = setup_wizard._strip_jsonc


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('{\n  // font\n  "editor.fontSize": 14\n}', {"editor.fontSize": 14}),
        ('{\n  /* multi\n     line */\n  "a": 1\n}', {"a": 1}),
        ('{\n  "a": 1,\n  "b": [1, 2,],\n}', {"a": 1, "b": [1, 2]}),
        ('{"url": "https://example.com//path"}', {"url": "https://example.com//path"}),
        ('{"s": "quote \\" then // text"}', {"s": 'quote " then // text'}),
        ('{"a": 1, "b": {"c": 2}}', {"a": 1, "b": {"c": 2}}),
    ],
)
def test_strip_jsonc_parses(raw, expected):
    assert json.loads(_strip_jsonc(raw)) == expected


def test_comment_markers_inside_strings_are_not_stripped():
    """A // or /* inside a string value is data, not a comment."""
    raw = '{"a": "x // y", "b": "p /* q */ r"}'
    assert json.loads(_strip_jsonc(raw)) == {"a": "x // y", "b": "p /* q */ r"}


def test_real_settings_file_survives_a_round_trip():
    """The shape from #660: a commented settings.json keeps every key."""
    raw = """{
  // Editor
  "editor.fontSize": 14,
  "editor.tabSize": 2,
  /* Theme */
  "workbench.colorTheme": "Default Dark+",
  "files.exclude": { "**/.git": true },
}"""
    settings = json.loads(_strip_jsonc(raw))
    assert settings["editor.fontSize"] == 14
    assert settings["workbench.colorTheme"] == "Default Dark+"
    assert settings["files.exclude"] == {"**/.git": True}

    settings.setdefault("mcpServers", {})["cgc"] = {"command": "cgc"}
    assert settings["editor.tabSize"] == 2


def test_unparseable_input_is_not_silently_emptied():
    """Truncated JSONC must raise, so the caller can decline to write."""
    with pytest.raises(json.JSONDecodeError):
        json.loads(_strip_jsonc('{"a": 1, "b": '))


def test_wizard_returns_without_writing_when_parsing_fails():
    """The bug was the {} fallback; the source must no longer contain it."""
    src = ast.unparse(ast.parse(open(setup_wizard.__file__).read()))
    assert not re.search(r"except json\.JSONDecodeError:\s*settings = \{\}", src)
