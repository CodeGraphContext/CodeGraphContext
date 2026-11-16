
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

    def test_list_active_jobs_includes_pending_and_running_only(self):
        """#1536: switch_context must see PENDING as well as RUNNING."""
        manager = JobManager()
        pending_id = manager.create_job("/pending")
        running_id = manager.create_job("/running")
        done_id = manager.create_job("/done")
        failed_id = manager.create_job("/failed")
        cancelled_id = manager.create_job("/cancelled")

        manager.update_job(running_id, status=JobStatus.RUNNING)
        manager.update_job(done_id, status=JobStatus.COMPLETED)
        manager.update_job(failed_id, status=JobStatus.FAILED)
        manager.update_job(cancelled_id, status=JobStatus.CANCELLED)

        active_ids = {job.job_id for job in manager.list_active_jobs()}
        assert active_ids == {pending_id, running_id}


    def test_cleanup_never_deletes_active_jobs(self):
        """#1537: a healthy long-running job must survive the age sweep."""
        from datetime import datetime, timedelta
        manager = JobManager()
        running_id = manager.create_job("/monorepo")
        manager.update_job(running_id, status=JobStatus.RUNNING)
        # Simulate a job that started long ago but reported progress recently.
        manager.jobs[running_id].start_time = datetime.now() - timedelta(hours=48)
        manager.update_job(running_id, processed_files=10_000)

        manager.cleanup_old_jobs(max_age_hours=24)

        job = manager.get_job(running_id)
        assert job is not None, "active job was deleted mid-run"
        assert job.status == JobStatus.RUNNING

    def test_cleanup_fails_stalled_active_jobs_instead_of_deleting(self):
        """A RUNNING job with no progress for the whole window is presumed
        crashed: flipped to FAILED (still visible), not vanished."""
        from datetime import datetime, timedelta
        manager = JobManager()
        stalled_id = manager.create_job("/crashed")
        manager.update_job(stalled_id, status=JobStatus.RUNNING)
        manager.jobs[stalled_id].start_time = datetime.now() - timedelta(hours=48)
        manager.jobs[stalled_id].last_update_time = datetime.now() - timedelta(hours=30)

        manager.cleanup_old_jobs(max_age_hours=24)

        job = manager.get_job(stalled_id)
        assert job is not None
        assert job.status == JobStatus.FAILED
        assert any("Presumed crashed" in e for e in job.errors)

    def test_cleanup_still_removes_old_terminal_jobs(self):
        from datetime import datetime, timedelta
        manager = JobManager()
        done_id = manager.create_job("/done")
        manager.update_job(done_id, status=JobStatus.COMPLETED,
                           end_time=datetime.now() - timedelta(hours=48))
        # update_job stamps last_update_time but aging uses end_time for
        # terminal jobs, so backdate it explicitly.
        manager.jobs[done_id].end_time = datetime.now() - timedelta(hours=48)

        manager.cleanup_old_jobs(max_age_hours=24)

        assert manager.get_job(done_id) is None

    def test_cancellation_request_is_idempotent_and_prevents_pending_admission(self):
        manager = JobManager()
        job_id = manager.create_job("/pending")
        assert manager.cancel_job("unknown") is False
        assert manager.cancel_job(job_id) is True
        assert manager.cancel_job(job_id) is False
        assert manager.begin_job(job_id) is False
        assert manager.get_job(job_id).status == JobStatus.CANCELLED
        assert manager.get_job(job_id).cancel_requested is True
        assert manager.get_job(job_id).end_time is not None
        assert manager.list_active_jobs() == []

    @pytest.mark.parametrize("outcome", [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED])
    def test_active_terminal_updates_wait_for_quiescence(self, outcome):
        from datetime import datetime

        manager = JobManager()
        job_id = manager.create_job("/active")
        assert manager.begin_job(job_id) is True
        assert manager.begin_job(job_id) is False
        manager.update_job(job_id, status=outcome, end_time=datetime.now())
        assert manager.get_job(job_id).status == JobStatus.RUNNING
        assert manager.get_job(job_id).end_time is None
        assert manager.find_active_job_by_path("/active").job_id == job_id
        assert manager.finish_job(job_id) == outcome
        assert manager.begin_job(job_id) is False
        assert manager.cancel_job(job_id) is False

    def test_request_before_completion_wins_and_preserves_failure_diagnostics(self):
        manager = JobManager()
        job_id = manager.create_job("/active")
        assert manager.begin_job(job_id)
        assert manager.cancel_job(job_id)
        manager.fail_job(job_id, OSError("native write failed while draining"))
        assert manager.get_job(job_id).status == JobStatus.RUNNING
        assert manager.get_job(job_id).end_time is None
        assert manager.finish_job(job_id) == JobStatus.CANCELLED
        job = manager.get_job(job_id)
        assert job.errors == ["native write failed while draining"]
        assert job.error_type == "OSError"
        assert "OSError" in job.traceback
        ended = job.end_time
        manager.update_job(job_id, status=JobStatus.COMPLETED, processed_files=99)
        manager.fail_job(job_id, RuntimeError("late callback"))
        assert job.status == JobStatus.CANCELLED
        assert job.processed_files == 0
        assert job.end_time == ended
        assert job.errors == ["native write failed while draining"]

    def test_completed_operation_rejects_late_request(self):
        manager = JobManager()
        job_id = manager.create_job("/finished")
        assert manager.begin_job(job_id)
        assert manager.finish_job(job_id) == JobStatus.COMPLETED
        assert manager.cancel_job(job_id) is False
        assert manager.get_job(job_id).cancel_requested is False

    @pytest.mark.parametrize("cancel", [False, True])
    def test_cleanup_retains_owned_worker_even_without_recent_progress(self, cancel):
        from datetime import datetime, timedelta

        manager = JobManager()
        job_id = manager.create_job("/blocked-native-call")
        assert manager.begin_job(job_id)
        if cancel:
            assert manager.cancel_job(job_id)
        job = manager.get_job(job_id)
        job.start_time = datetime.now() - timedelta(hours=48)
        job.last_update_time = datetime.now() - timedelta(hours=30)
        manager.cleanup_old_jobs()
        assert manager.get_job(job_id) is job
        assert job.status == JobStatus.RUNNING
        assert job.end_time is None
        assert manager.finish_job(job_id) == (JobStatus.CANCELLED if cancel else JobStatus.COMPLETED)
