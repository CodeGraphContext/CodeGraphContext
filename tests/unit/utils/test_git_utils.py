"""Tests for the silent git metadata helpers."""

import subprocess
from pathlib import Path

from codegraphcontext.utils.git_utils import (
    get_repo_branch_name,
    get_repo_commit_hash,
    get_repo_remote_url,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _init_repo(repo: Path) -> Path:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "a.txt").write_text("hello\n", encoding="utf-8")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-q", "-m", "initial")
    return repo


def test_remote_url_returns_origin(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    _git(repo, "remote", "add", "origin", "https://github.com/example/demo.git")

    assert get_repo_remote_url(repo) == "https://github.com/example/demo.git"


def test_remote_url_is_none_without_an_origin_remote(tmp_path):
    """A repo with no `origin` must degrade to None, not raise."""
    repo = _init_repo(tmp_path / "repo")

    assert get_repo_remote_url(repo) is None


def test_remote_url_is_none_outside_a_git_tree(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()

    assert get_repo_remote_url(plain) is None


def test_helpers_agree_on_a_real_repo(tmp_path):
    """The three helpers share one silent-failure contract."""
    repo = _init_repo(tmp_path / "repo")
    _git(repo, "remote", "add", "origin", "git@github.com:example/demo.git")

    assert len(get_repo_commit_hash(repo)) == 40
    assert get_repo_branch_name(repo) is not None
    assert get_repo_remote_url(repo) == "git@github.com:example/demo.git"
