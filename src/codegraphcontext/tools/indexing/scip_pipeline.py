# src/codegraphcontext/tools/indexing/scip_pipeline.py
"""SCIP-based indexing orchestration."""

from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from ...core.cgcignore import build_ignore_spec
from ...core.jobs import JobManager, JobStatus
from ...utils.debug_log import debug_log, error_logger, info_logger, warning_logger
from ...utils.path_ignore import file_path_has_ignore_dir_segment
from .constants import DEFAULT_IGNORE_PATTERNS
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
    cgcignore_path: Optional[str] = None,
) -> None:
    """Run SCIP CLI, write graph, supplement with Tree-sitter, write SCIP CALLS edges."""
    ScipIndexer = scip_indexer_mod.ScipIndexer
    ScipIndexParser = scip_indexer_mod.ScipIndexParser

    if job_id:
        job_manager.update_job(job_id, status=JobStatus.RUNNING)

    repo_root = path if path.is_dir() else path.parent.resolve()
    writer.add_repository_to_graph(repo_root, is_dependency)
    repo_name = repo_root.name
    index_root = path.resolve() if path.is_dir() else path.parent.resolve()

    ignore_spec = None
    try:
        ignore_spec, resolved_cgcignore = build_ignore_spec(
            ignore_root=index_root,
            default_patterns=DEFAULT_IGNORE_PATTERNS,
            explicit_path=cgcignore_path,
        )
        if resolved_cgcignore:
            debug_log(
                f"SCIP using .cgcignore at {resolved_cgcignore} "
                f"(filtering relative to {index_root})"
            )
    except OSError as e:
        warning_logger(f"Could not load/create .cgcignore for SCIP indexing: {e}")

    def should_skip_file(file_path: Path) -> bool:
        if file_path.is_file() and file_path_has_ignore_dir_segment(file_path, index_root):
            return True
        if not ignore_spec:
            return False
        try:
            rel_path = file_path.relative_to(index_root).as_posix()
        except ValueError:
            return False
        return ignore_spec.match_file(rel_path)

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
        if ignore_spec:
            files_data = {
                abs_path_str: file_data
                for abs_path_str, file_data in files_data.items()
                if not should_skip_file(Path(abs_path_str))
            }
        file_paths = [Path(p) for p in files_data.keys() if Path(p).exists()]

        imports_map = pre_scan_for_imports(file_paths, parsers_keys, get_parser)

        if job_id:
            job_manager.update_job(job_id, total_files=len(files_data))

        processed = 0
        for abs_path_str, file_data in files_data.items():
            file_path = Path(abs_path_str)
            if should_skip_file(file_path):
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

                        ts_item_map = {}
                        ts_key_map = {}
                        for k in ["classes", "structs", "traits", "interfaces"]:
                            for c in ts_data.get(k, []):
                                ts_item_map[c["name"]] = c
                                ts_key_map[c["name"]] = k

                        new_file_data = {k: [] for k in ["classes", "structs", "traits", "interfaces"]}
                        
                        for key in ["classes", "structs", "traits", "interfaces"]:
                            for item in file_data.get(key, []):
                                ts_item = ts_item_map.get(item["name"])
                                target_key = key
                                if ts_item:
                                    item.update({
                                        "source": ts_item.get("source"),
                                    })
                                    item["bases"] = item.get("bases") or ts_item.get("bases", [])
                                    # Move to Tree-sitter's preferred category if they disagree
                                    if ts_key_map[item["name"]] != key:
                                        target_key = ts_key_map[item["name"]]
                                        
                                new_file_data[target_key].append(item)
                                
                        for key in ["classes", "structs", "traits", "interfaces"]:
                            file_data[key] = new_file_data[key]

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

        # ── Supplementary pass: Tree-sitter-only for files SCIP missed ───
        # Some SCIP indexers (e.g. scip-php with Composer classmap) only
        # index a subset of repo files. Discover remaining parseable files
        # and index them via Tree-sitter so the graph has full coverage.
        scip_abs_paths = set(files_data.keys())
        supplemented = 0
        from .discovery import discover_files_to_index
        supplementary_files, _ = discover_files_to_index(
            index_root,
            cgcignore_path=cgcignore_path,
            supported_extensions=set(parsers_keys),
        )
        for repo_file in supplementary_files:
            abs_str = str(repo_file.resolve())
            if abs_str in scip_abs_paths:
                continue
            ts_parser = get_parser(repo_file.suffix)
            if not ts_parser:
                continue
            try:
                ts_data = ts_parser.parse(repo_file, is_dependency, index_source=True)
                if "error" in ts_data:
                    continue
                ts_data["repo_path"] = str(index_root)
                ts_data.setdefault("function_calls_scip", [])
                ts_data.setdefault("module_level_calls_scip", [])
                writer.add_file_to_graph(ts_data, repo_name, imports_map)
                # Also include in files_data so inheritance/calls resolution sees them
                files_data[abs_str] = ts_data
                supplemented += 1
                processed += 1
                if job_id:
                    job_manager.update_job(
                        job_id, processed_files=processed, current_file=abs_str
                    )
            except Exception as e:
                debug_log(f"Tree-sitter supplement (non-SCIP file) failed for {abs_str}: {e}")
        if supplemented:
            # Re-run pre_scan with the expanded file list so imports_map is complete
            all_paths = [Path(p) for p in files_data.keys() if Path(p).exists()]
            imports_map = pre_scan_for_imports(all_paths, parsers_keys, get_parser)
            info_logger(
                f"[SCIP+TS] Supplemented {supplemented} files not covered by SCIP indexer"
            )

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
