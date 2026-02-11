"""Unit tests for JavaScript parser: exports and parse() structure."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager
from codegraphcontext.tools.languages.javascript import JavascriptTreeSitterParser


@pytest.fixture(scope="class")
def parser():
    manager = get_tree_sitter_manager()
    wrapper = MagicMock()
    wrapper.language_name = "javascript"
    wrapper.language = manager.get_language_safe("javascript")
    wrapper.parser = manager.create_parser("javascript")
    return JavascriptTreeSitterParser(wrapper)


def test_parse_returns_exports_key(parser, javascript_sample_project):
    """Parse exporter.js and assert 'exports' key is present with entries."""
    path = javascript_sample_project / "exporter.js"
    if not path.exists():
        pytest.skip("exporter.js fixture not found")
    result = parser.parse(path)
    assert "exports" in result
    assert isinstance(result["exports"], list)


def test_find_exports_named_and_default(parser, javascript_sample_project):
    """Exporter.js has named exports and a default export; all should be found (PR #530 shape)."""
    path = javascript_sample_project / "exporter.js"
    if not path.exists():
        pytest.skip("exporter.js fixture not found")
    result = parser.parse(path)
    exports = result["exports"]
    names = {e["name"] for e in exports}
    # Named: exportedFunction, ExportedClass, exportedVariable
    assert "exportedFunction" in names
    assert "ExportedClass" in names
    assert "exportedVariable" in names
    # Default export: stored as name 'default' with optional original_name
    assert "default" in names


def test_find_exports_original_name_and_is_default(parser, javascript_sample_project):
    """Exports should have original_name and is_default (PR #530)."""
    path = javascript_sample_project / "exporter.js"
    if not path.exists():
        pytest.skip("exporter.js fixture not found")
    result = parser.parse(path)
    for e in result["exports"]:
        assert "line_number" in e
        assert e.get("lang") == "javascript"
        assert "original_name" in e
        assert "is_default" in e


def test_parse_importer_imports(parser, javascript_sample_project):
    """Importer.js imports from ./exporter.js; imports list should reflect that."""
    path = javascript_sample_project / "importer.js"
    if not path.exists():
        pytest.skip("importer.js fixture not found")
    result = parser.parse(path)
    assert "imports" in result
    imports = result["imports"]
    sources = [i["source"] for i in imports]
    assert "./exporter.js" in sources
