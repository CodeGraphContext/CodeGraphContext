from codegraphcontext.tools.code_finder import _levenshtein_distance


def test_levenshtein_single_typo():
    assert _levenshtein_distance("myfuncton", "myfunction") == 1


def test_levenshtein_identical():
    assert _levenshtein_distance("abc", "abc") == 0
