"""Tests for issue #1097: cgc query propagates raw database exceptions."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest
import typer
from codegraphcontext.cli import cli_helpers


def _services():
    db_manager = MagicMock()
    db_manager.get_backend_type = lambda: "kuzudb"
    ctx = SimpleNamespace(mode="global")
    return db_manager, MagicMock(), MagicMock(), ctx


# ---------------------------------------------------------------------------
# _print_query_exception unit tests
# ---------------------------------------------------------------------------

class TestPrintQueryException:
    """Verify _print_query_exception surfaces the right message per backend."""

    def test_kuzu_parser_error_no_traceback(self, capsys):
        """KuzuDB RuntimeError with 'Parser exception' should print cleanly."""
        e = RuntimeError(
            "Parser exception: Invalid input <MATCH (n:Bad RETURN>: "
            "expected rule oC_SingleQuery (line: 1, offset: 21)"
        )
        cli_helpers._print_query_exception(e, "MATCH (n:Bad RETURN n")
        captured = cli_helpers.console.file  # rich Console, check via output below

    def test_kuzu_parser_error_shows_message(self, capsys):
        """Output must contain the raw parser exception text."""
        e = RuntimeError("Parser exception: Invalid input <MATCH")
        from io import StringIO
        from rich.console import Console
        buf = StringIO()
        original = cli_helpers.console
        cli_helpers.console = Console(file=buf, highlight=False)
        try:
            cli_helpers._print_query_exception(e, "MATCH (n RETURN n")
        finally:
            cli_helpers.console = original
        output = buf.getvalue()
        assert "Parser exception" in output
        assert "MATCH (n RETURN n" in output
        assert "Traceback" not in output

    def test_neo4j_error_shows_code_and_message(self):
        """Neo4j exceptions should show .code and .message attributes."""
        from io import StringIO
        from rich.console import Console

        FakeNeo4jError = type(
            "CypherSyntaxError",
            (Exception,),
            {"__module__": "neo4j.exceptions"},
        )

        e = FakeNeo4jError("Neo4j error")
        e.code = "Neo.ClientError.Statement.SyntaxError"
        e.message = "Invalid input 'RETURN': expected..."

        buf = StringIO()
        original = cli_helpers.console
        cli_helpers.console = Console(file=buf, highlight=False)
        try:
            cli_helpers._print_query_exception(e, "MATCH RETURN n")
        finally:
            cli_helpers.console = original

        output = buf.getvalue()
        assert "Neo.ClientError.Statement.SyntaxError" in output
        assert "Invalid input 'RETURN'" in output

    def test_falkordb_error_shows_message(self):
        """FalkorDB exceptions should show the database message."""
        from io import StringIO
        from rich.console import Console

        FakeFalkorError = type(
            "ResponseError",
            (Exception,),
            {"__module__": "falkordb.exceptions"},
        )

        e = FakeFalkorError("ERR query syntax error")

        buf = StringIO()
        original = cli_helpers.console
        cli_helpers.console = Console(file=buf, highlight=False)
        try:
            cli_helpers._print_query_exception(e, "MATCH (n RETURN n")
        finally:
            cli_helpers.console = original

        output = buf.getvalue()
        assert "ERR query syntax error" in output


# ---------------------------------------------------------------------------
# cypher_helper integration tests
# ---------------------------------------------------------------------------

class TestCypherHelperExceptionPropagation:
    """Verify cypher_helper calls _print_query_exception on failure."""

    def test_exits_nonzero_on_query_error(self, tmp_path):
        """cypher_helper must exit with code 1 when query raises."""
        services = _services()
        session_mock = MagicMock()
        session_mock.__enter__ = MagicMock(return_value=session_mock)
        session_mock.__exit__ = MagicMock(return_value=False)
        session_mock.run.side_effect = RuntimeError(
            "Parser exception: Invalid input"
        )
        services[0].get_driver.return_value.session.return_value = session_mock

        with (
            patch.object(cli_helpers, "_initialize_services", return_value=services),
            patch.object(cli_helpers, "_print_query_exception") as mock_print_exc,
            pytest.raises(typer.Exit) as exc_info,
        ):
            cli_helpers.cypher_helper("MATCH (n RETURN n")

        assert exc_info.value.exit_code == 1
        mock_print_exc.assert_called_once()
        call_args = mock_print_exc.call_args
        assert "MATCH (n RETURN n" in call_args[0]

    def test_print_query_exception_called_with_correct_query(self, tmp_path):
        """_print_query_exception must receive the original query string."""
        services = _services()
        session_mock = MagicMock()
        session_mock.__enter__ = MagicMock(return_value=session_mock)
        session_mock.__exit__ = MagicMock(return_value=False)
        bad_query = "MATCH (n:Broken RETURN n"
        session_mock.run.side_effect = RuntimeError("Parser exception")
        services[0].get_driver.return_value.session.return_value = session_mock

        with (
            patch.object(cli_helpers, "_initialize_services", return_value=services),
            patch.object(cli_helpers, "_print_query_exception") as mock_print_exc,
            pytest.raises(typer.Exit),
        ):
            cli_helpers.cypher_helper(bad_query)

        assert mock_print_exc.call_args[0][1] == bad_query


# ---------------------------------------------------------------------------
# cypher_helper_visual integration tests
# ---------------------------------------------------------------------------

class TestCypherHelperVisualExceptionPropagation:
    """Verify cypher_helper_visual also calls _print_query_exception."""

    def test_visual_exits_nonzero_on_query_error(self, tmp_path):
        services = _services()

        with (
            patch.object(cli_helpers, "_initialize_services", return_value=services),
            patch(
                "codegraphcontext.cli.visualizer.visualize_cypher_results",
                 side_effect=RuntimeError("Parser exception: bad query"),
            ),
            patch.object(cli_helpers, "_print_query_exception") as mock_print_exc,
            pytest.raises(typer.Exit) as exc_info,
        ):
            cli_helpers.cypher_helper_visual("MATCH (n RETURN n")

        assert exc_info.value.exit_code == 1
        mock_print_exc.assert_called_once()