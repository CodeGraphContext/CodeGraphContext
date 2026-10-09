# src/codegraphcontext/tools/query_tool_languages/hcl_toolkit.py
_HCL_FILE = "(f.path ENDS WITH '.tf' OR f.path ENDS WITH '.tfvars' OR f.path ENDS WITH '.hcl')"


class HclToolkit:
    """Cypher queries for HCL graph data (Terraform, OpenTofu, Terragrunt; ``lang = 'hcl'``)."""

    def get_cypher_query(self, query: str) -> str:
        query = query.strip()

        if query == "Repository":
            return f"""
                MATCH (r:Repository)-[:CONTAINS*]->(f:File)
                WHERE {_HCL_FILE}
                RETURN DISTINCT r.name AS name, r.path AS path
                ORDER BY r.path
            """

        if query == "File":
            return f"""
                MATCH (f:File)
                WHERE {_HCL_FILE}
                RETURN f.name AS name, f.path AS path, f.relative_path AS relative_path
                ORDER BY f.path
            """

        if query == "Module":
            return f"""
                MATCH (f:File)-[i:IMPORTS]->(m:Module)
                WHERE {_HCL_FILE}
                RETURN f.name AS file_name,
                       f.path AS file_path,
                       m.name AS module_name,
                       i.line_number AS line_number
                ORDER BY f.path, i.line_number, m.name
            """

        if query == "Class":
            return """
                MATCH (c:Class)
                WHERE c.lang = 'hcl'
                RETURN c.name AS name,
                       c.node_type AS block_type,
                       c.path AS path,
                       c.line_number AS line_number,
                       c.end_line AS end_line,
                       c.docstring AS docstring
                ORDER BY c.path, c.line_number
            """

        if query == "Variable":
            return """
                MATCH (v:Variable)
                WHERE v.lang = 'hcl'
                RETURN v.name AS name,
                       v.path AS path,
                       v.line_number AS line_number,
                       v.value AS value,
                       v.docstring AS docstring
                ORDER BY v.path, v.line_number
            """

        raise ValueError(f"Unsupported HCL query type: {query}")
