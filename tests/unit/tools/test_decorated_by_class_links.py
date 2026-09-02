"""DECORATED_BY must reach class-level decorators, not just function-level ones.

`DECORATED_BY` is declared as a two-pair relationship group
(`FROM Function TO Function, FROM Class TO Function`), and
`build_decorated_by_links` correctly emits rows for both decorated
functions and decorated classes. `write_decorated_by_links` hardcoded
`:Function` on the *decorated* endpoint, so every class-decorator row
matched nothing and was dropped -- no error, no log, no edge.

This affects every language that records class-level decorators, not just
Kotlin: TypeScript's `@Component`, C#'s attributes and so on take the same
path. See issue #1601.

Two notes on the fixture, both deliberate:

1. Kotlin, not Python. Python's parser does not currently populate
   `decorators` on classes at all (`@my_decorator class C` yields
   `decorators == []`), so it cannot exercise the class branch of the
   builder. That is a separate parser gap, not this bug. Kotlin's parser
   does populate class decorators, so it reaches the writer.

2. The decorator is declared as a `fun`, not an `annotation class`.
   DECORATED_BY declares both pairs as `TO Function`, so the decorator
   endpoint must resolve to a `Function` node for any edge to form. A real
   Kotlin annotation is an annotation *class* and would land as a `Class`
   node, failing to match `TO Function` for a reason that has nothing to do
   with the bug under test and would mask it. Naming a plain function here
   keeps the decorated endpoint -- the one this issue is about -- as the
   only variable between the two assertions below.

Drives the real chain (real tree-sitter parser, real builder, real writer,
real query) rather than hand-built rows, because the defect is precisely
that correctly-built rows never land.
"""
from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.indexing.persistence.writer import GraphWriter
from codegraphcontext.tools.indexing.resolution.inheritance import (
    build_decorated_by_links,
)
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager

ladybug = pytest.importorskip("ladybug")

from codegraphcontext.core.database_ladybug import LadybugDBManager  # noqa: E402
from codegraphcontext.tools.languages.kotlin import (  # noqa: E402
    KotlinTreeSitterParser,
)

SOURCE = """\
package a

fun Marker() {
}

@Marker
class DecoratedClass {
}

@Marker
fun decoratedFunction() {
}
"""


def _kotlin_parser() -> KotlinTreeSitterParser:
    manager = get_tree_sitter_manager()
    wrapper = MagicMock()
    wrapper.language_name = "kotlin"
    wrapper.language = manager.get_language_safe("kotlin")
    wrapper.parser = manager.create_parser("kotlin")
    return KotlinTreeSitterParser(wrapper)


def _parse(tmp_path):
    source = tmp_path / "Decorators.kt"
    source.write_text(SOURCE, encoding="utf-8")
    return source, _kotlin_parser().parse(source)


@pytest.fixture
def decorated_by_edges(tmp_path):
    """Run the full chain and yield the set of (decorated, decorator) pairs."""
    manager = LadybugDBManager(str(tmp_path / "db"))
    try:
        driver = manager.get_driver()
        writer = GraphWriter(driver)
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        writer.add_repository_to_graph(repo_path)

        source = repo_path / "Decorators.kt"
        source.write_text(SOURCE, encoding="utf-8")
        file_data = _kotlin_parser().parse(source)

        writer.add_file_to_graph(
            file_data, repo_path.name, {}, repo_path_str=str(repo_path)
        )
        writer.write_decorated_by_links(build_decorated_by_links([file_data], {}))

        with driver.session() as session:
            result = session.run(
                "MATCH (d)-[:DECORATED_BY]->(dec:Function) "
                "RETURN d.name AS decorated, dec.name AS decorator"
            )
            yield {(r["decorated"], r["decorator"]) for r in result}
    finally:
        manager.close_driver()


def test_builder_emits_rows_for_both_decorated_kinds(tmp_path):
    """Premise check: the bug is in the writer, not the builder.

    Without this, a missing edge downstream could equally mean the builder
    never produced the row, leaving the writer fix unverified.
    """
    _, file_data = _parse(tmp_path)

    rows = build_decorated_by_links([file_data], {})
    emitted = {(r["decorated_name"], r["decorator_name"]) for r in rows}

    assert ("DecoratedClass", "Marker") in emitted
    assert ("decoratedFunction", "Marker") in emitted


def test_function_level_decorator_reaches_the_graph(decorated_by_edges):
    """Positive control: this pair always worked.

    It is what makes the class-level assertion meaningful -- if this failed
    too, the cause would be the harness, not the hardcoded label.
    """
    assert ("decoratedFunction", "Marker") in decorated_by_edges


def test_class_level_decorator_reaches_the_graph(decorated_by_edges):
    assert ("DecoratedClass", "Marker") in decorated_by_edges
