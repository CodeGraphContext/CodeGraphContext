# src/codegraphcontext/tools/handlers/indexing_handlers.py
import ast
import os
from typing import Any, Dict, List, Set
from pathlib import Path
import asyncio
import stdlibs
from ...utils.debug_log import debug_log
from ...utils.path_sandbox import is_path_allowed as _is_path_allowed
from ...utils.repo_path import repo_record_matches_path
from ..package_resolver import get_local_package_path


def _collect_python_imports(path_obj: Path) -> Set[str]:
    """Collect top-level import names from Python files in the given path."""
    import_names: Set[str] = set()
    try:
        all_files = path_obj.rglob("*") if path_obj.is_dir() else [path_obj]
        for file_path in all_files:
            if file_path.is_file() and file_path.suffix == '.py':
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        source = f.read()
                    tree = ast.parse(source)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                top_level = alias.name.split('.')[0]
                                import_names.add(top_level)
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                top_level = node.module.split('.')[0]
                                import_names.add(top_level)
                except (SyntaxError, UnicodeDecodeError):
                    continue
    except Exception as e:
        debug_log(f"Error collecting imports from {path_obj}: {e}")
    return import_names


def _filter_and_resolve_dependencies(import_names: Set[str], project_path: Path) -> List[Dict[str, Any]]:
    """Filter out stdlib and local modules, then resolve external packages."""
    dependencies: List[Dict[str, Any]] = []
    project_modules = {f.stem for f in project_path.rglob("*.py") if f.is_file()}
    for init_file in project_path.rglob("__init__.py"):
        parts = list(init_file.parent.relative_to(project_path).parts)
        if parts:
            project_modules.add(parts[0])

    resolved: Set[str] = set()
    for module_name in import_names:
        if module_name in stdlibs.module_names:
            continue
        if module_name in project_modules:
            continue
        if module_name in resolved:
            continue
        package_path = get_local_package_path(module_name, "python")
        if package_path and os.path.exists(package_path):
            resolved.add(module_name)
            dependencies.append({
                "package_name": module_name,
                "package_path": package_path,
                "is_dependency": True
            })
    return dependencies


def add_code_to_graph(graph_builder, job_manager, loop, list_repos_func, **args) -> Dict[str, Any]:
    """
    Tool implementation to index a directory of code.
    Runs indexing asynchronously via a background job.
    """
    path = args.get("path") or args.get("repo_path")
    is_dependency = args.get("is_dependency", False)

    if not path:
        return {"error": "Path is a required argument (repo_path)."}

    # Indexing into a named graph is supported on multi-graph backends
    # (FalkorDB): a scoped GraphBuilder is constructed whose writer binds to
    # get_driver(graph_name). Single-graph backends (KùzuDB/LadybugDB/Neo4j)
    # would silently ignore the name and land the repo in the default graph —
    # the exact lie #1558 is about — so those still refuse explicitly.
    graph_name = args.get("graph_name")
    if graph_name:
        backend = graph_builder.db_manager.get_backend_type()
        if backend in ("falkordb", "falkordb-remote"):
            from ..graph_builder import GraphBuilder
            graph_builder = GraphBuilder(
                graph_builder.db_manager, job_manager, loop, graph_name=graph_name
            )
        else:
            return {
                "error": (
                    f"The active backend ({backend}) is single-graph, so "
                    f"graph_name={graph_name!r} cannot be honoured. Omit it to "
                    "index into the default graph, or select a graph via the CLI "
                    "context (`cgc context create` / `cgc index --context`)."
                ),
                "unsupported_argument": "graph_name",
            }
    
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
                "success": False,
                "status": "path_not_found",
                "error": f"Path '{path}' does not exist.",
                "message": f"Path '{path}' does not exist.",
            }

        # Prevent re-indexing the same repository. list_repos_func reads the
        # default graph, so the check only applies there — a named graph is a
        # separate namespace and legitimately re-indexes the same path.
        indexed_repos = [] if graph_name else list_repos_func().get("repositories", [])
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
        
        # If index_dependencies is True, collect imports and queue dependency indexing jobs.
        dependency_job_ids: List[str] = []
        index_dependencies = args.get("index_dependencies", False)
        if index_dependencies:
            debug_log("Collecting Python imports for dependency indexing...")
            import_names = _collect_python_imports(path_obj)
            debug_log(f"Found {len(import_names)} top-level imports: {import_names}")
            
            dependencies = _filter_and_resolve_dependencies(import_names, path_obj)
            
            for dep in dependencies:
                dep_job_id = job_manager.create_job(dep["package_path"], True)
                job_manager.update_job(dep_job_id, total_files=1, estimated_duration=1.0)
                dep_coro = graph_builder.build_graph_from_path_async(
                    Path(dep["package_path"]), True, dep_job_id
                )
                asyncio.run_coroutine_threadsafe(dep_coro, loop)
                dependency_job_ids.append(dep_job_id)
                debug_log(f"Started dependency indexing job {dep_job_id} for package: {dep['package_name']}")
            
            if dependency_job_ids:
                debug_log(f"Started {len(dependency_job_ids)} dependency indexing jobs.")
        
        return {
            "success": True, "job_id": job_id,
            **({"graph_name": graph_name} if graph_name else {}),
            "message": f"Background processing started for {str(path_obj)}"
                       + (f" into graph '{graph_name}'" if graph_name else ""),
            "estimated_files": total_files,
            "estimated_duration_seconds": round(estimated_time, 2),
            "estimated_duration_human": f"{int(estimated_time // 60)}m {int(estimated_time % 60)}s" if estimated_time >= 60 else f"{int(estimated_time)}s",
            "instructions": f"Use 'check_job_status' with job_id '{job_id}' to monitor progress",
            **({"dependency_job_ids": dependency_job_ids} if index_dependencies else {})
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

        package_resolved = Path(package_path).resolve()
        if not _is_path_allowed(package_resolved):
            return {
                "error": (
                    f"Package path '{package_resolved}' is outside allowed roots. "
                    "Add its parent directory to CGC_ALLOWED_ROOTS to index packages."
                )
            }

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
