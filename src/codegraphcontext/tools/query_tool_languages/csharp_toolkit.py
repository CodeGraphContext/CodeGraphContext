# src/codegraphcontext/tools/query_tool_languages/csharp_toolkit.py
from .base_toolkit import BaseLanguageToolkit


class CSharpToolkit(BaseLanguageToolkit):
    """Cypher queries for C# graph data."""

    lang = "c_sharp"
    display_name = "C#"
    extensions = (".cs",)
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
