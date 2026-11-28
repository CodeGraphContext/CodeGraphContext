# src/codegraphcontext/tools/query_tool_languages/scala_toolkit.py
from .base_toolkit import BaseLanguageToolkit


class ScalaToolkit(BaseLanguageToolkit):
    """Cypher queries for Scala graph data."""

    lang = "scala"
    display_name = "Scala"
    extensions = (".scala", ".sc")
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
