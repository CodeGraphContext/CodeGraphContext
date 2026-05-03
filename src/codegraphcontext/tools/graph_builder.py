
# src/codegraphcontext/tools/graph_builder.py
"""Facade for graph indexing; implementation lives in indexing/."""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from ..cli.config_manager import get_config_value
from ..core.database import DatabaseManager
from ..core.jobs import JobManager, JobStatus
from ..utils.debug_log import debug_log, error_logger, info_logger, warning_logger
from .indexing.constants import DEFAULT_IGNORE_PATTERNS
from .indexing.persistence.writer import GraphWriter
from .indexing.pipeline import run_tree_sitter_index_async
from .indexing.pre_scan import pre_scan_for_imports
from .indexing.resolution.calls import build_function_call_groups, resolve_function_call
from .indexing.resolution.inheritance import build_inheritance_and_csharp_files
from .indexing.sanitize import MAX_STR_LEN, sanitize_props
from .indexing.schema import create_graph_schema
from .indexing.scip_pipeline import name_from_symbol, run_scip_index_async
from .tree_sitter_parser import TreeSitterParser


class GraphBuilder:
    """Module for building and managing the code graph (Neo4j / Falkor / Kùzu)."""

    def __init__(self, db_manager: DatabaseManager, job_manager: JobManager, loop: asyncio.AbstractEventLoop):
        self.db_manager = db_manager
        self.job_manager = job_manager
        self.loop = loop
        self.driver = self.db_manager.get_driver()
        self._writer = GraphWriter(self.driver)
        self.parsers = {
            ".py": "python",
            ".ipynb": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".mjs": "javascript",
            ".cjs": "javascript",
            ".go": "go",
            ".ts": "typescript",
            ".d.ts": "typescript",
            ".tsx": "tsx",
            ".cpp": "cpp",
            ".h": "cpp",
            ".hpp": "cpp",
            ".hh": "cpp",
            ".rs": "rust",
            ".c": "c",
            ".java": "java",
            ".rb": "ruby",
            ".cs": "c_sharp",
            ".php": "php",
            ".kt": "kotlin",
            ".scala": "scala",
            ".sc": "scala",
            ".swift": "swift",
            ".hs": "haskell",
            ".dart": "dart",
            ".pl": "perl",
            ".pm": "perl",
            ".lua": "lua",
            ".ex": "elixir",
            ".exs": "elixir",
            ".html": "html",
            ".css": "css",
        }
        
        # Files that should be added to the graph as minimal File nodes, even if not parsed
        self.generic_extensions = {
            ".toml", ".sh", ".yaml", ".yml", ".json", ".ini", ".cfg", ".md", ".txt", ".env",
            ".bat", ".ps1", ".dockerignore", ".gitignore"
        }
        self.generic_filenames = {
            "Dockerfile", "Makefile"
        }
        
        self._parsed_cache = {}
        self.create_schema()

    def get_parser(self, extension: str) -> Optional[TreeSitterParser]:
        """Gets or creates a TreeSitterParser for the given extension."""
        lang_name = self.parsers.get(extension)
        if not lang_name:
            return None

        if lang_name not in self._parsed_cache:
            try:
                self._parsed_cache[lang_name] = TreeSitterParser(lang_name)
            except Exception as e:
                warning_logger(f"Failed to initialize parser for {lang_name}: {e}")
                return None
        return self._parsed_cache[lang_name]

    def create_schema(self) -> None:
        create_graph_schema(self.driver, self.db_manager)

    _MAX_STR_LEN = MAX_STR_LEN

    @staticmethod
    def _sanitize_props(props: Dict) -> Dict:
        return sanitize_props(props)

    def _resolve_function_call(
        self,
        call: Dict,
        caller_file_path: str,
        local_names: set,
        local_imports: dict,
        imports_map: dict,
        skip_external: bool,
    ):
        return resolve_function_call(
            call, caller_file_path, local_names, local_imports, imports_map, skip_external
        )

    def pre_scan_imports(self, files: list[Path]) -> dict:
        """Build global imports_map from language pre-scans (public API for watchers/pipeline)."""
        return pre_scan_for_imports(files, self.parsers, self.get_parser)

    def _pre_scan_for_imports(self, files: list[Path]) -> dict:
        return self.pre_scan_imports(files)

    def add_repository_to_graph(self, repo_path: Path, is_dependency: bool = False) -> None:
        self._writer.add_repository_to_graph(repo_path, is_dependency)

    def add_file_to_graph(
        self, file_data: Dict, repo_name: str, imports_map: dict, repo_path_str: str = None
    ) -> None:
        self._writer.add_file_to_graph(file_data, repo_name, imports_map, repo_path_str=repo_path_str)

    def link_function_calls(
        self,
        all_file_data: list[Dict],
        imports_map: dict,
        file_class_lookup: Optional[Dict[str, set]] = None,
    ) -> None:
        """Resolve and persist CALLS relationships (public API)."""
        groups = build_function_call_groups(all_file_data, imports_map, file_class_lookup)
        self._writer.write_function_call_groups(*groups)

    def _create_all_function_calls(
        self, all_file_data: list[Dict], imports_map: dict, file_class_lookup: Optional[Dict[str, set]] = None
    ) -> None:
        self.link_function_calls(all_file_data, imports_map, file_class_lookup)

    def link_inheritance(self, all_file_data: list[Dict], imports_map: dict) -> None:
        """Resolve and persist INHERITS / C# IMPLEMENTS (public API)."""
        info_logger(f"[INHERITS] Resolving inheritance links across {len(all_file_data)} files...")
        inheritance_batch, csharp_files = build_inheritance_and_csharp_files(all_file_data, imports_map)
        self._writer.write_inheritance_links(inheritance_batch, csharp_files, imports_map)

    def _create_all_inheritance_links(self, all_file_data: list[Dict], imports_map: dict) -> None:
        self.link_inheritance(all_file_data, imports_map)

    def delete_file_from_graph(self, path: str) -> None:
        self._writer.delete_file_from_graph(path)

    def delete_repository_from_graph(self, repo_path: str) -> bool:
        return self._writer.delete_repository_from_graph(repo_path)

    def get_caller_file_paths(self, file_path_str: str) -> set:
        return self._writer.get_caller_file_paths(file_path_str)

    def get_inheritance_neighbor_paths(self, file_path_str: str) -> set:
        return self._writer.get_inheritance_neighbor_paths(file_path_str)

    def delete_outgoing_calls_from_files(self, file_paths: list) -> None:
        self._writer.delete_outgoing_calls_from_files(file_paths)

    def delete_inherits_for_files(self, file_paths: list) -> None:
        self._writer.delete_inherits_for_files(file_paths)

    def get_repo_class_lookup(self, repo_path: Path) -> dict:
        return self._writer.get_repo_class_lookup(repo_path)

    def delete_relationship_links(self, repo_path: Path) -> None:
        self._writer.delete_relationship_links(repo_path)

    def update_file_in_graph(self, path: Path, repo_path: Path, imports_map: dict):
        file_path_str = str(path.resolve())
        repo_name = repo_path.name

        self.delete_file_from_graph(file_path_str)

        if path.exists():
            file_data = self.parse_file(repo_path, path)

            if "error" not in file_data:
                self.add_file_to_graph(file_data, repo_name, imports_map)
                return file_data
            error_logger(f"Skipping graph add for {file_path_str} due to parsing error: {file_data['error']}")
            return None
        return {"deleted": True, "path": file_path_str}

    def parse_file(self, repo_path: Path, path: Path, is_dependency: bool = False) -> Dict:
        ext = path.suffix
        if path.name.endswith(".d.ts"):
            ext = ".d.ts"

        if ext in self.generic_extensions or path.name in self.generic_filenames:
            debug_log(f"[parse_file] Adding generic file node for {path}")
            return {"path": str(path), "error": f"Generic file type {ext or path.name}", "unsupported": False}

        parser = self.get_parser(ext)
        if not parser:
            warning_logger(f"No parser found for file extension {ext}. Skipping {path}")
            return {"path": str(path), "error": f"No parser for {ext}", "unsupported": True}

        debug_log(f"[parse_file] Starting parsing for: {path} with {parser.language_name} parser")
        try:
            index_source = (get_config_value("INDEX_SOURCE") or "false").lower() == "true"
            if parser.language_name == "python":
                is_notebook = path.suffix == ".ipynb"
                file_data = parser.parse(
                    path,
                    is_dependency,
                    is_notebook=is_notebook,
                    index_source=index_source,
                )
            else:
                file_data = parser.parse(path, is_dependency, index_source=index_source)
            file_data["repo_path"] = str(repo_path)
            return file_data
        except Exception as e:
            error_logger(f"Error parsing {path} with {parser.language_name} parser: {e}")
            debug_log(f"[parse_file] Error parsing {path}: {e}")
            return {"path": str(path), "error": str(e)}

    def estimate_processing_time(self, path: Path) -> Optional[Tuple[int, float]]:
        try:
            supported_extensions = set(self.parsers.keys()) | self.generic_extensions
            if path.is_file():
                if path.suffix in supported_extensions or path.name in self.generic_filenames:
                    files = [path]
                else:
                    return 0, 0.0
            else:
                all_files = path.rglob("*")
                files = []
                for f in all_files:
                    if not f.is_file():
                        continue
                    ext = f.suffix
                    if f.name.endswith(".d.ts"):
                        ext = ".d.ts"
                    if ext in supported_extensions or f.name in self.generic_filenames:
                        files.append(f)

                ignore_dirs_str = get_config_value("IGNORE_DIRS") or ""
                if ignore_dirs_str:
                    ignore_dirs = {d.strip().lower() for d in ignore_dirs_str.split(",") if d.strip()}
                    if ignore_dirs:
                        kept_files = []
                        for f in files:
                            try:
                                parts = set(p.lower() for p in f.relative_to(path).parent.parts)
                                if not parts.intersection(ignore_dirs):
                                    kept_files.append(f)
                            except ValueError:
                                kept_files.append(f)
                        files = kept_files

            total_files = len(files)
            estimated_time = total_files * 0.05
            return total_files, estimated_time
        except Exception as e:
            error_logger(f"Could not estimate processing time for {path}: {e}")
            return None

    async def _build_graph_from_scip(
        self, path: Path, is_dependency: bool, job_id: Optional[str], lang: str
    ):
        from . import scip_indexer

        await run_scip_index_async(
            path,
            is_dependency,
            job_id,
            lang,
            self._writer,
            self.job_manager,
            self.parsers.keys(),
            self.get_parser,
            scip_indexer,
        )

    def _name_from_symbol(self, symbol: str) -> str:
        return name_from_symbol(symbol)

    async def build_graph_from_path_async(
        self, path: Path, is_dependency: bool = False, job_id: str = None, cgcignore_path: str = None
    ):
        try:
            scip_enabled = (get_config_value("SCIP_INDEXER") or "false").lower() == "true"
            if scip_enabled:
                from .scip_indexer import detect_project_lang, is_scip_available

                scip_langs_str = get_config_value("SCIP_LANGUAGES") or "python,typescript,go,rust,java"
                scip_languages = [l.strip() for l in scip_langs_str.split(",") if l.strip()]
                detected_lang = detect_project_lang(path, scip_languages)

                if detected_lang and is_scip_available(detected_lang):
                    info_logger(f"SCIP_INDEXER=true — using SCIP for language: {detected_lang}")
                    await self._build_graph_from_scip(path, is_dependency, job_id, detected_lang)
                    return
                if detected_lang:
                    warning_logger(
                        f"SCIP_INDEXER=true but scip-{detected_lang} binary not found. "
                        f"Falling back to Tree-sitter. Install it first."
                    )
                else:
                    info_logger(
                        "SCIP_INDEXER=true but no SCIP-supported language detected. "
                        "Falling back to Tree-sitter."
                    )

            await run_tree_sitter_index_async(
                path,
                is_dependency,
                job_id,
                cgcignore_path,
                self._writer,
                self.job_manager,
                self.parsers,
                self.get_parser,
                self.parse_file,
                self.add_minimal_file_node,
            )
        except Exception as e:
            error_message = str(e)
            error_logger(f"Failed to build graph for path {path}: {error_message}")
            if job_id:
                if (
                    "no such file found" in error_message
                    or "deleted" in error_message
                    or "not found" in error_message
                ):
                    status = JobStatus.CANCELLED
                else:
                    status = JobStatus.FAILED

                self.job_manager.update_job(
                    job_id, status=status, end_time=datetime.now(), errors=[str(e)]
                )

    def add_minimal_file_node(self, file_path: Path, repo_path: Path, is_dependency: bool = False) -> None:
        self._writer.add_minimal_file_node(file_path, repo_path, is_dependency)
