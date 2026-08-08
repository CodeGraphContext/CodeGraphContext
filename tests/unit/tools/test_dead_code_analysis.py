"""Dead-code analysis defects (#600, #1559).

The two implementations — `CodeFinder.find_dead_code` and the report
generator's `_section_dead_code` — each got something the other got wrong,
so the same repository produced different answers depending on which
surface you asked.
"""

from __future__ import annotations

import inspect

from codegraphcontext.tools import report_generator
from codegraphcontext.tools.code_finder import _ENTRY_POINT_NAMES, CodeFinder


def _query_src() -> str:
    return inspect.getsource(CodeFinder.find_dead_code)


# --------------------------------------------------------------- #600
def test_caller_pattern_is_not_restricted_to_function_nodes():
    """A JS module-level call is persisted as a File-sourced edge.

    `writer.py` has an explicit `caller_label == "File"` branch producing
    `(:File)-[:CALLS]->(:Function)`. Restricting the caller to
    `(caller:Function)` ignored those edges, so any JS function called only at
    module level was reported dead — the report generator's query already got
    this right with an anonymous caller.
    """
    src = _query_src()
    assert "OPTIONAL MATCH (caller)-[:CALLS|HEURISTIC_CALLS]->(func)" in src
    assert "(caller:Function)-[:CALLS" not in src, "still ignores File-sourced callers"


def test_caller_filter_tolerates_nodes_without_is_dependency():
    """File nodes reached as callers may not carry `is_dependency`; a bare
    equality test would drop them again through the back door."""
    src = _query_src()
    assert "caller.is_dependency IS NULL OR caller.is_dependency = false" in src


# --------------------------------------------------------------- #1559 (1)
def test_entry_point_names_match_whole_names_not_substrings():
    """`name CONTAINS 'main'` also excluded `domain_check`, `remainder` and
    `maintain_index`, hiding genuinely unused code with no way to tell."""
    src = _query_src()
    # The query is an f-string, so the source carries the placeholder rather
    # than the rendered list.
    assert "toLower(func.name) IN {_ENTRY_POINT_NAMES_CYPHER}" in src, "must match whole names"
    for bad in (
        "func.name CONTAINS 'main'",
        "toLower(func.name) CONTAINS 'application'",
        "toLower(func.name) CONTAINS 'entry'",
    ):
        assert bad not in src, f"substring filter still present: {bad}"


def test_names_that_merely_contain_an_entry_point_word_are_not_excluded():
    """The exclusion list is exact, so these are still analyzed."""
    lowered = {n.lower() for n in _ENTRY_POINT_NAMES}
    for name in ("domain_check", "remainder", "maintain_index", "entry_count", "runner"):
        assert name not in lowered, f"{name} must not be treated as an entry point"


# --------------------------------------------------------------- #1559 (4)
def test_report_generator_applies_the_same_exclusions():
    """The report had no name exclusions at all, so every dunder and `test_*`
    appeared as dead code in CGC_REPORT.md while the CLI filtered them out."""
    src = inspect.getsource(report_generator._section_dead_code)
    assert "_ENTRY_POINT_NAMES_CYPHER" in src, "must share the CLI's exclusion list"
    for guard in ("STARTS WITH 'test_'", "STARTS WITH '__'", "<module>"):
        assert guard in src, f"report query missing guard: {guard}"


def test_both_implementations_use_an_anonymous_caller():
    """Having agreed on exclusions, they must also agree on the caller shape."""
    report_src = inspect.getsource(report_generator._section_dead_code)
    assert "NOT ()-[:CALLS|HEURISTIC_CALLS]->(fn)" in report_src
    assert "(caller)-[:CALLS|HEURISTIC_CALLS]->(func)" in _query_src()


# --------------------------------------------------------------- #1559 (3)
def test_cli_forwards_the_path_argument_as_repo_scope():
    """`analyze dead-code .` used to drop the path, so results spanned every
    repository in the database."""
    from codegraphcontext.cli import main as cli_main

    src = inspect.getsource(cli_main.analyze_dead_code)
    assert "repo_path=repo_path" in src, "path must be forwarded as repo scope"
    assert "not yet implemented" not in src


# --------------------------------------------------------------- #1559 (2)
def test_cli_help_does_not_claim_classes_are_analyzed():
    """The query matches `(func:Function)` only; the help said 'and classes'."""
    from codegraphcontext.cli import main as cli_main

    doc = inspect.getdoc(cli_main.analyze_dead_code) or ""
    assert "classes" not in doc.lower(), "help still claims classes are analyzed"
