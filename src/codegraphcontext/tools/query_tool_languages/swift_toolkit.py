# src/codegraphcontext/tools/query_tool_languages/swift_toolkit.py
from .base_toolkit import BaseLanguageToolkit


class SwiftToolkit(BaseLanguageToolkit):
    """Cypher queries for Swift graph data."""

    lang = "swift"
    display_name = "Swift"
    extensions = (".swift",)
    supported_types = (
        "Repository",
        "Directory",
        "File",
        "Module",
        "Function",
        "Class",
        "Struct",
        "Enum",
        "Variable",
    )
