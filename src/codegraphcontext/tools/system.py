# src/codegraphcontext/tools/system.py
import logging
from dataclasses import asdict
from typing import Any, Dict
from datetime import datetime, timedelta

from neo4j.exceptions import CypherSyntaxError

from ..core.database import DatabaseManager
from ..core.jobs import JobManager, JobStatus
from ..utils.debug_log import debug_log

logger = logging.getLogger(__name__)


class SystemTools:
    """Handles system-level tools like job management and direct DB queries."""

    def __init__(self, db_manager: DatabaseManager, job_manager: JobManager):
        self.db_manager = db_manager
        self.job_manager = job_manager

    def check_job_status_tool(self, job_id: str) -> Dict[str, Any]:
        """Tool to check job status"""
        try:
            job = self.job_manager.get_job(job_id)
            if not job:
                return {"error": f"Job {job_id} not found"}
            
            job_dict = asdict(job)
            
            if job.status == JobStatus.RUNNING:
                if job.estimated_time_remaining:
                    remaining = job.estimated_time_remaining
                    job_dict["estimated_time_remaining_human"] = (
                        f"{int(remaining // 60)}m {int(remaining % 60)}s" 
                        if remaining >= 60 else f"{int(remaining)}s"
                    )
                
                if job.start_time:
                    elapsed = (datetime.now() - job.start_time).total_seconds()
                    job_dict["elapsed_time_human"] = (
                        f"{int(elapsed // 60)}m {int(elapsed % 60)}s" 
                        if elapsed >= 60 else f"{int(elapsed)}s"
                    )
            
            elif job.status == JobStatus.COMPLETED and job.start_time and job.end_time:
                duration = (job.end_time - job.start_time).total_seconds()
                job_dict["actual_duration_human"] = (
                    f"{int(duration // 60)}m {int(duration % 60)}s" 
                    if duration >= 60 else f"{int(duration)}s"
                )
            
            job_dict["start_time"] = job.start_time.strftime("%Y-%m-%d %H:%M:%S")
            if job.end_time:
                job_dict["end_time"] = job.end_time.strftime("%Y-%m-%d %H:%M:%S")
            
            job_dict["status"] = job.status.value
            return {"success": True, "job": job_dict}
        except Exception as e:
            return {"error": f"Failed to check job status: {str(e)}"}

    def list_jobs_tool(self) -> Dict[str, Any]:
        """Tool to list all jobs"""
        try:
            jobs = self.job_manager.list_jobs()
            jobs_data = []
            for job in sorted(jobs, key=lambda j: j.start_time, reverse=True):
                job_dict = asdict(job)
                job_dict["status"] = job.status.value
                job_dict["start_time"] = job.start_time.isoformat()
                if job.end_time:
                    job_dict["end_time"] = job.end_time.isoformat()
                jobs_data.append(job_dict)
            return {"success": True, "jobs": jobs_data, "total_jobs": len(jobs_data)}
        except Exception as e:
            return {"error": f"Failed to list jobs: {str(e)}"}

    def execute_cypher_query_tool(self, cypher_query: str) -> Dict[str, Any]:
        """Tool to execute a read-only Cypher query."""
        if not cypher_query:
            return {"error": "Cypher query cannot be empty."}

        forbidden_keywords = ['CREATE', 'MERGE', 'DELETE', 'SET', 'REMOVE', 'DROP', 'CALL apoc']
        if any(keyword in cypher_query.upper() for keyword in forbidden_keywords):
            return {"error": "This tool only supports read-only queries."}

        try:
            with self.db_manager.get_driver().session() as session:
                result = session.run(cypher_query)
                records = [record.data() for record in result]
                return {
                    "success": True,
                    "query": cypher_query,
                    "record_count": len(records),
                    "results": records
                }
        except CypherSyntaxError as e:
            return {"error": "Cypher syntax error.", "details": str(e)}
        except Exception as e:
            return {"error": "An unexpected error occurred.", "details": str(e)}

    def find_dead_code_tool(self) -> Dict[str, Any]:
        """Finds potentially unused functions (dead code)."""
        # This logic was moved from CodeFinder to be a system diagnostic tool
        try:
            with self.db_manager.get_driver().session() as session:
                result = session.run("""
                    MATCH (func:Function)
                    WHERE func.is_dependency = false
                      AND NOT func.name STARTS WITH '_'
                      AND NOT func.name IN ['main', 'setup', 'run']
                    OPTIONAL MATCH (caller:Function)-[:CALLS]->(func)
                    WHERE caller.is_dependency = false
                    WITH func, count(caller) as caller_count
                    WHERE caller_count = 0
                    RETURN func.name as function_name, func.path as path, func.line_number as line_number
                    ORDER BY func.path, func.line_number
                    LIMIT 50
                """)
                return {
                    "success": True,
                    "results": {
                        "potentially_unused_functions": [dict(record) for record in result],
                        "note": "These functions might be entry points or called dynamically."
                    }
                }
        except Exception as e:
            return {"error": f"Failed to find dead code: {str(e)}"}