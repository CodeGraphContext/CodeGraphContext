# src/codegraphcontext/tools/graph_builder.py

# src/codegraphcontext/tools/graph_builder.py
"""Facade for graph indexing.

Implementation lives in the ``indexing/`` subpackage, including
parsers, persistence, resolution, and schema management.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING

from ..cli.config_manager import get_config_value
if TYPE_CHECKING:
    from ..core.database import DatabaseManager
from ..core.jobs import JobManager, JobStatus
from ..utils.debug_log import debug_log, error_logger, info_logger, warning_logger
from .indexing.constants import DEFAULT_IGNORE_PATTERNS
from .indexing.persistence.writer import GraphWriter, sort_import_rows_for_metadata
from .indexing.pipeline import run_tree_sitter_index_async
from .indexing.pre_scan import pre_scan_for_imports
from .indexing.resolution.calls import build_function_call_groups, resolve_function_call
from .indexing.resolution.inheritance import build_inheritance_and_csharp_files
from .indexing.sanitize import MAX_STR_LEN, sanitize_props
from .indexing.schema import create_graph_schema
from .indexing.scip_pipeline import name_from_symbol, run_scip_index_async
from .tree_sitter_parser import TreeSitterParser


class GraphBuilder:
    """Build and manage the code graph.

    Provides a high-level facade over the indexing pipeline, including
    repository ingestion, file parsing, call resolution, and inheritance
    linking for Neo4j, FalkorDB, and Kùzu backends.
    """

    def __init__(self, db_manager: DatabaseManager, job_manager: JobManager, loop: asyncio.AbstractEventLoop, graph_name: str = None):
        """Initialize GraphBuilder.

        Parameters
        ----------
        db_manager : DatabaseManager
            Active database manager instance.
        job_manager : JobManager
            Job manager for tracking indexing progress.
        loop : asyncio.AbstractEventLoop
            Event loop for async operations.
        graph_name : str, optional
            Named graph to write into, on backends that support multiple
            graphs per instance (FalkorDB). None selects the default graph
            (#1558).
        """
        self.db_manager = db_manager
        self.job_manager = job_manager
        self.loop = loop
        self.graph_name = graph_name
        self._writer = GraphWriter(self.db_manager.get_driver(graph_name), db_manager=self.db_manager)
        self.last_call_resolution_diagnostics: list[Dict[str, Any]] = []
        self.last_index_summary: Dict[str, Any] = {}
        self.parsers = {
            ".py": "python",
            ".ipynb": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".mjs": "javascript",
            ".cjs": "javascript",
            ".go": "go",
            ".ts": "typescript",
            ".mts": "typescript",
            ".cts": "typescript",
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
            ".el": "elisp",
            ".sol": "solidity",
            ".html": "html",
            ".css": "css",
            ".svelte": "svelte",
            ".vue": "vue",
        }
        
        # Files that should be added to the graph as minimal File nodes, even if not parsed
        # Keep in sync with discovery._GENERIC_EXTENSIONS / _GENERIC_FILENAMES.
        # Dotfiles have no suffix, so they must be matched by name, not extension.
        self.generic_extensions = {
            ".toml", ".sh", ".yaml", ".yml", ".json", ".ini", ".cfg", ".md", ".txt",
            ".bat", ".ps1"
        }
        # Literal dotfiles/config filenames have no suffix (e.g. Path(".gitignore").suffix == ""),
        # so they must be matched by name rather than extension.
        self.generic_filenames = {
            "Dockerfile", "Makefile", ".gitignore", ".dockerignore", ".env"
        }
        
        import threading
        self._parsed_cache = threading.local()
        self.create_schema()

    @property
    def driver(self):
        """Driver for this builder's graph (default graph unless a
        graph_name was given at construction)."""
        return self.db_manager.get_driver(self.graph_name)

    def _driver_for(self, graph_name: str = None):
        """Get driver for a specific graph, or default."""
        return self.db_manager.get_driver(graph_name)

    def get_parser(self, extension: str) -> Optional[TreeSitterParser]:
        """Gets or creates a TreeSitterParser for the given extension (thread-local)."""
        lang_name = self.parsers.get(extension)
        if not lang_name:
            return None

        if not hasattr(self._parsed_cache, 'parsers'):
            self._parsed_cache.parsers = {}

        if lang_name not in self._parsed_cache.parsers:
            try:
                self._parsed_cache.parsers[lang_name] = TreeSitterParser(lang_name)
            except Exception as e:
                warning_logger(f"Failed to initialize parser for {lang_name}: {e}")
                return None
        return self._parsed_cache.parsers[lang_name]

    def create_schema(self, graph_name: str = None) -> None:
        create_graph_schema(self._driver_for(graph_name), self.db_manager)

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
        """Build global imports map from language pre-scans.

        Public API for watchers and the indexing pipeline.

        Parameters
        ----------
        files : list[Path]
            List of file paths to scan for import declarations.

        Returns
        -------
        dict
            Global imports mapping ``{name: [file_paths]}`` used for
            cross-file relationship resolution.
        """
        return pre_scan_for_imports(files, self.parsers, self.get_parser)


    # Language-agnostic method
    def add_repository_to_graph(self, repo_path: Path, is_dependency: bool = False) -> None:
        """Add a repository node to the graph.

        Delegates to :meth:`GraphWriter.add_repository_to_graph`.

        Parameters
        ----------
        repo_path : Path
            Filesystem path to the repository root.
        is_dependency : bool, optional
            Whether this repository is a dependency (default ``False``).
        """
        self._writer.add_repository_to_graph(repo_path, is_dependency)

    def add_file_to_graph(
        self, file_data: Dict, repo_name: str, imports_map: dict, repo_path_str: str = None
    ) -> None:
        """Add a file and its parsed contents to the graph.

        Delegates to :meth:`GraphWriter.add_file_to_graph`.

        Parameters
        ----------
        file_data : Dict
            Parsed file data including functions, classes, imports, etc.
        repo_name : str
            Name of the parent repository.
        imports_map : dict
            Global imports map for cross-file resolution.
        repo_path_str : str, optional
            Pre-resolved repository path to skip a DB lookup.
        """
        self._writer.add_file_to_graph(file_data, repo_name, imports_map, repo_path_str=repo_path_str)

    def link_function_calls(
        self,
        all_file_data: list[Dict],
        imports_map: dict,
        file_class_lookup: Optional[Dict[str, set]] = None,
    ) -> None:
        """Resolve and persist CALLS relationships.

        Parameters
        ----------
        all_file_data : list[Dict]
            Parsed data for all files in the repository.
        imports_map : dict
            Global imports map for cross-file resolution.
        file_class_lookup : dict, optional
            Pre-built ``{file_path: set_of_class_names}`` for incremental mode.
        """
        diagnostics: list[Dict[str, Any]] = []
        groups = build_function_call_groups(
            all_file_data,
            imports_map,
            file_class_lookup,
            diagnostics=diagnostics,
        )
        self.last_call_resolution_diagnostics = diagnostics
        if diagnostics:
            sample = ", ".join(
                f"{d.get('full_call_name')}:{d.get('reason')}"
                for d in diagnostics[:5]
            )
            info_logger(
                f"[CALLS] Skipped {len(diagnostics)} unresolved call(s). "
                f"Sample: {sample}"
            )
        try:
            self._writer.write_function_call_groups(*groups)
        except Exception as exc:
            error_logger(f"[CALLS] Failed to persist call relationships: {exc}")
            raise

    def _create_all_function_calls(
        self, all_file_data: list[Dict], imports_map: dict, file_class_lookup: Optional[Dict[str, set]] = None
    ) -> None:
        self.link_function_calls(all_file_data, imports_map, file_class_lookup)

    def link_inheritance(self, all_file_data: list[Dict], imports_map: dict) -> None:
        """Resolve and persist INHERITS / C# IMPLEMENTS / Go IMPLEMENTS relationships.

        Parameters
        ----------
        all_file_data : list[Dict]
            Parsed data for all files in the repository.
        imports_map : dict
            Global imports map for cross-file resolution.
        """
        from .indexing.resolution.inheritance import (
            build_binds_links,
            build_companion_of_links,
            build_decorated_by_links,
            build_elixir_implements_links,
            build_embeds_links,
            build_go_implements_links,
            build_haskell_implements_links,
            build_metaclass_links,
            build_partial_of_links,
            build_part_of_links,
            build_previews_links,
        )

        info_logger(f"[INHERITS] Resolving inheritance links across {len(all_file_data)} files...")
        inheritance_batch, csharp_files = build_inheritance_and_csharp_files(all_file_data, imports_map)
        implements_batch = build_go_implements_links(all_file_data)
        implements_batch.extend(build_haskell_implements_links(all_file_data))
        implements_batch.extend(build_elixir_implements_links(all_file_data))
        self._writer.write_inheritance_links(inheritance_batch, csharp_files, imports_map)
        self._writer.write_implements_links(implements_batch)
        self._writer.write_embeds_links(build_embeds_links(all_file_data))
        self._writer.write_companion_of_links(build_companion_of_links(all_file_data))
        self._writer.write_partial_of_links(build_partial_of_links(all_file_data))
        self._writer.write_part_of_links(build_part_of_links(all_file_data))
        self._writer.write_metaclass_links(build_metaclass_links(all_file_data, imports_map))
        self._writer.write_decorated_by_links(build_decorated_by_links(all_file_data, imports_map))
        self._writer.write_binds_links(build_binds_links(all_file_data, imports_map))
        self._writer.write_previews_links(build_previews_links(all_file_data, imports_map))

    def _create_all_inheritance_links(self, all_file_data: list[Dict], imports_map: dict) -> None:
        self.link_inheritance(all_file_data, imports_map)

    def delete_file_from_graph(self, path: str) -> None:
        """Remove a file node and all its relationships from the graph.

        Parameters
        ----------
        path : str
            Absolute path of the file to remove.
        """
        self._writer.delete_file_from_graph(path)

    def delete_repository_from_graph(self, repo_path: str, graph_name: str = None) -> bool:
        """Remove a repository node and all its contents from the graph.

        Parameters
        ----------
        repo_path : str
            Absolute path to the repository root.
        graph_name : str, optional
            Name of the FalkorDB graph to target. When ``None`` the default
            graph is used; otherwise a writer bound to that graph's driver
            performs the deletion.

        Returns
        -------
        bool
            ``True`` if the repository was found and removed.
        """
        if graph_name is None:
            return self._writer.delete_repository_from_graph(repo_path)
        return GraphWriter(self._driver_for(graph_name)).delete_repository_from_graph(repo_path)

    def get_caller_file_paths(self, file_path_str: str) -> set:
        """Get all files that have CALLS relationships to the given file.

        Parameters
        ----------
        file_path_str : str
            Absolute path of the target file.

        Returns
        -------
        set
            Set of file paths that call into the target file.
        """
        return self._writer.get_caller_file_paths(file_path_str)

    def get_repo_file_paths(self, repo_path: Path) -> set:
        """Get all file paths indexed for a repository.

        Parameters
        ----------
        repo_path : Path
            Path to the repository root.

        Returns
        -------
        set
            Set of absolute file paths in the repository.
        """
        return self._writer.get_repo_file_paths(repo_path)

    def get_inheritance_neighbor_paths(self, file_path_str: str) -> set:
        """Get files with INHERITS relationships to/from the given file.

        Parameters
        ----------
        file_path_str : str
            Absolute path of the target file.

        Returns
        -------
        set
            Set of file paths connected via inheritance relationships.
        """
        return self._writer.get_inheritance_neighbor_paths(file_path_str)

    def delete_outgoing_calls_from_files(self, file_paths: list) -> None:
        """Remove outgoing CALLS relationships from the specified files.

        Parameters
        ----------
        file_paths : list
            List of absolute file paths.
        """
        self._writer.delete_outgoing_calls_from_files(file_paths)

    def delete_inherits_for_files(self, file_paths: list) -> None:
        """Remove INHERITS relationships for the specified files.

        Parameters
        ----------
        file_paths : list
            List of absolute file paths.
        """
        self._writer.delete_inherits_for_files(file_paths)

    def get_repo_class_lookup(self, repo_path: Path) -> dict:
        """Get a mapping of file paths to their defined class names.

        Parameters
        ----------
        repo_path : Path
            Path to the repository root.

        Returns
        -------
        dict
            Mapping of ``{file_path: set_of_class_names}``.
        """
        return self._writer.get_repo_class_lookup(repo_path)

    def delete_relationship_links(self, repo_path: Path) -> None:
        """Remove all relationship links for a repository.

        Parameters
        ----------
        repo_path : Path
            Path to the repository root.
        """
        self._writer.delete_relationship_links(repo_path)

    def update_file_in_graph(self, path: Path, repo_path: Path, imports_map: dict):
        """Update a file node in the graph (delete and re-index).

        Parameters
        ----------
        path : Path
            Path to the file to update.
        repo_path : Path
            Path to the parent repository.
        imports_map : dict
            Global imports map for cross-file resolution.
        """
        file_path_str = path.resolve().as_posix()
        repo_name = repo_path.name

        self.delete_file_from_graph(file_path_str)

        if path.exists():
            file_data = self.parse_file(repo_path, path)

            if "error" not in file_data:
                self.add_file_to_graph(file_data, repo_name, imports_map)
                return file_data
            if not file_data.get("unsupported"):
                # Generic file type (.md, .yml, .json, etc.) — create a bare File node
                self.add_minimal_file_node(path, repo_path)
                return file_data
            error_logger(f"Skipping graph add for {file_path_str} due to parsing error: {file_data['error']}")
            return None
        return {"deleted": True, "path": file_path_str}

    def parse_file(self, repo_path: Path, path: Path, is_dependency: bool = False) -> Dict:
        """Parse a source file and extract code structure.

        Parameters
        ----------
        repo_path : Path
            Path to the parent repository.
        path : Path
            Path to the file to parse.
        is_dependency : bool, optional
            Whether this file belongs to a dependency (default ``False``).

        Returns
        -------
        Dict
            Parsed file data with keys for functions, classes, imports, etc.
            On failure, returns a dict with an ``error`` key.
        """
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
            elif parser.language_name == "solidity":
                # Solidity resolves import remappings relative to the repo root.
                file_data = parser.parse(
                    path,
                    is_dependency,
                    index_source=index_source,
                    repo_path=repo_path,
                )
            else:
                file_data = parser.parse(path, is_dependency, index_source=index_source)
            file_data["repo_path"] = str(repo_path)
            # Most parsers catch their own exceptions and return {"path", "error"}
            # rather than raising, so the handler below never sees them. Flag the
            # failure here so it is distinguishable from the benign "generic file"
            # and "no parser" returns above, which share the same shape.
            if "error" in file_data:
                file_data["parse_failed"] = True
            return file_data
        except Exception as e:
            error_logger(f"Error parsing {path} with {parser.language_name} parser: {e}")
            debug_log(f"[parse_file] Error parsing {path}: {e}")
            # `parse_failed` distinguishes a genuine parser failure from the
            # benign "generic file type" / "no parser" returns above, which
            # otherwise share the same shape. Without it a broken parse and a
            # .md file take the identical branch in the pipeline and the run
            # still reports "Successfully finished indexing".
            return {"path": str(path), "error": str(e), "parse_failed": True}

    def estimate_processing_time(self, path: Path, cgcignore_path: Optional[str] = None) -> Optional[Tuple[int, float]]:
        """Estimate the time required to index a repository.

        Parameters
        ----------
        path : Path
            Path to the repository root.

        Returns
        -------
        tuple of (int, float) or None
            ``(total_files, estimated_seconds)``, or ``None`` on error.
        """
        try:
            from codegraphcontext.tools.indexing.discovery import discover_files_to_index
            supported_extensions = set(self.parsers.keys())
            # cgcignore_path must match what the indexing pipelines use:
            # counting files a context-specific ignore excludes made the
            # resume check expect more files than indexing will ever produce
            # ("only N of M files indexed" on every run, #1673).
            files, _ = discover_files_to_index(
                path,
                cgcignore_path=cgcignore_path,
                supported_extensions=supported_extensions,
            )
            total_files = len(files)
            estimated_time = total_files * 0.05
            return total_files, estimated_time
        except Exception as e:
            error_logger(f"Could not estimate processing time for {path}: {e}")
            return None

    async def _build_graph_from_scip(
        self, path: Path, is_dependency: bool, job_id: Optional[str], lang: str, cgcignore_path: Optional[str] = None
    ):
        from . import scip_indexer

        # Reset here too: without it a SCIP run left (and printed) the
        # PREVIOUS Tree-sitter run's summary from the same process (#1673).
        self.last_index_summary = {}
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
            cgcignore_path,
            index_summary=self.last_index_summary,
        )

    def _name_from_symbol(self, symbol: str) -> str:
        """Extract a human-readable name from a SCIP symbol string.

        Parameters
        ----------
        symbol : str
            SCIP symbol identifier.

        Returns
        -------
        str
            Simplified name extracted from the symbol.
        """
        return name_from_symbol(symbol)

    async def build_graph_from_path_async(
        self, path: Path, is_dependency: bool = False, job_id: str = None, cgcignore_path: str = None
    ):
        try:
            scip_enabled = (get_config_value("SCIP_INDEXER") or "false").lower() == "true"
            if scip_enabled:
                from .scip_indexer import ScipIndexer, detect_project_lang, is_scip_available

                scip_langs_str = get_config_value("SCIP_LANGUAGES") or "python,typescript,javascript,go,rust,java,dart,cpp,c,csharp,php,ruby,kotlin,swift,elixir"
                scip_languages = [l.strip() for l in scip_langs_str.split(",") if l.strip()]
                detected_lang = detect_project_lang(path, scip_languages)

                if (
                    detected_lang in ("cpp", "c")
                    and path.is_dir()
                    and not ScipIndexer._find_compdb(path)
                ):
                    warning_logger(
                        "[SCIP] C/C++ project detected but no compile_commands.json was found "
                        f"(searched under {path.resolve()}). scip-clang needs a JSON compilation database "
                        "listing real compiler invocations (include paths, -D defines, -std, etc.). "
                        "Typical ways to create it: CMake with "
                        "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON, or run your build under "
                        "Bear (https://github.com/rizsotto/Bear) (e.g. `bear -- make`). "
                        "Without it, SCIP cannot index C/C++; CGC will fall back to Tree-sitter if SCIP fails. "
                        'See README section "SCIP indexing (optional)".'
                    )

                if detected_lang and is_scip_available(detected_lang):
                    info_logger(f"SCIP_INDEXER=true — using SCIP for language: {detected_lang}")
                    try:
                        await self._build_graph_from_scip(path, is_dependency, job_id, detected_lang, cgcignore_path)
                        return
                    except Exception as e:
                        warning_logger(
                            f"SCIP indexing failed for {path}: {e}. "
                            "Falling back to Tree-sitter."
                        )
                elif detected_lang:
                    warning_logger(
                        f"SCIP_INDEXER=true but scip-{detected_lang} binary not found. "
                        f"Falling back to Tree-sitter. Install it first."
                    )
                else:
                    info_logger(
                        "SCIP_INDEXER=true but no SCIP-supported language detected. "
                        "Falling back to Tree-sitter."
                    )

            self.last_call_resolution_diagnostics = []
            self.last_index_summary = {}
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
                call_resolution_diagnostics=self.last_call_resolution_diagnostics,
                index_summary=self.last_index_summary,
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
        """Create a minimal File node without parsing (for unsupported file types).

        Delegates to :meth:`GraphWriter.add_minimal_file_node`.

        Parameters
        ----------
        file_path : Path
            Path to the file.
        repo_path : Path
            Path to the parent repository.
        is_dependency : bool, optional
            Whether this file belongs to a dependency (default ``False``).
        """
        self._writer.add_minimal_file_node(file_path, repo_path, is_dependency)
