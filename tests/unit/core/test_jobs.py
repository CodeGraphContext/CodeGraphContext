
import pytest
from codegraphcontext.core.jobs import JobManager, JobStatus

class TestJobManager:
    """
    Unit tests for JobManager logic.
    """

    def test_create_job(self):
        manager = JobManager()
        job_id = manager.create_job("/tmp")
        
        assert job_id is not None
        job = manager.get_job(job_id)
        assert job.status == JobStatus.PENDING
        # JobInfo uses 'type' is not a field, strict dataclass. Check path instead?
        assert job.path == "/tmp"

    def test_update_job_status(self):
        manager = JobManager()
        job_id = manager.create_job("/tmp")
        
        # Update progress (JobInfo has processed_files/total_files)
        manager.update_job(job_id, status=JobStatus.RUNNING, processed_files=50, total_files=100)
        
        job = manager.get_job(job_id)
        assert job.status == JobStatus.RUNNING
        assert job.progress_percentage == 50.0

    def test_job_not_found(self):
        manager = JobManager()
        job = manager.get_job("non_existent_id")
        assert job is None

