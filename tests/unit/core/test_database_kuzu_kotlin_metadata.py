from pathlib import Path
from unittest.mock import MagicMock

import pytest

pytest.importorskip("kuzu")

from codegraphcontext.core.database_kuzu import KuzuDBManager
from codegraphcontext.tools.indexing.persistence.writer import GraphWriter


def _fresh_kuzu_manager(db_path: Path) -> KuzuDBManager:
    if KuzuDBManager._instance is not None:
        KuzuDBManager._instance.close_driver()
    KuzuDBManager._instance = None
    KuzuDBManager._db = None
    KuzuDBManager._conn = None
    return KuzuDBManager(db_path=str(db_path))


def test_kuzu_schema_metadata_migration_failures_are_fatal(tmp_path):
    manager = _fresh_kuzu_manager(tmp_path / "migration-failure-db")
    try:
        manager._conn = MagicMock()

        def execute(statement):
            if "class_context_line" in statement:
                raise Exception("permission denied")
            return None

        manager._conn.execute.side_effect = execute

        with pytest.raises(RuntimeError, match="Kuzu Schema Migration Failed"):
            manager._initialize_schema()
    finally:
        manager.close_driver()


def test_class_node_type_persists_in_kuzu(tmp_path):
    manager = _fresh_kuzu_manager(tmp_path / "node-type-db")
    try:
        driver = manager.get_driver()
        with driver.session() as session:
            session.run(
                """
                MERGE (c:Class {uid: $uid})
                SET c.name = $name,
                    c.path = $path,
                    c.line_number = $line_number,
                    c.node_type = $node_type
                """,
                uid="class-1",
                name="Factory",
                path="/repo/Sample.kt",
                line_number=4,
                node_type="companion_object",
            )
            row = session.run(
                "MATCH (c:Class {uid: $uid}) RETURN c.node_type AS node_type",
                uid="class-1",
            ).single()

        assert row is not None
        assert row["node_type"] == "companion_object"
    finally:
        manager.close_driver()


def test_calls_metadata_updates_do_not_duplicate_kuzu_relationships(tmp_path):
    manager = _fresh_kuzu_manager(tmp_path / "calls-db")
    try:
        driver = manager.get_driver()
        with driver.session() as session:
            session.run(
                """
                MERGE (f:Function {uid: $uid})
                SET f.name = $name, f.path = $path, f.line_number = $line_number
                """,
                uid="caller",
                name="caller",
                path="/repo/Sample.kt",
                line_number=1,
            )
            session.run(
                """
                MERGE (f:Function {uid: $uid})
                SET f.name = $name, f.path = $path, f.line_number = $line_number
                """,
                uid="target",
                name="target",
                path="/repo/Sample.kt",
                line_number=5,
            )

        writer = GraphWriter(driver)
        call = {
            "caller_name": "caller",
            "caller_file_path": "/repo/Sample.kt",
            "caller_line_number": 1,
            "called_name": "target",
            "called_file_path": "/repo/Sample.kt",
            "called_line_number": 5,
            "line_number": 2,
            "args": [],
            "full_call_name": "target",
        }
        writer.write_function_call_groups(
            [{**call, "type": "function", "confidence": 0.25, "resolution_tier": 5}],
        )
        writer.write_function_call_groups(
            [{**call, "type": "function", "confidence": 0.95, "resolution_tier": 1}],
        )

        with driver.session() as session:
            rows = session.run(
                """
                MATCH (:Function {name: $caller, path: $path, line_number: $caller_line})
                      -[r:CALLS]->
                      (:Function {name: $called, path: $path, line_number: $called_line})
                RETURN r.confidence AS confidence, r.resolution_tier AS resolution_tier
                """,
                caller="caller",
                called="target",
                path="/repo/Sample.kt",
                caller_line=1,
                called_line=5,
            ).data()

        assert rows == [{"confidence": pytest.approx(0.95), "resolution_tier": 1}]
    finally:
        manager.close_driver()


