# src/codegraphcontext/tools/query_tool_languages/ruby_toolkit.py
from .base_toolkit import BaseLanguageToolkit


class RubyToolkit(BaseLanguageToolkit):
    """Cypher queries for Ruby graph data."""

    lang = "ruby"
    display_name = "Ruby"
    extensions = (".rb",)
