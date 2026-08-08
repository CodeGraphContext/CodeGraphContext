from pathlib import Path

from codegraphcontext.utils.repo_path import any_repo_matches_path, repo_record_matches_path


def test_repo_record_matches_path_skips_null():
    p = Path("/tmp/foo").resolve()
    assert not repo_record_matches_path({"path": None}, p)
    assert not repo_record_matches_path({"path": ""}, p)


def test_any_repo_matches_path_ignores_bad_rows():
    target = Path("/tmp/foo").resolve()
    repos = [
        {"path": None, "name": "bad"},
        {"path": str(target), "name": "good"},
    ]
    assert any_repo_matches_path(repos, target)
