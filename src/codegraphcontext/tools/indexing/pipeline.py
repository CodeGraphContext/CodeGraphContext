"""Orchestrates full-repo indexing (Tree-sitter path)."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ...core.jobs import JobManager, JobStatus
from ...utils.debug_log import debug_log, error_logger, info_logger
from .discovery import discover_files_to_index
from .persistence.writer import GraphWriter
from .pre_scan import pre_scan_for_imports
from .resolution.calls import build_function_call_groups
from .resolution.inheritance import build_inheritance_and_csharp_files


async def run_tree_sitter_index_async(
    path: Path,
    is_dependency: bool,
    job_id: Optional[str],
    cgcignore_path: Optional[str],
    writer: GraphWriter,
    job_manager: JobManager,
    parsers: Dict[str, str],
    get_parser: Callable[[str], Any],
    parse_file: Callable[[Path, Path, bool], Dict[str, Any]],
    add_minimal_file_node: Callable[[Path, Path, bool], None],
) -> None:
    """Parse all discovered files, write symbols, then inheritance + CALLS."""
    if job_id:
        job_manager.update_job(job_id, status=JobStatus.RUNNING)

    writer.add_repository_to_graph(path, is_dependency)
    repo_name = path.name

    files, _ignore_root = discover_files_to_index(path, cgcignore_path)

    if job_id:
        job_manager.update_job(job_id, total_files=len(files))

    debug_log("Starting pre-scan to build imports map...")
    imports_map = pre_scan_for_imports(files, parsers.keys(), get_parser)
    debug_log(f"Pre-scan complete. Found {len(imports_map)} definitions.")

    all_file_data: List[Dict[str, Any]] = []
    resolved_repo_path_str = str(path.resolve()) if path.is_dir() else str(path.parent.resolve())

    processed_count = 0
    for file in files:
        if not file.is_file():
            continue
        if job_id:
            job_manager.update_job(job_id, current_file=str(file))
        repo_path = path.resolve() if path.is_dir() else file.parent.resolve()
        file_data = parse_file(repo_path, file, is_dependency)
        if "error" not in file_data:
            writer.add_file_to_graph(file_data, repo_name, imports_map, repo_path_str=resolved_repo_path_str)
            all_file_data.append(file_data)
        elif not file_data.get("unsupported"):
            add_minimal_file_node(file, repo_path, is_dependency)
        processed_count += 1

        if job_id:
            job_manager.update_job(job_id, processed_files=processed_count)
        if processed_count % 50 == 0:
            await asyncio.sleep(0)

    info_logger(
        f"File processing complete. {len(all_file_data)} files parsed. "
        f"Starting post-processing phase (inheritance + function calls)..."
    )

    t0 = time.time()
    info_logger(f"[INHERITS] Resolving inheritance links across {len(all_file_data)} files...")
    inheritance_batch, csharp_files = build_inheritance_and_csharp_files(all_file_data, imports_map)
    writer.write_inheritance_links(inheritance_batch, csharp_files, imports_map)
    t1 = time.time()
    info_logger(f"Inheritance links created in {t1 - t0:.1f}s. Starting function calls...")

    groups = build_function_call_groups(all_file_data, imports_map, None)
    writer.write_function_call_groups(*groups)
    t2 = time.time()
    info_logger(f"Function calls created in {t2 - t1:.1f}s. Total post-processing: {t2 - t0:.1f}s")

    if job_id:
        job_manager.update_job(job_id, status=JobStatus.COMPLETED, end_time=datetime.now())
