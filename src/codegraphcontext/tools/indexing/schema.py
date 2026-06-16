# src/codegraphcontext/tools/indexing/schema.py
"""Create constraints and indexes for graph backends (Neo4j / Falkor-style Cypher)."""

from typing import Any

from ...utils.debug_log import info_logger, warning_logger


def create_graph_schema(driver: Any, db_manager: Any) -> None:
    """Create constraints and indexes. *driver* must support .session() context manager."""
    backend_type = getattr(db_manager, "get_backend_type", lambda: "neo4j")()
    # FalkorDB (both embedded and remote) has a confirmed null-pointer crash in
    # EnforceUniqueEntity when composite UNIQUE constraints are used with MERGE.
    # Skip all CREATE CONSTRAINT statements for FalkorDB backends; the indices
    # created below are sufficient for MERGE to perform correct deduplication.
    is_falkordb = backend_type.startswith("falkordb")

    with driver.session() as session:
        try:
            if is_falkordb:
                # FalkorDB requires a supporting index to exist BEFORE creating a UNIQUE constraint.
                session.run("CREATE INDEX IF NOT EXISTS FOR (r:Repository) ON (r.path)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (f:File) ON (f.path)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (d:Directory) ON (d.path)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (m:Module) ON (m.name)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (f:Function) ON (f.name, f.path, f.line_number)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (c:Class) ON (c.name, c.path, c.line_number)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (t:Trait) ON (t.name, t.path, t.line_number)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (i:Interface) ON (i.name, i.path, i.line_number)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (m:Macro) ON (m.name, m.path, m.line_number)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (v:Variable) ON (v.name, v.path, v.line_number)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (s:Struct) ON (s.name, s.path, s.line_number)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (e:Enum) ON (e.name, e.path, e.line_number)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (u:Union) ON (u.name, u.path, u.line_number)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (a:Annotation) ON (a.name, a.path, a.line_number)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (r:Record) ON (r.name, r.path, r.line_number)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (p:Property) ON (p.name, p.path, p.line_number)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (em:EnumMember) ON (em.name, em.path)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (o:Object) ON (o.name, o.path, o.line_number)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (mx:Mixin) ON (mx.name, mx.path, mx.line_number)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (ex:Extension) ON (ex.name, ex.path, ex.line_number)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (p:Parameter) ON (p.name, p.path, p.function_line_number)")

            if not is_falkordb:
                session.run(
                    "CREATE CONSTRAINT repository_path IF NOT EXISTS FOR (r:Repository) REQUIRE r.path IS UNIQUE"
                )
                session.run("CREATE CONSTRAINT path IF NOT EXISTS FOR (f:File) REQUIRE f.path IS UNIQUE")
                session.run(
                    "CREATE CONSTRAINT directory_path IF NOT EXISTS FOR (d:Directory) REQUIRE d.path IS UNIQUE"
                )
                session.run(
                    "CREATE CONSTRAINT function_unique IF NOT EXISTS FOR (f:Function) REQUIRE (f.name, f.path, f.line_number) IS UNIQUE"
                )
                session.run(
                    "CREATE CONSTRAINT class_unique IF NOT EXISTS FOR (c:Class) REQUIRE (c.name, c.path, c.line_number) IS UNIQUE"
                )
                session.run(
                    "CREATE CONSTRAINT trait_unique IF NOT EXISTS FOR (t:Trait) REQUIRE (t.name, t.path, t.line_number) IS UNIQUE"
                )
                session.run(
                    "CREATE CONSTRAINT interface_unique IF NOT EXISTS FOR (i:Interface) REQUIRE (i.name, i.path, i.line_number) IS UNIQUE"
                )
                session.run(
                    "CREATE CONSTRAINT macro_unique IF NOT EXISTS FOR (m:Macro) REQUIRE (m.name, m.path, m.line_number) IS UNIQUE"
                )
                session.run(
                    "CREATE CONSTRAINT variable_unique IF NOT EXISTS FOR (v:Variable) REQUIRE (v.name, v.path, v.line_number) IS UNIQUE"
                )
                session.run("CREATE CONSTRAINT module_name IF NOT EXISTS FOR (m:Module) REQUIRE m.name IS UNIQUE")
                session.run(
                    "CREATE CONSTRAINT struct_cpp IF NOT EXISTS FOR (cstruct: Struct) REQUIRE (cstruct.name, cstruct.path, cstruct.line_number) IS UNIQUE"
                )
                session.run(
                    "CREATE CONSTRAINT enum_cpp IF NOT EXISTS FOR (cenum: Enum) REQUIRE (cenum.name, cenum.path, cenum.line_number) IS UNIQUE"
                )
                session.run(
                    "CREATE CONSTRAINT union_cpp IF NOT EXISTS FOR (cunion: Union) REQUIRE (cunion.name, cunion.path, cunion.line_number) IS UNIQUE"
                )
                session.run(
                    "CREATE CONSTRAINT annotation_unique IF NOT EXISTS FOR (a:Annotation) REQUIRE (a.name, a.path, a.line_number) IS UNIQUE"
                )
                session.run(
                    "CREATE CONSTRAINT record_unique IF NOT EXISTS FOR (r:Record) REQUIRE (r.name, r.path, r.line_number) IS UNIQUE"
                )
                session.run(
                    "CREATE CONSTRAINT property_unique IF NOT EXISTS FOR (p:Property) REQUIRE (p.name, p.path, p.line_number) IS UNIQUE"
                )

            session.run("CREATE INDEX function_lang IF NOT EXISTS FOR (f:Function) ON (f.lang)")
            session.run("CREATE INDEX class_lang IF NOT EXISTS FOR (c:Class) ON (c.lang)")
            session.run("CREATE INDEX annotation_lang IF NOT EXISTS FOR (a:Annotation) ON (a.lang)")
            session.run(
                "CREATE INDEX parameter_unique IF NOT EXISTS FOR (p:Parameter) ON (p.name, p.path, p.function_line_number)"
            )

            if is_falkordb and backend_type == "falkordb":
                for label in ["Function", "Class"]:
                    try:
                        session.run(
                            f"CALL db.idx.fulltext.createNodeIndex('{label}', 'name', 'source', 'docstring')"
                        )
                    except Exception:
                        pass
            elif backend_type == "neo4j":
                session.run("""
                    CREATE FULLTEXT INDEX code_search_index IF NOT EXISTS
                    FOR (n:Function|Class|Variable)
                    ON EACH [n.name, n.source, n.docstring]
                """)

            info_logger("Database schema verified/created successfully")
        except Exception as e:
            warning_logger(f"Schema creation warning: {e}")
