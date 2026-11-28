# src/codegraphcontext/tools/query_tool_languages/perl_toolkit.py
from .base_toolkit import BaseLanguageToolkit


class PerlToolkit(BaseLanguageToolkit):
    """Cypher queries for Perl graph data."""

    lang = "perl"
    display_name = "Perl"
    extensions = (".pl", ".pm")
