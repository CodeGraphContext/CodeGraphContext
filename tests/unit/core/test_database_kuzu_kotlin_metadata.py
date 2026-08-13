from pathlib import Path
from unittest.mock import MagicMock

import pytest

pytest.importorskip("kuzu")

import kuzu

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


def test_is_composable_persists_in_kuzu(tmp_path):
    """The is_composable flag must survive the writer's property allow-list.

    Both True and False must round-trip correctly to catch falsy-drop bugs.
    """
    from codegraphcontext.tools.languages.kotlin import KotlinTreeSitterParser
    from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager

    manager_ts = get_tree_sitter_manager()
    wrapper = MagicMock()
    wrapper.language_name = "kotlin"
    wrapper.language = manager_ts.get_language_safe("kotlin")
    wrapper.parser = manager_ts.create_parser("kotlin")
    parser = KotlinTreeSitterParser(wrapper)

    source = tmp_path / "Compose.kt"
    source.write_text(
        'package a\n'
        '\n'
        '@Composable\n'
        'fun MyComposable() {\n'
        '}\n'
        '\n'
        'fun plainFunction() {\n'
        '}\n',
        encoding="utf-8",
    )
    file_data = parser.parse(source)

    manager = _fresh_kuzu_manager(tmp_path / "is-composable-db")
    try:
        driver = manager.get_driver()
        GraphWriter(driver).add_file_to_graph(
            file_data, "repo", {}, repo_path_str=str(tmp_path)
        )

        with driver.session() as session:
            fn_composable = session.run(
                "MATCH (f:Function {name: $name}) RETURN f.is_composable AS is_composable",
                name="MyComposable",
            ).single()
            fn_plain = session.run(
                "MATCH (f:Function {name: $name}) RETURN f.is_composable AS is_composable",
                name="plainFunction",
            ).single()

        assert fn_composable is not None
        assert fn_composable["is_composable"] is True

        assert fn_plain is not None
        assert fn_plain["is_composable"] is False
    finally:
        manager.close_driver()


def test_modifier_columns_persist_in_kuzu(tmp_path):
    """The 1b columns must survive the writer's property allow-list."""
    manager = _fresh_kuzu_manager(tmp_path / "modifiers-db")
    try:
        driver = manager.get_driver()
        file_data = {
            "path": "/repo/Mods.kt",
            "lang": "kotlin",
            "is_dependency": False,
            "functions": [
                {
                    "name": "onCreate",
                    "path": "/repo/Mods.kt",
                    "line_number": 3,
                    "end_line": 4,
                    "decorators": [],
                    "args": [],
                    "visibility": "public",
                    "modifiers": ["override"],
                }
            ],
            "classes": [
                {
                    "name": "State",
                    "path": "/repo/Mods.kt",
                    "line_number": 8,
                    "end_line": 9,
                    "decorators": [],
                    "visibility": "internal",
                    "modifiers": ["sealed"],
                }
            ],
            "interfaces": [
                {
                    "name": "UserDao",
                    "path": "/repo/Mods.kt",
                    "line_number": 12,
                    "end_line": 13,
                    "decorators": ["@Dao"],
                }
            ],
            "objects": [
                {
                    "name": "AppModule",
                    "path": "/repo/Mods.kt",
                    "line_number": 16,
                    "end_line": 17,
                    "decorators": ["@Module"],
                }
            ],
        }
        GraphWriter(driver).add_file_to_graph(
            file_data, "repo", {}, repo_path_str="/repo"
        )

        with driver.session() as session:
            fn = session.run(
                "MATCH (f:Function {name: $n}) RETURN f.visibility AS v, f.modifiers AS m",
                n="onCreate",
            ).single()
            cls = session.run(
                "MATCH (c:Class {name: $n}) RETURN c.visibility AS v, c.modifiers AS m",
                n="State",
            ).single()
            iface = session.run(
                "MATCH (i:Interface {name: $n}) RETURN i.decorators AS d", n="UserDao"
            ).single()
            obj = session.run(
                "MATCH (o:Object {name: $n}) RETURN o.decorators AS d", n="AppModule"
            ).single()

        assert fn is not None and fn["v"] == "public" and fn["m"] == ["override"]
        assert cls is not None and cls["v"] == "internal" and cls["m"] == ["sealed"]
        assert iface is not None and iface["d"] == ["@Dao"]
        assert obj is not None and obj["d"] == ["@Module"]
    finally:
        manager.close_driver()


