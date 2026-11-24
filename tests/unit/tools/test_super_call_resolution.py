"""Issues #1938 and #1939: ``super`` calls whose base chain yields no method.

A super call reaches a method of a base class. When the resolver cannot find
that method (the base lives outside the repository, such as an npm package or
the standard library), it used to pick by name in the caller's own file, which
is the calling method itself: a self-loop CALLS edge at confidence 1.0.

``super(Cls, self).m()`` in Python is the same call as ``super().m()`` inside
``Cls`` and walks the same base chain.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.indexing.resolution.calls import build_function_call_groups
from codegraphcontext.tools.languages.javascript import (
    JavascriptTreeSitterParser,
    pre_scan_javascript,
)
from codegraphcontext.tools.languages.python import PythonTreeSitterParser
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager


WIDGETS_JS = """\
import { BasePanel } from "ui-kit";

export class StockPanel extends BasePanel {
    render() {
        return super.render();
    }
}

class LocalBase {
    refresh() { return 1; }
}

export class PricePanel extends LocalBase {
    refresh() {
        return super.refresh();
    }
}
"""

MODELS_PY = """\
from collections import OrderedDict


class Ledger(OrderedDict):
    def update(self, *args, **kwargs):
        return super().update(*args, **kwargs)


class Account:
    def close(self):
        return "closed"


class SavingsAccount(Account):
    def audit(self):
        return super().close()

    def close(self):
        return super(SavingsAccount, self).close()


class Wallet:
    def pay(self, amount):
        return super(Wallet, self).pay(amount)
"""


def _wrapper(language: str):
    manager = get_tree_sitter_manager()
    wrapper = MagicMock()
    wrapper.language_name = language
    wrapper.language = manager.get_language_safe(language)
    wrapper.parser = manager.create_parser(language)
    return wrapper


def _file_data(parsed, path: Path, lang: str):
    return {
        "path": path.resolve().as_posix(),
        "lang": lang,
        "functions": parsed["functions"],
        "classes": parsed.get("classes", []),
        "function_calls": parsed["function_calls"],
        "imports": parsed.get("imports", []),
        "variables": parsed.get("variables", []),
    }


def _calls(files, imports_map, diagnostics=None):
    groups = build_function_call_groups(files, imports_map, diagnostics=diagnostics)
    return [edge for group in groups for edge in group]


@pytest.fixture
def js_index(tmp_path):
    wrapper = _wrapper("javascript")
    path = tmp_path / "widgets.js"
    path.write_text(WIDGETS_JS)
    parsed = JavascriptTreeSitterParser(wrapper).parse(path)
    return [_file_data(parsed, path, "javascript")], pre_scan_javascript([path], wrapper)


@pytest.fixture
def py_index(tmp_path):
    path = tmp_path / "models.py"
    path.write_text(MODELS_PY)
    parsed = PythonTreeSitterParser(_wrapper("python")).parse(str(path))
    return [_file_data(parsed, path, "python")], {}


def _edges_by_line(edges, called_name):
    return {
        e.get("line_number"): (e.get("called_context"), e.get("called_line_number"))
        for e in edges
        if e["called_name"] == called_name
    }


def test_js_super_call_to_unresolved_base_writes_no_self_loop(js_index):
    files, imports_map = js_index
    diagnostics = []
    edges = _calls(files, imports_map, diagnostics)

    assert 5 not in _edges_by_line(edges, "render")
    assert _edges_by_line(edges, "refresh") == {15: ("LocalBase", 10)}
    assert any(
        d["reason"] == "super_base_unresolved" and d["line_number"] == 5
        for d in diagnostics
    )


def test_python_super_call_to_unresolved_base_writes_no_self_loop(py_index):
    files, imports_map = py_index
    diagnostics = []
    edges = _calls(files, imports_map, diagnostics)

    assert 6 not in _edges_by_line(edges, "update")
    assert any(
        d["reason"] == "super_base_unresolved" and d["line_number"] == 6
        for d in diagnostics
    )


def test_python_super_with_explicit_class_walks_its_bases(py_index):
    files, imports_map = py_index
    edges = _calls(files, imports_map)

    close_targets = _edges_by_line(edges, "close")
    # super().close() and super(SavingsAccount, self).close() reach Account.close
    assert close_targets[16] == ("Account", 10)
    assert close_targets[19] == ("Account", 10)
    # Wallet has no base that defines pay: no pay -> pay self-loop
    assert 24 not in _edges_by_line(edges, "pay")
