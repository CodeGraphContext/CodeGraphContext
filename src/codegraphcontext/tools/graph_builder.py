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

    def __init__(self, db_manager: DatabaseManager, job_manager: JobManager, loop: asyncio.AbstractEventLoop):
        """Initialize GraphBuilder.

        Parameters
        ----------
        db_manager : DatabaseManager
            Active database manager instance.
        job_manager : JobManager
            Job manager for tracking indexing progress.
        loop : asyncio.AbstractEventLoop
            Event loop for async operations.
        """
        self.db_manager = db_manager
        self.job_manager = job_manager
        self.loop = loop
        self.driver = self.db_manager.get_driver()
        self._writer = GraphWriter(self.driver, db_manager=self.db_manager)
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
        
        import threading
        self._parsed_cache = threading.local()
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
    def add_repository_to_graph(self, repo_path: Path, is_dependency: bool = False):
        """Adds a repository node using its absolute path as the unique key."""
        repo_name = repo_path.name
        repo_path_str = repo_path.resolve().as_posix()
        with self.driver.session() as session:
            session.run(
                """
                MERGE (r:Repository {path: $path})
                SET r.name = $name, r.is_dependency = $is_dependency
                """,
                path=repo_path_str,
                name=repo_name,
                is_dependency=is_dependency,
            )

    # First pass to add file and its contents
    def add_file_to_graph(self, file_data: Dict, repo_name: str, imports_map: dict, repo_path_str: str = None):
        """Adds a file and its contents using batched UNWIND queries (one round-trip per node type)."""
        file_path_str = Path(file_data['path']).resolve().as_posix()
        file_name = Path(file_path_str).name
        is_dependency = file_data.get('is_dependency', False)
        lang = file_data.get('lang')

        with self.driver.session() as session:
            # Resolve repo path — use caller-supplied value when available to skip a DB round-trip.
            if repo_path_str:
                resolved_repo_str = repo_path_str
            else:
                repo_result = session.run(
                    "MATCH (r:Repository {path: $repo_path}) RETURN r.path as path",
                    repo_path=Path(file_data['repo_path']).resolve().as_posix()
                ).single()
                resolved_repo_str = repo_result['path'] if repo_result else Path(file_data['repo_path']).resolve().as_posix()
                if not repo_result:
                    warning_logger(f"Repository node not found for {file_data['repo_path']} during indexing of {file_name}.")

            try:
                repo_path_obj = Path(resolved_repo_str).resolve()
                file_path_obj = Path(file_path_str).resolve()
                relative_path = str(file_path_obj.relative_to(repo_path_obj))
            except ValueError:
                try:
                    relative_path = os.path.relpath(str(file_path_obj), str(repo_path_obj))
                except Exception:
                    relative_path = file_name

            # ── UPSERT File node ─────────────────────────────────────────────
            session.run("""
                MERGE (f:File {path: $path})
                SET f.name = $name, f.relative_path = $relative_path, f.is_dependency = $is_dependency
            """, path=file_path_str, name=file_name, relative_path=relative_path, is_dependency=is_dependency)

            # ── Directory hierarchy + file link (one pass, sequential MERGEs) ─
            file_path_obj = Path(file_path_str).resolve()
            repo_path_obj = Path(resolved_repo_str).resolve()
            try:
                relative_path_to_file = file_path_obj.relative_to(repo_path_obj)
            except ValueError:
                relative_path_to_file = Path(os.path.relpath(str(file_path_obj), str(repo_path_obj)))
            parent_path = resolved_repo_str
            parent_label = 'Repository'
            for part in relative_path_to_file.parts[:-1]:
                current_path_str = f"{parent_path}/{part}"  # keep forward-slash DB paths
                session.run(f"""
                    MATCH (p:{parent_label} {{path: $parent_path}})
                    MERGE (d:Directory {{path: $current_path}})
                    SET d.name = $part
                    MERGE (p)-[:CONTAINS]->(d)
                """, parent_path=parent_path, current_path=current_path_str, part=part)
                parent_path = current_path_str
                parent_label = 'Directory'
            session.run(f"""
                MATCH (p:{parent_label} {{path: $parent_path}})
                MATCH (f:File {{path: $path}})
                MERGE (p)-[:CONTAINS]->(f)
            """, parent_path=parent_path, path=file_path_str)

            # ── Batch UPSERT all code nodes (functions, classes, etc.) ────────
            # To add a new language-specific node type (e.g., 'Trait' for Rust):
            # 1. Parser returns a list under a unique key (e.g., 'traits': [...]).
            # 2. Add a constraint for the label in create_schema().
            # 3. Add an entry to item_mappings below.
            item_mappings = [
                (file_data.get('functions', []),  'Function'),
                (file_data.get('classes', []),    'Class'),
                (file_data.get('traits', []),     'Trait'),
                (file_data.get('variables', []),  'Variable'),
                (file_data.get('interfaces', []), 'Interface'),
                (file_data.get('macros', []),     'Macro'),
                (file_data.get('structs', []),    'Struct'),
                (file_data.get('enums', []),      'Enum'),
                (file_data.get('unions', []),     'Union'),
                (file_data.get('records', []),    'Record'),
                (file_data.get('properties', []), 'Property'),
            ]
            params_batch = []  # accumulated for bulk parameter creation
            class_fn_batch = []  # accumulated for class->function CONTAINS links
            nested_fn_batch = []  # accumulated for function->function CONTAINS links

            for item_list, label in item_mappings:
                if not item_list:
                    continue
                batch = []
                for item in item_list:
                    row = dict(item)  # shallow copy so we can set defaults safely
                    if label == 'Function' and 'cyclomatic_complexity' not in row:
                        row['cyclomatic_complexity'] = 1
                    batch.append(self._sanitize_props(row))
                    if label == 'Function':
                        for arg_name in item.get('args', []):
                            params_batch.append({
                                'func_name': item['name'],
                                'line_number': item['line_number'],
                                'arg_name': arg_name,
                            })
                        if item.get('class_context'):
                            class_fn_batch.append({
                                'class_name': item['class_context'],
                                'class_line': item.get('class_context_line', -1)
                                if item.get('class_context_line') is not None
                                else -1,
                                'func_name': item['name'],
                                'func_line': item['line_number'],
                            })
                        if item.get('context_type') == 'function_definition':
                            nested_fn_batch.append({
                                'outer': item['context'],
                                'inner_name': item['name'],
                                'inner_line': item['line_number'],
                            })

                # Normalize batch: KuzuDB requires uniform struct keys AND
                # consistent types across all UNWIND items.  After
                # _sanitize_props some items may have STRING[] while others
                # have STRING (JSON-serialised) or None for the same key.
                # We force every field to a single canonical type.
                if batch:
                    import json as _json
                    all_keys = set()
                    for b in batch:
                        all_keys.update(b.keys())

                    for k in all_keys:
                        # Determine dominant concrete type
                        counts = {}
                        for b in batch:
                            v = b.get(k)
                            if v is not None:
                                counts[type(v).__name__] = counts.get(type(v).__name__, 0) + 1

                        dominant = max(counts, key=counts.get) if counts else 'str'

                        for b in batch:
                            v = b.get(k)
                            if dominant == 'list':
                                if isinstance(v, list):
                                    b[k] = [str(x) for x in v] if v else [""]
                                elif isinstance(v, str) and v:
                                    try:
                                        p = _json.loads(v)
                                        b[k] = [str(x) for x in p] if isinstance(p, list) and p else [""]
                                    except Exception:
                                        b[k] = [v]
                                else:
                                    b[k] = [""]
                            elif dominant == 'int':
                                if v is None or v == "":
                                    b[k] = 0
                                elif not isinstance(v, int):
                                    try:
                                        b[k] = int(v)
                                    except Exception:
                                        b[k] = 0
                            elif dominant == 'bool':
                                b[k] = bool(v) if v is not None else False
                            else:
                                if v is None:
                                    b[k] = ""
                                elif isinstance(v, list):
                                    b[k] = _json.dumps(v)
                                elif not isinstance(v, str):
                                    b[k] = str(v)

                    # Ensure consistent key order (KuzuDB structs are order-sensitive)
                    key_order = sorted(all_keys)
                    batch[:] = [{k: b[k] for k in key_order} for b in batch]

                # One UNWIND per label — replaces N individual session.run() calls.
                # Split into node creation + relationship linking to avoid
                # KuzuDB "Casting between NODE and NODE" errors when MERGE
                # on a relationship follows MERGE on a node in the same query.
                session.run(f"""
                    UNWIND $batch AS row
                    MERGE (n:{label} {{name: row.name, path: $file_path, line_number: row.line_number}})
                    SET n += row
                """, batch=batch, file_path=file_path_str)
                session.run(f"""
                    UNWIND $batch AS row
                    MATCH (f:File {{path: $file_path}})
                    MATCH (n:{label} {{name: row.name, path: $file_path, line_number: row.line_number}})
                    MERGE (f)-[:CONTAINS]->(n)
                """, batch=batch, file_path=file_path_str)

            # ── Batch: Function parameters ────────────────────────────────────
            if params_batch:
                session.run("""
                    UNWIND $batch AS row
                    MATCH (fn:Function {name: row.func_name, path: $file_path, line_number: row.line_number})
                    MERGE (p:Parameter {name: row.arg_name, path: $file_path, function_line_number: row.line_number})
                    SET p.name = row.arg_name, p.path = $file_path, p.function_line_number = row.line_number
                    MERGE (fn)-[:HAS_PARAMETER]->(p)
                """, batch=params_batch, file_path=file_path_str)

            # ── Batch: Class -[:CONTAINS]-> Function ──────────────────────────
            if class_fn_batch:
                # C++ out-of-line methods (.cpp defines what .h declares) are handled
                # in a dedicated post-pass (write_cpp_class_function_links) after ALL
                # file nodes exist, so the Class match never fails due to ordering.
                # Skip the cpp_batch here; only run the same-file pass for other langs.
                _cpp_exts = ('.cpp', '.cc', '.cxx', '.c++', '.C')
                other_batch = [] if file_path_str.endswith(_cpp_exts) else class_fn_batch
                if other_batch:
                    session.run("""
                        UNWIND $batch AS row
                        MATCH (c:Class {name: row.class_name, path: $file_path})
                        MATCH (fn:Function {name: row.func_name, path: $file_path, line_number: row.func_line})
                        WHERE row.class_line < 0 OR c.line_number = row.class_line
                        MERGE (c)-[:CONTAINS]->(fn)
                    """, batch=other_batch, file_path=file_path_str)

            # ── Batch: Nested Function -[:CONTAINS]-> Function ────────────────
            if nested_fn_batch:
                session.run("""
                    UNWIND $batch AS row
                    MATCH (outer:Function {name: row.outer, path: $file_path})
                    MATCH (inner:Function {name: row.inner_name, path: $file_path, line_number: row.inner_line})
                    MERGE (outer)-[:CONTAINS]->(inner)
                """, batch=nested_fn_batch, file_path=file_path_str)

            # ── Batch: Ruby Modules ───────────────────────────────────────────
            ruby_modules = file_data.get('modules', [])
            if ruby_modules:
                session.run("""
                    UNWIND $batch AS row
                    MERGE (mod:Module {name: row.name})
                    ON CREATE SET mod.lang = row.lang
                    ON MATCH  SET mod.lang = coalesce(mod.lang, row.lang)
                """, batch=[{'name': m['name'], 'lang': lang} for m in ruby_modules])

            # ── Batch: Imports → Module nodes + IMPORTS relationships ─────────
            js_imports = []
            other_imports = []
            for imp in file_data.get('imports', []):
                if lang == 'javascript':
                    module_name = imp.get('source')
                    if module_name:
                        js_imports.append({
                            'module_name': module_name,
                            'imported_name': imp.get('name', '*'),
                            'alias': imp.get('alias'),
                            'line_number': imp.get('line_number'),
                        })
                else:
                    module_name = imp.get('name') or imp.get('source') or imp.get('full_import_name')
                    if not module_name:
                        continue
                    full_import_name = imp.get('full_import_name') or imp.get('source') or module_name
                    other_imports.append({
                        'name': module_name,
                        'full_import_name': full_import_name,
                        'imported_name': imp.get('imported_name') or module_name,
                        'alias': imp.get('alias'),
                        'line_number': imp.get('line_number') or 0,
                        'lang': imp.get('lang') or lang,
                    })

            if js_imports:
                session.run("""
                    UNWIND $batch AS row
                    MATCH (f:File {path: $file_path})
                    MERGE (m:Module {name: row.module_name})
                    MERGE (f)-[r:IMPORTS {line_number: row.line_number}]->(m)
                    SET r.imported_name = row.imported_name,
                        r.alias = row.alias
                """, batch=js_imports, file_path=file_path_str)

            if other_imports:
                other_imports = sort_import_rows_for_metadata(other_imports)
                session.run("""
                    UNWIND $batch AS row
                    MATCH (f:File {path: $file_path})
                    MERGE (m:Module {name: row.name})
                    SET m.lang = coalesce(m.lang, row.lang),
                        m.full_import_name = coalesce(m.full_import_name, row.full_import_name)
                    MERGE (f)-[r:IMPORTS {line_number: row.line_number}]->(m)
                    SET r.alias = row.alias,
                        r.imported_name = row.imported_name,
                        r.full_import_name = row.full_import_name
                """, batch=other_imports, file_path=file_path_str)

            # ── Batch: Ruby Class INCLUDES Module ─────────────────────────────
            module_inclusions = file_data.get('module_inclusions', [])
            if module_inclusions:
                session.run("""
                    UNWIND $batch AS row
                    MATCH (c:Class {name: row.class_name, path: $file_path})
                    MERGE (m:Module {name: row.module_name})
                    MERGE (c)-[:INCLUDES]->(m)
                """, batch=[{'class_name': i['class'], 'module_name': i['module']} for i in module_inclusions],
                     file_path=file_path_str)

            # Class inheritance and function calls are handled in a second pass after all files are processed.

    # Second pass to create relationships that depend on all files being present like call functions and class inheritance
    def _resolve_function_call(self, call: Dict, caller_file_path: str, local_names: set, local_imports: dict, imports_map: dict, skip_external: bool) -> Optional[Dict]:
        """Resolve a single function call to its target."""
        return resolve_function_call(
            call,
            caller_file_path,
            local_names,
            local_imports,
            imports_map,
            skip_external,
        )

    def _create_all_function_calls(self, all_file_data: list[Dict], imports_map: dict, file_class_lookup: Optional[Dict] = None):
        """Create CALLS relationships using fully label-specific UNWIND queries (V3).
        Both caller AND called sides use specific labels — no OR scans anywhere.
        
        Args:
            file_class_lookup: Optional pre-built {file_path: set_of_class_names} covering the full
                repo. When supplied (incremental mode), the lookup is supplemented with data from
                all_file_data so newly-created/renamed classes are reflected immediately. When None
                (full-scan mode) the lookup is built solely from all_file_data as before.
        """
        skip_external = (get_config_value("SKIP_EXTERNAL_RESOLUTION") or "false").lower() == "true"

        # Build or supplement the global lookup: which names are classes in which files.
        # In incremental mode an externally-built lookup (from Neo4j) is passed in; we still
        # overlay the parsed subset so in-flight changes are reflected.
        if file_class_lookup is None:
            file_class_lookup = {}
        for fd in all_file_data:
            fp = Path(fd['path']).resolve().as_posix()
            file_class_lookup[fp] = {c['name'] for c in fd.get('classes', [])}
        
        # Phase 1: Resolve all calls, categorized by (caller_label, called_label)
        info_logger(f"[CALLS] Resolving function calls across {len(all_file_data)} files...")
        fn_to_fn = []     # Function -> Function (most common, no init lookup)
        fn_to_cls = []    # Function -> Class (needs init lookup)
        cls_to_fn = []    # Class -> Function
        cls_to_cls = []   # Class -> Class (needs init lookup)
        file_to_fn = []   # File -> Function
        file_to_cls = []  # File -> Class (needs init lookup)
        
        for idx, file_data in enumerate(all_file_data):
            caller_file_path = Path(file_data['path']).resolve().as_posix()
            func_names = {f['name'] for f in file_data.get('functions', [])}
            class_names = {c['name'] for c in file_data.get('classes', [])}
            local_names = func_names | class_names
            local_imports = {imp.get('alias') or imp['name'].split('.')[-1]: imp['name'] 
                            for imp in file_data.get('imports', [])}
            
            for call in file_data.get('function_calls', []):
                resolved = self._resolve_function_call(
                    call, caller_file_path, local_names, local_imports, imports_map, skip_external
                )
                if not resolved:
                    continue
                
                called_path = resolved.get('called_file_path', '')
                called_name = resolved['called_name']
                called_is_class = called_name in file_class_lookup.get(called_path, set())
                
                if resolved['type'] == 'file':
                    if called_is_class:
                        file_to_cls.append(resolved)
                    else:
                        file_to_fn.append(resolved)
                else:
                    caller_name = resolved['caller_name']
                    caller_is_class = caller_name in class_names
                    if caller_is_class:
                        (cls_to_cls if called_is_class else cls_to_fn).append(resolved)
                    else:
                        (fn_to_cls if called_is_class else fn_to_fn).append(resolved)
            
            if (idx + 1) % 1000 == 0:
                total = len(fn_to_fn) + len(fn_to_cls) + len(cls_to_fn) + len(cls_to_cls)
                file_total = len(file_to_fn) + len(file_to_cls)
                info_logger(f"[CALLS] Resolved {idx + 1}/{len(all_file_data)} files... "
                           f"({total} fn/cls calls, {file_total} file calls)")
        
        total_all = len(fn_to_fn) + len(fn_to_cls) + len(cls_to_fn) + len(cls_to_cls) + len(file_to_fn) + len(file_to_cls)
        info_logger(f"[CALLS] Resolution complete: fn→fn={len(fn_to_fn)}, fn→cls={len(fn_to_cls)}, "
                    f"cls→fn={len(cls_to_fn)}, cls→cls={len(cls_to_cls)}, "
                    f"file→fn={len(file_to_fn)}, file→cls={len(file_to_cls)}. Total={total_all}")
        
        # Phase 2: Batch write — fully label-specific queries (no OR scans)
        BATCH_SIZE = 1000
        
        Q_FN_TO_FN = """
            UNWIND $batch AS row
            MATCH (caller:Function {name: row.caller_name, path: row.caller_file_path, line_number: row.caller_line_number})
            MATCH (called:Function {name: row.called_name, path: row.called_file_path})
            CREATE (caller)-[:CALLS {line_number: row.line_number, args: row.args, full_call_name: row.full_call_name}]->(called)
        """
        Q_FN_TO_CLS = """
            UNWIND $batch AS row
            MATCH (caller:Function {name: row.caller_name, path: row.caller_file_path, line_number: row.caller_line_number})
            MATCH (called:Class {name: row.called_name, path: row.called_file_path})
            CREATE (caller)-[:CALLS {line_number: row.line_number, args: row.args, full_call_name: row.full_call_name}]->(called)
        """
        Q_CLS_TO_FN = """
            UNWIND $batch AS row
            MATCH (caller:Class {name: row.caller_name, path: row.caller_file_path, line_number: row.caller_line_number})
            MATCH (called:Function {name: row.called_name, path: row.called_file_path})
            CREATE (caller)-[:CALLS {line_number: row.line_number, args: row.args, full_call_name: row.full_call_name}]->(called)
        """
        Q_CLS_TO_CLS = """
            UNWIND $batch AS row
            MATCH (caller:Class {name: row.caller_name, path: row.caller_file_path, line_number: row.caller_line_number})
            MATCH (called:Class {name: row.called_name, path: row.called_file_path})
            CREATE (caller)-[:CALLS {line_number: row.line_number, args: row.args, full_call_name: row.full_call_name}]->(called)
        """
        Q_FILE_TO_FN = """
            UNWIND $batch AS row
            MATCH (caller:File {path: row.caller_file_path})
            MATCH (called:Function {name: row.called_name, path: row.called_file_path})
            CREATE (caller)-[:CALLS {line_number: row.line_number, args: row.args, full_call_name: row.full_call_name}]->(called)
        """
        Q_FILE_TO_CLS = """
            UNWIND $batch AS row
            MATCH (caller:File {path: row.caller_file_path})
            MATCH (called:Class {name: row.called_name, path: row.called_file_path})
            CREATE (caller)-[:CALLS {line_number: row.line_number, args: row.args, full_call_name: row.full_call_name}]->(called)
        """
        
        groups = [
            ("fn→fn", fn_to_fn, Q_FN_TO_FN),
            ("fn→cls", fn_to_cls, Q_FN_TO_CLS),
            ("cls→fn", cls_to_fn, Q_CLS_TO_FN),
            ("cls→cls", cls_to_cls, Q_CLS_TO_CLS),
            ("file→fn", file_to_fn, Q_FILE_TO_FN),
            ("file→cls", file_to_cls, Q_FILE_TO_CLS),
        ]
        
        import time as _time
        with self.driver.session() as session:
            for label, calls, query in groups:
                if not calls:
                    info_logger(f"[CALLS] {label}: 0 (skipped)")
                    continue
                t0 = _time.time()
                for i in range(0, len(calls), BATCH_SIZE):
                    batch = calls[i:i + BATCH_SIZE]
                    session.run(query, batch=batch)
                    written = min(i + BATCH_SIZE, len(calls))
                    if written % 5000 < BATCH_SIZE or written == len(calls):
                        elapsed = _time.time() - t0
                        info_logger(f"[CALLS] {label}: {written}/{len(calls)} ({elapsed:.1f}s)")
                elapsed = _time.time() - t0
                info_logger(f"[CALLS] {label} done: {len(calls)} in {elapsed:.1f}s")
        
        info_logger(f"[CALLS] All complete: {total_all} CALLS relationships processed.")

    def _resolve_inheritance_link(self, class_item: Dict, base_class_str: str, caller_file_path: str, local_class_names: set, local_imports: dict, imports_map: dict) -> Optional[Dict]:
        """Resolve a single inheritance link. Returns a dict with params or None."""
        if base_class_str == 'object':
            return None

        resolved_path = None
        target_class_name = base_class_str.split('.')[-1]

        if '.' in base_class_str:
            lookup_name = base_class_str.split('.')[0]
            if lookup_name in local_imports:
                full_import_name = local_imports[lookup_name]
                possible_paths = imports_map.get(target_class_name, [])
                for path in possible_paths:
                    if full_import_name.replace('.', '/') in path:
                        resolved_path = path
                        break
        else:
            lookup_name = base_class_str
            if lookup_name in local_class_names:
                resolved_path = caller_file_path
            elif lookup_name in local_imports:
                full_import_name = local_imports[lookup_name]
                possible_paths = imports_map.get(target_class_name, [])
                for path in possible_paths:
                    if full_import_name.replace('.', '/') in path:
                        resolved_path = path
                        break
            elif lookup_name in imports_map:
                possible_paths = imports_map[lookup_name]
                if len(possible_paths) == 1:
                    resolved_path = possible_paths[0]

        if resolved_path:
            return {
                'child_name': class_item['name'],
                'path': caller_file_path,
                'parent_name': target_class_name,
                'resolved_parent_file_path': resolved_path,
            }
        return None

    def _create_csharp_inheritance_and_interfaces(self, session, file_data: Dict, imports_map: dict):
        """Create INHERITS and IMPLEMENTS relationships for C# types."""
        if file_data.get('lang') != 'c_sharp':
            return
            
        caller_file_path = Path(file_data['path']).resolve().as_posix()
        
        # Collect all local type names
        local_type_names = set()
        for type_list in ['classes', 'interfaces', 'structs', 'records']:
            local_type_names.update(t['name'] for t in file_data.get(type_list, []))
        
        # Process all type declarations that can have bases
        for type_list_name, type_label in [('classes', 'Class'), ('structs', 'Struct'), ('records', 'Record'), ('interfaces', 'Interface')]:
            for type_item in file_data.get(type_list_name, []):
                if not type_item.get('bases'):
                    continue
                
                for base_str in type_item['bases']:
                    base_name = base_str.split('<')[0].strip()
                    
                    is_interface = False
                    resolved_path = caller_file_path
                    
                    for iface in file_data.get('interfaces', []):
                        if iface['name'] == base_name:
                            is_interface = True
                            break
                    
                    if base_name in imports_map:
                        possible_paths = imports_map[base_name]
                        if len(possible_paths) > 0:
                            resolved_path = possible_paths[0]
                    
                    base_index = type_item['bases'].index(base_str)
                    
                    if is_interface or (base_index > 0 and type_label == 'Class'):
                        session.run("""
                            MATCH (child {name: $child_name, path: $path})
                            WHERE child:Class OR child:Struct OR child:Record
                            MATCH (iface:Interface {name: $interface_name})
                            MERGE (child)-[:IMPLEMENTS]->(iface)
                        """,
                        child_name=type_item['name'],
                        path=caller_file_path,
                        interface_name=base_name)
                    else:
                        session.run("""
                            MATCH (child {name: $child_name, path: $path})
                            WHERE child:Class OR child:Record OR child:Interface
                            MATCH (parent {name: $parent_name})
                            WHERE parent:Class OR parent:Record OR parent:Interface
                            MERGE (child)-[:INHERITS]->(parent)
                        """,
                        child_name=type_item['name'],
                        path=caller_file_path,
                        parent_name=base_name)

    def _create_all_inheritance_links(self, all_file_data: list[Dict], imports_map: dict):
        """Create INHERITS relationships for all classes using batched UNWIND queries."""
        return self.pre_scan_imports(files)

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
            build_companion_of_links,
            build_decorated_by_links,
            build_elixir_implements_links,
            build_embeds_links,
            build_go_implements_links,
            build_haskell_implements_links,
            build_metaclass_links,
            build_partial_of_links,
            build_part_of_links,
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

    def delete_repository_from_graph(self, repo_path: str) -> bool:
        """Remove a repository node and all its contents from the graph.

        Parameters
        ----------
        repo_path : str
            Absolute path to the repository root.

        Returns
        -------
        bool
            ``True`` if the repository was found and removed.
        """
        return self._writer.delete_repository_from_graph(repo_path)

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
            else:
                file_data = parser.parse(path, is_dependency, index_source=index_source)
            file_data["repo_path"] = str(repo_path)
            return file_data
        except Exception as e:
            error_logger(f"Error parsing {path} with {parser.language_name} parser: {e}")
            debug_log(f"[parse_file] Error parsing {path}: {e}")
            return {"path": str(path), "error": str(e)}

    def estimate_processing_time(self, path: Path) -> Optional[Tuple[int, float]]:
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
        self, path: Path, is_dependency: bool, job_id: Optional[str], lang: str, cgcignore_path: Optional[str] = None
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
            cgcignore_path,
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
