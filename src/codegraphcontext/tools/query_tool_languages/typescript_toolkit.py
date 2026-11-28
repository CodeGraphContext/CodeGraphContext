# src/codegraphcontext/tools/query_tool_languages/typescript_toolkit.py
from .base_toolkit import BaseLanguageToolkit


class TypescriptToolkit(BaseLanguageToolkit):
    """Cypher queries for TypeScript graph data."""

    lang = "typescript"
    display_name = "TypeScript"
    extensions = (".ts", ".tsx", ".mts", ".cts")
    supported_types = (
        "Repository",
        "Directory",
        "File",
        "Module",
        "Function",
        "Class",
        "Enum",
        "Variable",
    )