def test_class_calls_use_target_line_in_kuzu(tmp_path):
    manager = _fresh_kuzu_manager(tmp_path / "class-calls-db")
    try:
        driver = manager.get_driver()
        with driver.session() as session:
            session.run(
                """
                MERGE (f:Function {uid: $uid})
                SET f.name = $name, f.path = $path, f.line_number = $line_number
                """,
                uid="make",
                name="make",
                path="/repo/Sample.kt",
                line_number=3,
            )
            for line_number in (2, 7):
                session.run(
                    """
                    MERGE (c:Class {uid: $uid})
                    SET c.name = $name, c.path = $path, c.line_number = $line_number
                    """,
                    uid=f"inner-{line_number}",
                    name="Inner",
                    path="/repo/Sample.kt",
                    line_number=line_number,
                )

        writer = GraphWriter(driver)
        writer.write_function_call_groups(
            [],
            [
                {
                    "type": "function",
                    "caller_name": "make",
                    "caller_file_path": "/repo/Sample.kt",
                    "caller_line_number": 3,
                    "called_name": "Inner",
                    "called_file_path": "/repo/Sample.kt",
                    "called_line_number": 2,
                    "line_number": 3,
                    "args": [],
                    "full_call_name": "Inner",
                }
            ],
        )

        with driver.session() as session:
            rows = session.run(
                """
                MATCH (:Function {name: $caller, path: $path, line_number: $caller_line})
                      -[:CALLS]->
                      (called:Class {name: $called, path: $path})
                RETURN called.line_number AS line_number
                ORDER BY line_number
                """,
                caller="make",
                called="Inner",
                path="/repo/Sample.kt",
                caller_line=3,
            ).data()

        assert rows == [{"line_number": 2}]
    finally:
        manager.close_driver()


def test_class_function_containment_uses_owner_line_in_kuzu(tmp_path):
    manager = _fresh_kuzu_manager(tmp_path / "contains-db")
    try:
        driver = manager.get_driver()
        writer = GraphWriter(driver)
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        file_path = repo_path / "Sample.kt"
        file_path.write_text("", encoding="utf-8")

        writer.add_repository_to_graph(repo_path)
        writer.add_file_to_graph(
            {
                "path": str(file_path),
                "repo_path": str(repo_path),
                "lang": "kotlin",
                "is_dependency": False,
                "functions": [
                    {
                        "name": "run",
                        "line_number": 3,
                        "args": [],
                        "class_context": "Worker",
                        "class_context_line": 2,
                    },
                    {
                        "name": "run",
                        "line_number": 8,
                        "args": [],
                        "class_context": "Worker",
                        "class_context_line": 7,
                    },
                ],
                "classes": [
                    {"name": "Worker", "line_number": 2, "node_type": "class_declaration"},
                    {"name": "Worker", "line_number": 7, "node_type": "class_declaration"},
                ],
                "variables": [],
                "imports": [],
                "function_calls": [],
            },
            repo_path.name,
            {},
            repo_path_str=str(repo_path),
        )

        with driver.session() as session:
            first_owner = session.run(
                """
                MATCH (:Class {name: $class_name, path: $path, line_number: $class_line})
                      -[:CONTAINS]->
                      (fn:Function {name: $function_name, path: $path})
                RETURN fn.line_number AS line_number
                ORDER BY line_number
                """,
                class_name="Worker",
                function_name="run",
                path=file_path.resolve().as_posix(),
                class_line=2,
            ).data()
            second_owner = session.run(
                """
                MATCH (:Class {name: $class_name, path: $path, line_number: $class_line})
                      -[:CONTAINS]->
                      (fn:Function {name: $function_name, path: $path})
                RETURN fn.line_number AS line_number
                ORDER BY line_number
                """,
                class_name="Worker",
                function_name="run",
                path=file_path.resolve().as_posix(),
                class_line=7,
            ).data()

        assert first_owner == [{"line_number": 3}]
        assert second_owner == [{"line_number": 8}]
    finally:
        manager.close_driver()


