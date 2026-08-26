"""find_dead_code must see functions produced by the real parser -> writer chain.

Every test in `test_dead_code_analysis.py` inspects the query source via
`inspect.getsource`, and hand-built `file_data` fixtures elsewhere in the
suite set `is_dependency` on each function dict directly -- exactly mirroring
what a *correct* parser should emit. That hid a real bug: language extractors
(including Kotlin's) only set `is_dependency` on the top-level file dict, not
on the per-function dicts written into `functions`. `add_file_to_graph` used
to copy each item verbatim (`row = dict(item)`), so every real `Function`
node landed with `is_dependency` NULL. `find_dead_code`'s query filters on
`func.is_dependency = false`, and in Cypher `NULL = false` evaluates to NULL
(not false), so that filter silently dropped every real function and the
tool always returned an empty list -- on every project, every language,
every backend.

This test drives the actual chain -- a real tree-sitter parser, followed by
`GraphWriter.add_file_to_graph` -- with no hand-built `file_data`, so it is
the one test in the suite that would have caught the bug.

Kotlin is used deliberately rather than Python: Python's `_find_functions`
hardcodes `"is_dependency": False` on every function dict it builds, which
would incidentally satisfy `find_dead_code` even without the fix and defeat
the point of this test. Kotlin's `_parse_functions` never sets
`is_dependency` per-function, so it actually exercises the propagation path
in `add_file_to_graph`.
"""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.code_finder import CodeFinder
from codegraphcontext.tools.indexing.persistence.writer import GraphWriter
from codegraphcontext.tools.languages.kotlin import KotlinTreeSitterParser
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager

ladybug = pytest.importorskip("ladybug")

from codegraphcontext.core.database_ladybug import LadybugDBManager  # noqa: E402


def _kotlin_parser() -> KotlinTreeSitterParser:
    manager = get_tree_sitter_manager()
    wrapper = MagicMock()
    wrapper.language_name = "kotlin"
    wrapper.language = manager.get_language_safe("kotlin")
    wrapper.parser = manager.create_parser("kotlin")
    return KotlinTreeSitterParser(wrapper)


def test_real_parser_output_reaches_find_dead_code(tmp_path):
    parser = _kotlin_parser()

    manager = LadybugDBManager(str(tmp_path / "db"))
    try:
        driver = manager.get_driver()
        writer = GraphWriter(driver)
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        writer.add_repository_to_graph(repo_path)

        source = repo_path / "Orphan.kt"
        source.write_text(
            "package a\n"
            "\n"
            "fun genuinelyUncalledHelper() {\n"
            "    println(\"never called by anything in this project\")\n"
            "}\n",
            encoding="utf-8",
        )

        file_data = parser.parse(source)
        # The bug is specifically about the per-function dicts, not the file
        # dict -- confirm the real parser does not set it per-item, so this
        # test cannot be accidentally satisfied by parser-level behavior.
        assert all(
            "is_dependency" not in fn for fn in file_data["functions"]
        ), "test premise broken: parser now sets is_dependency per-function"

        writer.add_file_to_graph(
            file_data, repo_path.name, {}, repo_path_str=str(repo_path)
        )

        finder = CodeFinder(manager)
        result = finder.find_dead_code()

        names = {r["function_name"] for r in result["potentially_unused_functions"]}
        assert names == {"genuinelyUncalledHelper"}
    finally:
        manager.close_driver()
