"""
Regression tests for _normalize_repo_path_filter (issue #1633).

find_code / find_dead_code filter graph nodes with `node.path STARTS WITH
$repo_path`, but node.path is stored as the absolute filesystem path used at
indexing time. Callers naturally pass whatever list_indexed_repositories()
just showed them — a bare repo name — which used to silently match nothing.
"""

from unittest.mock import MagicMock

from codegraphcontext.tools.code_finder import CodeFinder


def _make_code_finder(indexed_repos):
    """CodeFinder wired to a stub db_manager; list_indexed_repositories() is
    monkeypatched directly so we don't need a fake Cypher session."""
    db_manager = MagicMock()
    db_manager.get_backend_type.return_value = "kuzudb"
    finder = CodeFinder(db_manager)
    finder.list_indexed_repositories = MagicMock(return_value=indexed_repos)
    return finder


def test_bare_repo_name_resolves_to_absolute_path():
    finder = _make_code_finder([
        {"name": "service_a", "path": "/data/repos/service_a", "is_dependency": False},
    ])
    assert finder._normalize_repo_path_filter("service_a") == "/data/repos/service_a"


def test_basename_of_a_differently_named_repo_resolves():
    finder = _make_code_finder([
        {"name": "some-graph-repo-name", "path": "/data/repos/service_a", "is_dependency": False},
    ])
    assert finder._normalize_repo_path_filter("service_a") == "/data/repos/service_a"


def test_already_absolute_path_passes_through_unchanged():
    finder = _make_code_finder([
        {"name": "service_a", "path": "/data/repos/service_a", "is_dependency": False},
    ])
    assert finder._normalize_repo_path_filter("/data/repos/service_a") == "/data/repos/service_a"


def test_none_passes_through():
    finder = _make_code_finder([])
    assert finder._normalize_repo_path_filter(None) is None


def test_trailing_slash_and_whitespace_are_stripped():
    finder = _make_code_finder([
        {"name": "service_a", "path": "/data/repos/service_a", "is_dependency": False},
    ])
    assert finder._normalize_repo_path_filter("  service_a/  ") == "/data/repos/service_a"


def test_multiple_repos_only_the_matching_one_resolves():
    finder = _make_code_finder([
        {"name": "service_a", "path": "/data/repos/service_a", "is_dependency": False},
        {"name": "service_b", "path": "/data/repos/service_b", "is_dependency": False},
    ])
    assert finder._normalize_repo_path_filter("service_b") == "/data/repos/service_b"
    assert finder._normalize_repo_path_filter("service_a") == "/data/repos/service_a"


def test_unknown_repo_name_returns_input_unchanged_rather_than_guessing():
    finder = _make_code_finder([
        {"name": "service_a", "path": "/data/repos/service_a", "is_dependency": False},
    ])
    assert finder._normalize_repo_path_filter("does-not-exist") == "does-not-exist"


def test_ambiguous_basename_across_two_repos_returns_input_unchanged():
    finder = _make_code_finder([
        {"name": "team-a/service", "path": "/data/team-a/service", "is_dependency": False},
        {"name": "team-b/service", "path": "/data/team-b/service", "is_dependency": False},
    ])
    # "service" matches the basename of both — ambiguous, so don't guess.
    assert finder._normalize_repo_path_filter("service") == "service"
