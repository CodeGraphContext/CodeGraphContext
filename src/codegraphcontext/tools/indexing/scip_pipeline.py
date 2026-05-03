"""SCIP-based indexing orchestration."""

from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from ...core.jobs import JobManager, JobStatus
from ...utils.debug_log import debug_log, error_logger, info_logger, warning_logger
from ...utils.path_ignore import file_path_has_ignore_dir_segment
from .persistence.writer import GraphWriter
from .pre_scan import pre_scan_for_imports
from .resolution.inheritance import build_inheritance_and_csharp_files


def name_from_symbol(symbol: str) -> str:
    import re

    s = symbol.rstrip(".#")
    s = re.sub(r"\(\)\.?$", "", s)
    parts = re.split(r"[/#]", s)
    last = parts[-1] if parts else symbol
    return last or symbol


async def run_scip_index_async(
    path: Path,
    is_dependency: bool,
    job_id: Optional[str],
    lang: str,
    writer: GraphWriter,
    job_manager: JobManager,
    parsers_keys: Any,
    get_parser: Callable[[str], Any],
    scip_indexer_mod: Any,
) -> None:
    """Run SCIP CLI, write graph, supplement with Tree-sitter, write SCIP CALLS edges."""
    ScipIndexer = scip_indexer_mod.ScipIndexer
    ScipIndexParser = scip_indexer_mod.ScipIndexParser

    if job_id:
        job_manager.update_job(job_id, status=JobStatus.RUNNING)

    writer.add_repository_to_graph(path, is_dependency)
    repo_name = path.name

    try:
        with tempfile.TemporaryDirectory(prefix="cgc_scip_") as tmpdir:
            scip_file = ScipIndexer().run(path, lang, Path(tmpdir))

            if not scip_file:
                warning_logger(
                    f"SCIP indexer produced no output for {path}. "
                    "Falling back to Tree-sitter."
                )
                raise RuntimeError("SCIP produced no index — triggering Tree-sitter fallback")

            scip_data = ScipIndexParser().parse(scip_file, path)

        if not scip_data:
            raise RuntimeError("SCIP parse returned empty result")

        files_data = scip_data.get("files", {})
        file_paths = [Path(p) for p in files_data.keys() if Path(p).exists()]

        imports_map = pre_scan_for_imports(file_paths, parsers_keys, get_parser)

        if job_id:
            job_manager.update_job(job_id, total_files=len(files_data))

        processed = 0
        index_root = path.resolve()
        for abs_path_str, file_data in files_data.items():
            file_path = Path(abs_path_str)
            if file_path.is_file() and file_path_has_ignore_dir_segment(file_path, index_root):
                continue
            file_data["repo_path"] = str(index_root)
            if job_id:
                job_manager.update_job(job_id, current_file=abs_path_str)

            ts_parser = get_parser(file_path.suffix)
            if file_path.exists() and ts_parser:
                try:
                    ts_data = ts_parser.parse(file_path, is_dependency, index_source=True)
                    if "error" not in ts_data:
                        ts_funcs = {f["name"]: f for f in ts_data.get("functions", [])}
                        for f in file_data.get("functions", []):
                            ts_f = ts_funcs.get(f["name"])
                            if ts_f:
                                f.update(
                                    {
                                        "source": ts_f.get("source"),
                                        "cyclomatic_complexity": ts_f.get("cyclomatic_complexity", 1),
                                        "decorators": ts_f.get("decorators", []),
                                    }
                                )

                        ts_classes = {c["name"]: c for c in ts_data.get("classes", [])}
                        for c in file_data.get("classes", []):
                            ts_c = ts_classes.get(c["name"])
                            if ts_c:
                                c["bases"] = ts_c.get("bases", [])

                        file_data["imports"] = ts_data.get("imports", [])
                        file_data["variables"] = ts_data.get("variables", [])
                except Exception as e:
                    debug_log(f"Tree-sitter supplement failed for {abs_path_str}: {e}")

            writer.add_file_to_graph(file_data, repo_name, imports_map)

            processed += 1
            if job_id:
                job_manager.update_job(job_id, processed_files=processed)
            if processed % 50 == 0:
                await asyncio.sleep(0)

        info_logger(
            f"[INHERITS] Resolving inheritance links across {len(files_data)} files..."
        )
        inheritance_batch, csharp_files = build_inheritance_and_csharp_files(
            list(files_data.values()), imports_map
        )
        writer.write_inheritance_links(inheritance_batch, csharp_files, imports_map)

        writer.write_scip_call_edges(files_data, name_from_symbol)

        if job_id:
            job_manager.update_job(job_id, status=JobStatus.COMPLETED, end_time=datetime.now())

    except RuntimeError:
        raise
    except Exception as e:
        error_logger(f"SCIP indexing failed for {path}: {e}")
        if job_id:
            job_manager.update_job(
                job_id, status=JobStatus.FAILED, end_time=datetime.now(), errors=[str(e)]
            )
