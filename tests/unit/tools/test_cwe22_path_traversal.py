"""
PoC test for CWE-22: Path traversal in add_code_to_graph.

The add_code_to_graph handler accepts any filesystem path and indexes it
into the graph database. An MCP client (or AI agent via prompt injection)
can supply paths like /etc, /home/user/.ssh, or any sensitive directory.

This test verifies that paths outside the current working directory
(or explicitly configured allowed roots) are rejected.
"""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from codegraphcontext.tools.handlers.indexing_handlers import add_code_to_graph


def _make_mocks():
    """Create mock dependencies for add_code_to_graph."""
    graph_builder = MagicMock()
    graph_builder.estimate_processing_time.return_value = (10, 5.0)
    job_manager = MagicMock()
    job_manager.create_job.return_value = "test-job-123"
    loop = MagicMock()
    list_repos_func = MagicMock(return_value={"repositories": []})
    return graph_builder, job_manager, loop, list_repos_func


def test_rejects_absolute_path_outside_cwd():
    """Indexing /etc (or any path outside cwd) should be rejected."""
    graph_builder, job_manager, loop, list_repos_func = _make_mocks()

    result = add_code_to_graph(
        graph_builder, job_manager, loop, list_repos_func,
        path="/etc"
    )

    assert "error" in result, (
        f"Expected path traversal to /etc to be rejected, but got: {result}"
    )
    assert "outside" in result["error"].lower()
    graph_builder.build_graph_from_path_async.assert_not_called()


def test_rejects_relative_path_traversal():
    """Paths with .. that escape the working directory should be rejected."""
    graph_builder, job_manager, loop, list_repos_func = _make_mocks()

    result = add_code_to_graph(
        graph_builder, job_manager, loop, list_repos_func,
        path="../../../etc"
    )

    assert "error" in result, (
        f"Expected relative path traversal to be rejected, but got: {result}"
    )
    assert "outside" in result["error"].lower()
    graph_builder.build_graph_from_path_async.assert_not_called()


def test_rejects_home_ssh_directory():
    """Indexing ~/.ssh should be rejected."""
    graph_builder, job_manager, loop, list_repos_func = _make_mocks()
    ssh_dir = str(Path.home() / ".ssh")

    result = add_code_to_graph(
        graph_builder, job_manager, loop, list_repos_func,
        path=ssh_dir
    )

    assert "error" in result, (
        f"Expected ~/.ssh to be rejected, but got: {result}"
    )
    graph_builder.build_graph_from_path_async.assert_not_called()


def test_rejects_symlink_escape(tmp_path):
    """A symlink inside cwd that points outside should be rejected after resolution."""
    cwd = Path.cwd()
    link_path = cwd / "symlink_escape_test_poc"
    try:
        os.symlink("/etc", str(link_path))
        graph_builder, job_manager, loop, list_repos_func = _make_mocks()

        result = add_code_to_graph(
            graph_builder, job_manager, loop, list_repos_func,
            path=str(link_path)
        )

        assert "error" in result, (
            f"Expected symlink escape to /etc to be rejected, but got: {result}"
        )
        graph_builder.build_graph_from_path_async.assert_not_called()
    finally:
        if link_path.is_symlink():
            link_path.unlink()


def test_rejects_dot_dot_encoding_variants():
    """Various path encoding tricks should all be rejected."""
    paths = ["/etc/../etc", "//etc", "/./etc"]
    for p in paths:
        graph_builder, job_manager, loop, list_repos_func = _make_mocks()
        result = add_code_to_graph(
            graph_builder, job_manager, loop, list_repos_func,
            path=p
        )
        assert "error" in result, (
            f"Expected path '{p}' to be rejected, but got: {result}"
        )
        graph_builder.build_graph_from_path_async.assert_not_called()


def test_allows_subdirectory_of_cwd():
    """Paths that are subdirectories of cwd should be allowed."""
    graph_builder, job_manager, loop, list_repos_func = _make_mocks()

    cwd = Path.cwd()
    test_subdir = cwd / "test_subdir_for_cwe22_poc"
    test_subdir.mkdir(exist_ok=True)

    try:
        result = add_code_to_graph(
            graph_builder, job_manager, loop, list_repos_func,
            path=str(test_subdir)
        )

        # Should not be rejected for path restriction reasons
        if "error" in result:
            assert "outside" not in result["error"].lower(), (
                f"Subdirectory of cwd should be allowed, but got: {result}"
            )
    finally:
        test_subdir.rmdir()


def test_allows_path_via_env_allowlist():
    """Paths in CGC_ALLOWED_ROOTS should be allowed even if outside cwd."""
    graph_builder, job_manager, loop, list_repos_func = _make_mocks()

    with tempfile.TemporaryDirectory(prefix="cgc_allowed_") as tmpdir:
        with patch.dict(os.environ, {"CGC_ALLOWED_ROOTS": tmpdir}):
            result = add_code_to_graph(
                graph_builder, job_manager, loop, list_repos_func,
                path=tmpdir
            )

            # Should not be rejected for path restriction reasons
            if "error" in result:
                assert "outside" not in result["error"].lower(), (
                    f"Path in CGC_ALLOWED_ROOTS should be allowed, but got: {result}"
                )


def test_allows_multiple_env_roots():
    """Multiple colon-separated paths in CGC_ALLOWED_ROOTS all work."""
    graph_builder, job_manager, loop, list_repos_func = _make_mocks()

    with tempfile.TemporaryDirectory(prefix="cgc_root1_") as dir1, \
         tempfile.TemporaryDirectory(prefix="cgc_root2_") as dir2:
        env_val = f"{dir1}:{dir2}"
        with patch.dict(os.environ, {"CGC_ALLOWED_ROOTS": env_val}):
            for d in [dir1, dir2]:
                gb, jm, lp, lr = _make_mocks()
                result = add_code_to_graph(gb, jm, lp, lr, path=d)
                if "error" in result:
                    assert "outside" not in result["error"].lower(), (
                        f"Path {d} in CGC_ALLOWED_ROOTS should be allowed, but got: {result}"
                    )
