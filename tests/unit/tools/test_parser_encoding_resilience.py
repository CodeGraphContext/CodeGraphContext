"""Regression tests: a non-UTF-8 source file must not be silently dropped."""
import glob
import re

import pytest

# open(...) calls that specify encoding but no errors= handler.
_UNGUARDED = re.compile(
    r"open\((?![^)]*errors=)[^)]*encoding=['\"]utf-8['\"][^)]*\)"
)

_PARSER_FILES = sorted(glob.glob("src/codegraphcontext/tools/languages/*.py")) or sorted(
    glob.glob("**/codegraphcontext/tools/languages/*.py", recursive=True)
)


def test_parser_files_were_found():
    assert _PARSER_FILES, "could not locate the language parser sources"


@pytest.mark.parametrize("path", _PARSER_FILES, ids=lambda p: p.split("/")[-1])
def test_every_parser_decodes_defensively(path):
    """Seven of the most-used parsers (Python, JS, TS, TSX, Go, CSS, HTML)
    opened source files with `encoding="utf-8"` and no `errors=` handler, while
    the other 20 passed `errors="ignore"`.

    A `UnicodeDecodeError` was caught upstream and turned into a result with an
    `error` key but no `unsupported` key, which the pipeline treats exactly like
    a `.md` file: the file got a bare `File` node, contributed no symbols, and
    the run still reported "Successfully finished indexing" with no failure
    count. A codebase with legacy latin-1 files lost them entirely.
    """
    source = open(path, encoding="utf-8").read()
    unguarded = _UNGUARDED.findall(source)
    assert not unguarded, (
        f"{path} opens source without an errors= handler: {unguarded[:2]}"
    )


def test_latin1_source_still_yields_symbols(tmp_path):
    """End-to-end at the parser level: a latin-1 file must parse, not raise."""
    from codegraphcontext.tools.languages.python import PythonTreeSitterParser
    from codegraphcontext.tools.graph_builder import GraphBuilder

    target = tmp_path / "latin.py"
    target.write_bytes(
        "def caf\xe9_handler():\n    return 1\n\ndef plain_one():\n    return 2\n".encode("latin-1")
    )

    import asyncio
    from unittest.mock import MagicMock

    builder = GraphBuilder.__new__(GraphBuilder)
    GraphBuilder.__init__(
        builder,
        db_manager=MagicMock(),
        job_manager=MagicMock(),
        loop=asyncio.new_event_loop(),
    )
    data = builder.parse_file(tmp_path, target)

    assert "error" not in data, f"latin-1 file failed to parse: {data.get('error')}"
    names = {f["name"] for f in data.get("functions", [])}
    assert "plain_one" in names, f"pure-ASCII function lost; got {names}"
    # The non-ASCII byte is dropped by errors="ignore", so the identifier is
    # mangled but present and still distinct.
    assert any(n.endswith("_handler") for n in names), f"got {names}"
