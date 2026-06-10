"""Tests for MCP delete_repository validation (BUG-006)."""

from unittest.mock import MagicMock

from codegraphcontext.tools.handlers import management_handlers


def test_delete_repository_requires_path(monkeypatch):
    monkeypatch.setattr(
        "codegraphcontext.cli.config_manager.is_db_deletion_allowed",
        lambda: True,
    )
    graph_builder = MagicMock()

    result = management_handlers.delete_repository(graph_builder)

    assert "error" in result
    assert "required" in result["error"].lower()
    graph_builder.delete_repository_from_graph.assert_not_called()


def test_delete_repository_accepts_path_alias(monkeypatch):
    monkeypatch.setattr(
        "codegraphcontext.cli.config_manager.is_db_deletion_allowed",
        lambda: True,
    )
    graph_builder = MagicMock()
    graph_builder.delete_repository_from_graph.return_value = False

    result = management_handlers.delete_repository(
        graph_builder, path="/tmp/sample_project"
    )

    assert result["success"] is False
    graph_builder.delete_repository_from_graph.assert_called_once_with("/tmp/sample_project")
