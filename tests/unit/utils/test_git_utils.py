from pathlib import Path
import subprocess
from unittest.mock import patch

from codegraphcontext.utils.git_utils import (
    get_repo_branch_name,
    get_repo_commit_hash,
)


def test_get_repo_commit_hash_success():
    with patch("subprocess.check_output") as mock_check_output:
        mock_check_output.return_value = (
            b"1234567890abcdef1234567890abcdef12345678\n"
        )

        result = get_repo_commit_hash(Path("."))

        assert result == "1234567890abcdef1234567890abcdef12345678"
        mock_check_output.assert_called_once()


def test_get_repo_commit_hash_empty_output():
    with patch("subprocess.check_output") as mock_check_output:
        mock_check_output.return_value = b"\n"

        assert get_repo_commit_hash(Path(".")) is None


def test_get_repo_commit_hash_called_process_error():
    with patch(
        "subprocess.check_output",
        side_effect=subprocess.CalledProcessError(1, "git"),
    ):
        assert get_repo_commit_hash(Path(".")) is None


def test_get_repo_commit_hash_file_not_found():
    with patch(
        "subprocess.check_output",
        side_effect=FileNotFoundError,
    ):
        assert get_repo_commit_hash(Path(".")) is None


def test_get_repo_commit_hash_os_error():
    with patch(
        "subprocess.check_output",
        side_effect=OSError,
    ):
        assert get_repo_commit_hash(Path(".")) is None


def test_get_repo_branch_name_success():
    with patch("subprocess.check_output") as mock_check_output:
        mock_check_output.return_value = b"main\n"

        result = get_repo_branch_name(Path("."))

        assert result == "main"
        mock_check_output.assert_called_once()


def test_get_repo_branch_name_empty_output():
    with patch("subprocess.check_output") as mock_check_output:
        mock_check_output.return_value = b"\n"

        assert get_repo_branch_name(Path(".")) is None


def test_get_repo_branch_name_called_process_error():
    with patch(
        "subprocess.check_output",
        side_effect=subprocess.CalledProcessError(1, "git"),
    ):
        assert get_repo_branch_name(Path(".")) is None


def test_get_repo_branch_name_file_not_found():
    with patch(
        "subprocess.check_output",
        side_effect=FileNotFoundError,
    ):
        assert get_repo_branch_name(Path(".")) is None


def test_get_repo_branch_name_os_error():
    with patch(
        "subprocess.check_output",
        side_effect=OSError,
    ):
        assert get_repo_branch_name(Path(".")) is None