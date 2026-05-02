"""Orchestrates full-repo indexing (Tree-sitter path)."""

from __future__ import annotations

import asyncio
import multiprocessing
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ...cli.config_manager import get_config_value
from ...core.jobs import JobManager, JobStatus
from ..tree_sitter_parser import TreeSitterParser
from ...utils.debug_log import debug_log, error_logger, info_logger
from .discovery import discover_files_to_index
from . import profiling
from .persistence.writer import GraphWriter
from .pre_scan import pre_scan_for_imports
from .resolution.calls import build_function_call_groups
from .resolution.inheritance import build_inheritance_and_csharp_files
from .worker_config import resolve_file_write_workers, resolve_parallel_workers

_WORKER_PARSER_CACHE: Dict[str, TreeSitterParser] = {}
_WORKER_INDEX_SOURCE: Optional[bool] = None


def _process_pool_context():
    if sys.platform == "darwin":
        try:
            return multiprocessing.get_context("fork")
        except Exception:
            return None
    return None


def _worker_get_parser_for_extension(ext: str, parsers: Dict[str, str]) -> Optional[TreeSitterParser]:
    lang_name = parsers.get(ext)
    if not lang_name:
        return None
    parser = _WORKER_PARSER_CACHE.get(lang_name)
    if parser is None:
        parser = TreeSitterParser(lang_name)
        _WORKER_PARSER_CACHE[lang_name] = parser
    return parser


def _worker_index_source_enabled() -> bool:
    global _WORKER_INDEX_SOURCE
    if _WORKER_INDEX_SOURCE is None:
        _WORKER_INDEX_SOURCE = (get_config_value("INDEX_SOURCE") or "false").lower() == "true"
    return _WORKER_INDEX_SOURCE


