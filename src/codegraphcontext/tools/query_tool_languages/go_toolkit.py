# src/codegraphcontext/tools/query_tool_languages/go_toolkit.py
from .base_toolkit import BaseLanguageToolkit


class GoToolkit(BaseLanguageToolkit):
    """Cypher queries for Go graph data."""

    lang = "go"
    display_name = "Go"
    extensions = (".go",)
    supported_types = (
        "Repository",
        "Directory",
        "File",
        "Module",
        "Function",
        "Class",
        "Struct",
        "Variable",
    )
