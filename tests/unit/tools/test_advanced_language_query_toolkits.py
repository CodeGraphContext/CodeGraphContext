import pytest

from codegraphcontext.tools.advanced_language_query_tool import Advanced_language_query


@pytest.mark.parametrize("language,toolkit_cls", sorted(Advanced_language_query.TOOLKITS.items()))
def test_all_registered_toolkits_generate_cypher_without_not_implemented(language, toolkit_cls):
    toolkit = toolkit_cls()
    query_types = ["Class", "Module", "Variable"]
    if language != "cpp":
        query_types.append("File")
    if language != "hcl":
        query_types.append("Function")

    for query_type in query_types:
        cypher = toolkit.get_cypher_query(query_type)
        assert isinstance(cypher, str)
        assert "MATCH" in cypher
        assert "RETURN" in cypher


def test_haskell_toolkit_is_registered():
    assert "haskell" in Advanced_language_query.TOOLKITS


def test_java_toolkit_preserves_spring_methods_and_supports_cypher():
    java_cls = Advanced_language_query.TOOLKITS["java"]
    toolkit = java_cls()
    assert hasattr(toolkit, "find_spring_endpoints")
    assert hasattr(toolkit, "find_beans_by_stereotype")
    assert "fn.lang = 'java'" in toolkit.get_cypher_query("Function")


def test_unsupported_query_type_raises_value_error():
    py_toolkit = Advanced_language_query.TOOLKITS["python"]()
    with pytest.raises(ValueError, match="Unsupported Python query type"):
        py_toolkit.get_cypher_query("Macro")
