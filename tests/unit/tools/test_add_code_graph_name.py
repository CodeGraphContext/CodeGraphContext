"""#1558: add_code_to_graph declares graph_name — it must be honoured or refused.

On multi-graph backends (FalkorDB) the handler builds a scoped GraphBuilder
bound to get_driver(graph_name). On single-graph backends it must refuse
explicitly instead of silently indexing into the default graph.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

from codegraphcontext.tools.handlers.indexing_handlers import add_code_to_graph


def _base_builder(backend: str):
    gb = MagicMock()
    gb.db_manager.get_backend_type.return_value = backend
    gb.estimate_processing_time.return_value = (3, 1.0)
    return gb


def test_graph_name_refused_on_single_graph_backend(tmp_path: Path):
    gb = _base_builder("ladybugdb")
    result = add_code_to_graph(
        gb, MagicMock(), MagicMock(), lambda: {"repositories": []},
        path=str(tmp_path), graph_name="service-a",
    )
    assert result.get("unsupported_argument") == "graph_name"
    assert "ladybugdb" in result["error"]
    gb.estimate_processing_time.assert_not_called()


def test_graph_name_builds_scoped_builder_on_falkordb(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CGC_ALLOWED_ROOTS", str(tmp_path))
    gb = _base_builder("falkordb")
    scoped = MagicMock()
    scoped.estimate_processing_time.return_value = (3, 1.0)
    scoped.build_graph_from_path_async.return_value = MagicMock()
    job_manager = MagicMock()
    job_manager.create_job.return_value = "job-1"

    with patch("codegraphcontext.tools.graph_builder.GraphBuilder",
               return_value=scoped) as ctor, \
         patch("codegraphcontext.tools.handlers.indexing_handlers.asyncio"):
        result = add_code_to_graph(
            gb, job_manager, MagicMock(), lambda: {"repositories": []},
            path=str(tmp_path), graph_name="service-a",
        )

    assert result.get("success") is True, result
    assert result.get("graph_name") == "service-a"
    ctor.assert_called_once()
    assert ctor.call_args.kwargs.get("graph_name") == "service-a"
    # The scoped builder, not the default one, does the indexing.
    scoped.build_graph_from_path_async.assert_called_once()
    gb.build_graph_from_path_async.assert_not_called()


def test_no_graph_name_keeps_default_builder(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CGC_ALLOWED_ROOTS", str(tmp_path))
    gb = _base_builder("ladybugdb")
    gb.build_graph_from_path_async.return_value = MagicMock()
    job_manager = MagicMock()
    job_manager.create_job.return_value = "job-2"

    with patch("codegraphcontext.tools.handlers.indexing_handlers.asyncio"):
        result = add_code_to_graph(
            gb, job_manager, MagicMock(), lambda: {"repositories": []},
            path=str(tmp_path),
        )

    assert result.get("success") is True, result
    assert "graph_name" not in result
    gb.build_graph_from_path_async.assert_called_once()
