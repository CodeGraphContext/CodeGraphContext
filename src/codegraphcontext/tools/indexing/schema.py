# src/codegraphcontext/tools/indexing/schema.py
"""Create constraints and indexes for graph backends (Neo4j / Falkor-style Cypher)."""

from typing import Any

from ...utils.debug_log import info_logger, warning_logger


# Labels whose node identity is positional: (name, path, line_number,
# occurrence_index). occurrence_index was added in #1393 because
# (name, path, line_number) is not unique -- a grouped CSS rule or a minified
# JS bundle produces several distinct symbols sharing a name and a line, and
# the old UNIQUE constraints below actively prevented the writer from keeping
# them apart. Maps label -> the Cypher variable used in its DDL.
POSITIONAL_IDENTITY_LABELS = {
    "Function": "f",
    "Class": "c",
    "Trait": "t",
    "Interface": "i",
    "Macro": "m",
    "Variable": "v",
    "Struct": "s",
    "Enum": "e",
    "Union": "u",
    "Record": "r",
    "Property": "p",
}

# Old three-property UNIQUE constraints, dropped so existing databases migrate.
# Recreating under a new name keeps the DROP a no-op on subsequent startups,
# which matters because rebuilding a constraint on a large graph is expensive.
_LEGACY_IDENTITY_CONSTRAINTS = {
    "Function": "function_unique",
    "Class": "class_unique",
    "Trait": "trait_unique",
    "Interface": "interface_unique",
    "Macro": "macro_unique",
    "Variable": "variable_unique",
    "Struct": "struct_cpp",
    "Enum": "enum_cpp",
    "Union": "union_cpp",
    "Record": "record_unique",
    "Property": "property_unique",
}


