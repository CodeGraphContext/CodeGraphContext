class SolidityToolkit:
    """Cypher helpers for Solidity graph data (``.sol`` / ``lang = 'solidity'``)."""

    def get_cypher_query(self, query: str) -> str:
        query = query.strip()

        if query == "Repository":
            return """
                MATCH (r:Repository)-[:CONTAINS*]->(f:File)
                WHERE f.path ENDS WITH '.sol'
                RETURN DISTINCT r.name AS name, r.path AS path
                ORDER BY r.path
            """

        if query == "File":
            return """
                MATCH (f:File)
                WHERE f.path ENDS WITH '.sol'
                RETURN f.name AS name, f.path AS path, f.relative_path AS relative_path
                ORDER BY f.path
            """

        if query == "Module":
            return """
                MATCH (f:File)-[i:IMPORTS]->(m:Module)
                WHERE f.path ENDS WITH '.sol'
                RETURN f.name AS file_name,
                       m.name AS module_name,
                       i.imported_name AS imported_name,
                       i.full_import_name AS full_import_name,
                       i.line_number AS line_number
                ORDER BY f.path, i.line_number, m.name
            """

        if query == "Function":
            return """
                MATCH (fn:Function)
                WHERE fn.lang = 'solidity'
                RETURN fn.name AS name,
                       fn.path AS path,
                       fn.line_number AS line_number,
                       fn.class_context AS class_context
                ORDER BY fn.path, fn.line_number, fn.name
            """

        if query == "Class":
            return """
                MATCH (c)
                WHERE (c:Class OR c:Interface OR c:Struct OR c:Enum)
                  AND coalesce(c.lang, '') = 'solidity'
                RETURN labels(c) AS labels,
                       c.name AS name,
                       c.path AS path,
                       c.line_number AS line_number
                ORDER BY c.path, c.name
            """

        if query == "Variable":
            return """
                MATCH (v:Variable)
                WHERE v.lang = 'solidity'
                RETURN v.name AS name,
                       v.path AS path,
                       v.type AS type,
                       v.line_number AS line_number,
                       v.class_context AS class_context
                ORDER BY v.path, v.line_number, v.name
            """

        raise ValueError(f"Unsupported Solidity toolkit query: {query}")
