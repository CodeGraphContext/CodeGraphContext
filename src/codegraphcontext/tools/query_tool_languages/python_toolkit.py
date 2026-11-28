# src/codegraphcontext/tools/query_tool_languages/python_toolkit.py
from .base_toolkit import BaseLanguageToolkit


class PythonToolkit(BaseLanguageToolkit):
    """Cypher queries for Python graph data."""

    lang = "python"
    display_name = "Python"
    extensions = (".py", ".ipynb")