def test_kotlin_decorators_persist_in_kuzu(tmp_path):
    """Annotations must survive the writer and the Kuzu property allow-list.

    Everything else in this feature is parser-level. This is the test that
    backs the claim that find_dead_code(exclude_decorated_with=...) works
    for Kotlin.
    """
    from codegraphcontext.tools.languages.kotlin import KotlinTreeSitterParser
    from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager

    manager_ts = get_tree_sitter_manager()
    wrapper = MagicMock()
    wrapper.language_name = "kotlin"
    wrapper.language = manager_ts.get_language_safe("kotlin")
    wrapper.parser = manager_ts.create_parser("kotlin")
    parser = KotlinTreeSitterParser(wrapper)

    source = tmp_path / "Android.kt"
    source.write_text(
        'package a\n'
        '\n'
        '@Composable\n'
        '@Preview(showBackground = true)\n'
        'fun GreetingPreview() {\n'
        '}\n'
        '\n'
        '@HiltViewModel\n'
        'class UserViewModel {\n'
        '    fun load(): String {\n'
        '        return "u"\n'
        '    }\n'
        '}\n',
        encoding="utf-8",
    )
    file_data = parser.parse(source)

    manager = _fresh_kuzu_manager(tmp_path / "decorators-db")
    try:
        driver = manager.get_driver()
        GraphWriter(driver).add_file_to_graph(
            file_data, "repo", {}, repo_path_str=str(tmp_path)
        )

        with driver.session() as session:
            fn = session.run(
                "MATCH (f:Function {name: $name}) RETURN f.decorators AS decorators",
                name="GreetingPreview",
            ).single()
            cls = session.run(
                "MATCH (c:Class {name: $name}) RETURN c.decorators AS decorators",
                name="UserViewModel",
            ).single()

            # The writer normalizes [] -> [""] (writer.py:405) for every language,
            # so the stored value is not literally []. What the feature actually
            # claims is that find_dead_code's filter behaves correctly, so assert
            # that directly -- this is the exact predicate the tool builds
            # (code_finder.py:816-820). Before this change, un-annotated Kotlin
            # functions stored NULL, and the predicate silently dropped them.
            retained = session.run(
                """
                MATCH (f:Function)
                WHERE NOT ANY(d IN f.decorators WHERE d CONTAINS 'Preview')
                RETURN f.name AS name
                """
            ).data()

        assert fn is not None
        assert fn["decorators"] == ["@Composable", "@Preview(showBackground = true)"]

        assert cls is not None
        assert cls["decorators"] == ["@HiltViewModel"]

        assert {r["name"] for r in retained} == {"load"}
    finally:
        manager.close_driver()


