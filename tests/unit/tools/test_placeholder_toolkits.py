# tests/unit/tools/test_placeholder_toolkits.py
"""
Regression tests for issue #1281.

Placeholder language toolkits previously defined get_cypher_query() without
a `self` parameter, causing TypeError when called as an instance method.
"""
import pytest

from codegraphcontext.tools.query_tool_languages.c_toolkit import CToolkit
from codegraphcontext.tools.query_tool_languages.python_toolkit import PythonToolkit
from codegraphcontext.tools.query_tool_languages.go_toolkit import GoToolkit
from codegraphcontext.tools.query_tool_languages.rust_toolkit import RustToolkit
from codegraphcontext.tools.query_tool_languages.ruby_toolkit import RubyToolkit
from codegraphcontext.tools.query_tool_languages.typescript_toolkit import TypescriptToolkit
from codegraphcontext.tools.query_tool_languages.javascript_toolkit import JavascriptToolkit
from codegraphcontext.tools.query_tool_languages.csharp_toolkit import CSharpToolkit
from codegraphcontext.tools.query_tool_languages.dart_toolkit import DartToolkit
from codegraphcontext.tools.query_tool_languages.perl_toolkit import PerlToolkit
from codegraphcontext.tools.query_tool_languages.java_toolkit import JavaToolkit


PLACEHOLDER_TOOLKITS = [
    CToolkit,
    PythonToolkit,
    GoToolkit,
    RustToolkit,
    RubyToolkit,
    TypescriptToolkit,
    JavascriptToolkit,
    CSharpToolkit,
    DartToolkit,
    PerlToolkit,
    JavaToolkit,
]


@pytest.mark.parametrize("toolkit_class", PLACEHOLDER_TOOLKITS)
def test_get_cypher_query_raises_not_implemented_not_type_error(toolkit_class):
    """
    Before the fix, calling instance.get_cypher_query('Function') raised:
        TypeError: get_cypher_query() takes 1 positional argument but 2 were given
    After the fix it must raise NotImplementedError instead.
    """
    instance = toolkit_class()
    with pytest.raises(NotImplementedError):
        instance.get_cypher_query("Function")


@pytest.mark.parametrize("toolkit_class", PLACEHOLDER_TOOLKITS)
def test_get_cypher_query_error_message(toolkit_class):
    """NotImplementedError message must contain the expected text."""
    instance = toolkit_class()
    with pytest.raises(NotImplementedError, match="AdvancedLanguageQuery is not implemented yet"):
        instance.get_cypher_query("Class")


@pytest.mark.parametrize("toolkit_class", PLACEHOLDER_TOOLKITS)
def test_toolkit_instantiates_without_arguments(toolkit_class):
    """Placeholder toolkits must be instantiable with no arguments."""
    instance = toolkit_class()
    assert instance is not None


def test_all_placeholder_toolkits_have_get_cypher_query():
    """Every placeholder toolkit must define get_cypher_query as an attribute."""
    for toolkit_class in PLACEHOLDER_TOOLKITS:
        assert hasattr(toolkit_class, "get_cypher_query"), (
            f"{toolkit_class.__name__} is missing get_cypher_query"
        )