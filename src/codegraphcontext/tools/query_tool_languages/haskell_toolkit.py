# src/codegraphcontext/tools/query_tool_languages/haskell_toolkit.py
from .base_toolkit import BaseLanguageToolkit


class HaskellToolkit(BaseLanguageToolkit):
    """Cypher queries for Haskell graph data."""

    lang = "haskell"
    display_name = "Haskell"
    extensions = (".hs",)
