"""Create constraints and indexes for graph backends (Neo4j / Falkor-style Cypher)."""

from typing import Any

from ...utils.debug_log import info_logger, warning_logger


def create_graph_schema(driver: Any, db_manager: Any) -> None:
    """Create constraints and indexes. *driver* must support .session() context manager."""
    with driver.session() as session:
        try:
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

            backend_type = getattr(db_manager, "get_backend_type", lambda: "neo4j")()
            if backend_type == "falkordb":
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
