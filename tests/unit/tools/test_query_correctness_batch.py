"""Query-shape and argument-plumbing defects found in the 0.5.x audit.

Each test pins one defect that produced a plausible-looking but wrong answer
rather than an error, which is the class of bug an agent cannot detect.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.code_finder import CodeFinder


# --------------------------------------------------------------- #1529
def test_repository_stats_count_distinct_nodes_not_contains_paths():
    """A method is reachable via File->CONTAINS and Class->CONTAINS both.

    Counting rows instead of distinct nodes inflated every per-repo figure
    (2202 reported against 1551 real Function nodes on a live database).
    """
    import inspect

    from codegraphcontext.tools.handlers import management_handlers

    src = inspect.getsource(management_handlers)
    for var, label in (("f", "File"), ("func", "Function"), ("cls", "Class")):
        assert (
            f"-[:CONTAINS*]->({var}:{label}) RETURN count(DISTINCT {var})" in src
        ), f"{label} counter must use count(DISTINCT {var})"
        # Only the traversal form can double-count. The global branch
        # (`MATCH (f:File) RETURN count(f)`) has no CONTAINS path and is
        # correct as-is, so assert specifically against the traversal shape.
        assert (
            f"-[:CONTAINS*]->({var}:{label}) RETURN count({var})" not in src
        ), f"{label} counter still counts CONTAINS paths"


# --------------------------------------------------------------- #1533
def test_injection_count_counts_relationships_not_rows():
    """`count(*)` after an unmatched OPTIONAL MATCH still counts one null row,
    so every Spring bean reported at least one injector."""
    import inspect

    from codegraphcontext.tools.handlers import analysis_handlers
    from codegraphcontext.tools.query_tool_languages import java_toolkit

    for mod in (analysis_handlers, java_toolkit):
        src = inspect.getsource(mod)
        assert "count(inj) AS injection_count" in src, f"{mod.__name__} must bind the relationship"
        assert "count(*) AS injection_count" not in src, f"{mod.__name__} still counts rows"


def test_key_patterns_collect_drops_empty_rows():
    """A map literal is non-null even when every field is null, so collecting
    maps kept a phantom all-null entry for a datasource with no patterns."""
    import inspect

    from codegraphcontext.tools.handlers import analysis_handlers

    src = inspect.getsource(analysis_handlers)
    assert "[x IN collect(kp) |" in src, "must collect the node, then project"
    assert "collect({pattern: kp.pattern" not in src, "still collects a map literal"


# --------------------------------------------------------------- #1530
class _Recorder:
    def __init__(self, rows):
        self._rows = rows
        self.last_query = None

    def session(self, *a, **k):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def run(self, query, **params):
        self.last_query = query
        res = MagicMock()
        res.data.return_value = self._rows
        return res


def _finder_with(rows):
    dbm = MagicMock()
    rec = _Recorder(rows)
    dbm.get_driver.return_value = rec
    dbm.get_backend_type.return_value = "neo4j"
    return CodeFinder(dbm)


def test_find_callers_keeps_per_row_target_when_definitions_differ():
    """Without `context`, callers of a common name legitimately point at
    different definitions; hoisting the first row's path reported every caller
    as calling whichever file sorted first."""
    rows = [
        {"caller": "a", "target_file_path": "/repo/models/user.py"},
        {"caller": "b", "target_file_path": "/repo/models/order.py"},
    ]
    finder = _finder_with(rows)
    out = finder.analyze_code_relationships("find_callers", "save")

    assert out["target_file_path"] is None, "must not claim a single target"
    paths = {r.get("target_file_path") for r in out["results"]}
    assert paths == {"/repo/models/user.py", "/repo/models/order.py"}
    assert "note" in out and "2 files" in out["note"]


def test_find_callers_still_hoists_when_all_rows_agree():
    """The payload-slimming behaviour is kept for the unambiguous case."""
    rows = [
        {"caller": "a", "target_file_path": "/repo/models/user.py"},
        {"caller": "b", "target_file_path": "/repo/models/user.py"},
    ]
    finder = _finder_with(rows)
    out = finder.analyze_code_relationships("find_callers", "save")

    assert out["target_file_path"] == "/repo/models/user.py"
    assert all("target_file_path" not in r for r in out["results"])
    assert "note" not in out


# --------------------------------------------------------------- #1531
@pytest.mark.parametrize(
    "query_type,method",
    [("dead_code", "find_dead_code"), ("find_complexity", "find_most_complex_functions")],
)
def test_graph_name_is_forwarded_to_inner_queries(query_type, method):
    """Both inner methods default graph_name to None and re-assign the shared
    `_active_graph`, so omitting it silently queried the default graph."""
    finder = _finder_with([])
    captured = {}

    def spy(*args, **kwargs):
        captured["graph_name"] = kwargs.get("graph_name")
        return {"potentially_unused_functions": []} if query_type == "dead_code" else []

    setattr(finder, method, spy)
    finder.analyze_code_relationships(query_type, "x", graph_name="myrepo")
    assert captured["graph_name"] == "myrepo"


# --------------------------------------------------------------- #1558
def test_add_code_to_graph_refuses_an_unsupported_graph_name():
    """The schema advertises graph_name but indexing cannot honour it, so it
    must refuse rather than write to the default graph and report success."""
    from codegraphcontext.tools.handlers.indexing_handlers import add_code_to_graph

    out = add_code_to_graph(
        MagicMock(), MagicMock(), MagicMock(), MagicMock(),
        repo_path=".", graph_name="service-a",
    )
    assert "error" in out
    assert out.get("unsupported_argument") == "graph_name"
    assert "service-a" in out["error"]
