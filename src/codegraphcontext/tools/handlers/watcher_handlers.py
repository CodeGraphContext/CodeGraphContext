# src/codegraphcontext/tools/handlers/watcher_handlers.py
from typing import Any, Dict

from ...utils.debug_log import error_logger
from ...utils.path_sandbox import is_path_allowed
from ...utils.repo_path import any_repo_matches_path

def list_watched_paths(code_watcher, **args) -> Dict[str, Any]:
    """Tool to list all currently watched directory paths."""
    try:
        paths = code_watcher.list_watched_paths()
        return {"success": True, "watched_paths": paths}
    except Exception as e:
        return {"error": f"Failed to list watched paths: {str(e)}"}

def unwatch_directory(code_watcher, **args) -> Dict[str, Any]:
    """Tool to stop watching a directory."""
    from pathlib import Path

    path = args.get("path") or args.get("repo_path")
    if not path:
        return {"error": "Path is a required argument."}

    path_obj = Path(path).resolve()
    if not is_path_allowed(path_obj):
        return {
            "error": (
                f"Path '{path_obj}' is outside the allowed roots. "
                "Only paths under the workspace or CGC_ALLOWED_ROOTS can be unwatched."
            )
        }
    return code_watcher.unwatch_directory(str(path_obj))

def watch_directory(code_watcher, list_repositories_func, add_code_func, **args) -> Dict[str, Any]:
    """
    Tool implementation to start watching a directory for changes.
    It checks if the path exists, if it's already watched, or if it needs indexing.
    """
    path = args.get("path") or args.get("repo_path")
    from pathlib import Path

    if not path:
        return {"error": "Path is a required argument."}

    path_obj = Path(path).resolve()
    path_str = str(path_obj)

    if not is_path_allowed(path_obj):
        return {
            "error": (
                f"Path '{path_str}' is outside the allowed roots. "
                "Only subdirectories of the current working directory (or paths "
                "listed in CGC_ALLOWED_ROOTS) can be watched."
            )
        }

    if not path_obj.is_dir():
        return {
            "success": False,
            "status": "path_not_found",
            "error": f"Path '{path_str}' does not exist or is not a directory.",
            "message": f"Path '{path_str}' does not exist or is not a directory.",
        }
    try:
        if path_str in code_watcher.watched_paths:
            return {"success": True, "message": f"Already watching directory: {path_str}"}

        indexed_repos_result = list_repositories_func()
        indexed_repos = indexed_repos_result.get("repositories", [])
        is_already_indexed = any_repo_matches_path(indexed_repos, path_obj)

        if is_already_indexed:
            # Reconcile changes made while the watcher was stopped before live updates.
            code_watcher.watch_directory(
                path_str,
                perform_initial_scan=False,
                sync_on_start=True,
            )
            return {
                "success": True,
                "message": f"Path '{path_str}' is synchronized. Now watching for live changes."
            }

        scan_job_result = add_code_func(path=path_str, is_dependency=False)

        if "error" in scan_job_result:
            return scan_job_result

        code_watcher.watch_directory(path_str, perform_initial_scan=False)

        return {
            "success": True,
            "message": f"Path '{path_str}' was not indexed. Started background indexing and now watching for live changes.",
            "job_id": scan_job_result.get("job_id"),
            "details": "Use check_job_status to monitor the initial scan."
        }
        
    except Exception as e:
        error_logger(f"Failed to start watching directory {path}: {e}")
        return {"error": f"Failed to start watching directory: {str(e)}"}
