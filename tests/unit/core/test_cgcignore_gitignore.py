"""A repository's .gitignore also acts as a .cgcignore (#729)."""

from pathlib import Path

import pytest

from codegraphcontext.core.cgcignore import build_ignore_spec, find_gitignore


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    return tmp_path


def _spec(root: Path, defaults=None):
    spec, _ = build_ignore_spec(root, defaults or [])
    return spec


def test_gitignore_patterns_are_honoured(repo: Path):
    (repo / ".gitignore").write_text("build/\n*.log\n")
    (repo / "build").mkdir()

    spec = _spec(repo)

    assert spec.match_file(repo / "build" / "out.o")
    assert spec.match_file(repo / "server.log")
    assert not spec.match_file(repo / "main.py")


def test_cgcignore_negation_re_includes_a_git_ignored_path(repo: Path):
    """The workflow the issue asks for: keep indexing one git-ignored path."""
    (repo / ".gitignore").write_text("dist/\n")
    (repo / ".cgcignore").write_text("!dist/\n")
    (repo / "dist").mkdir()

    spec = _spec(repo)

    assert not spec.match_file(repo / "dist" / "bundle.js")


def test_missing_gitignore_changes_nothing(repo: Path):
    (repo / ".cgcignore").write_text("*.tmp\n")

    spec = _spec(repo)

    assert spec.match_file(repo / "scratch.tmp")
    assert not spec.match_file(repo / "main.py")


def test_gitignore_comments_and_blank_lines_are_skipped(repo: Path):
    (repo / ".gitignore").write_text("# a comment\n\n  \n*.bak\n")

    spec = _spec(repo)

    assert spec.match_file(repo / "old.bak")
    assert not spec.match_file(repo / "a comment")


def test_gitignore_is_found_from_a_subdirectory_of_the_worktree(repo: Path):
    (repo / ".gitignore").write_text("*.log\n")
    nested = repo / "services" / "api"
    nested.mkdir(parents=True)

    assert find_gitignore(nested) == repo / ".gitignore"


def test_gitignore_outside_a_git_worktree_is_not_picked_up(tmp_path: Path):
    """Without a .git marker the walk must not escape upward."""
    (tmp_path / ".gitignore").write_text("*.log\n")
    loose = tmp_path / "loose"
    loose.mkdir()

    assert find_gitignore(loose) is None


def test_defaults_still_lose_to_a_cgcignore_negation(repo: Path):
    (repo / ".gitignore").write_text("*.log\n")
    (repo / ".cgcignore").write_text("!vendor/\n")
    (repo / "vendor").mkdir()

    spec = _spec(repo, defaults=["vendor/"])

    assert not spec.match_file(repo / "vendor" / "lib.py")
    assert spec.match_file(repo / "server.log")
