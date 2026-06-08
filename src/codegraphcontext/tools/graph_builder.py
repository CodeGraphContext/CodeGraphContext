# src/codegraphcontext/tools/graph_builder.py

# src/codegraphcontext/tools/graph_builder.py
"""Facade for graph indexing; implementation lives in indexing/."""
from __future__ import annotations

import asyncio
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING

from ..cli.config_manager import get_config_value
if TYPE_CHECKING:
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
        # Per-graph schema memoization. Writers are created on demand bound to a
        # specific graph_name so concurrent indexing jobs can target different
        # graphs without clobbering each other.
        self._schema_created: set = set()
        self._schema_lock = threading.Lock()
        self.last_call_resolution_diagnostics: list[Dict[str, Any]] = []
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
        
        self._parsed_cache = threading.local()
        # Ensure the default graph's schema exists so fresh servers fail fast.
        self.create_schema()

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

    def create_schema(self, graph_name: Optional[str] = None) -> None:
        """Create schema against the named graph, memoized per graph_name."""
        key = graph_name or ""
        if key in self._schema_created:
            return
        with self._schema_lock:
            if key in self._schema_created:
                return
            create_graph_schema(self.db_manager, graph_name=graph_name)
            self._schema_created.add(key)

    def _writer_for(self, graph_name: Optional[str] = None) -> GraphWriter:
        """Return a GraphWriter bound to ``graph_name`` (or the env default)."""
        self.create_schema(graph_name)
        return GraphWriter(self.db_manager, graph_name=graph_name)

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
        """Dispatches pre-scan to the correct language-specific implementation."""
        imports_map = {}
        
        # Group files by language/extension
        files_by_lang = {}
        for file in files:
            if file.suffix in self.parsers:
                lang_ext = file.suffix
                if lang_ext not in files_by_lang:
                    files_by_lang[lang_ext] = []
                files_by_lang[lang_ext].append(file)

        if '.py' in files_by_lang:
            from .languages import python as python_lang_module
            imports_map.update(python_lang_module.pre_scan_python(files_by_lang['.py'], self.get_parser('.py')))
        if '.ipynb' in files_by_lang:
            from .languages import python as python_lang_module
            imports_map.update(python_lang_module.pre_scan_python(files_by_lang['.ipynb'], self.get_parser('.ipynb')))
        if '.js' in files_by_lang:
            from .languages import javascript as js_lang_module
            imports_map.update(js_lang_module.pre_scan_javascript(files_by_lang['.js'], self.get_parser('.js')))
        if '.jsx' in files_by_lang:
            from .languages import javascript as js_lang_module
            imports_map.update(js_lang_module.pre_scan_javascript(files_by_lang['.jsx'], self.get_parser('.jsx')))
        if '.mjs' in files_by_lang:
            from .languages import javascript as js_lang_module
            imports_map.update(js_lang_module.pre_scan_javascript(files_by_lang['.mjs'], self.get_parser('.mjs')))
        if '.cjs' in files_by_lang:
            from .languages import javascript as js_lang_module
            imports_map.update(js_lang_module.pre_scan_javascript(files_by_lang['.cjs'], self.get_parser('.cjs')))
        if '.go' in files_by_lang:
             from .languages import go as go_lang_module
             imports_map.update(go_lang_module.pre_scan_go(files_by_lang['.go'], self.get_parser('.go')))
        if '.ts' in files_by_lang:
            from .languages import typescript as ts_lang_module
            imports_map.update(ts_lang_module.pre_scan_typescript(files_by_lang['.ts'], self.get_parser('.ts')))
        if '.tsx' in files_by_lang:
            from .languages import typescriptjsx as tsx_lang_module
            imports_map.update(tsx_lang_module.pre_scan_typescript(files_by_lang['.tsx'], self.get_parser('.tsx')))
        if '.cpp' in files_by_lang:
            from .languages import cpp as cpp_lang_module
            imports_map.update(cpp_lang_module.pre_scan_cpp(files_by_lang['.cpp'], self.get_parser('.cpp')))
        if '.h' in files_by_lang:
            from .languages import cpp as cpp_lang_module
            imports_map.update(cpp_lang_module.pre_scan_cpp(files_by_lang['.h'], self.get_parser('.h')))
        if '.hpp' in files_by_lang:
            from .languages import cpp as cpp_lang_module
            imports_map.update(cpp_lang_module.pre_scan_cpp(files_by_lang['.hpp'], self.get_parser('.hpp')))
        if '.hh' in files_by_lang:
            from .languages import cpp as cpp_lang_module
            imports_map.update(cpp_lang_module.pre_scan_cpp(files_by_lang['.hh'], self.get_parser('.hh')))
        if '.rs' in files_by_lang:
            from .languages import rust as rust_lang_module
            imports_map.update(rust_lang_module.pre_scan_rust(files_by_lang['.rs'], self.get_parser('.rs')))
        if '.c' in files_by_lang:
            from .languages import c as c_lang_module
            imports_map.update(c_lang_module.pre_scan_c(files_by_lang['.c'], self.get_parser('.c')))
        elif '.java' in files_by_lang:
            from .languages import java as java_lang_module
            imports_map.update(java_lang_module.pre_scan_java(files_by_lang['.java'], self.get_parser('.java')))
        elif '.rb' in files_by_lang:
            from .languages import ruby as ruby_lang_module
            imports_map.update(ruby_lang_module.pre_scan_ruby(files_by_lang['.rb'], self.get_parser('.rb')))
        elif '.cs' in files_by_lang:
            from .languages import csharp as csharp_lang_module
            imports_map.update(csharp_lang_module.pre_scan_csharp(files_by_lang['.cs'], self.get_parser('.cs')))
        if '.kt' in files_by_lang:
            from .languages import kotlin as kotlin_lang_module
            imports_map.update(kotlin_lang_module.pre_scan_kotlin(files_by_lang['.kt'], self.get_parser('.kt')))
        if '.scala' in files_by_lang:
            from .languages import scala as scala_lang_module
            imports_map.update(scala_lang_module.pre_scan_scala(files_by_lang['.scala'], self.get_parser('.scala')))
        if '.sc' in files_by_lang:
            from .languages import scala as scala_lang_module
            imports_map.update(scala_lang_module.pre_scan_scala(files_by_lang['.sc'], self.get_parser('.sc')))
        if '.swift' in files_by_lang:
            from .languages import swift as swift_lang_module
            imports_map.update(swift_lang_module.pre_scan_swift(files_by_lang['.swift'], self.get_parser('.swift')))
        if '.dart' in files_by_lang:
            from .languages import dart as dart_lang_module
            imports_map.update(dart_lang_module.pre_scan_dart(files_by_lang['.dart'], self.get_parser('.dart')))
        if '.pl' in files_by_lang:
            from .languages import perl as perl_lang_module
            imports_map.update(perl_lang_module.pre_scan_perl(files_by_lang['.pl'], self.get_parser('.pl')))
        if '.pm' in files_by_lang:
            from .languages import perl as perl_lang_module
            imports_map.update(perl_lang_module.pre_scan_perl(files_by_lang['.pm'], self.get_parser('.pm')))
        if '.ex' in files_by_lang:
            from .languages import elixir as elixir_lang_module
            imports_map.update(elixir_lang_module.pre_scan_elixir(files_by_lang['.ex'], self.get_parser('.ex')))
        if '.exs' in files_by_lang:
            from .languages import elixir as elixir_lang_module
            imports_map.update(elixir_lang_module.pre_scan_elixir(files_by_lang['.exs'], self.get_parser('.exs')))
        if '.el' in files_by_lang:
            from .languages import elisp as elisp_lang_module
            imports_map.update(elisp_lang_module.pre_scan_elisp(files_by_lang['.el'], self.get_parser('.el')))

        return imports_map

    def add_repository_to_graph(self, repo_path: Path, is_dependency: bool = False, graph_name: Optional[str] = None) -> None:
        self._writer_for(graph_name).add_repository_to_graph(repo_path, is_dependency)

    def add_file_to_graph(
        self, file_data: Dict, repo_name: str, imports_map: dict, repo_path_str: str = None, graph_name: Optional[str] = None
    ) -> None:
        self._writer_for(graph_name).add_file_to_graph(file_data, repo_name, imports_map, repo_path_str=repo_path_str)

    def link_function_calls(
        self,
        all_file_data: list[Dict],
        imports_map: dict,
        file_class_lookup: Optional[Dict[str, set]] = None,
        graph_name: Optional[str] = None,
    ) -> None:
        """Resolve and persist CALLS relationships (public API)."""
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
            self._writer_for(graph_name).write_function_call_groups(*groups)
        except Exception as exc:
            error_logger(f"[CALLS] Failed to persist call relationships: {exc}")
            raise

    def _create_all_function_calls(
        self, all_file_data: list[Dict], imports_map: dict, file_class_lookup: Optional[Dict[str, set]] = None, graph_name: Optional[str] = None,
    ) -> None:
        self.link_function_calls(all_file_data, imports_map, file_class_lookup, graph_name=graph_name)

    def link_inheritance(self, all_file_data: list[Dict], imports_map: dict, graph_name: Optional[str] = None) -> None:
        """Resolve and persist INHERITS / C# IMPLEMENTS (public API)."""
        info_logger(f"[INHERITS] Resolving inheritance links across {len(all_file_data)} files...")
        inheritance_batch, csharp_files = build_inheritance_and_csharp_files(all_file_data, imports_map)
        self._writer_for(graph_name).write_inheritance_links(inheritance_batch, csharp_files, imports_map)

    def _create_all_inheritance_links(self, all_file_data: list[Dict], imports_map: dict, graph_name: Optional[str] = None) -> None:
        self.link_inheritance(all_file_data, imports_map, graph_name=graph_name)

    def delete_file_from_graph(self, path: str, graph_name: Optional[str] = None) -> None:
        self._writer_for(graph_name).delete_file_from_graph(path)

    def delete_repository_from_graph(self, repo_path: str, graph_name: Optional[str] = None) -> bool:
        return self._writer_for(graph_name).delete_repository_from_graph(repo_path)

    def get_caller_file_paths(self, file_path_str: str, graph_name: Optional[str] = None) -> set:
        return self._writer_for(graph_name).get_caller_file_paths(file_path_str)

    def get_inheritance_neighbor_paths(self, file_path_str: str, graph_name: Optional[str] = None) -> set:
        return self._writer_for(graph_name).get_inheritance_neighbor_paths(file_path_str)

    def delete_outgoing_calls_from_files(self, file_paths: list, graph_name: Optional[str] = None) -> None:
        self._writer_for(graph_name).delete_outgoing_calls_from_files(file_paths)

    def delete_inherits_for_files(self, file_paths: list, graph_name: Optional[str] = None) -> None:
        self._writer_for(graph_name).delete_inherits_for_files(file_paths)

    def get_repo_class_lookup(self, repo_path: Path, graph_name: Optional[str] = None) -> dict:
        return self._writer_for(graph_name).get_repo_class_lookup(repo_path)

    def delete_relationship_links(self, repo_path: Path, graph_name: Optional[str] = None) -> None:
        self._writer_for(graph_name).delete_relationship_links(repo_path)

    def update_file_in_graph(self, path: Path, repo_path: Path, imports_map: dict, graph_name: Optional[str] = None):
        file_path_str = str(path.resolve())
        repo_name = repo_path.name

        self.delete_file_from_graph(file_path_str, graph_name=graph_name)

        if path.exists():
            file_data = self.parse_file(repo_path, path)

            if "error" not in file_data:
                self.add_file_to_graph(file_data, repo_name, imports_map, graph_name=graph_name)
                return file_data
            if not file_data.get("unsupported"):
                # Generic file type (.md, .yml, .json, etc.) — create a bare File node
                self.add_minimal_file_node(path, repo_path)
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
            from codegraphcontext.tools.indexing.discovery import discover_files_to_index
            supported_extensions = set(self.parsers.keys())
            files, _ = discover_files_to_index(
                path,
                supported_extensions=supported_extensions,
            )
            total_files = len(files)
            estimated_time = total_files * 0.05
            return total_files, estimated_time
        except Exception as e:
            error_logger(f"Could not estimate processing time for {path}: {e}")
            return None

    async def _build_graph_from_scip(
        self, path: Path, is_dependency: bool, job_id: Optional[str], lang: str, graph_name: Optional[str] = None
    ):
        from . import scip_indexer

        await run_scip_index_async(
            path,
            is_dependency,
            job_id,
            lang,
            self._writer_for(graph_name),
            self.job_manager,
            self.parsers.keys(),
            self.get_parser,
            scip_indexer,
        )

    def _name_from_symbol(self, symbol: str) -> str:
        return name_from_symbol(symbol)

    async def build_graph_from_path_async(
        self, path: Path, is_dependency: bool = False, job_id: str = None, cgcignore_path: str = None, graph_name: Optional[str] = None,
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
                        await self._build_graph_from_scip(path, is_dependency, job_id, detected_lang, graph_name=graph_name)
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

            writer = self._writer_for(graph_name)
            self.last_call_resolution_diagnostics = []

            def _add_minimal(file_path: Path, repo_path: Path, is_dependency: bool = False) -> None:
                writer.add_minimal_file_node(file_path, repo_path, is_dependency)

            await run_tree_sitter_index_async(
                path,
                is_dependency,
                job_id,
                cgcignore_path,
                writer,
                self.job_manager,
                self.parsers,
                self.get_parser,
                self.parse_file,
                _add_minimal,
                call_resolution_diagnostics=self.last_call_resolution_diagnostics,
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

    def add_minimal_file_node(self, file_path: Path, repo_path: Path, is_dependency: bool = False, graph_name: Optional[str] = None) -> None:
        self._writer_for(graph_name).add_minimal_file_node(file_path, repo_path, is_dependency)
