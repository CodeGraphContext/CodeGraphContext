# tests/unit/tools/test_issue_1393_node_identity.py
"""Node identity must survive two symbols sharing a name and a line.

Regression tests for https://github.com/CodeGraphContext/CodeGraphContext/issues/1393

Root cause: the writer merged code entities on ``(name, path, line_number)``,
which is not unique. Two distinct symbols in one file sharing a name and a line
collapsed onto a single node and the following ``SET n += row`` overwrote the
first one's ``args``, ``class_context``, ``end_line`` and
``cyclomatic_complexity`` with the last one's.

Two confirmed sources, both reproduced below:

* CSS -- every selector is emitted as a ``Function``, so ``tfoot th, tfoot td``
  produces two ``tfoot`` records on one line.
* Minified/bundled JS -- the whole file is one line, so genuinely different
  functions all carry ``line_number: 1``.
"""

from __future__ import annotations

from codegraphcontext.tools.indexing import schema_contract as sc
from codegraphcontext.tools.indexing.persistence.writer import (
    _NAME_ONLY_MERGE_LABELS,
    _assign_occurrence_indices,
)


# ===========================================================================
# 1. The disambiguator itself -- pure function, no DB needed
# ===========================================================================

class TestAssignOccurrenceIndices:
    def test_no_collision_leaves_every_index_zero(self):
        """The common case must be byte-identical to the old behaviour."""
        items = [
            {"name": "parse", "line_number": 10},
            {"name": "render", "line_number": 20},
            {"name": "main", "line_number": 30},
        ]
        indices, collisions = _assign_occurrence_indices(items)
        assert indices == [0, 0, 0]
        assert collisions == []

    def test_grouped_css_selectors_get_distinct_indices(self):
        """`tfoot th, tfoot td { }` -- two `tfoot` records, same line."""
        items = [
            {"name": "tfoot", "line_number": 41},
            {"name": "th", "line_number": 41},
            {"name": "tfoot", "line_number": 41},
            {"name": "td", "line_number": 41},
        ]
        indices, collisions = _assign_occurrence_indices(items)
        assert indices == [0, 0, 1, 0]
        assert collisions == [("tfoot", 41, 2)]

    def test_minified_js_all_on_line_one(self):
        """A bundle is one line, so different functions share line_number 1."""
        items = [
            {"name": "endIndex", "line_number": 1, "class_context": "Node"},
            {"name": "endIndex", "line_number": 1, "class_context": "TreeCursor"},
        ]
        indices, collisions = _assign_occurrence_indices(items)
        assert indices == [0, 1]
        assert collisions == [("endIndex", 1, 2)]

    def test_three_way_collision(self):
        items = [{"name": "code", "line_number": 558} for _ in range(3)]
        indices, collisions = _assign_occurrence_indices(items)
        assert indices == [0, 1, 2]
        assert collisions == [("code", 558, 3)]

    def test_same_name_different_lines_do_not_collide(self):
        items = [
            {"name": "handler", "line_number": 5},
            {"name": "handler", "line_number": 9},
        ]
        indices, collisions = _assign_occurrence_indices(items)
        assert indices == [0, 0]
        assert collisions == []

    def test_indices_are_unique_per_key(self):
        """The whole point: (name, line_number, occurrence_index) must be unique."""
        items = [
            {"name": "a", "line_number": 1},
            {"name": "a", "line_number": 1},
            {"name": "a", "line_number": 1},
            {"name": "b", "line_number": 1},
            {"name": "a", "line_number": 2},
        ]
        indices, _ = _assign_occurrence_indices(items)
        keys = [(it["name"], it["line_number"], ix) for it, ix in zip(items, indices)]
        assert len(set(keys)) == len(items), "merge keys are still not unique"

    def test_is_deterministic_for_unchanged_input(self):
        """Re-indexing an unchanged file must produce the same ordinals."""
        items = [
            {"name": "tfoot", "line_number": 41},
            {"name": "tfoot", "line_number": 41},
        ]
        assert _assign_occurrence_indices(items)[0] == _assign_occurrence_indices(items)[0]

    def test_empty_input(self):
        assert _assign_occurrence_indices([]) == ([], [])

    def test_missing_name_or_line_does_not_raise(self):
        """Not every extractor fills both fields; the writer must not crash."""
        items = [{}, {}, {"name": "x"}]
        indices, collisions = _assign_occurrence_indices(items)
        assert indices == [0, 1, 0]
        assert collisions == [("", None, 2)]

    def test_returns_index_per_item(self):
        items = [{"name": f"n{i}", "line_number": i} for i in range(50)]
        indices, _ = _assign_occurrence_indices(items)
        assert len(indices) == len(items)


