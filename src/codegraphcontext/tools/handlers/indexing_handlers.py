# src/codegraphcontext/tools/handlers/indexing_handlers.py
from typing import Any, Dict, List
from pathlib import Path
import asyncio
import os
from ...utils.debug_log import debug_log
from ...utils.repo_path import repo_record_matches_path
from ..package_resolver import get_local_package_path


def _get_allowed_roots() -> List[Path]:
    """
    Return the list of allowed root directories for indexing.

    By default only the current working directory is allowed.  Additional
    roots can be specified via the ``CGC_ALLOWED_ROOTS`` environment
    variable (colon-separated on Unix, semicolon-separated on Windows).
    """
    roots: List[Path] = [Path.cwd().resolve()]

    env_roots = os.environ.get("CGC_ALLOWED_ROOTS", "")
    if env_roots:
        separator = ";" if os.name == "nt" else ":"
        for entry in env_roots.split(separator):
            entry = entry.strip()
            if entry:
                roots.append(Path(entry).resolve())

    return roots


def _is_path_allowed(path: Path) -> bool:
    """Check whether *path* falls under one of the allowed root directories."""
    resolved = path.resolve()
    for root in _get_allowed_roots():
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def add_code_to_graph(graph_builder, job_manager, loop, list_repos_func, **args) -> Dict[str, Any]:
    """
    Tool implementation to index a directory of code.
    Runs indexing asynchronously via a background job.
    """
    path = args.get("path")
    is_dependency = args.get("is_dependency", False)
    
    try:
        path_obj = Path(path).resolve()

        # --- Path-traversal guard ---------------------------------------------------
        if not _is_path_allowed(path_obj):
            return {
                "error": (
                    f"Path '{path}' is outside the allowed roots. "
                    "Only subdirectories of the current working directory (or paths "
                    "listed in the CGC_ALLOWED_ROOTS environment variable) can be indexed."
                )
            }
        # -----------------------------------------------------------------------------

        if not path_obj.exists():
            return {
                "success": True,
                "status": "path_not_found",
                "message": f"Path '{path}' does not exist."
            }

        # Prevent re-indexing the same repository.
        indexed_repos = list_repos_func().get("repositories", [])
        for repo in indexed_repos:
            if repo_record_matches_path(repo, path_obj):
                return {
                    "success": False,
                    "message": f"Repository '{path}' is already indexed."
                }
        
        # Estimate time and create a job for the user to track.
        total_files, estimated_time = graph_builder.estimate_processing_time(path_obj)
        job_id = job_manager.create_job(str(path_obj), is_dependency)
        job_manager.update_job(job_id, total_files=total_files, estimated_duration=estimated_time)
        
        # Create the coroutine for the background task and schedule it on the main event loop.
        coro = graph_builder.build_graph_from_path_async(
            path_obj, is_dependency, job_id
        )
        asyncio.run_coroutine_threadsafe(coro, loop)
        
        debug_log(f"Started background job {job_id} for path: {str(path_obj)}, is_dependency: {is_dependency}")
        
        return {
            "success": True, "job_id": job_id,
            "message": f"Background processing started for {str(path_obj)}",
            "estimated_files": total_files,
            "estimated_duration_seconds": round(estimated_time, 2),
            "estimated_duration_human": f"{int(estimated_time // 60)}m {int(estimated_time % 60)}s" if estimated_time >= 60 else f"{int(estimated_time)}s",
            "instructions": f"Use 'check_job_status' with job_id '{job_id}' to monitor progress"
        }
    
    except Exception as e:
        debug_log(f"Error creating background job: {str(e)}")
        return {"error": f"Failed to start background processing: {str(e)}"}

def add_package_to_graph(graph_builder, job_manager, loop, list_repos_func, **args) -> Dict[str, Any]:
    """Tool to add a package to the graph by auto-discovering its location"""
    package_name = args.get("package_name")
    language = args.get("language")
    is_dependency = args.get("is_dependency", True)

    if not language:
        return {"error": "The 'language' parameter is required."}

    try:
        # Check if the package is already indexed
        indexed_repos = list_repos_func().get("repositories", [])
        for repo in indexed_repos:
            if repo.get("is_dependency") and (repo.get("name") == package_name or repo.get("name") == f"{package_name}.py"):
                return {
                    "success": False,
                    "message": f"Package '{package_name}' is already indexed."
                }

        package_path = get_local_package_path(package_name, language)
        
        if not package_path:
            return {"error": f"Could not find package '{package_name}' for language '{language}'. Make sure it's installed."}
        
        if not os.path.exists(package_path):
            return {"error": f"Package path '{package_path}' does not exist"}
        
        path_obj = Path(package_path)
        
        total_files, estimated_time = graph_builder.estimate_processing_time(path_obj)
        
        job_id = job_manager.create_job(package_path, is_dependency)
        
        job_manager.update_job(job_id, total_files=total_files, estimated_duration=estimated_time)
        
        coro = graph_builder.build_graph_from_path_async(
            path_obj, is_dependency, job_id
        )
        asyncio.run_coroutine_threadsafe(coro, loop)
        
        debug_log(f"Started background job {job_id} for package: {package_name} at {package_path}, is_dependency: {is_dependency}")
        
        return {
            "success": True, "job_id": job_id, "package_name": package_name,
            "discovered_path": package_path,
            "message": f"Background processing started for package '{package_name}'",
            "estimated_files": total_files,
            "estimated_duration_seconds": round(estimated_time, 2),
            "estimated_duration_human": f"{int(estimated_time // 60)}m {int(estimated_time % 60)}s" if estimated_time >= 60 else f"{int(estimated_time)}s",
            "instructions": f"Use 'check_job_status' with job_id '{job_id}' to monitor progress"
        }
    
    except Exception as e:
        debug_log(f"Error creating background job for package {package_name}: {str(e)}")
        return {"error": f"Failed to start background processing for package '{package_name}': {str(e)}"}
