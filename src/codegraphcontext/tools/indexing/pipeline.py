# src/codegraphcontext/tools/indexing/pipeline.py
"""Orchestrates full-repo indexing (Tree-sitter path)."""

from __future__ import annotations

import asyncio
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ...core.jobs import JobManager, JobStatus
from ...utils.debug_log import debug_log, error_logger, info_logger, warning_logger
from .discovery import discover_files_to_index
from .persistence.writer import GraphWriter
from .pre_scan import pre_scan_for_imports
from .resolution.calls import build_function_call_groups
from .resolution.inheritance import (
    build_companion_of_links,
    build_decorated_by_links,
    build_elixir_implements_links,
    build_embeds_links,
    build_go_implements_links,
    build_haskell_implements_links,
    build_inheritance_and_csharp_files,
    build_metaclass_links,
    build_partial_of_links,
    build_part_of_links,
)


def build_index_summary(
    files: List[Path],
    parsers: Dict[str, str],
    all_file_data: List[Dict[str, Any]],
    resolved_call_groups: tuple,
    serialization_seconds: float,
    parse_failures: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Build CLI-facing metrics for a completed Tree-sitter indexing run."""
    extension_counts = Counter()
    for file in files:
        extension = file.suffix or file.name
        language = parsers.get(file.suffix, "generic")
        extension_counts[f"{extension} ({language})"] += 1

    # Exclude the synthetic `<module>` frame the Python parser adds per file —
    # it is the attribution target for module-level calls, not a function the
    # user wrote, and counting it inflated every reported total by one per file.
    function_nodes = sum(
        1
        for file_data in all_file_data
        for func in file_data.get("functions", [])
        if not func.get("is_synthetic") and func.get("name") != "<module>"
    )
    class_nodes = sum(len(file_data.get("classes", [])) for file_data in all_file_data)
    call_edges = sum(len(group) for group in resolved_call_groups)

    failed = list(parse_failures or [])

    return {
        "total_scanned_files": len(files),
        "files_by_extension": dict(sorted(extension_counts.items())),
        "function_nodes": function_nodes,
        "class_nodes": class_nodes,
        "call_edges": call_edges,
        "serialization_seconds": serialization_seconds,
        # A run where files failed to parse used to be indistinguishable from a
        # clean one: the summary had no failure row at all.
        "failed_files": len(failed),
        "failed_file_details": failed,
    }


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
    index_summary: Optional[Dict[str, Any]] = None,
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
    resolved_repo_path_str = path.resolve().as_posix() if path.is_dir() else path.parent.resolve().as_posix()

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
                
                file_data["_index_repo_path"] = str(repo_path)
                return file_data
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

    serialization_start = time.time()

    # Parsing remains concurrent, but graph writes are ordered so shared nodes
    # such as imported modules receive deterministic canonical metadata.
    # One unwritable file must not abort the run. There is no transaction here,
    # so an exception escaping this loop left a partially written graph with no
    # rollback and every remaining file silently unindexed.
    write_failures: List[Dict[str, Any]] = []
    for file_data in sorted(all_file_data, key=lambda data: str(data.get("path") or "")):
        repo_path = Path(file_data.pop("_index_repo_path"))
        try:
            if "error" not in file_data:
                await asyncio.to_thread(
                    writer.add_file_to_graph,
                    file_data,
                    repo_name,
                    imports_map,
                    repo_path_str=resolved_repo_path_str,
                )
            elif not file_data.get("unsupported"):
                await asyncio.to_thread(
                    add_minimal_file_node,
                    Path(file_data["path"]),
                    repo_path,
                    is_dependency,
                )
        except Exception as exc:  # noqa: BLE001 - keep indexing the other files
            path = file_data.get("path")
            write_failures.append({"path": path, "error": str(exc)})
            error_logger(f"Failed to write {path} to the graph: {exc}")
            file_data["error"] = str(exc)
            file_data["parse_failed"] = True

    if write_failures:
        warning_logger(
            f"{len(write_failures)} file(s) could not be written to the graph; "
            "the rest of the repository was still indexed."
        )

    # Capture genuine parse failures before the error entries are dropped —
    # build_index_summary runs much later, against the filtered list.
    parse_failures = [
        {"path": file_data.get("path"), "error": file_data.get("error")}
        for file_data in all_file_data
        if file_data.get("parse_failed")
    ]
    if parse_failures:
        warning_logger(
            f"{len(parse_failures)} file(s) failed to parse and contributed no "
            "symbols to the graph."
        )
        for failure in parse_failures[:10]:
            warning_logger(f"  parse failed: {failure['path']}: {failure['error']}")

    all_file_data = [file_data for file_data in all_file_data if "error" not in file_data]

    info_logger(
        f"File processing complete. {len(all_file_data)} files parsed. "
        f"Starting post-processing phase (inheritance + function calls)..."
    )

    t0 = time.time()
    if job_id:
        job_manager.update_job(job_id, status_message="Resolving inheritance links...")
    info_logger(f"[INHERITS] Resolving inheritance links across {len(all_file_data)} files...")
    inheritance_batch, csharp_files = build_inheritance_and_csharp_files(all_file_data, imports_map)
    implements_batch = build_go_implements_links(all_file_data)
    implements_batch.extend(build_haskell_implements_links(all_file_data))
    implements_batch.extend(build_elixir_implements_links(all_file_data))
    writer.write_inheritance_links(inheritance_batch, csharp_files, imports_map)
    writer.write_implements_links(implements_batch)
    writer.write_embeds_links(build_embeds_links(all_file_data))
    writer.write_companion_of_links(build_companion_of_links(all_file_data))
    writer.write_partial_of_links(build_partial_of_links(all_file_data))
    writer.write_part_of_links(build_part_of_links(all_file_data))
    writer.write_metaclass_links(build_metaclass_links(all_file_data, imports_map))
    writer.write_decorated_by_links(build_decorated_by_links(all_file_data, imports_map))
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
            repo_path_str = path.resolve().as_posix()
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
            repo_path_str = path.resolve().as_posix()
            improved = run_inheritance_reresolve(writer.driver, repo_path_str, vector_resolver)
            info_logger(f"[INHERIT-RESOLVE] Post-resolution complete: {improved} edges improved")
        except Exception as _ie:
            info_logger(f"[INHERIT-RESOLVE] Post-resolution failed (skipping): {_ie}")

    if index_summary is not None:
        index_summary.clear()
        index_summary.update(
            build_index_summary(
                files,
                parsers,
                all_file_data,
                resolved_calls,
                time.time() - serialization_start,
                parse_failures=parse_failures,
            )
        )

    if job_id:
        job_manager.update_job(job_id, status=JobStatus.COMPLETED, end_time=datetime.now())
