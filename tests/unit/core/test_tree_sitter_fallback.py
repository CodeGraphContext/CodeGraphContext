import asyncio
from unittest.mock import MagicMock, patch

from codegraphcontext.core.jobs import JobManager
from codegraphcontext.tools import graph_builder as graph_builder_module
from codegraphcontext.tools.graph_builder import GraphBuilder


def make_graph_builder(loop):
    db_manager = MagicMock()
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    db_manager.get_driver.return_value = driver
    builder = GraphBuilder(db_manager, JobManager(), loop)
    session.reset_mock()
    return builder, session


def test_get_parser_caches_unavailable_parser():
    loop = asyncio.new_event_loop()
    try:
        builder, _session = make_graph_builder(loop)

        with patch.object(graph_builder_module, "TreeSitterParser", side_effect=ValueError("missing grammar")) as parser_cls:
            assert builder.get_parser(".go") is None
            assert builder.get_parser(".go") is None

        assert ".go" in builder._unavailable_parsers
        assert parser_cls.call_count == 1
    finally:
        loop.close()


def test_pre_scan_for_imports_skips_language_when_parser_is_unavailable(tmp_path):
    loop = asyncio.new_event_loop()
    try:
        builder, _session = make_graph_builder(loop)
        source_file = tmp_path / "sample.py"
        source_file.write_text("import os\n")

        with patch.object(builder, "get_parser", return_value=None), patch(
            "codegraphcontext.tools.languages.python.pre_scan_python"
        ) as pre_scan_python:
            imports_map = builder._pre_scan_for_imports([source_file])

        assert imports_map == {}
        pre_scan_python.assert_not_called()
    finally:
        loop.close()


def test_parse_file_returns_file_only_payload_when_parser_is_unavailable(tmp_path):
    loop = asyncio.new_event_loop()
    try:
        builder, _session = make_graph_builder(loop)
        source_file = tmp_path / "pkg" / "sample.py"
        source_file.parent.mkdir(parents=True, exist_ok=True)
        source_file.write_text("def hello():\n    return 1\n")

        with patch.object(builder, "get_parser", return_value=None):
            file_data = builder.parse_file(tmp_path, source_file)

        assert file_data["path"] == str(source_file.resolve())
        assert file_data["repo_path"] == str(tmp_path.resolve())
        assert file_data["lang"] == "python"
        assert file_data["functions"] == []
        assert file_data["classes"] == []
        assert file_data["imports"] == []
        assert file_data["function_calls"] == []
        assert file_data["is_dependency"] is False
        assert "error" not in file_data
    finally:
        loop.close()
