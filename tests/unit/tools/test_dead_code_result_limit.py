"""find_dead_code must not silently cap its own result set at 50.

`code_finder.py` ended its query with a hardcoded `LIMIT 50`, applied
*after* the decorator filter. Two things followed, both user-visible:

- The total was unobtainable. The most useful number about dead code --
  how much there is -- could not be retrieved at any call site.
- `exclude_decorated_with` appeared to do nothing. Rows removed by the
  filter were backfilled by the next ones in path order, so the returned
  count was 50 either way. On a real Android codebase the reporter
  measured 7,141 dead functions capped to 50, and a filter that genuinely
  removed 6,086 false positives presenting as a no-op.

The cap also starved the pagination the handler already had:
`analysis_handlers.find_dead_code` reads `TOOL_RESULT_LIMITS` and sets
`truncated`/`result_limit`, but never saw more than 50 rows, so raising
the configured limit above 50 changed nothing.

Drives the real parser -> writer -> query chain, because the defect is in
what the query returns rather than in how any single row is built. See
issue #1606.
"""
from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.code_finder import CodeFinder
from codegraphcontext.tools.indexing.persistence.writer import GraphWriter
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager

ladybug = pytest.importorskip("ladybug")

from codegraphcontext.core.database_ladybug import LadybugDBManager  # noqa: E402
from codegraphcontext.tools.handlers.analysis_handlers import (  # noqa: E402
    find_dead_code as find_dead_code_handler,
)
from codegraphcontext.tools.languages.kotlin import (  # noqa: E402
    KotlinTreeSitterParser,
)

# Comfortably above the old hardcoded cap, and split so that filtering by
# the annotation leaves a count that is neither 50 nor the unfiltered total
# -- otherwise a still-capped result could coincide with a correct one.
TOTAL_DEAD = 70
ANNOTATED_DEAD = 30


def _source() -> str:
    lines = ["package a", ""]
    for i in range(TOTAL_DEAD):
        if i < ANNOTATED_DEAD:
            lines.append("@Marker")
        lines.append(f"fun deadFunction{i:03d}() {{")
        lines.append("}")
        lines.append("")
    return "\n".join(lines)


def _kotlin_parser() -> KotlinTreeSitterParser:
    manager = get_tree_sitter_manager()
    wrapper = MagicMock()
    wrapper.language_name = "kotlin"
    wrapper.language = manager.get_language_safe("kotlin")
    wrapper.parser = manager.create_parser("kotlin")
    return KotlinTreeSitterParser(wrapper)


@pytest.fixture
def finder(tmp_path):
    manager = LadybugDBManager(str(tmp_path / "db"))
    try:
        driver = manager.get_driver()
        writer = GraphWriter(driver)
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        writer.add_repository_to_graph(repo_path)

        source = repo_path / "Dead.kt"
        source.write_text(_source(), encoding="utf-8")
        file_data = _kotlin_parser().parse(source)
        writer.add_file_to_graph(
            file_data, repo_path.name, {}, repo_path_str=str(repo_path)
        )

        yield CodeFinder(manager)
    finally:
        manager.close_driver()


def test_all_dead_functions_are_returned_not_just_the_first_fifty(finder):
    result = finder.find_dead_code()

    names = {r["function_name"] for r in result["potentially_unused_functions"]}
    assert len(names) == TOTAL_DEAD


def test_total_is_reported(finder):
    """The count is the headline number and was previously unobtainable."""
    result = finder.find_dead_code()

    assert result["total_count"] == TOTAL_DEAD


def test_decorator_filter_actually_reduces_the_result(finder):
    """The symptom that made the cap visible.

    With the cap in place both calls returned 50, so the filter looked
    inert. The filtered count must be the genuine remainder.
    """
    unfiltered = finder.find_dead_code()
    filtered = finder.find_dead_code(exclude_decorated_with=["Marker"])

    assert unfiltered["total_count"] == TOTAL_DEAD
    assert filtered["total_count"] == TOTAL_DEAD - ANNOTATED_DEAD
    filtered_names = {r["function_name"] for r in filtered["potentially_unused_functions"]}
    assert len(filtered_names) == TOTAL_DEAD - ANNOTATED_DEAD


def test_explicit_limit_pages_the_result_but_keeps_the_true_total(finder):
    """A caller-supplied limit bounds the page, not the count."""
    result = finder.find_dead_code(limit=10)

    assert len(result["potentially_unused_functions"]) == 10
    assert result["total_count"] == TOTAL_DEAD


def test_handler_reports_total_and_truncation(finder):
    """The handler already had TOOL_RESULT_LIMITS plumbing; the cap starved it.

    `total_count` must survive to the tool response unconditionally --
    a count that appears only when truncated is nearly as unusable as no
    count at all.
    """
    response = find_dead_code_handler(finder)

    assert response["success"] is True
    assert response["results"]["total_count"] == TOTAL_DEAD
    # Default configured limit for this tool is 50, so 70 rows truncate.
    assert response["truncated"] is True
    assert response["result_limit"] == 50
    assert len(response["results"]["potentially_unused_functions"]) == 50