class _DDLRunner:
    """Runs schema DDL so that one failing statement cannot skip the rest.

    Every statement here is independent (`CREATE INDEX ...` on a distinct
    label), but they used to share a single try/except: the first failure
    aborted the remaining ~35, leaving the graph without indexes on Class,
    Variable, Parameter and friends. Every `MERGE` then degenerated into a
    full label scan, turning indexing quadratic with nothing surfaced.
    """

    def __init__(self, session: Any) -> None:
        self._session = session
        self.attempted = 0
        self.failures: list[tuple[str, str]] = []

    def run(self, statement: str, *args: Any, **kwargs: Any) -> Any:
        self.attempted += 1
        try:
            return self._session.run(statement, *args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - one bad statement must not stop the rest
            self.failures.append((" ".join(statement.split())[:120], str(exc)))
            return None


def create_graph_schema(driver: Any, db_manager: Any) -> None:
    """Create constraints and indexes. *driver* must support .session() context manager."""
    backend_type = getattr(db_manager, "get_backend_type", lambda: "neo4j")()
    # FalkorDB (both embedded and remote) has a confirmed null-pointer crash in
    # EnforceUniqueEntity when composite UNIQUE constraints are used with MERGE,
    # so all CREATE CONSTRAINT statements are skipped for FalkorDB backends.
    #
    # Be precise about what that costs: there are then NO uniqueness constraints
    # on FalkorDB — `CALL db.constraints()` returns []. Indexes do not enforce
    # uniqueness; they only make the MERGE lookup fast. Deduplication holds
    # because MERGE deduplicates within an UNWIND and FalkorDB serialises writes
    # per graph, not because the schema guarantees it. That assumption breaks
    # with an external writer or a future FalkorDB executing writes
    # concurrently. (The previous comment claimed the indexes were "sufficient
    # for MERGE to perform correct deduplication", which overstates it.)
    is_falkordb = backend_type.startswith("falkordb")

    with driver.session() as session:
        ddl = _DDLRunner(session)
        try:
            if is_falkordb:
                # FalkorDB requires a supporting index to exist BEFORE creating a UNIQUE constraint.
                ddl.run("CREATE INDEX IF NOT EXISTS FOR (r:Repository) ON (r.path)")
                ddl.run("CREATE INDEX IF NOT EXISTS FOR (f:File) ON (f.path)")
                ddl.run("CREATE INDEX IF NOT EXISTS FOR (d:Directory) ON (d.path)")
                ddl.run("CREATE INDEX IF NOT EXISTS FOR (m:Module) ON (m.name)")
                # occurrence_index is part of the MERGE key for these labels
                # (#1393), so it belongs in the supporting index.
                for _label, _var in POSITIONAL_IDENTITY_LABELS.items():
                    ddl.run(
                        f"CREATE INDEX IF NOT EXISTS FOR ({_var}:{_label}) "
                        f"ON ({_var}.name, {_var}.path, {_var}.line_number, {_var}.occurrence_index)"
                    )
                ddl.run("CREATE INDEX IF NOT EXISTS FOR (a:Annotation) ON (a.name, a.path, a.line_number)")
                ddl.run("CREATE INDEX IF NOT EXISTS FOR (em:EnumMember) ON (em.name, em.path)")
                ddl.run("CREATE INDEX IF NOT EXISTS FOR (o:Object) ON (o.name, o.path, o.line_number)")
                ddl.run("CREATE INDEX IF NOT EXISTS FOR (mx:Mixin) ON (mx.name, mx.path, mx.line_number)")
                ddl.run("CREATE INDEX IF NOT EXISTS FOR (ex:Extension) ON (ex.name, ex.path, ex.line_number)")
                ddl.run("CREATE INDEX IF NOT EXISTS FOR (p:Parameter) ON (p.name, p.path, p.function_line_number)")

            if not is_falkordb:
                ddl.run(
                    "CREATE CONSTRAINT repository_path IF NOT EXISTS FOR (r:Repository) REQUIRE r.path IS UNIQUE"
                )
                ddl.run("CREATE CONSTRAINT path IF NOT EXISTS FOR (f:File) REQUIRE f.path IS UNIQUE")
                ddl.run(
                    "CREATE CONSTRAINT directory_path IF NOT EXISTS FOR (d:Directory) REQUIRE d.path IS UNIQUE"
                )
                # (name, path, line_number) is not a unique identity: a grouped
                # CSS rule such as `tfoot th, tfoot td { }` emits two `tfoot`
                # selectors on one line, and a minified JS bundle puts every
                # function on line 1. These constraints made that unfixable --
                # the writer could not create the second node even once it knew
                # the two symbols were distinct. Drop them in favour of the
                # four-property identity that includes occurrence_index (#1393).
                for _label, _legacy_name in _LEGACY_IDENTITY_CONSTRAINTS.items():
                    ddl.run(f"DROP CONSTRAINT {_legacy_name} IF EXISTS")
                for _label, _var in POSITIONAL_IDENTITY_LABELS.items():
                    _constraint = f"{_label.lower()}_identity"
                    ddl.run(
                        f"CREATE CONSTRAINT {_constraint} IF NOT EXISTS "
                        f"FOR ({_var}:{_label}) REQUIRE "
                        f"({_var}.name, {_var}.path, {_var}.line_number, "
                        f"{_var}.occurrence_index) IS UNIQUE"
                    )
                ddl.run("CREATE CONSTRAINT module_name IF NOT EXISTS FOR (m:Module) REQUIRE m.name IS UNIQUE")
                ddl.run(
                    "CREATE CONSTRAINT annotation_unique IF NOT EXISTS FOR (a:Annotation) REQUIRE (a.name, a.path, a.line_number) IS UNIQUE"
                )
                # The relationship passes and code_finder look these nodes up
                # by (name, path) with no line_number: write_inheritance_links
                # matches `(child:<Label> {name: row.child_name, path:
                # row.path})`, and the same for the parent, for every label
                # pair it enumerates; write_function_call_groups matches the
                # callee by (name, path) in both the batched and the single-row
                # path; and code_finder's who_calls_function,
                # what_does_function_call, find_class_hierarchy,
                # find_all_callers and find_all_callees do the same.
                #
                # Neo4j uses a composite index only when EVERY indexed property
                # has a predicate, so the four-property identity constraints
                # above cannot serve those lookups -- the planner falls back to
                # NodeByLabelScan + Filter, once per row. These plain
                # two-property indexes restore an index seek. They do not
                # collide with the identity constraints: a constraint's backing
                # index covers a different property set, so the two coexist.
                #
                # FalkorDB is excluded (this is inside `not is_falkordb`): it
                # indexes per attribute, not per property tuple, and the
                # composite CREATE INDEX statements in its own branch already
                # cover name and path. A second (name, path) index would add
                # nothing there and only re-issue an index creation FalkorDB
                # rejects as "already indexed".
                for _label, _var in POSITIONAL_IDENTITY_LABELS.items():
                    ddl.run(
                        f"CREATE INDEX {_label.lower()}_name_path IF NOT EXISTS "
                        f"FOR ({_var}:{_label}) ON ({_var}.name, {_var}.path)"
                    )

            ddl.run("CREATE INDEX function_lang IF NOT EXISTS FOR (f:Function) ON (f.lang)")
            ddl.run("CREATE INDEX class_lang IF NOT EXISTS FOR (c:Class) ON (c.lang)")
            ddl.run("CREATE INDEX annotation_lang IF NOT EXISTS FOR (a:Annotation) ON (a.lang)")
            ddl.run(
                "CREATE INDEX parameter_unique IF NOT EXISTS FOR (p:Parameter) ON (p.name, p.path, p.function_line_number)"
            )

            if is_falkordb and backend_type == "falkordb":
                for label in ["Function", "Class"]:
                    try:
                        ddl.run(
                            f"CALL db.idx.fulltext.createNodeIndex('{label}', 'name', 'source', 'docstring')"
                        )
                    except Exception:
                        pass
            elif backend_type == "neo4j":
                ddl.run("""
                    CREATE FULLTEXT INDEX code_search_index IF NOT EXISTS
                    FOR (n:Function|Class|Variable)
                    ON EACH [n.name, n.source, n.docstring]
                """)

            if ddl.failures:
                warning_logger(
                    f"Database schema created with {len(ddl.failures)} failed "
                    f"statement(s) out of {ddl.attempted}; the affected indexes "
                    "are missing and MERGE-heavy queries may be slow."
                )
                for statement, error in ddl.failures:
                    warning_logger(f"  DDL failed: {statement} -> {error}")
            else:
                info_logger("Database schema verified/created successfully")
        except Exception as e:
            warning_logger(f"Schema creation warning: {e}")