def test_visibility_modifiers_decorators_migrate_onto_pre_existing_kuzu_db(tmp_path):
    """visibility/modifiers/decorators must reach a database that already
    existed before those columns were added to the node-table declaration.

    _initialize_schema's CREATE NODE TABLE only helps a brand-new database --
    on a pre-existing one it raises "already exists" and that exception is
    swallowed (see _initialize_schema below), so a column that ships only in
    the CREATE NODE TABLE string never reaches an already-indexed repo. It
    must also have an entry in simple_migrations, which runs ALTER TABLE ...
    ADD against existing tables. This test builds Function/Class/Interface/
    Object tables by hand, without the new columns, then opens that same
    database through KuzuDBManager (which runs _initialize_schema and the
    migrations) and checks the columns actually landed.
    """
    db_path = tmp_path / "pre-existing-metadata-db"

    db = kuzu.Database(str(db_path))
    conn = kuzu.Connection(db)
    conn.execute(
        "CREATE NODE TABLE Function(uid STRING, name STRING, path STRING, "
        "line_number INT64, PRIMARY KEY (uid))"
    )
    conn.execute(
        "CREATE NODE TABLE Class(uid STRING, name STRING, path STRING, "
        "line_number INT64, PRIMARY KEY (uid))"
    )
    conn.execute(
        "CREATE NODE TABLE Interface(uid STRING, name STRING, path STRING, "
        "line_number INT64, PRIMARY KEY (uid))"
    )
    conn.execute(
        "CREATE NODE TABLE Object(uid STRING, name STRING, path STRING, "
        "line_number INT64, PRIMARY KEY (uid))"
    )
    conn.close()
    db.close()

    manager = _fresh_kuzu_manager(db_path)
    try:
        driver = manager.get_driver()
        with driver.session() as session:
            function_columns = {
                row["name"]
                for row in session.run("CALL TABLE_INFO('Function') RETURN *").data()
            }
            class_columns = {
                row["name"]
                for row in session.run("CALL TABLE_INFO('Class') RETURN *").data()
            }
            interface_columns = {
                row["name"]
                for row in session.run("CALL TABLE_INFO('Interface') RETURN *").data()
            }
            object_columns = {
                row["name"]
                for row in session.run("CALL TABLE_INFO('Object') RETURN *").data()
            }

        assert {"visibility", "modifiers"} <= function_columns
        assert {"visibility", "modifiers"} <= class_columns
        assert "decorators" in interface_columns
        assert "decorators" in object_columns
    finally:
        manager.close_driver()


