# src/codegraphcontext/core/jobs.py
"""
This module defines the data structures and manager for handling long-running,
background jobs, such as code indexing.
"""
import uuid
import threading
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Dict, List, Optional
from pathlib import Path


class JobStatus(Enum):
    """Enumeration for the possible statuses of a background job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class JobInfo:
    """
    A data class to hold all information about a single background job.
    This makes it easy to track the job's progress, status, and results.
    """
    job_id: str
    status: JobStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    total_files: int = 0
    processed_files: int = 0
    current_file: Optional[str] = None
    estimated_duration: Optional[float] = None
    actual_duration: Optional[float] = None
    errors: List[str] = None
    result: Optional[Dict[str, Any]] = None
    path: Optional[str] = None
    is_dependency: bool = False
    graph_name: Optional[str] = None

    def __post_init__(self):
        """Ensures the errors list is initialized after the object is created."""
        if self.errors is None:
            self.errors = []

    @property
    def progress_percentage(self) -> float:
        """Calculates the completion percentage of the job."""
        if self.total_files == 0:
            return 0.0
        return (self.processed_files / self.total_files) * 100

    @property
    def estimated_time_remaining(self) -> Optional[float]:
        """Calculates the estimated time remaining based on the average time per file."""
        if self.status != JobStatus.RUNNING or self.processed_files == 0:
            return None
        elapsed = (datetime.now() - self.start_time).total_seconds()
        avg_time_per_file = elapsed / self.processed_files
        remaining_files = self.total_files - self.processed_files
        return remaining_files * avg_time_per_file

class JobManager:
    """
    A thread-safe manager for creating, updating, and retrieving information
    about background jobs. It stores job information in memory.
    """
    def __init__(self):
        self.jobs: Dict[str, JobInfo] = {}
        self.lock = threading.Lock() # A lock to ensure thread-safe access to the jobs dictionary.

    def create_job(self, path: str, is_dependency: bool = False, graph_name: Optional[str] = None) -> str:
        """Creates a new job, assigns it a unique ID, and stores it."""
        job_id = str(uuid.uuid4())
        with self.lock:
            self.jobs[job_id] = JobInfo(
                job_id=job_id,
                status=JobStatus.PENDING,
                start_time=datetime.now(),
                path=path,
                is_dependency=is_dependency,
                graph_name=graph_name,
            )
        return job_id

    def update_job(self, job_id: str, **kwargs):
        """Updates the information for a specific job in a thread-safe manner."""
        with self.lock:
            if job_id in self.jobs:
                job = self.jobs[job_id]
                for key, value in kwargs.items():
                    if hasattr(job, key):
                        setattr(job, key, value)

    def get_job(self, job_id: str) -> Optional[JobInfo]:
        """Retrieves the information for a single job."""
        with self.lock:
            return self.jobs.get(job_id)

    def list_jobs(self) -> List[JobInfo]:
        """Returns a list of all jobs currently in the manager."""
        with self.lock:
            return list(self.jobs.values())

    def find_active_job_by_path(self, path: str) -> Optional[JobInfo]:
        """Finds the most recent, currently active (pending or running) job for a given path."""
        with self.lock:
            path_obj = Path(path).resolve()
            
            matching_jobs = sorted(
                [job for job in self.jobs.values() if job.path and Path(job.path).resolve() == path_obj],
                key=lambda j: j.start_time,
                reverse=True
            )

            for job in matching_jobs:
                if job.status in [JobStatus.PENDING, JobStatus.RUNNING]:
                    return job
                    
            return None

    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Removes old, completed jobs from memory to prevent memory leaks."""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        with self.lock:
            jobs_to_remove = [
                job_id for job_id, job in self.jobs.items()
                if job.end_time and job.end_time < cutoff_time
            ]
            for job_id in jobs_to_remove:
                del self.jobs[job_id]