def _process_parse_file_task(
    task: tuple[str, str, bool, Dict[str, str]]
) -> tuple[str, Dict[str, Any]]:
    repo_path_str, file_path_str, is_dependency, parsers = task
    file_path = Path(file_path_str)
    parser = _worker_get_parser_for_extension(file_path.suffix, parsers)
    if not parser:
        return file_path_str, {
            "path": file_path_str,
            "error": f"No parser for {file_path.suffix}",
            "unsupported": True,
        }

    index_source = _worker_index_source_enabled()
    try:
        if parser.language_name == "python":
            file_data = parser.parse(
                file_path,
                is_dependency,
                is_notebook=file_path.suffix == ".ipynb",
                index_source=index_source,
            )
        else:
            file_data = parser.parse(file_path, is_dependency, index_source=index_source)
        file_data["repo_path"] = repo_path_str
        return file_path_str, file_data
    except Exception as e:
        return file_path_str, {"path": file_path_str, "error": str(e)}


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

    profiling.set_phase("repository_setup")
    writer.add_repository_to_graph(path, is_dependency)
    repo_name = path.name

    files, _ignore_root = discover_files_to_index(path, cgcignore_path)

    if job_id:
        job_manager.update_job(job_id, total_files=len(files))

    parallel_workers = resolve_parallel_workers()
    all_file_data: List[Dict[str, Any]] = []
    resolved_repo_path_str = str(path.resolve()) if path.is_dir() else str(path.parent.resolve())
    repo_path = path.resolve() if path.is_dir() else path.parent.resolve()
    files_to_parse = [file for file in files if file.is_file()]
    processed_count = 0

    if parallel_workers == 1:
        with profiling.phase_scope("prescan"):
            debug_log("Starting pre-scan to build imports map...")
            imports_map = pre_scan_for_imports(files, parsers.keys(), get_parser)
            debug_log(f"Pre-scan complete. Found {len(imports_map)} definitions.")
        with profiling.phase_scope("directory_precreation"):
            writer.pre_create_directory_structure(files_to_parse, repo_path)
        profiling.set_phase("file_writes")
        for file in files_to_parse:
            if job_id:
                job_manager.update_job(job_id, current_file=str(file))
            file_data = parse_file(repo_path, file, is_dependency)
            if "error" not in file_data:
                writer.add_file_to_graph(
                    file_data, repo_name, imports_map,
                    repo_path_str=resolved_repo_path_str,
                    directories_pre_created=True,
                )
                all_file_data.append(file_data)
            elif not file_data.get("unsupported"):
                add_minimal_file_node(file, repo_path, is_dependency)
            processed_count += 1
            if job_id:
                job_manager.update_job(job_id, processed_files=processed_count)
            if processed_count % 50 == 0:
                await asyncio.sleep(0)
    else:
        process_ctx = _process_pool_context()
        info_logger(f"Using {parallel_workers} process workers for pre-scan + parse phases.")
        with ProcessPoolExecutor(max_workers=parallel_workers, mp_context=process_ctx) as executor:
            with profiling.phase_scope("prescan"):
                debug_log("Starting pre-scan to build imports map...")
                imports_map = pre_scan_for_imports(
                    files,
                    parsers.keys(),
                    get_parser,
                    parsers_map=parsers,
                    executor=executor,
                )
                debug_log(f"Pre-scan complete. Found {len(imports_map)} definitions.")

            # --- Phase: parse all files first, then pre-create shared nodes, then write. ---
            # Collecting all parse results before any writes lets us pre-create Module nodes
            # (shared across files) in a single bulk pass, eliminating the lock-order
            # inversion deadlock that occurs when parallel writers race to MERGE the same
            # Module node while simultaneously creating IMPORTS relationships.
            with profiling.phase_scope("parse_collection"):
                info_logger("Collecting parse results before write phase...")
                parse_futures: Dict[Any, Path] = {}
                for file in files_to_parse:
                    task = (str(repo_path), str(file), is_dependency, parsers)
                    parse_futures[executor.submit(_process_parse_file_task, task)] = file

                parsed_results: List[Dict[str, Any]] = []
                minimal_file_nodes: List[Path] = []
                for future in as_completed(parse_futures):
                    file = parse_futures[future]
                    if job_id:
                        job_manager.update_job(job_id, current_file=str(file))
                    try:
                        _file_path, file_data = future.result()
                    except Exception as e:
                        error_logger(f"Unexpected parsing failure for {file}: {e}")
                        file_data = {"path": str(file), "error": str(e)}
                    if "error" not in file_data:
                        parsed_results.append(file_data)
                    elif not file_data.get("unsupported"):
                        minimal_file_nodes.append(file)
                    processed_count += 1
                    if job_id:
                        job_manager.update_job(job_id, processed_files=processed_count)
                    if processed_count % 50 == 0:
                        await asyncio.sleep(0)

            info_logger(f"Parse complete: {len(parsed_results)} files parsed.")

            with profiling.phase_scope("directory_precreation"):
                writer.pre_create_directory_structure(files_to_parse, repo_path)
            with profiling.phase_scope("module_precreation"):
                writer.pre_create_module_nodes(parsed_results)

            profiling.set_phase("file_writes")
            write_workers = resolve_file_write_workers()
            info_logger(f"Using {write_workers} workers for file-write phase.")

            for file in minimal_file_nodes:
                add_minimal_file_node(file, repo_path, is_dependency)

            _fw_t0 = time.time()
            with ThreadPoolExecutor(max_workers=write_workers) as write_executor:
                write_futures = {}
                max_pending_writes = max(8, write_workers * 8)
                for file_data in parsed_results:
                    all_file_data.append(file_data)
                    wf = write_executor.submit(
                        writer.add_file_to_graph,
                        file_data,
                        repo_name,
                        imports_map,
                        repo_path_str=resolved_repo_path_str,
                        directories_pre_created=True,
                    )
                    write_futures[wf] = file_data.get("path", "unknown")

                    if len(write_futures) >= max_pending_writes:
                        done_futures = []
                        for wf in as_completed(list(write_futures.keys())):
                            done_futures.append(wf)
                            failed_file = write_futures[wf]
                            try:
                                wf.result()
                            except Exception as e:
                                error_logger(f"Unexpected write failure for {failed_file}: {e}")
                                raise
                            if len(done_futures) >= write_workers:
                                break
                        for done in done_futures:
                            write_futures.pop(done, None)

                for wf, failed_file in list(write_futures.items()):
                    try:
                        wf.result()
                    except Exception as e:
                        error_logger(f"Unexpected write failure for {failed_file}: {e}")
                        raise
            profiling.record_phase_elapsed("file_writes", time.time() - _fw_t0)

    info_logger(
        f"File processing complete. {len(all_file_data)} files parsed. "
        f"Starting post-processing phase (inheritance + function calls)..."
    )

    t0 = time.time()
    info_logger(f"[INHERITS] Resolving inheritance links across {len(all_file_data)} files...")
    profiling.set_phase("inheritance")
    inheritance_batch, csharp_files = build_inheritance_and_csharp_files(all_file_data, imports_map)
    writer.write_inheritance_links(inheritance_batch, csharp_files, imports_map)
    t1 = time.time()
    profiling.record_phase_elapsed("inheritance", t1 - t0)
    info_logger(f"Inheritance links created in {t1 - t0:.1f}s. Starting function calls...")

    profiling.set_phase("function_calls")
    groups = build_function_call_groups(all_file_data, imports_map, None)
    writer.write_function_call_groups(*groups)
    t2 = time.time()
    profiling.record_phase_elapsed("function_calls", t2 - t1)
    info_logger(f"Function calls created in {t2 - t1:.1f}s. Total post-processing: {t2 - t0:.1f}s")

    if job_id:
        job_manager.update_job(job_id, status=JobStatus.COMPLETED, end_time=datetime.now())