def test_interface_object_visibility_modifiers_persist_in_kuzu(tmp_path):
    """The Kotlin parser sets visibility/modifiers on interfaces and objects
    too (e.g. `internal interface Repo`, `private object Holder`), not just
    on classes and functions. The Interface/Object node tables and the
    SCHEMA_MAP allow-list must carry those two columns through, or the
    allow-list `continue` silently drops them on Kuzu while schemaless
    backends (Neo4j, FalkorDB) keep them -- a backend-parity divergence.
    """
    manager = _fresh_kuzu_manager(tmp_path / "interface-object-modifiers-db")
    try:
        driver = manager.get_driver()
        file_data = {
            "path": "/repo/Mods.kt",
            "lang": "kotlin",
            "is_dependency": False,
            "interfaces": [
                {
                    "name": "Repo",
                    "path": "/repo/Mods.kt",
                    "line_number": 12,
                    "end_line": 13,
                    "decorators": [],
                    "visibility": "internal",
                    "modifiers": ["sealed"],
                }
            ],
            "objects": [
                {
                    "name": "Holder",
                    "path": "/repo/Mods.kt",
                    "line_number": 16,
                    "end_line": 17,
                    "decorators": [],
                    "visibility": "private",
                    "modifiers": [],
                }
            ],
        }
        GraphWriter(driver).add_file_to_graph(
            file_data, "repo", {}, repo_path_str="/repo"
        )

        with driver.session() as session:
            iface = session.run(
                "MATCH (i:Interface {name: $n}) RETURN i.visibility AS v, i.modifiers AS m",
                n="Repo",
            ).single()
            obj = session.run(
                "MATCH (o:Object {name: $n}) RETURN o.visibility AS v, o.modifiers AS m",
                n="Holder",
            ).single()

        assert iface is not None
        assert iface["v"] == "internal"
        assert iface["m"] == ["sealed"]

        assert obj is not None
        assert obj["v"] == "private"
        assert obj["m"] is not None
    finally:
        manager.close_driver()


def test_interface_object_visibility_modifiers_migrate_onto_pre_existing_kuzu_db(tmp_path):
    """visibility/modifiers on Interface/Object must reach a database that
    already existed before those columns were added to the node-table
    declaration. _initialize_schema's CREATE NODE TABLE only helps a
    brand-new database -- on a pre-existing one it raises "already exists"
    and that exception is swallowed, so a column that ships only in the
    CREATE NODE TABLE string never reaches an already-indexed repo. It must
    also have an entry in simple_migrations, which runs ALTER TABLE ... ADD
    against existing tables. This test builds Interface/Object tables by
    hand, without the new columns, then opens that same database through
    KuzuDBManager (which runs _initialize_schema and the migrations) and
    checks the columns actually landed.
    """
    db_path = tmp_path / "pre-existing-interface-object-modifiers-db"

    db = kuzu.Database(str(db_path))
    conn = kuzu.Connection(db)
    conn.execute(
        "CREATE NODE TABLE Interface(uid STRING, name STRING, path STRING, "
        "line_number INT64, decorators STRING[], PRIMARY KEY (uid))"
    )
    conn.execute(
        "CREATE NODE TABLE Object(uid STRING, name STRING, path STRING, "
        "line_number INT64, decorators STRING[], PRIMARY KEY (uid))"
    )
    conn.close()
    db.close()

    manager = _fresh_kuzu_manager(db_path)
    try:
        driver = manager.get_driver()
        with driver.session() as session:
            interface_columns = {
                row["name"]
                for row in session.run("CALL TABLE_INFO('Interface') RETURN *").data()
            }
            object_columns = {
                row["name"]
                for row in session.run("CALL TABLE_INFO('Object') RETURN *").data()
            }

        assert {"visibility", "modifiers"} <= interface_columns
        assert {"visibility", "modifiers"} <= object_columns
    finally:
        manager.close_driver()


