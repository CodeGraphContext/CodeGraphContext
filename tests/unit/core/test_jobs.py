
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

    def test_cancel_pending_job(self):
        manager = JobManager()
        job_id = manager.create_job("/tmp")

        assert manager.cancel_job(job_id) is True

        job = manager.get_job(job_id)
        assert job.status == JobStatus.CANCELLED
        assert job.end_time is not None

    def test_cancel_running_job(self):
        manager = JobManager()
        job_id = manager.create_job("/tmp")
        manager.update_job(job_id, status=JobStatus.RUNNING)

        assert manager.cancel_job(job_id) is True
        assert manager.get_job(job_id).status == JobStatus.CANCELLED

    def test_cancel_is_false_for_unknown_job(self):
        manager = JobManager()
        assert manager.cancel_job("non_existent_id") is False

    def test_cancel_does_not_reopen_a_finished_job(self):
        """A COMPLETED job must keep its status and its original end_time."""
        manager = JobManager()
        job_id = manager.create_job("/tmp")
        manager.update_job(job_id, status=JobStatus.COMPLETED)
        finished_at = manager.get_job(job_id).end_time

        assert manager.cancel_job(job_id) is False

        job = manager.get_job(job_id)
        assert job.status == JobStatus.COMPLETED
        assert job.end_time == finished_at

    def test_cancel_is_idempotent(self):
        manager = JobManager()
        job_id = manager.create_job("/tmp")

        assert manager.cancel_job(job_id) is True
        assert manager.cancel_job(job_id) is False
        assert manager.get_job(job_id).status == JobStatus.CANCELLED

