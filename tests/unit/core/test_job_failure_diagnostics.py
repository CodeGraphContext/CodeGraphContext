import json
from unittest.mock import AsyncMock, patch

import pytest

from codegraphcontext.core.jobs import JobManager, JobStatus, MAX_TRACEBACK_CHARS
from codegraphcontext.tools.graph_builder import GraphBuilder
from codegraphcontext.tools.handlers.management_handlers import check_job_status, list_jobs


def test_failure_keeps_message_and_serializes_traceback():
    manager = JobManager()
    job_id = manager.create_job('/repo')
    try:
        raise ValueError('bad index')
    except ValueError as error:
        manager.fail_job(job_id, error)
    job = manager.get_job(job_id)
    assert job.status == JobStatus.FAILED
    assert job.errors == ['bad index']
    assert job.error_type == 'ValueError'
    assert 'test_failure_keeps_message' in job.traceback
    assert 'ValueError: bad index' in job.traceback
    for response in (check_job_status(manager, job_id=job_id), list_jobs(manager)):
        assert 'ValueError: bad index' in json.dumps(response)


def test_traceback_is_bounded_and_marks_truncation():
    manager = JobManager()
    job_id = manager.create_job('/repo')
    manager.fail_job(job_id, RuntimeError('x' * (MAX_TRACEBACK_CHARS * 2)))
    trace = manager.get_job(job_id).traceback
    assert len(trace) == MAX_TRACEBACK_CHARS
    assert trace.startswith('[traceback truncated;')


@pytest.mark.asyncio
async def test_indexing_exception_exposes_diagnostics(tmp_path):
    manager = JobManager()
    job_id = manager.create_job(str(tmp_path))
    builder = GraphBuilder.__new__(GraphBuilder)
    builder.job_manager = manager
    builder.parsers = {}
    builder._writer = object()
    builder.get_parser = lambda extension: None
    builder.parse_file = lambda *args: {}
    builder.add_minimal_file_node = lambda *args: None
    with patch('codegraphcontext.tools.graph_builder.get_config_value', return_value='false'), patch(
        'codegraphcontext.tools.graph_builder.run_tree_sitter_index_async',
        new=AsyncMock(side_effect=ValueError('index exploded')),
    ):
        await builder.build_graph_from_path_async(tmp_path, job_id=job_id)
    job = manager.get_job(job_id)
    assert job.status == JobStatus.FAILED
    assert job.errors == ['index exploded']
    assert job.error_type == 'ValueError'
    assert 'ValueError: index exploded' in job.traceback
