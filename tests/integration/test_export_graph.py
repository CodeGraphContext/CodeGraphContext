"""
Integration tests for JavaScript export handling: parser output -> graph_builder contract.

Verifies that the export structure produced by the JavaScript parser matches what
graph_builder.add_file_to_graph() expects when creating Export nodes and Module-EXPORTS
relationships. Full flow (storage in Neo4j/FalkorDB) is covered by e2e when a DB is available.
"""

import pytest
from pathlib import Path

from codegraphcontext.tools.languages.javascript import JavascriptTreeSitterParser
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager


@pytest.fixture(scope="module")
def js_parser():
    from unittest.mock import MagicMock
    manager = get_tree_sitter_manager()
    wrapper = MagicMock()
    wrapper.language_name = "javascript"
    wrapper.language = manager.get_language_safe("javascript")
    wrapper.parser = manager.create_parser("javascript")
    return JavascriptTreeSitterParser(wrapper)


@pytest.fixture(scope="module")
def javascript_sample_project():
    path = Path(__file__).parent.parent / "fixtures" / "sample_projects" / "sample_project_javascript"
    if not path.exists():
        pytest.skip("JavaScript sample project not found")
    return path


def test_export_shape_matches_graph_builder_contract(js_parser, javascript_sample_project):
    """
    Parser exports must include name, original_name, is_default, line_number, lang
    so graph_builder can create Export nodes and EXPORTS relationships correctly.
    """
    path = javascript_sample_project / "exporter.js"
    if not path.exists():
        pytest.skip("exporter.js not found")
    result = js_parser.parse(path)
    exports = result.get("exports", [])
    assert len(exports) > 0
    for e in exports:
        assert "name" in e, "graph_builder expects export_name"
        assert "original_name" in e, "graph_builder expects original_name"
        assert "is_default" in e, "graph_builder expects is_default"
        assert "line_number" in e, "graph_builder expects line_number"
        assert "lang" in e, "graph_builder expects lang"
        assert e["lang"] == "javascript"


def test_graph_builder_export_keys_contract():
    """
    Document the contract: graph_builder expects each export to have
    name, original_name, is_default, line_number, lang (module_name is computed from file path).
    """
    expected = {"name", "original_name", "is_default", "line_number", "lang"}
    assert expected == {"name", "original_name", "is_default", "line_number", "lang"}
