"""An empty list property must persist as `[]`, not `[""]`.

`writer.py`'s batch type-coercion rendered every empty list-valued
property as a one-element list containing the empty string. A function
with no decorators stored `decorators == [""]`, and the same applied to
`args`, `modifiers` and every other list property in every language.

It did not corrupt query results -- `"" CONTAINS 'Preview'` is false, so
un-annotated functions were still correctly retained by find_dead_code --
but `[""]` is not what any caller means by "none", and it forced every
consumer to special-case a one-element list holding an empty string.

The issue asked whether the `else [""]` branch was working around a
backend that rejects empty lists, in which case the fix would belong at
the read boundary instead. It is not: Ladybug accepts `[]` for a `STRING[]`
column in every shape the writer uses -- inside `UNWIND $rows`, as a
single-row parameter, and when *every* row in the batch is empty (so
there is no element type to infer from a sibling row). `test_all_empty_*`
below pins that last case, which is the one that would plausibly have
motivated a sentinel.

See issue #1607.
"""
from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.indexing.persistence.writer import GraphWriter
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager

kuzu = pytest.importorskip("kuzu")

from codegraphcontext.core.database_ladybug import LadybugDBManager  # noqa: E402
from codegraphcontext.tools.languages.kotlin import (  # noqa: E402
    KotlinTreeSitterParser,
)

# Every function here is un-annotated and takes no arguments, so `decorators`
# and `args` are empty for *all* rows in the batch -- the case where no
# sibling row can supply an element type.
ALL_EMPTY_SOURCE = """\
package a

fun first() {
}

fun second() {
}
"""

# A batch where the same key is empty on one row and populated on another,
# so the coercion's dominant-type inference sees a real list alongside the
# empty one.
MIXED_SOURCE = """\
package a

@Marker
fun annotated() {
}

fun plain() {
}
"""


def _kotlin_parser() -> KotlinTreeSitterParser:
    manager = get_tree_sitter_manager()
    wrapper = MagicMock()
    wrapper.language_name = "kotlin"
    wrapper.language = manager.get_language_safe("kotlin")
    wrapper.parser = manager.create_parser("kotlin")
    return KotlinTreeSitterParser(wrapper)


def _store_and_read(tmp_path, source: str):
    """Run the real parser -> writer chain, return {name: {prop: value}}."""
    manager = LadybugDBManager(str(tmp_path / "db"))
    try:
        driver = manager.get_driver()
        writer = GraphWriter(driver)
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        writer.add_repository_to_graph(repo_path)

        src = repo_path / "Sample.kt"
        src.write_text(source, encoding="utf-8")
        writer.add_file_to_graph(
            _kotlin_parser().parse(src), repo_path.name, {}, repo_path_str=str(repo_path)
        )

        with driver.session() as session:
            result = session.run(
                "MATCH (f:Function) RETURN f.name AS name, "
                "f.decorators AS decorators, f.args AS args, f.modifiers AS modifiers"
            )
            return {
                r["name"]: {
                    "decorators": r["decorators"],
                    "args": r["args"],
                    "modifiers": r["modifiers"],
                }
                for r in result
            }
    finally:
        manager.close_driver()


def test_all_empty_batch_stores_empty_lists(tmp_path):
    """Every row empty -- no sibling row to infer an element type from."""
    stored = _store_and_read(tmp_path, ALL_EMPTY_SOURCE)

    assert stored["first"]["decorators"] == []
    assert stored["first"]["args"] == []
    assert stored["second"]["decorators"] == []


def test_mixed_batch_keeps_populated_lists_intact(tmp_path):
    """The empty row must become [] without disturbing the populated one."""
    stored = _store_and_read(tmp_path, MIXED_SOURCE)

    assert stored["annotated"]["decorators"] == ["@Marker"]
    assert stored["plain"]["decorators"] == []
