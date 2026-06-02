class ElispToolkit:
    """Cypher queries for Emacs Lisp graph data."""

    def get_cypher_query(self, query: str) -> str:
        query = query.strip()

        if query == "Repository":
            return """
                MATCH (r:Repository)-[:CONTAINS*]->(f:File)
                WHERE f.path ENDS WITH '.el'
                RETURN DISTINCT r.name AS name, r.path AS path
                ORDER BY r.path
            """

        if query == "File":
            return """
                MATCH (f:File)
                WHERE f.path ENDS WITH '.el'
                RETURN f.name AS name, f.path AS path, f.relative_path AS relative_path
                ORDER BY f.path
            """

        if query == "Module":
            return """
                MATCH (f:File)-[i:IMPORTS]->(m:Module)
                WHERE f.path ENDS WITH '.el'
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
                WHERE fn.lang = 'elisp'
                RETURN fn.name AS name,
                       fn.path AS path,
                       fn.line_number AS line_number,
                       fn.end_line AS end_line,
                       fn.args AS args,
                       fn.docstring AS docstring
                ORDER BY fn.path, fn.line_number
            """

        if query == "Class":
            return """
                MATCH (c:Class)
                WHERE c.lang = 'elisp'
                RETURN c.name AS name,
                       c.path AS path,
                       c.line_number AS line_number,
                       c.end_line AS end_line,
                       c.docstring AS docstring
                ORDER BY c.path, c.line_number
            """

        if query == "Variable":
            return """
                MATCH (v:Variable)
                WHERE v.lang = 'elisp'
                RETURN v.name AS name,
                       v.path AS path,
                       v.line_number AS line_number,
                       v.value AS value,
                       v.context AS context,
                       v.docstring AS docstring
                ORDER BY v.path, v.line_number
            """

        raise ValueError(f"Unsupported Emacs Lisp query type: {query}")