def test_write_inheritance_links_skips_empty_label_pairs_in_kuzu(tmp_path):
    """write_inheritance_links used to UNWIND-query all 12*12 (child, parent)
    label combinations regardless of whether either node table held any
    rows -- 144 pair queries plus 12 external-batch queries per call, most
    of them pure waste against empty Kuzu node tables. It now probes which
    of the 12 labels have at least one row and skips any pair where either
    side is empty.

    This test creates only two Class nodes (Base, Derived), so 11 of the 12
    labels are empty tables. It asserts both halves of the contract: the
    INHERITS edge for the real Class->Class hierarchy must still be created
    (the skip must never drop a real edge), and the number of session.run
    calls issued must stay far below the naive 12*12 + 12 = 156 fan-out the
    unoptimized code would have issued.
    """
    manager = _fresh_kuzu_manager(tmp_path / "inherits-skip-db")
    try:
        driver = manager.get_driver()
        with driver.session() as session:
            session.run(
                """
                MERGE (c:Class {uid: $uid})
                SET c.name = $name, c.path = $path, c.line_number = $line_number
                """,
                uid="base",
                name="Base",
                path="/repo/Hierarchy.kt",
                line_number=2,
            )
            session.run(
                """
                MERGE (c:Class {uid: $uid})
                SET c.name = $name, c.path = $path, c.line_number = $line_number
                """,
                uid="derived",
                name="Derived",
                path="/repo/Hierarchy.kt",
                line_number=6,
            )

        writer = GraphWriter(driver)

        session_cls = type(driver.session())
        original_run = session_cls.run
        call_count = 0

        def counting_run(self, query, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            return original_run(self, query, *args, **kwargs)

        session_cls.run = counting_run
        try:
            writer.write_inheritance_links(
                [
                    {
                        "child_name": "Derived",
                        "path": "/repo/Hierarchy.kt",
                        "parent_name": "Base",
                        "resolved_parent_file_path": "/repo/Hierarchy.kt",
                        "confidence_label": "EXTRACTED",
                    }
                ],
                [],
                {},
            )
        finally:
            session_cls.run = original_run

        with driver.session() as session:
            edge = session.run(
                """
                MATCH (child:Class {name: $child_name, path: $path})
                      -[r:INHERITS]->
                      (parent:Class {name: $parent_name, path: $path})
                RETURN r.confidence_label AS confidence_label
                """,
                child_name="Derived",
                parent_name="Base",
                path="/repo/Hierarchy.kt",
            ).data()

        assert edge == [{"confidence_label": "EXTRACTED"}]

        # Unoptimized fan-out: 12*12 internal pair queries + 12 external
        # per-label queries = 156, every one of them a full Kuzu parse ->
        # bind -> plan for a table that (in this test) is empty 11/12 of
        # the time. The skip should reduce this to a handful of existence
        # probes plus the one populated (Class, Class) pair.
        naive_fanout = 12 * 12 + 12
        assert call_count < naive_fanout
        assert call_count <= 20
    finally:
        manager.close_driver()


def test_write_inheritance_links_probe_failure_falls_back_to_populated_in_kuzu(tmp_path):
    """If the existence probe for a label raises for any reason, that label
    must be treated as populated (i.e. fall back to the old, unconditional
    behaviour) rather than skipped -- the task's explicit invariant is that
    the optimisation must never cause a *missed* edge.

    This forces the probe for `Class` specifically to raise, and asserts the
    Derived->Base INHERITS edge is still created despite the probe failure
    -- proving the fallback path keeps Class in the populated set instead of
    incorrectly skipping every pair involving it.
    """
    manager = _fresh_kuzu_manager(tmp_path / "inherits-probe-failure-db")
    try:
        driver = manager.get_driver()
        with driver.session() as session:
            session.run(
                """
                MERGE (c:Class {uid: $uid})
                SET c.name = $name, c.path = $path, c.line_number = $line_number
                """,
                uid="base",
                name="Base",
                path="/repo/Hierarchy.kt",
                line_number=2,
            )
            session.run(
                """
                MERGE (c:Class {uid: $uid})
                SET c.name = $name, c.path = $path, c.line_number = $line_number
                """,
                uid="derived",
                name="Derived",
                path="/repo/Hierarchy.kt",
                line_number=6,
            )

        writer = GraphWriter(driver)

        session_cls = type(driver.session())
        original_run = session_cls.run

        def failing_probe_run(self, query, *args, **kwargs):
            if "MATCH (n:Class)" in query and "LIMIT 1" in query:
                raise RuntimeError("simulated existence-probe failure")
            return original_run(self, query, *args, **kwargs)

        session_cls.run = failing_probe_run
        try:
            writer.write_inheritance_links(
                [
                    {
                        "child_name": "Derived",
                        "path": "/repo/Hierarchy.kt",
                        "parent_name": "Base",
                        "resolved_parent_file_path": "/repo/Hierarchy.kt",
                        "confidence_label": "EXTRACTED",
                    }
                ],
                [],
                {},
            )
        finally:
            session_cls.run = original_run

        with driver.session() as session:
            edge = session.run(
                """
                MATCH (child:Class {name: $child_name, path: $path})
                      -[r:INHERITS]->
                      (parent:Class {name: $parent_name, path: $path})
                RETURN r.confidence_label AS confidence_label
                """,
                child_name="Derived",
                parent_name="Base",
                path="/repo/Hierarchy.kt",
            ).data()

        assert edge == [{"confidence_label": "EXTRACTED"}]
    finally:
        manager.close_driver()


def test_write_inheritance_links_resolves_cross_label_hierarchy_with_empty_labels_skipped(tmp_path):
    """The skip optimisation gates the child loop and the parent loop
    independently via a shared `populated_labels` set -- it does not gate
    on a single (child, parent) pair being "the same label". Both of the
    tests added by 500f87e only ever create Class->Class hierarchies, so
    neither one would catch a future refactor that broke resolution across
    two *different*, both-populated labels (e.g. accidentally intersecting
    populated_labels per-loop instead of sharing it, or only probing the
    child's labels).

    This test creates one Class node and one Interface node (both
    populated, different labels) and leaves the other ten labels (Trait,
    Struct, Enum, Union, Record, Mixin, Extension, Module, Object,
    Variable) empty, so the skip path is genuinely active for most of the
    12*12 grid while the Class->Interface pair must still be probed as
    populated on both sides and produce an edge. It asserts the INHERITS
    edge runs specifically from the Class to the Interface, not merely
    that some edge exists.
    """
    manager = _fresh_kuzu_manager(tmp_path / "inherits-cross-label-db")
    try:
        driver = manager.get_driver()
        with driver.session() as session:
            session.run(
                """
                MERGE (c:Class {uid: $uid})
                SET c.name = $name, c.path = $path, c.line_number = $line_number
                """,
                uid="widget",
                name="Widget",
                path="/repo/Widget.kt",
                line_number=2,
            )
            session.run(
                """
                MERGE (i:Interface {uid: $uid})
                SET i.name = $name, i.path = $path, i.line_number = $line_number
                """,
                uid="drawable",
                name="Drawable",
                path="/repo/Widget.kt",
                line_number=1,
            )

        writer = GraphWriter(driver)
        writer.write_inheritance_links(
            [
                {
                    "child_name": "Widget",
                    "path": "/repo/Widget.kt",
                    "parent_name": "Drawable",
                    "resolved_parent_file_path": "/repo/Widget.kt",
                    "confidence_label": "EXTRACTED",
                }
            ],
            [],
            {},
        )

        with driver.session() as session:
            edge = session.run(
                """
                MATCH (child:Class {name: $child_name, path: $path})
                      -[r:INHERITS]->
                      (parent:Interface {name: $parent_name, path: $path})
                RETURN r.confidence_label AS confidence_label
                """,
                child_name="Widget",
                parent_name="Drawable",
                path="/repo/Widget.kt",
            ).data()

        assert edge == [{"confidence_label": "EXTRACTED"}]

        # Confirm there is exactly one INHERITS edge overall, and that it is
        # the Class->Interface one -- not just "some edge exists" that could
        # be satisfied by an unrelated or misdirected match.
        with driver.session() as session:
            all_edges = session.run(
                """
                MATCH (child)-[r:INHERITS]->(parent)
                RETURN labels(child) AS child_labels, child.name AS child_name,
                       labels(parent) AS parent_labels, parent.name AS parent_name
                """
            ).data()

        assert len(all_edges) == 1
        assert all_edges[0]["child_name"] == "Widget"
        assert all_edges[0]["parent_name"] == "Drawable"
        assert "Class" in all_edges[0]["child_labels"]
        assert "Interface" in all_edges[0]["parent_labels"]
    finally:
        manager.close_driver()


