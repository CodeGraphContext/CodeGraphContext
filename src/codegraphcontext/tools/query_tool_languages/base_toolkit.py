# src/codegraphcontext/tools/query_tool_languages/base_toolkit.py
"""Shared Cypher query builder for language-specific query toolkits."""

from __future__ import annotations

from typing import Tuple


class BaseLanguageToolkit:
    """Base toolkit generating read-only Cypher queries scoped to a language."""

    lang: str = ""
    display_name: str = ""
    extensions: Tuple[str, ...] = ()
    supported_types: Tuple[str, ...] = (
        "Repository",
        "Directory",
        "File",
        "Module",
        "Function",
        "Class",
        "Variable",
    )

    def _file_filter(self, alias: str = "f") -> str:
        if not self.extensions:
            return f"{alias}.lang = '{self.lang}'"
        clauses = [f"{alias}.path ENDS WITH '{ext}'" for ext in self.extensions]
        return "(" + " OR ".join(clauses) + ")" if len(clauses) > 1 else clauses[0]

    def get_cypher_query(self, query: str) -> str:
        """Return a read-only Cypher query string for *query* scoped to this language."""
        query = query.strip()
        if query not in self.supported_types:
            label = self.display_name or self.lang or "this language"
            raise ValueError(f"Unsupported {label} query type: {query}")

        file_filter = self._file_filter("f")

        if query == "Repository":
            return f"""
                MATCH (r:Repository)-[:CONTAINS*]->(f:File)
                WHERE {file_filter}
                RETURN DISTINCT r.name AS name, r.path AS path
                ORDER BY r.path
            """

        if query == "Directory":
            return f"""
                MATCH (d:Directory)-[:CONTAINS*]->(f:File)
                WHERE {file_filter}
                RETURN DISTINCT d.name AS name, d.path AS path
                ORDER BY d.path
            """

        if query == "File":
            return f"""
                MATCH (f:File)
                WHERE {file_filter}
                RETURN f.name AS name, f.path AS path, f.relative_path AS relative_path
                ORDER BY f.path
            """

        if query == "Module":
            return f"""
                MATCH (f:File)-[i:IMPORTS]->(m:Module)
                WHERE {file_filter}
                RETURN f.name AS file_name,
                       m.name AS module_name,
                       i.imported_name AS imported_name,
                       i.full_import_name AS full_import_name,
                       i.line_number AS line_number
                ORDER BY f.path, i.line_number, m.name
            """

        if query == "Function":
            return f"""
                MATCH (fn:Function)
                WHERE fn.lang = '{self.lang}'
                RETURN fn.name AS name,
                       fn.path AS path,
                       fn.line_number AS line_number,
                       fn.end_line AS end_line,
                       fn.args AS args,
                       fn.docstring AS docstring
                ORDER BY fn.path, fn.line_number
            """

        if query == "Class":
            return f"""
                MATCH (c:Class)
                WHERE c.lang = '{self.lang}'
                RETURN c.name AS name,
                       c.path AS path,
                       c.line_number AS line_number,
                       c.end_line AS end_line,
                       c.docstring AS docstring
                ORDER BY c.path, c.line_number
            """

        if query == "Struct":
            return f"""
                MATCH (s:Struct)
                WHERE s.lang = '{self.lang}'
                RETURN s.name AS name,
                       s.path AS path,
                       s.line_number AS line_number,
                       s.fields AS fields
                ORDER BY s.path, s.line_number
            """

        if query == "Enum":
            return f"""
                MATCH (e:Enum)
                WHERE e.lang = '{self.lang}'
                RETURN e.name AS name,
                       e.path AS path,
                       e.line_number AS line_number,
                       e.values AS values
                ORDER BY e.path, e.line_number
            """

        if query == "Union":
            return f"""
                MATCH (u:Union)
                WHERE u.lang = '{self.lang}'
                RETURN u.name AS name,
                       u.path AS path,
                       u.line_number AS line_number,
                       u.members AS members
                ORDER BY u.path, u.line_number
            """

        if query == "Macro":
            return f"""
                MATCH (m:Macro)
                WHERE m.lang = '{self.lang}'
                RETURN m.name AS name,
                       m.path AS path,
                       m.line_number AS line_number,
                       m.value AS value
                ORDER BY m.path, m.line_number
            """

        if query == "Variable":
            return f"""
                MATCH (v:Variable)
                WHERE v.lang = '{self.lang}'
                RETURN v.name AS name,
                       v.path AS path,
                       v.line_number AS line_number,
                       v.value AS value,
                       v.context AS context
                ORDER BY v.path, v.line_number
            """

        raise ValueError(f"Unsupported {self.display_name or self.lang} query type: {query}")
