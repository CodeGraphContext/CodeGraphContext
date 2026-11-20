import json

import pytest

from codegraphcontext.core.jobs import JobManager
from codegraphcontext.tools.handlers.management_handlers import (
    check_job_status,
    list_jobs,
)


@pytest.fixture
def updated_job_manager():
    manager = JobManager()
    job_id = manager.create_job("/tmp/repo")
    manager.update_job(job_id, processed_files=1)
    return manager, job_id


def test_check_job_status_returns_json_serializable_updated_job(updated_job_manager):
    manager, job_id = updated_job_manager

    result = check_job_status(manager, job_id=job_id)

    json.dumps(result)
    assert isinstance(result["job"]["last_update_time"], str)


def test_list_jobs_returns_json_serializable_updated_jobs(updated_job_manager):
    manager, _ = updated_job_manager

    result = list_jobs(manager)

    json.dumps(result)
    assert isinstance(result["jobs"][0]["last_update_time"], str)


def test_list_jobs_points_at_a_jobs_result_instead_of_carrying_it():
    """A finished index job's summary (counts, files_by_extension,
    phase_seconds, failed_file_details) is check_job_status' answer; list_jobs rows keep
    their shape with a compact pointer in `result`, so the list does not grow with every
    finished index of a long-lived server."""
    manager = JobManager()
    plain = manager.create_job("/tmp/plain")
    indexed = manager.create_job("/tmp/repo")
    summary = {"phase_seconds": {"parse": 1.5}, "total_seconds": 2.0, "files_by_extension": {".py": 3},
               "failed_file_details": [{"path": f"/tmp/repo/f{i}.py"} for i in range(5)]}
    manager.update_job(indexed, result={"index_summary": summary})

    rows = {row["job_id"]: row for row in list_jobs(manager)["jobs"]}
    assert rows[plain]["result"] is None
    assert rows[indexed]["result"] == {"keys": ["index_summary"], "see": "check_job_status"}
    assert "phase_seconds" not in json.dumps(list_jobs(manager))
    assert check_job_status(manager, job_id=indexed)["job"]["result"] == {"index_summary": summary}
