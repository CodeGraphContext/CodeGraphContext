"""estimate_processing_time() returns None on failure; the indexing handlers
must surface that as a clean error instead of unpacking None into two names.

GraphBuilder.estimate_processing_time is typed Optional[Tuple[int, float]] and
returns None when discovery raises. add_code_to_graph and add_package_to_graph
destructured the result directly (`total_files, estimated_time = ...`), which
raises `TypeError: cannot unpack non-iterable NoneType`. The outer `except`
then masked the real cause with a generic "failed to start" message and no job
was created. The handlers now guard the None and return a specific error.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from codegraphcontext.tools.handlers.indexing_handlers import (
    add_code_to_graph,
    add_package_to_graph,
)


def test_add_code_to_graph_reports_a_failed_estimate(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CGC_ALLOWED_ROOTS", str(tmp_path))
    gb = MagicMock()
    gb.db_manager.get_backend_type.return_value = "kuzudb"
    gb.estimate_processing_time.return_value = None
    job_manager = MagicMock()

    with patch("codegraphcontext.tools.handlers.indexing_handlers.asyncio"):
        result = add_code_to_graph(
            gb, job_manager, MagicMock(), lambda: {"repositories": []}, path=str(tmp_path)
        )

    assert "error" in result, result
    assert "estimate processing time" in result["error"].lower()
    # No job is created on a failed estimate, and nothing is dispatched.
    job_manager.create_job.assert_not_called()
    gb.build_graph_from_path_async.assert_not_called()


def test_add_package_to_graph_reports_a_failed_estimate(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CGC_ALLOWED_ROOTS", str(tmp_path))
    package_path = tmp_path / "pkg"
    package_path.mkdir()
    gb = MagicMock()
    gb.estimate_processing_time.return_value = None
    job_manager = MagicMock()

    with patch(
        "codegraphcontext.tools.handlers.indexing_handlers.get_local_package_path",
        return_value=str(package_path),
    ):
        result = add_package_to_graph(
            gb, job_manager, MagicMock(), lambda: {"repositories": []},
            package_name="somepkg", language="python",
        )

    assert "error" in result, result
    assert "estimate processing time" in result["error"].lower()
    job_manager.create_job.assert_not_called()