def test_write_binds_links_creates_kuzu_edge_between_interface_and_class(tmp_path):
    """Hilt's @Binds is the only link between an interface and its impl class.

    write_binds_links MATCHes existing nodes rather than creating them, so
    this test creates the Interface and Class first -- otherwise the MERGE
    would silently match nothing and the test would pass vacuously.
    """
    manager = _fresh_kuzu_manager(tmp_path / "binds-db")
    try:
        driver = manager.get_driver()
        with driver.session() as session:
            session.run(
                """
                MERGE (i:Interface {uid: $uid})
                SET i.name = $name, i.path = $path, i.line_number = $line_number
                """,
                uid="iface-1",
                name="UserRepository",
                path="/repo/UserRepository.kt",
                line_number=3,
            )
            session.run(
                """
                MERGE (c:Class {uid: $uid})
                SET c.name = $name, c.path = $path, c.line_number = $line_number
                """,
                uid="class-1",
                name="UserRepositoryImpl",
                path="/repo/UserRepositoryImpl.kt",
                line_number=5,
            )

        writer = GraphWriter(driver)
        writer.write_binds_links(
            [
                {
                    "source_name": "UserRepository",
                    "source_path": "/repo/UserRepository.kt",
                    "target_name": "UserRepositoryImpl",
                    "target_path": "/repo/UserRepositoryImpl.kt",
                    "line_number": 12,
                    "provider": "Binds",
                    "confidence_label": "EXTRACTED",
                }
            ]
        )

        with driver.session() as session:
            rows = session.run(
                """
                MATCH (:Interface {name: $source_name, path: $source_path})
                      -[r:BINDS]->
                      (:Class {name: $target_name, path: $target_path})
                RETURN r.line_number AS line_number, r.provider AS provider
                """,
                source_name="UserRepository",
                source_path="/repo/UserRepository.kt",
                target_name="UserRepositoryImpl",
                target_path="/repo/UserRepositoryImpl.kt",
            ).data()
            total = session.run(
                "MATCH ()-[r:BINDS]->() RETURN count(r) AS n"
            ).single()

        assert rows == [{"line_number": 12, "provider": "Binds"}]
        assert total is not None and total["n"] == 1
    finally:
        manager.close_driver()


def test_write_binds_links_does_not_create_spurious_edge_from_same_named_node(tmp_path):
    """A same-named node under a different label must not pick up an edge.

    Kotlin does not qualify `name` by enclosing scope (kotlin.py:1394-1436),
    so a top-level `interface Foo` and an unrelated nested `class Foo` can
    legitimately share name+path. write_binds_links tries every declared
    (source_label, target_label) pair since the row carries no label -- it
    must stop at the first pair that actually matches real endpoints, or the
    coincidentally same-named Class would also match and produce a second,
    spurious BINDS edge for the same row.
    """
    manager = _fresh_kuzu_manager(tmp_path / "binds-same-name-db")
    try:
        driver = manager.get_driver()
        with driver.session() as session:
            session.run(
                """
                MERGE (i:Interface {uid: $uid})
                SET i.name = $name, i.path = $path, i.line_number = $line_number
                """,
                uid="iface-foo",
                name="Foo",
                path="/a.kt",
                line_number=1,
            )
            # An unrelated Class that happens to share name+path with the
            # Interface above -- e.g. a nested `class Foo` in the same file.
            session.run(
                """
                MERGE (c:Class {uid: $uid})
                SET c.name = $name, c.path = $path, c.line_number = $line_number
                """,
                uid="class-foo",
                name="Foo",
                path="/a.kt",
                line_number=20,
            )
            session.run(
                """
                MERGE (c:Class {uid: $uid})
                SET c.name = $name, c.path = $path, c.line_number = $line_number
                """,
                uid="class-fooimpl",
                name="FooImpl",
                path="/a.kt",
                line_number=30,
            )

        writer = GraphWriter(driver)
        writer.write_binds_links(
            [
                {
                    "source_name": "Foo",
                    "source_path": "/a.kt",
                    "target_name": "FooImpl",
                    "target_path": "/a.kt",
                    "line_number": 5,
                    "provider": "Binds",
                    "confidence_label": "EXTRACTED",
                }
            ]
        )

        with driver.session() as session:
            total = session.run(
                "MATCH ()-[r:BINDS]->() RETURN count(r) AS n"
            ).single()
            from_interface = session.run(
                """
                MATCH (:Interface {name: $name, path: $path})-[r:BINDS]->(:Class {name: $target})
                RETURN count(r) AS n
                """,
                name="Foo",
                path="/a.kt",
                target="FooImpl",
            ).single()
            from_class = session.run(
                """
                MATCH (:Class {name: $name, path: $path})-[r:BINDS]->(:Class {name: $target})
                RETURN count(r) AS n
                """,
                name="Foo",
                path="/a.kt",
                target="FooImpl",
            ).single()

        assert total is not None and total["n"] == 1
        assert from_interface is not None and from_interface["n"] == 1
        assert from_class is not None and from_class["n"] == 0
    finally:
        manager.close_driver()