# ===========================================================================
# 2. The data loss itself, under the writer's real MERGE semantics
# ===========================================================================

def _merge(rows, key_fields):
    """Model `MERGE (n {key}) SET n += row` -- last write wins per key."""
    graph: dict = {}
    for row in rows:
        graph.setdefault(tuple(row.get(f) for f in key_fields), {}).update(row)
    return graph


class TestPropertiesAreNoLongerClobbered:
    """Two `endIndex` methods on line 1 of a minified bundle, different classes."""

    PATH = "/repo/website/public/wasm/tree-sitter-core.js"
    ROWS = [
        {
            "name": "endIndex", "line_number": 1, "class_context": "Node",
            "end_line": 1, "cyclomatic_complexity": 3, "args": ["self"],
        },
        {
            "name": "endIndex", "line_number": 1, "class_context": "TreeCursor",
            "end_line": 1, "cyclomatic_complexity": 7, "args": ["self", "cursor"],
        },
    ]

    def test_old_three_property_key_loses_a_symbol(self):
        """Characterises the bug: the triple collapses both symbols into one."""
        rows = [dict(r, path=self.PATH) for r in self.ROWS]
        graph = _merge(rows, ("name", "path", "line_number"))
        assert len(graph) == 1, "the old key was expected to be non-unique"
        survivor = next(iter(graph.values()))
        # The first symbol's properties were overwritten by the second's.
        assert survivor["class_context"] == "TreeCursor"
        assert survivor["cyclomatic_complexity"] == 7
        assert survivor["args"] == ["self", "cursor"]

    def test_new_key_keeps_both_symbols_with_their_own_properties(self):
        indices, _ = _assign_occurrence_indices(self.ROWS)
        rows = [
            dict(r, path=self.PATH, occurrence_index=i)
            for r, i in zip(self.ROWS, indices)
        ]
        graph = _merge(rows, sc.FUNCTION_MERGE_KEYS)
        assert len(graph) == 2, "both symbols must survive"
        by_class = {n["class_context"]: n for n in graph.values()}
        assert by_class["Node"]["cyclomatic_complexity"] == 3
        assert by_class["Node"]["args"] == ["self"]
        assert by_class["TreeCursor"]["cyclomatic_complexity"] == 7
        assert by_class["TreeCursor"]["args"] == ["self", "cursor"]

    def test_collision_free_file_is_unaffected_by_the_new_key(self):
        """The new key must not change the graph for files that never collide."""
        rows = [
            {"name": "parse", "line_number": 10, "path": self.PATH},
            {"name": "render", "line_number": 20, "path": self.PATH},
        ]
        indices, collisions = _assign_occurrence_indices(rows)
        assert collisions == []
        new_rows = [dict(r, occurrence_index=i) for r, i in zip(rows, indices)]
        old_graph = _merge(rows, ("name", "path", "line_number"))
        new_graph = _merge(new_rows, sc.FUNCTION_MERGE_KEYS)
        assert len(old_graph) == len(new_graph) == 2


# ===========================================================================
# 3. Identity contract
# ===========================================================================

class TestIdentityContract:
    def test_merge_keys_include_the_disambiguator(self):
        assert "occurrence_index" in sc.FUNCTION_MERGE_KEYS
        assert "occurrence_index" in sc.CLASS_MERGE_KEYS

    def test_line_number_is_still_part_of_identity(self):
        """The fix adds a key; it must not drop the existing ones."""
        for key in ("name", "path", "line_number"):
            assert key in sc.FUNCTION_MERGE_KEYS

    def test_globally_shared_labels_keep_name_only_identity(self):
        """Module nodes are shared across files and must not take an ordinal."""
        assert "Module" in _NAME_ONLY_MERGE_LABELS
