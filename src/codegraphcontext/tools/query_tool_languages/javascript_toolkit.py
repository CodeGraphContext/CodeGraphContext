# src/codegraphcontext/tools/query_tool_languages/javascript_toolkit.py
from .base_toolkit import BaseLanguageToolkit


class JavascriptToolkit(BaseLanguageToolkit):
    """Cypher queries for JavaScript graph data."""

    lang = "javascript"
    display_name = "JavaScript"
    extensions = (".js", ".jsx", ".mjs", ".cjs")
