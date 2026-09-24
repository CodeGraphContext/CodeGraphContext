"""Regression tests for command-to-command delegation and `cgc index` exit codes."""
import re
import ast
import inspect
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from codegraphcontext.cli import main as cli_main
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



def _command_functions(tree):
    """Map command function name -> (ordered params, typer-defaulted params)."""
    commands = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if not any("command" in ast.dump(d) for d in node.decorator_list):
            continue
        params = [a.arg for a in node.args.args]
        defaults = node.args.defaults
        offset = len(params) - len(defaults)
        typer_defaulted = {
            params[offset + i]
            for i, d in enumerate(defaults)
            if "typer" in ast.dump(d) and ("Option" in ast.dump(d) or "Argument" in ast.dump(d))
        }
        commands[node.name] = (params, typer_defaulted)
    return commands


def test_no_command_delegates_without_supplying_typer_defaults():
    """Typer resolves defaults only when *it* invokes the command. A command
    calling a sibling as a plain function must pass every Typer-defaulted
    parameter explicitly, or the callee receives a `typer.models.OptionInfo`
    sentinel — which is truthy, and which leaks into user-facing errors.

    This guards the whole bug class, not just the instances found so far:
      - bundle_load -> bundle_import omitted `context`, making `cgc bundle
        load` and `cgc load` fail 100% of the time.
      - index_abbrev -> index omitted `summarize`, so `cgc i` always printed
        the codebase summary.
    """
    tree = ast.parse(inspect.getsource(cli_main))
    commands = _command_functions(tree)

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for call in ast.walk(node):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
                continue
            callee = call.func.id
            if callee not in commands or callee == node.name:
                continue
            params, typer_defaulted = commands[callee]
            supplied = set(params[: len(call.args)]) | {
                kw.arg for kw in call.keywords if kw.arg
            }
            missing = typer_defaulted - supplied
            if missing:
                offenders.append(
                    f"main.py:{call.lineno} {node.name}() -> {callee}() "
                    f"missing {sorted(missing)}"
                )

    assert not offenders, "command delegation drops Typer defaults:\n  " + "\n  ".join(offenders)


def test_optioninfo_is_truthy():
    """Documents why an omitted boolean flag silently turns itself on."""
    assert bool(typer.Option(False, "--summarize")) is True


@pytest.mark.parametrize("argv", [
    ["index", "/nonexistent-path-for-cgc-tests"],
    ["index", "--force", "/nonexistent-path-for-cgc-tests"],
])
def test_index_exits_nonzero_when_the_helper_aborts(argv):
    """`typer.Exit` subclasses RuntimeError with an empty str(), so the bare
    `except Exception` swallowed it and returned 0 — CI treated every indexing
    failure as success."""
    with patch.object(cli_main, "index_helper", side_effect=typer.Exit(code=1)), \
         patch.object(cli_main, "reindex_helper", side_effect=typer.Exit(code=1)), \
         patch.object(cli_main, "_load_credentials"):
        result = runner.invoke(app, argv)

    assert result.exit_code == 1


def test_index_exits_nonzero_on_an_unexpected_error():
    with patch.object(cli_main, "index_helper", side_effect=RuntimeError("boom")), \
         patch.object(cli_main, "_load_credentials"):
        result = runner.invoke(app, ["index", "."])

    assert result.exit_code == 1


def test_index_still_exits_zero_on_success():
    with patch.object(cli_main, "index_helper"), \
         patch.object(cli_main, "_load_credentials"):
        result = runner.invoke(app, ["index", "."])

    assert result.exit_code == 0


def test_bundle_load_accepts_a_context_flag():
    result = runner.invoke(app, ["bundle", "load", "--help"])
    assert result.exit_code == 0
    assert "--context" in _plain(result.output)
