# tests/unit/utils/test_visualize_graph.py
"""Unit tests for src/codegraphcontext/utils/visualize_graph.py"""

import json
import os
import pytest
from unittest.mock import patch, MagicMock

from codegraphcontext.utils.visualize_graph import (
    node_color,
    edge_color,
    build_graph_data,
    render_html,
    open_in_browser,
    save_graph_html,
)


SAMPLE_NODES = [
    {"id": "1", "label": "Function", "name": "foo", "file_path": "/src/a.py", "line_number": 10},
    {"id": "2", "label": "Class",    "name": "Bar", "file_path": "/src/b.py", "line_number": 5},
]

SAMPLE_EDGES = [
    {"source": "1", "target": "2", "type": "CALLS"},
]


class TestNodeColor:
    def test_known_labels_return_hex(self):
        assert node_color("Function").startswith("#")
        assert node_color("Class").startswith("#")
        assert node_color("File").startswith("#")

    def test_unknown_label_returns_default(self):
        color = node_color("SomeWeirdLabel")
        assert color == node_color("default") or color.startswith("#")


class TestEdgeColor:
    def test_known_types_return_hex(self):
        assert edge_color("CALLS").startswith("#")
        assert edge_color("INHERITS").startswith("#")

    def test_unknown_type_returns_default(self):
        color = edge_color("UNKNOWN_TYPE")
        assert color.startswith("#")


class TestBuildGraphData:
    def test_returns_dict_with_nodes_and_edges(self):
        result = build_graph_data(SAMPLE_NODES, SAMPLE_EDGES)
        assert "nodes" in result
        assert "edges" in result

    def test_node_count_matches(self):
        result = build_graph_data(SAMPLE_NODES, SAMPLE_EDGES)
        assert len(result["nodes"]) == len(SAMPLE_NODES)

    def test_edge_count_matches(self):
        result = build_graph_data(SAMPLE_NODES, SAMPLE_EDGES)
        assert len(result["edges"]) == len(SAMPLE_EDGES)

    def test_nodes_have_required_fields(self):
        result = build_graph_data(SAMPLE_NODES, SAMPLE_EDGES)
        for node in result["nodes"]:
            assert "id" in node
            assert "label" in node
            assert "color" in node
            assert node["color"].startswith("#")

    def test_edges_have_required_fields(self):
        result = build_graph_data(SAMPLE_NODES, SAMPLE_EDGES)
        for edge in result["edges"]:
            assert "source" in edge
            assert "target" in edge
            assert "type" in edge

    def test_empty_inputs_return_empty_lists(self):
        result = build_graph_data([], [])
        assert result["nodes"] == []
        assert result["edges"] == []

    def test_graph_data_is_json_serialisable(self):
        result = build_graph_data(SAMPLE_NODES, SAMPLE_EDGES)
        dumped = json.dumps(result)
        assert isinstance(dumped, str)


class TestRenderHtml:
    def test_returns_string(self):
        graph_data = build_graph_data(SAMPLE_NODES, SAMPLE_EDGES)
        html = render_html(graph_data)
        assert isinstance(html, str)

    def test_contains_doctype(self):
        graph_data = build_graph_data(SAMPLE_NODES, SAMPLE_EDGES)
        html = render_html(graph_data)
        assert "<!DOCTYPE html>" in html

    def test_contains_title(self):
        graph_data = build_graph_data(SAMPLE_NODES, SAMPLE_EDGES)
        html = render_html(graph_data, title="My Graph")
        assert "My Graph" in html

    def test_contains_graph_json(self):
        graph_data = build_graph_data(SAMPLE_NODES, SAMPLE_EDGES)
        html = render_html(graph_data)
        assert "GRAPH" in html

    def test_default_title(self):
        graph_data = build_graph_data(SAMPLE_NODES, SAMPLE_EDGES)
        html = render_html(graph_data)
        assert "CGC Code Graph" in html


class TestRenderHtmlEscaping:
    """A name or title carrying markup must not escape into the document."""

    BREAKOUT = "x</script><script>alert(1)</script>"

    def test_node_name_cannot_close_the_script_block(self):
        nodes = [{"id": "1", "label": "Function", "name": self.BREAKOUT, "file_path": "/a.py"}]
        html = render_html(build_graph_data(nodes, []))
        assert self.BREAKOUT not in html
        # the only closing tag left is the one that ends the real script block
        assert html.count("</script>") == 1

    def test_payload_still_parses_back_to_the_original_name(self):
        nodes = [{"id": "1", "label": "Function", "name": self.BREAKOUT, "file_path": "/a.py"}]
        html = render_html(build_graph_data(nodes, []))
        start = html.index("const GRAPH = ") + len("const GRAPH = ")
        data, _ = json.JSONDecoder().raw_decode(html[start:])
        assert data["nodes"][0]["name"] == self.BREAKOUT

    def test_file_path_cannot_close_the_script_block(self):
        nodes = [{"id": "1", "label": "File", "name": "a", "file_path": "/x</script>/a.py"}]
        html = render_html(build_graph_data(nodes, []))
        assert "/x</script>/a.py" not in html
        assert html.count("</script>") == 1

    def test_title_is_html_escaped(self):
        graph_data = build_graph_data(SAMPLE_NODES, SAMPLE_EDGES)
        html = render_html(graph_data, title="t</title><script>alert(2)</script>")
        assert "<script>alert(2)</script>" not in html
        assert "&lt;/title&gt;" in html

    def test_ordinary_title_is_untouched(self):
        graph_data = build_graph_data(SAMPLE_NODES, SAMPLE_EDGES)
        html = render_html(graph_data, title="My Graph")
        assert "My Graph" in html


class TestOpenInBrowser:
    def test_creates_html_file(self, tmp_path):
        graph_data = build_graph_data(SAMPLE_NODES, SAMPLE_EDGES)
        output = str(tmp_path / "test_graph.html")
        with patch("webbrowser.open"):
            result = open_in_browser(graph_data, output_path=output)
        assert os.path.exists(result)

    def test_returns_path_string(self, tmp_path):
        graph_data = build_graph_data(SAMPLE_NODES, SAMPLE_EDGES)
        output = str(tmp_path / "out.html")
        with patch("webbrowser.open"):
            result = open_in_browser(graph_data, output_path=output)
        assert isinstance(result, str)

    def test_calls_webbrowser_open(self, tmp_path):
        graph_data = build_graph_data(SAMPLE_NODES, SAMPLE_EDGES)
        output = str(tmp_path / "out.html")
        with patch("webbrowser.open") as mock_browser:
            open_in_browser(graph_data, output_path=output)
        mock_browser.assert_called_once()


class TestSaveGraphHtml:
    def test_saves_file_and_returns_path(self, tmp_path):
        output = str(tmp_path / "graph.html")
        with patch("webbrowser.open"):
            result = save_graph_html(SAMPLE_NODES, SAMPLE_EDGES, output_path=output)
        assert os.path.exists(result)
        assert result.endswith(".html")