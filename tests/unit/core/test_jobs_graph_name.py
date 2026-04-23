"""JobManager persists graph_name on created jobs."""

from codegraphcontext.core.jobs import JobInfo, JobManager, JobStatus


def test_create_job_stores_graph_name():
    jm = JobManager()
    job_id = jm.create_job("/some/path", is_dependency=False, graph_name="tenant_x")
    job = jm.get_job(job_id)
    assert job.graph_name == "tenant_x"


def test_create_job_default_graph_name_is_none():
    jm = JobManager()
    job_id = jm.create_job("/some/path", is_dependency=False)
    job = jm.get_job(job_id)
    assert job.graph_name is None


def test_job_info_graph_name_field_exists():
    # Field is declared so background workers can rehydrate the target graph.
    job = JobInfo(job_id="x", status=JobStatus.PENDING, start_time=None, graph_name="g")
    assert job.graph_name == "g"
