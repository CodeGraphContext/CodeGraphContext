# src/codegraphcontext/tools/query_tool_languages/c_toolkit.py
from .base_toolkit import BaseLanguageToolkit


class CToolkit(BaseLanguageToolkit):
    """Cypher queries for C graph data."""

    lang = "c"
    display_name = "C"
    extensions = (".c",)
    supported_types = (
        "Repository",
        "Directory",
        "File",
        "Module",
        "Function",
        "Class",
        "Struct",
        "Enum",
        "Union",
        "Macro",
        "Variable",
    )
