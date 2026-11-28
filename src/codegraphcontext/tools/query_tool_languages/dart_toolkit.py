# src/codegraphcontext/tools/query_tool_languages/dart_toolkit.py
from .base_toolkit import BaseLanguageToolkit


class DartToolkit(BaseLanguageToolkit):
    """Cypher queries for Dart graph data."""

    lang = "dart"
    display_name = "Dart"
    extensions = (".dart",)
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
