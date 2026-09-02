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