def test_write_previews_links_creates_kuzu_edge_between_functions(tmp_path):
    """A @Preview function's edge to the composable it renders must
    persist and be queryable, and a composable with no inbound PREVIEWS
    edge must be identifiable -- that second query is the actual point of
    this relationship ("which composables have no preview").

    write_previews_links MATCHes existing nodes rather than creating them,
    so this test creates the Function nodes first -- otherwise the MERGE
    would silently match nothing and the test would pass vacuously.
    """
    manager = _fresh_kuzu_manager(tmp_path / "previews-db")
    try:
        driver = manager.get_driver()
        with driver.session() as session:
            session.run(
                """
                MERGE (f:Function {uid: $uid})
                SET f.name = $name, f.path = $path, f.line_number = $line_number,
                    f.is_composable = $is_composable
                """,
                uid="fn-greeting",
                name="Greeting",
                path="/repo/AndroidAnnotations.kt",
                line_number=13,
                is_composable=True,
            )
            session.run(
                """
                MERGE (f:Function {uid: $uid})
                SET f.name = $name, f.path = $path, f.line_number = $line_number,
                    f.is_composable = $is_composable
                """,
                uid="fn-label",
                name="Label",
                path="/repo/AndroidAnnotations.kt",
                line_number=18,
                is_composable=True,
            )
            session.run(
                """
                MERGE (f:Function {uid: $uid})
                SET f.name = $name, f.path = $path, f.line_number = $line_number,
                    f.is_composable = $is_composable
                """,
                uid="fn-greeting-preview",
                name="GreetingPreview",
                path="/repo/AndroidAnnotations.kt",
                line_number=23,
                is_composable=True,
            )

        writer = GraphWriter(driver)
        writer.write_previews_links(
            [
                {
                    "preview_name": "GreetingPreview",
                    "preview_path": "/repo/AndroidAnnotations.kt",
                    "preview_line": 23,
                    "composable_name": "Greeting",
                    "composable_path": "/repo/AndroidAnnotations.kt",
                    "line_number": 23,
                    "confidence_label": "EXTRACTED",
                }
            ]
        )

        with driver.session() as session:
            edge = session.run(
                """
                MATCH (:Function {name: $preview_name, path: $path})
                      -[r:PREVIEWS]->
                      (:Function {name: $composable_name, path: $path})
                RETURN r.line_number AS line_number
                """,
                preview_name="GreetingPreview",
                composable_name="Greeting",
                path="/repo/AndroidAnnotations.kt",
            ).data()
            total = session.run(
                "MATCH ()-[r:PREVIEWS]->() RETURN count(r) AS n"
            ).single()

            # The query PREVIEWS exists to answer: which composables have
            # no inbound preview edge. Label must come back as one of
            # them; Greeting must not.
            unpreviewed = session.run(
                """
                MATCH (f:Function {path: $path})
                WHERE f.is_composable = true
                OPTIONAL MATCH (:Function)-[r:PREVIEWS]->(f)
                WITH f, r
                WHERE r IS NULL
                RETURN f.name AS name
                """,
                path="/repo/AndroidAnnotations.kt",
            ).data()

        assert edge == [{"line_number": 23}]
        assert total is not None and total["n"] == 1
        unpreviewed_names = {r["name"] for r in unpreviewed}
        assert "Label" in unpreviewed_names
        assert "Greeting" not in unpreviewed_names
    finally:
        manager.close_driver()
