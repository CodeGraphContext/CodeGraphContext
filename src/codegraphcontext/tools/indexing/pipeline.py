# src/codegraphcontext/tools/indexing/pipeline.py
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
    call_resolution_diagnostics: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """Parse all discovered files, write symbols, then inheritance + CALLS."""
    if job_id:
        job_manager.update_job(job_id, status=JobStatus.RUNNING)

    repo_root = path if path.is_dir() else path.parent.resolve()
    writer.add_repository_to_graph(repo_root, is_dependency)
    repo_name = repo_root.name

    files, _ignore_root = discover_files_to_index(path, cgcignore_path, supported_extensions=set(parsers.keys()))

    if job_id:
        job_manager.update_job(job_id, total_files=len(files))

    debug_log("Starting pre-scan to build imports map...")
    imports_map = pre_scan_for_imports(files, parsers.keys(), get_parser)
    debug_log(f"Pre-scan complete. Found {len(imports_map)} definitions.")

    all_file_data: List[Dict[str, Any]] = []
    resolved_repo_path_str = str(path.resolve()) if path.is_dir() else str(path.parent.resolve())

    processed_count = 0
    concurrency_limit = 10
    semaphore = asyncio.Semaphore(concurrency_limit)
    
    async def process_file(file: Path) -> Optional[Dict[str, Any]]:
        nonlocal processed_count
        async with semaphore:
            if not file.is_file():
                return None
            
            if job_id:
                job_manager.update_job(job_id, current_file=str(file))
            
            repo_path = path.resolve() if path.is_dir() else file.parent.resolve()
            
            try:
                # 1. Parse file (CPU bound, run in thread)
                file_data = await asyncio.to_thread(parse_file, repo_path, file, is_dependency)
                
                # 2. Write to graph (I/O bound, run in thread)
                if "error" not in file_data:
                    await asyncio.to_thread(
                        writer.add_file_to_graph, 
                        file_data, repo_name, imports_map, 
                        repo_path_str=resolved_repo_path_str
                    )
                    return file_data
                elif not file_data.get("unsupported"):
                    await asyncio.to_thread(add_minimal_file_node, file, repo_path, is_dependency)
            except Exception as e:
                error_logger(f"Error indexing file {file}: {e}")
            
            return None

    # Process all files in parallel with the semaphore limit
    tasks = [process_file(f) for f in files]
    for coro in asyncio.as_completed(tasks):
        file_data = await coro
        if file_data:
            all_file_data.append(file_data)
        
        processed_count += 1
        if job_id:
            job_manager.update_job(job_id, processed_files=processed_count)
        
        if processed_count % 50 == 0:
            info_logger(f"Processed {processed_count}/{len(files)} files...")

    info_logger(
        f"File processing complete. {len(all_file_data)} files parsed. "
        f"Starting post-processing phase (inheritance + function calls)..."
    )

    t0 = time.time()
    if job_id:
        job_manager.update_job(job_id, status_message="Resolving inheritance links...")
    info_logger(f"[INHERITS] Resolving inheritance links across {len(all_file_data)} files...")
    inheritance_batch, csharp_files = build_inheritance_and_csharp_files(all_file_data, imports_map)
    writer.write_inheritance_links(inheritance_batch, csharp_files, imports_map)
    t1 = time.time()
    info_logger(f"Inheritance links created in {t1 - t0:.1f}s. Starting function calls...")

    resolved_calls = build_function_call_groups(
        all_file_data,
        imports_map,
        None,
        diagnostics=call_resolution_diagnostics,
    )
    if job_id:
        job_manager.update_job(job_id, status_message="Writing function CALLS edges...")
    writer.write_function_call_groups(*resolved_calls)
    t2 = time.time()
    info_logger(f"Function calls created in {t2 - t1:.1f}s. Total post-processing: {t2 - t0:.1f}s")

    # ── C++: Class->Function edges (post-pass, after all files written) ───────
    # C++ method definitions live in .cpp while the Class node lives in .h.
    # The per-file write cannot create these edges reliably due to ordering;
    # this single repo-scoped pass runs after every node is in the graph.
    if job_id:
        job_manager.update_job(job_id, status_message="Linking C++ class-function edges...")
    info_logger("[CPP] Linking C++ out-of-line method definitions to their classes...")
    writer.write_cpp_class_function_links(resolved_repo_path_str)

    # ── Spring injection edges (#887) ─────────────────────────────────────────
    if job_id:
        job_manager.update_job(job_id, status_message="Processing Spring injection edges...")
    spring_inject_batch = []
    for fd in all_file_data:
        injections = fd.get("spring_injections")
        if injections:
            spring_inject_batch.extend(injections)
    if spring_inject_batch:
        info_logger(f"[SPRING] Writing {len(spring_inject_batch)} Spring injection edges...")
        writer.write_spring_inject_links(spring_inject_batch)

    # Also collect Spring endpoint properties from functions and write them
    endpoint_batch = []
    for fd in all_file_data:
        for fn in fd.get("functions", []):
            if fn.get("http_method"):
                endpoint_batch.append({
                    "func_name": fn["name"],
                    "path": fn["path"],
                    "line_number": fn["line_number"],
                    "http_method": fn.get("http_method"),
                    "http_path": fn.get("http_path"),
                })
    if endpoint_batch:
        writer.write_spring_endpoint_properties(endpoint_batch)

    # ── Maven / Gradle build graph (#888) ────────────────────────────────────
    if not is_dependency and path.is_dir():
        if job_id:
            job_manager.update_job(job_id, status_message="Processing Maven build graph...")
        try:
            from ...tools.languages.maven import parse_repo_maven
            maven_data = parse_repo_maven(path.resolve())
            if maven_data.get("modules"):
                writer.write_maven_build_graph(maven_data, str(path.resolve()))
        except Exception as _me:
            info_logger(f"[MAVEN] Build graph failed (skipping): {_me}")

        if job_id:
            job_manager.update_job(job_id, status_message="Processing Gradle build graph...")
        try:
            from ...tools.languages.gradle import parse_repo_gradle
            gradle_data = parse_repo_gradle(path.resolve())
            if gradle_data.get("modules"):
                writer.write_gradle_build_graph(gradle_data, str(path.resolve()))
        except Exception as _ge:
            info_logger(f"[GRADLE] Build graph failed (skipping): {_ge}")

    # ── ORM / datasource code linkage (#843) ─────────────────────────────────
    if job_id:
        job_manager.update_job(job_id, status_message="Processing ORM mappings...")
    orm_batch = []
    for fd in all_file_data:
        orm_mappings = fd.get("orm_mappings")
        if orm_mappings:
            orm_batch.extend(orm_mappings)
    if orm_batch:
        class_table_count = sum(1 for r in orm_batch if r.get("kind") == "class_table")
        query_count = sum(1 for r in orm_batch if r.get("kind") == "method_query")
        info_logger(
            f"[ORM] Writing {class_table_count} class→table mappings and {query_count} query links..."
        )
        writer.write_orm_mappings(orm_batch)
        writer.write_query_links(orm_batch)
        writer.write_spring_data_repo_links(orm_batch)

    # ── MyBatis XML mapper READS / WRITES edges ───────────────────────────────
    if not is_dependency and path.is_dir():
        if job_id:
            job_manager.update_job(job_id, status_message="Processing MyBatis XML mappers...")
        try:
            from ...tools.languages.mybatis import find_and_parse_mybatis_mappers
            mybatis_batch = find_and_parse_mybatis_mappers(path.resolve())
            if mybatis_batch:
                writer.write_mybatis_links(mybatis_batch)
        except Exception as _me:
            info_logger(f"[MYBATIS] Mapper parsing failed (skipping): {_me}")

    # ── Phase 4: embedding generation (optional, config-gated) ────────────────
    from ...cli.config_manager import get_config_value as _gcv
    if (_gcv("ENABLE_VECTOR_RESOLVE") or "false").lower() == "true":
        if job_id:
            job_manager.update_job(job_id, status_message="Generating embeddings...")
        try:
            from .embeddings import EmbeddingPipeline
            repo_path_str = str(path.resolve())
            info_logger("[EMBED] Starting embedding pipeline...")
            EmbeddingPipeline(writer.driver).run(repo_path_str)
            info_logger("[EMBED] Embedding pipeline complete.")
        except Exception as _ee:
            info_logger(f"[EMBED] Embedding pipeline failed (skipping): {_ee}")

    # ── Phase 5: inheritance-aware re-resolution (optional, config-gated) ─────
    if (_gcv("ENABLE_INHERIT_RESOLVE") or "false").lower() == "true":
        if job_id:
            job_manager.update_job(job_id, status_message="Running inheritance re-resolution...")
        try:
            from .resolution.post_resolution import run_inheritance_reresolve
            vector_resolver = None
            if (_gcv("ENABLE_VECTOR_RESOLVE") or "false").lower() == "true":
                try:
                    from .vector_resolver import VectorResolver
                    vector_resolver = VectorResolver(writer.driver)
                except Exception as _ve:
                    info_logger(f"[VECTOR] Resolver unavailable: {_ve}")
            repo_path_str = str(path.resolve())
            improved = run_inheritance_reresolve(writer.driver, repo_path_str, vector_resolver)
            info_logger(f"[INHERIT-RESOLVE] Post-resolution complete: {improved} edges improved")
        except Exception as _ie:
            info_logger(f"[INHERIT-RESOLVE] Post-resolution failed (skipping): {_ie}")

    if job_id:
        job_manager.update_job(job_id, status=JobStatus.COMPLETED, end_time=datetime.now())
