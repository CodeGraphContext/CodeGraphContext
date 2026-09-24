"""Regression tests for stats counting, doctor honesty and report scoping."""
import inspect
import re

from typer.testing import CliRunner

from codegraphcontext.cli import cli_helpers, main as cli_main
from codegraphcontext.cli.main import app

runner = CliRunner()

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _plain(text: str) -> str:
    """Strip ANSI escapes and collapse whitespace.

    Rich emits colour codes (and soft-wraps) whenever it thinks the terminal
    supports them — which it does in CI but not always locally. Asserting on
    raw `result.output` therefore passes on a dev machine and fails in CI with
    the expected text plainly visible, just interleaved with \x1b[1;36m codes.
    """
    return " ".join(_ANSI_RE.sub("", text).split())



def _stats_source():
    return inspect.getsource(cli_helpers.stats_helper)


def test_stats_counts_are_distinct():
    """`count(x)` over a variable-length CONTAINS* match counts rows, not
    nodes: a method is reachable both as File->Function and
    File->Class->Function, so functions were over-reported by ~55%."""
    source = _stats_source()
    contains_counts = re.findall(r"CONTAINS\*\]->\((\w+):(\w+)\) RETURN count\((DISTINCT )?", source)
    assert contains_counts, "expected the CONTAINS* count queries to be present"
    for var, label, distinct in contains_counts:
        assert distinct, f"count over CONTAINS* for {label} must use DISTINCT"


def test_doctor_probes_the_connection_for_the_default_backend():
    """Section 2 is titled 'Checking Database Connection', but for the default
    falkordb backend it was only an import probe."""
    source = inspect.getsource(cli_main.doctor)
    assert "is_falkordb_usable" in source
    # It must now actually open a connection, like the neo4j / remote branches.
    assert "get_database_manager" in source
    assert "RETURN 1" in source


def test_doctor_does_not_claim_health_when_warnings_were_printed():
    source = inspect.getsource(cli_main.doctor)
    assert "warnings_found = False" in source
    assert "if all_checks_passed and not warnings_found:" in source
    # Every ⚠ line in doctor should set the flag.
    warn_lines = [
        line for line in source.splitlines()
        if "[yellow]⚠[/yellow]" in line and "console.print" in line
    ]
    assert len(warn_lines) >= 4
    assert source.count("warnings_found = True") >= len(warn_lines)


def test_report_accepts_a_repo_flag():
    """`cgc report` had no way to target a repo; with several indexed it
    silently picked the one with the most files."""
    result = runner.invoke(app, ["report", "--help"])
    assert result.exit_code == 0
    normalised = _plain(result.output)
    assert "--repo" in normalised

    source = inspect.getsource(cli_main.report)
    assert "repo_path=scoped_repo" in source
