"""Query execution must be serialised across threads (#1370).

Building a `Query` / running a `QueryCursor` concurrently on different
languages crashes the native extension — a `Fatal Python error: Segmentation
fault`, not a Python exception, so nothing above can catch or retry it. The
reported traceback shows three threads inside `execute_query` at once, on
three different grammars.

These tests pin the guard rather than the crash: a segfault cannot be asserted
on from inside the process that takes it, and the race is timing-dependent
enough that a passing run proves nothing on its own.
"""

from __future__ import annotations

import concurrent.futures
import threading

from codegraphcontext.utils import tree_sitter_manager
from codegraphcontext.utils.tree_sitter_manager import execute_query


def test_a_process_wide_query_lock_exists():
    """Per-language would not be enough — the reports involve different
    languages crashing together."""
    assert hasattr(tree_sitter_manager, "_QUERY_LOCK")
    assert isinstance(
        tree_sitter_manager._QUERY_LOCK, type(threading.Lock())
    ), "expected a threading.Lock"


def test_execute_query_holds_the_lock_while_running():
    """The lock must cover query construction *and* execution, not just one."""
    observed = []
    real_body = tree_sitter_manager._execute_query_locked

    def spy(*args, **kwargs):
        observed.append(tree_sitter_manager._QUERY_LOCK.locked())
        return real_body(*args, **kwargs)

    tree_sitter_manager._execute_query_locked = spy
    try:
        from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser

        wrapper = TreeSitterParser("python")
        tree = wrapper.parser.parse(b"def f():\n    return 1\n")
        execute_query(wrapper.language, "(function_definition) @fn", tree.root_node)
    finally:
        tree_sitter_manager._execute_query_locked = real_body

    assert observed, "execute_query did not route through the locked body"
    assert all(observed), "query body ran without the lock held"


def test_queries_never_overlap_under_concurrency():
    """No two threads may be inside the query body at the same time."""
    from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser

    wrapper = TreeSitterParser("python")
    tree = wrapper.parser.parse(b"def f(x):\n    return x\n" * 20)

    concurrent_peak = 0
    inside = 0
    counter_lock = threading.Lock()
    real_body = tree_sitter_manager._execute_query_locked

    def spy(*args, **kwargs):
        nonlocal inside, concurrent_peak
        with counter_lock:
            inside += 1
            concurrent_peak = max(concurrent_peak, inside)
        try:
            return real_body(*args, **kwargs)
        finally:
            with counter_lock:
                inside -= 1

    tree_sitter_manager._execute_query_locked = spy
    try:
        def run(_):
            return execute_query(
                wrapper.language, "(function_definition) @fn", tree.root_node
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            results = list(ex.map(run, range(64)))
    finally:
        tree_sitter_manager._execute_query_locked = real_body

    assert len(results) == 64
    assert all(r for r in results), "some queries returned nothing"
    assert concurrent_peak == 1, (
        f"{concurrent_peak} threads were inside the query body at once; "
        "execution is not serialised"
    )


def test_mixed_language_concurrency_completes():
    """The shape reported in #1370: several grammars queried at once."""
    from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser

    langs = ["python", "javascript", "typescript"]
    wrappers = {l: TreeSitterParser(l) for l in langs}
    sources = {
        "python": b"def f(x):\n    return x\n" * 10,
        "javascript": b"function g(a) { return a; }\n" * 10,
        "typescript": b"export function h(a: string): string { return a; }\n" * 10,
    }
    queries = {
        "python": "(function_definition) @fn",
        "javascript": "(function_declaration) @fn",
        "typescript": "(function_declaration) @fn",
    }

    def run(i):
        lang = langs[i % len(langs)]
        w = wrappers[lang]
        tree = w.parser.parse(sources[lang])
        return execute_query(w.language, queries[lang], tree.root_node)

    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(run, range(120)))

    assert len(results) == 120
    assert all(len(r) > 0 for r in results)
