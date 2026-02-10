class CppToolkit:
    """Handles Neo4j queries for C++ file graph."""
    def get_cypher_query(query: str) -> str:
        """
        Returns a Cypher query string based on the query type requested.

        Supported query types:
        - functions
        - classes
        - imports
        - structs
        - enums
        - unions
        - macros
        - variables
        """


        query = query.strip().lower()

        if query == "functions":
            return """
                MATCH (f:Function)
                RETURN f.name AS name, f.path AS path, 
                    f.line_number AS line_number, f.docstring AS docstring
                ORDER BY f.path, f.line_number
            """

        elif query == "classes":
            return """
                MATCH (c:Class)
                RETURN c.name AS name, c.path AS path, 
                    c.line_number AS line_number, c.docstring AS docstring
                ORDER BY c.path, c.line_number
            """

        elif query == "imports":
            return """
                MATCH (f:File)-[i:IMPORTS]->(m:Module)
                RETURN f.name AS file_name, m.name AS module_name, 
                    m.full_import_name AS full_import_name, m.alias AS alias
                ORDER BY f.name
            """

        elif query == "structs":
            return """
                MATCH (s:Struct)
                RETURN s.name AS name, s.path AS path, 
                    s.line_number AS line_number, s.fields AS fields
                ORDER BY s.path, s.line_number
            """

        elif query == "enums":
            return """
                MATCH (e:Enum)
                RETURN e.name AS name, e.path AS path, 
                    e.line_number AS line_number, e.values AS values
                ORDER BY e.path, e.line_number
            """

        elif query == "unions":
            return """
                MATCH (u:Union)
                RETURN u.name AS name, u.path AS path, 
                    u.line_number AS line_number, u.members AS members
                ORDER BY u.path, u.line_number
            """

        elif query == "macros":
            return """
                MATCH (m:Macro)
                RETURN m.name AS name, m.path AS path, 
                    m.line_number AS line_number, m.value AS value
                ORDER BY m.path, m.line_number
            """

        elif query == "variables":
            return """
                MATCH (v:Variable)
                RETURN v.name AS name, v.path AS path, 
                    v.line_number AS line_number, v.value AS value, 
                    v.context AS context
                ORDER BY v.path, v.line_number
            """

        else:
            raise ValueError(f"Unsupported query type: {query}")
