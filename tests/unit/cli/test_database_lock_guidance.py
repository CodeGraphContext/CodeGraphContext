from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import typer
from rich.console import Console

from codegraphcontext.cli import cli_helpers


def test_initialize_services_explains_embedded_database_lock():
    db_manager = MagicMock()
    db_manager.get_driver.side_effect = RuntimeError(
        "IO exception: Could not set lock on file : /tmp/ladybugdb "
        "(Error: Resource temporarily unavailable)"
    )
    ctx = SimpleNamespace(mode="global", database="ladybugdb", db_path="/tmp/ladybugdb")
    output = StringIO()

    with (
        patch.object(cli_helpers, "ensure_first_run_bootstrap"),
        patch.object(cli_helpers, "resolve_context", return_value=ctx),
        patch.object(cli_helpers, "get_database_manager", return_value=db_manager),
        patch.object(
            cli_helpers,
            "console",
            Console(file=output, force_terminal=False, width=120),
        ),
        pytest.raises(typer.Exit) as exc_info,
    ):
        cli_helpers._initialize_services()

    message = " ".join(output.getvalue().split())
    assert exc_info.value.exit_code == 1
    assert "Another CGC process" in message
    assert "Gateway or watcher" in message
    assert "use its MCP/HTTP interface or stop it" in message
    assert "Please ensure your database is configured correctly" not in message
