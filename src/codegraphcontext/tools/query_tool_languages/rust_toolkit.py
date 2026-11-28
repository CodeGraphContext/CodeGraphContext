# src/codegraphcontext/tools/query_tool_languages/rust_toolkit.py
from .base_toolkit import BaseLanguageToolkit


class RustToolkit(BaseLanguageToolkit):
    """Cypher queries for Rust graph data."""

    lang = "rust"
    display_name = "Rust"
    extensions = (".rs",)
    supported_types = (
        "Repository",
        "Directory",
        "File",
        "Module",
        "Function",
        "Class",
        "Struct",
        "Enum",
        "Macro",
        "Variable",
    )
