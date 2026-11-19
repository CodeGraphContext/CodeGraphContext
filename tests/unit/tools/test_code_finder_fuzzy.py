from codegraphcontext.tools.code_finder import (
    _escape_lucene_query,
    _escape_lucene_term,
    _has_searchable_content,
    _levenshtein_distance,
    summarize_kotlin_call_ambiguity,
)


def test_levenshtein_single_typo():
    assert _levenshtein_distance("myfuncton", "myfunction") == 1


def test_levenshtein_identical():
    assert _levenshtein_distance("abc", "abc") == 0


def test_escape_lucene_term_plain_text_untouched():
    assert _escape_lucene_term("apply_route") == "apply_route"


def test_escape_lucene_term_escapes_parenthesis():
    assert _escape_lucene_term("apply_route(") == "apply_route\\("


def test_escape_lucene_term_escapes_brackets():
    assert _escape_lucene_term("[x]") == "\\[x\\]"


def test_escape_lucene_term_escapes_slash():
    assert _escape_lucene_term("a/b") == "a\\/b"


def test_escape_lucene_term_lowercases_operators():
    assert _escape_lucene_term("NOT") == "not"
    assert _escape_lucene_term("AND") == "and"
    assert _escape_lucene_term("OR") == "or"
    assert _escape_lucene_term("TO") == "to"


def test_escape_lucene_query_escapes_each_token():
    assert _escape_lucene_query("foo NOT bar") == "foo not bar"
    assert _escape_lucene_query("call(x)") == "call\\(x\\)"


def test_has_searchable_content():
    assert _has_searchable_content("[x]") is True
    assert _has_searchable_content("apply_route(") is True
    assert _has_searchable_content("[]") is False
    assert _has_searchable_content("()") is False
    assert _has_searchable_content("") is False


def test_summarize_kotlin_call_ambiguity_groups_multi_target_calls():
    rows = [
        {
            "caller_name": "run",
            "caller_path": "/repo/A.kt",
            "caller_line": 10,
            "caller_end_line": 20,
            "call_line": 12,
            "full_call_name": "service.target",
            "target_name": "target",
            "target_path": "/repo/Service.kt",
            "target_line": 5,
            "target_context": "Service",
            "args": ["value"],
        },
        {
            "caller_name": "run",
            "caller_path": "/repo/A.kt",
            "caller_line": 10,
            "caller_end_line": 20,
            "call_line": 12,
            "full_call_name": "service.target",
            "target_name": "target",
            "target_path": "/repo/Service.kt",
            "target_line": 9,
            "target_context": "Service",
            "args": ["value"],
        },
        {
            "caller_name": "run",
            "caller_path": "/repo/A.kt",
            "caller_line": 10,
            "caller_end_line": 20,
            "call_line": 13,
            "full_call_name": "helper",
            "target_name": "helper",
            "target_path": "/repo/A.kt",
            "target_line": 30,
            "target_context": None,
            "args": [],
        },
    ]

    summary = summarize_kotlin_call_ambiguity(rows)

    assert summary["kotlin_fn_to_fn_edges"] == 3
    assert summary["ambiguous_groups"] == 1
    assert summary["ambiguous_edges"] == 2
    assert summary["top_names"] == [{"name": "target", "groups": 1}]
    assert summary["examples"][0]["target_count"] == 2
