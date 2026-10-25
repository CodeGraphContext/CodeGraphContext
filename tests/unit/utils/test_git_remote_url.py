import subprocess
from unittest.mock import patch

import pytest

from codegraphcontext.utils.git_utils import get_repo_remote_url


def test_origin_is_read_without_contacting_remote(tmp_path):
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    assert get_repo_remote_url(tmp_path) is None
    url = "git@example.invalid:team/project.git"
    subprocess.run(["git", "-C", str(tmp_path), "remote", "add", "origin", url], check=True)
    assert get_repo_remote_url(tmp_path) == url


@pytest.mark.parametrize("error", [subprocess.CalledProcessError(1, "git"), FileNotFoundError(), OSError()])
def test_remote_lookup_failure_is_optional(tmp_path, error):
    with patch("subprocess.check_output", side_effect=error):
        assert get_repo_remote_url(tmp_path) is None


def test_empty_remote_output_is_none(tmp_path):
    with patch("subprocess.check_output", return_value=b"\n"):
        assert get_repo_remote_url(tmp_path) is None
