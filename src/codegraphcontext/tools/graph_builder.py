
# src/codegraphcontext/tools/graph_builder.py
import asyncio
from pathlib import Path
from typing import Any, Coroutine, Dict, Optional, Tuple
from datetime import datetime

from ..core.database import DatabaseManager
from ..core.cgcignore import build_ignore_spec
from ..core.jobs import JobManager, JobStatus
from ..utils.debug_log import debug_log, info_logger, error_logger, warning_logger

# New imports for tree-sitter (using tree-sitter-language-pack)
from tree_sitter import Language, Parser
from ..utils.tree_sitter_manager import get_tree_sitter_manager
from ..cli.config_manager import get_config_value
from ..utils.path_ignore import file_path_has_ignore_dir_segment
import fnmatch
 
DEFAULT_IGNORE_PATTERNS = [
    # Vendor / env dirs (gitignore-style; complements IGNORE_DIRS during indexing)
    "node_modules/",
    "venv/",
    ".venv/",
    "env/",
    ".env/",
    "dist/",
    "build/",
    "target/",
    "out/",
    ".git/",
    "__pycache__/",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.svg",
    "*.mp4",
    "*.mp3",
    "*.zip",
    "*.tar",
    "*.gz",
]

class TreeSitterParser:
    """A generic parser wrapper for a specific language using tree-sitter."""

    def __init__(self, language_name: str):
        self.language_name = language_name
        self.ts_manager = get_tree_sitter_manager()
        
        # Get the language (cached) and create a new parser for this instance
        self.language: Language = self.ts_manager.get_language_safe(language_name)
        # In tree-sitter 0.25+, Parser takes language in constructor
        self.parser = Parser(self.language)

        self.language_specific_parser = None
        if self.language_name == 'python':
            from .languages.python import PythonTreeSitterParser
            self.language_specific_parser = PythonTreeSitterParser(self)
        elif self.language_name == 'javascript':
            from .languages.javascript import JavascriptTreeSitterParser
            self.language_specific_parser = JavascriptTreeSitterParser(self)
        elif self.language_name == 'go':
            from .languages.go import GoTreeSitterParser
            self.language_specific_parser = GoTreeSitterParser(self)
        elif self.language_name == 'typescript':
            from .languages.typescript import TypescriptTreeSitterParser
            self.language_specific_parser = TypescriptTreeSitterParser(self)
        elif self.language_name == 'cpp':
            from .languages.cpp import CppTreeSitterParser
            self.language_specific_parser = CppTreeSitterParser(self)
        elif self.language_name == 'rust':
            from .languages.rust import RustTreeSitterParser
            self.language_specific_parser = RustTreeSitterParser(self)
        elif self.language_name == 'c':
            from .languages.c import CTreeSitterParser
            self.language_specific_parser = CTreeSitterParser(self)
        elif self.language_name == 'java':
            from .languages.java import JavaTreeSitterParser
            self.language_specific_parser = JavaTreeSitterParser(self)
        elif self.language_name == 'ruby':
            from .languages.ruby import RubyTreeSitterParser
            self.language_specific_parser = RubyTreeSitterParser(self)
        elif self.language_name == 'c_sharp':
            from .languages.csharp import CSharpTreeSitterParser
            self.language_specific_parser = CSharpTreeSitterParser(self)
        elif self.language_name == 'php':
            from .languages.php import PhpTreeSitterParser
            self.language_specific_parser = PhpTreeSitterParser(self)
        elif self.language_name == 'kotlin':
            from .languages.kotlin import KotlinTreeSitterParser
            self.language_specific_parser = KotlinTreeSitterParser(self)
        elif self.language_name == 'scala':
            from .languages.scala import ScalaTreeSitterParser
            self.language_specific_parser = ScalaTreeSitterParser(self)
        elif self.language_name == 'swift':
            from .languages.swift import SwiftTreeSitterParser
            self.language_specific_parser = SwiftTreeSitterParser(self)
        elif self.language_name == 'haskell':
            from .languages.haskell import HaskellTreeSitterParser
            self.language_specific_parser = HaskellTreeSitterParser(self)
        elif self.language_name == 'dart':
            from .languages.dart import DartTreeSitterParser
            self.language_specific_parser = DartTreeSitterParser(self)
        elif self.language_name == 'perl':
            from .languages.perl import PerlTreeSitterParser
            self.language_specific_parser = PerlTreeSitterParser(self)
        elif self.language_name == 'elixir':
            from .languages.elixir import ElixirTreeSitterParser
            self.language_specific_parser = ElixirTreeSitterParser(self)



    def parse(self, path: Path, is_dependency: bool = False, **kwargs) -> Dict:
        """Dispatches parsing to the language-specific parser."""
        if self.language_specific_parser:
            return self.language_specific_parser.parse(path, is_dependency, **kwargs)
        else:
            raise NotImplementedError(f"No language-specific parser implemented for {self.language_name}")

class GraphBuilder:
    """Module for building and managing the Neo4j code graph."""

    def __init__(self, db_manager: DatabaseManager, job_manager: JobManager, loop: asyncio.AbstractEventLoop):
        self.db_manager = db_manager
        self.job_manager = job_manager
        self.loop = loop
        self.driver = self.db_manager.get_driver()
        self.parsers = {
            '.py': 'python',
            '.ipynb': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.mjs': 'javascript',
            '.cjs': 'javascript',
            '.go': 'go',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.cpp': 'cpp',
            '.h': 'cpp',
            '.hpp': 'cpp',
            '.hh': 'cpp',
            '.rs': 'rust',
            '.c': 'c',
            # '.h': 'c', # Need to write an algo for distinguishing C vs C++ headers
            '.java': 'java',
            '.rb': 'ruby',
            '.cs': 'c_sharp',
            '.php': 'php',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.sc': 'scala',
            '.swift': 'swift',
            '.hs': 'haskell',
            '.dart': 'dart',
            '.pl': 'perl',
            '.pm': 'perl',
            '.ex': 'elixir',
            '.exs': 'elixir',
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

    # A general schema creation based on common features across languages
    def create_schema(self):
        """Create constraints and indexes in Neo4j."""
        # When adding a new node type with a unique key, add its constraint here.
        with self.driver.session() as session:
            try:
                session.run("CREATE CONSTRAINT repository_path IF NOT EXISTS FOR (r:Repository) REQUIRE r.path IS UNIQUE")
                session.run("CREATE CONSTRAINT path IF NOT EXISTS FOR (f:File) REQUIRE f.path IS UNIQUE")
                session.run("CREATE CONSTRAINT directory_path IF NOT EXISTS FOR (d:Directory) REQUIRE d.path IS UNIQUE")
                session.run("CREATE CONSTRAINT function_unique IF NOT EXISTS FOR (f:Function) REQUIRE (f.name, f.path, f.line_number) IS UNIQUE")
                session.run("CREATE CONSTRAINT class_unique IF NOT EXISTS FOR (c:Class) REQUIRE (c.name, c.path, c.line_number) IS UNIQUE")
                session.run("CREATE CONSTRAINT trait_unique IF NOT EXISTS FOR (t:Trait) REQUIRE (t.name, t.path, t.line_number) IS UNIQUE") # Added trait constraint
                session.run("CREATE CONSTRAINT interface_unique IF NOT EXISTS FOR (i:Interface) REQUIRE (i.name, i.path, i.line_number) IS UNIQUE")
                session.run("CREATE CONSTRAINT macro_unique IF NOT EXISTS FOR (m:Macro) REQUIRE (m.name, m.path, m.line_number) IS UNIQUE")
                session.run("CREATE CONSTRAINT variable_unique IF NOT EXISTS FOR (v:Variable) REQUIRE (v.name, v.path, v.line_number) IS UNIQUE")
                session.run("CREATE CONSTRAINT module_name IF NOT EXISTS FOR (m:Module) REQUIRE m.name IS UNIQUE")
                session.run("CREATE CONSTRAINT struct_cpp IF NOT EXISTS FOR (cstruct: Struct) REQUIRE (cstruct.name, cstruct.path, cstruct.line_number) IS UNIQUE")
                session.run("CREATE CONSTRAINT enum_cpp IF NOT EXISTS FOR (cenum: Enum) REQUIRE (cenum.name, cenum.path, cenum.line_number) IS UNIQUE")
                session.run("CREATE CONSTRAINT union_cpp IF NOT EXISTS FOR (cunion: Union) REQUIRE (cunion.name, cunion.path, cunion.line_number) IS UNIQUE")
                session.run("CREATE CONSTRAINT annotation_unique IF NOT EXISTS FOR (a:Annotation) REQUIRE (a.name, a.path, a.line_number) IS UNIQUE")
                session.run("CREATE CONSTRAINT record_unique IF NOT EXISTS FOR (r:Record) REQUIRE (r.name, r.path, r.line_number) IS UNIQUE")
                session.run("CREATE CONSTRAINT property_unique IF NOT EXISTS FOR (p:Property) REQUIRE (p.name, p.path, p.line_number) IS UNIQUE")
                
                # Indexes for language attribute
                session.run("CREATE INDEX function_lang IF NOT EXISTS FOR (f:Function) ON (f.lang)")
                session.run("CREATE INDEX class_lang IF NOT EXISTS FOR (c:Class) ON (c.lang)")
                session.run("CREATE INDEX annotation_lang IF NOT EXISTS FOR (a:Annotation) ON (a.lang)")
                
                is_falkordb = getattr(self.db_manager, 'get_backend_type', lambda: 'neo4j')() != 'neo4j'
                if is_falkordb:
                    # FalkorDB uses db.idx.fulltext.createNodeIndex per label
                    for label in ['Function', 'Class']:
                        try:
                            session.run(f"CALL db.idx.fulltext.createNodeIndex('{label}', 'name', 'source', 'docstring')")
                        except Exception:
                            pass  # Index may already exist
                else:
                    session.run("""
                        CREATE FULLTEXT INDEX code_search_index IF NOT EXISTS
                        FOR (n:Function|Class|Variable)
                        ON EACH [n.name, n.source, n.docstring]
                    """)
                
                info_logger("Database schema verified/created successfully")
            except Exception as e:
                warning_logger(f"Schema creation warning: {e}")

    # Neo4j RANGE indexes have an ~8 kB key-size limit.  Long C++ template
    # function names (e.g. from llama.cpp) can exceed this, causing
    # "Property value is too large to index" errors.  We cap string properties
    # at 4096 chars, which is comfortably under the 8 kB boundary.
    _MAX_STR_LEN = 4096

    @staticmethod
    def _sanitize_props(props: Dict) -> Dict:
        """Return a copy of *props* with all values coerced to database-safe types.

        FalkorDB and KùzuDB only accept node properties that are primitives
        (str, int, float, bool, None) or flat lists of primitives.  Complex
        values such as tuples, dicts, or lists-of-dicts that come from language
        parsers (e.g. C's ``detailed_args`` or Scala's tuple ``class_context``)
        are serialized to a JSON string so the data is preserved rather than
        being silently dropped.

        Additionally, string values are truncated to _MAX_STR_LEN characters to
        avoid Neo4j's RANGE-index 8 kB property-size limit (triggered by very
        long C++ template-mangled function names).
        """
        import json

        MAX = GraphBuilder._MAX_STR_LEN

        def _is_primitive(v):
            return isinstance(v, (str, int, float, bool)) or v is None

        def _is_flat_list(v):
            return isinstance(v, list) and all(_is_primitive(item) for item in v)

        def _coerce(v):
            if isinstance(v, str):
                # Truncate long strings to stay within Neo4j RANGE index limits
                return v[:MAX] if len(v) > MAX else v
            if _is_primitive(v):
                return v
            if _is_flat_list(v):
                # Truncate any long strings in lists too
                return [s[:MAX] if isinstance(s, str) and len(s) > MAX else s for s in v]
            # Tuples, dicts, lists-of-dicts, nested structures → JSON string
            try:
                serialized = json.dumps(v, default=str)
                return serialized[:MAX] if len(serialized) > MAX else serialized
            except Exception:
                s = str(v)
                return s[:MAX] if len(s) > MAX else s

        return {k: _coerce(v) for k, v in props.items()}


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

        return imports_map

    # Language-agnostic method
    def add_repository_to_graph(self, repo_path: Path, is_dependency: bool = False):
        """Adds a repository node using its absolute path as the unique key."""
        repo_name = repo_path.name
        repo_path_str = str(repo_path.resolve())
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
        file_path_str = str(Path(file_data['path']).resolve())
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
                    repo_path=str(Path(file_data['repo_path']).resolve())
                ).single()
                resolved_repo_str = repo_result['path'] if repo_result else str(Path(file_data['repo_path']).resolve())
                if not repo_result:
                    warning_logger(f"Repository node not found for {file_data['repo_path']} during indexing of {file_name}.")

            try:
                relative_path = str(Path(file_path_str).relative_to(Path(resolved_repo_str)))
            except ValueError:
                relative_path = file_name

            # ── UPSERT File node ─────────────────────────────────────────────
            session.run("""
                MERGE (f:File {path: $path})
                SET f.name = $name, f.relative_path = $relative_path, f.is_dependency = $is_dependency
            """, path=file_path_str, name=file_name, relative_path=relative_path, is_dependency=is_dependency)

            # ── Directory hierarchy + file link (one pass, sequential MERGEs) ─
            file_path_obj = Path(file_path_str)
            repo_path_obj = Path(resolved_repo_str)
            relative_path_to_file = file_path_obj.relative_to(repo_path_obj)
            parent_path = resolved_repo_str
            parent_label = 'Repository'
            for part in relative_path_to_file.parts[:-1]:
                current_path_str = str(Path(parent_path) / part)
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
                    MERGE (fn)-[:HAS_PARAMETER]->(p)
                """, batch=params_batch, file_path=file_path_str)

            # ── Batch: Class -[:CONTAINS]-> Function ──────────────────────────
            if class_fn_batch:
                session.run("""
                    UNWIND $batch AS row
                    MATCH (c:Class {name: row.class_name, path: $file_path})
                    MATCH (fn:Function {name: row.func_name, path: $file_path, line_number: row.func_line})
                    MERGE (c)-[:CONTAINS]->(fn)
                """, batch=class_fn_batch, file_path=file_path_str)

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
                    other_imports.append(imp)

            if js_imports:
                session.run("""
                    UNWIND $batch AS row
                    MATCH (f:File {path: $file_path})
                    MERGE (m:Module {name: row.module_name})
                    MERGE (f)-[r:IMPORTS]->(m)
                    SET r.imported_name = row.imported_name,
                        r.alias = row.alias,
                        r.line_number = row.line_number
                """, batch=js_imports, file_path=file_path_str)

            if other_imports:
                # Non-JS languages share the same shape: name, alias, full_import_name
                session.run("""
                    UNWIND $batch AS row
                    MATCH (f:File {path: $file_path})
                    MERGE (m:Module {name: row.name})
                    SET m.alias = row.alias,
                        m.full_import_name = coalesce(row.full_import_name, m.full_import_name)
                    MERGE (f)-[r:IMPORTS]->(m)
                    SET r.line_number = row.line_number,
                        r.alias = row.alias
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
        """Resolve a single function call to its target. Returns a dict with call params or None if skipped."""
        called_name = call['name']
        if called_name in __builtins__: return None

        resolved_path = None
        full_call = call.get('full_name', called_name)
        base_obj = full_call.split('.')[0] if '.' in full_call else None
        
        is_chained_call = full_call.count('.') > 1 if '.' in full_call else False
        
        if is_chained_call and base_obj in ('self', 'this', 'super', 'super()', 'cls', '@'):
            lookup_name = called_name
        else:
            lookup_name = base_obj if base_obj else called_name

        if base_obj in ('self', 'this', 'super', 'super()', 'cls', '@') and not is_chained_call:
            resolved_path = caller_file_path
        elif lookup_name in local_names:
            resolved_path = caller_file_path
        elif call.get('inferred_obj_type'):
            obj_type = call['inferred_obj_type']
            possible_paths = imports_map.get(obj_type, [])
            if len(possible_paths) > 0:
                resolved_path = possible_paths[0]
        
        if not resolved_path:
            possible_paths = imports_map.get(lookup_name, [])
            if len(possible_paths) == 1:
                resolved_path = possible_paths[0]
            elif len(possible_paths) > 1:
                if lookup_name in local_imports:
                    full_import_name = local_imports[lookup_name]
                    if full_import_name in imports_map:
                         direct_paths = imports_map[full_import_name]
                         if direct_paths and len(direct_paths) == 1:
                             resolved_path = direct_paths[0]
                    if not resolved_path:
                        for path in possible_paths:
                            if full_import_name.replace('.', '/') in path:
                                resolved_path = path
                                break
        
        if not resolved_path:
            is_unresolved_external = True
        else:
            is_unresolved_external = False
        
        # Legacy fallback
        if not resolved_path:
            possible_paths = imports_map.get(lookup_name, [])
            if len(possible_paths) > 0:
                 if lookup_name in local_imports:
                     pass
                 else:
                    pass
        if not resolved_path:
            if called_name in local_names:
                resolved_path = caller_file_path
                is_unresolved_external = False
            elif called_name in imports_map and imports_map[called_name]:
                candidates = imports_map[called_name]
                for path in candidates:
                    for imp_name in local_imports.values():
                        if imp_name.replace('.', '/') in path:
                            resolved_path = path
                            is_unresolved_external = False
                            break
                    if resolved_path: break
                if not resolved_path:
                    resolved_path = candidates[0]
            else:
                resolved_path = caller_file_path
        
        if skip_external and is_unresolved_external:
            return None

        caller_context = call.get('context')
        if caller_context and len(caller_context) == 3 and caller_context[0] is not None:
            caller_name, _, caller_line_number = caller_context
            return {
                'type': 'function',
                'caller_name': caller_name,
                'caller_file_path': caller_file_path,
                'caller_line_number': caller_line_number,
                'called_name': called_name,
                'called_file_path': resolved_path,
                'line_number': call['line_number'],
                'args': call.get('args', []),
                'full_call_name': call.get('full_name', called_name),
            }
        else:
            return {
                'type': 'file',
                'caller_file_path': caller_file_path,
                'called_name': called_name,
                'called_file_path': resolved_path,
                'line_number': call['line_number'],
                'args': call.get('args', []),
                'full_call_name': call.get('full_name', called_name),
            }

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
            fp = str(Path(fd['path']).resolve())
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
            caller_file_path = str(Path(file_data['path']).resolve())
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
            
        caller_file_path = str(Path(file_data['path']).resolve())
        
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
        info_logger(f"[INHERITS] Resolving inheritance links across {len(all_file_data)} files...")
        
        inheritance_batch = []
        csharp_files = []
        
        for file_data in all_file_data:
            if file_data.get('lang') == 'c_sharp':
                csharp_files.append(file_data)
                continue
            
            caller_file_path = str(Path(file_data['path']).resolve())
            local_class_names = {c['name'] for c in file_data.get('classes', [])}
            local_imports = {imp.get('alias') or imp['name'].split('.')[-1]: imp['name']
                             for imp in file_data.get('imports', [])}
            
            for class_item in file_data.get('classes', []):
                if not class_item.get('bases'):
                    continue
                for base_class_str in class_item['bases']:
                    resolved = self._resolve_inheritance_link(
                        class_item, base_class_str, caller_file_path,
                        local_class_names, local_imports, imports_map
                    )
                    if resolved:
                        inheritance_batch.append(resolved)
        
        info_logger(f"[INHERITS] Resolved {len(inheritance_batch)} inheritance links, "
                    f"{len(csharp_files)} C# files. Writing to Neo4j...")
        
        BATCH_SIZE = 500
        with self.driver.session() as session:
            # Batch non-C# inheritance
            for i in range(0, len(inheritance_batch), BATCH_SIZE):
                batch = inheritance_batch[i:i + BATCH_SIZE]
                session.run("""
                    UNWIND $batch AS row
                    MATCH (child:Class {name: row.child_name, path: row.path})
                    MATCH (parent:Class {name: row.parent_name, path: row.resolved_parent_file_path})
                    MERGE (child)-[:INHERITS]->(parent)
                """, batch=batch)
            
            # C# still uses individual queries (different logic per type)
            for file_data in csharp_files:
                self._create_csharp_inheritance_and_interfaces(session, file_data, imports_map)
        
        info_logger(f"[INHERITS] Complete: {len(inheritance_batch)} inheritance links processed.")
                
    def delete_file_from_graph(self, path: str):
        """Deletes a file and all its contained elements and relationships."""
        file_path_str = str(Path(path).resolve())
        with self.driver.session() as session:
            parents_res = session.run("""
                MATCH (f:File {path: $path})<-[:CONTAINS*]-(d:Directory)
                RETURN d.path as path ORDER BY d.path DESC
            """, path=file_path_str)
            parent_paths = [record["path"] for record in parents_res]

            session.run(
                """
                MATCH (f:File {path: $path})
                OPTIONAL MATCH (f)-[:CONTAINS]->(element)
                DETACH DELETE f, element
                """,
                path=file_path_str,
            )
            info_logger(f"Deleted file and its elements from graph: {file_path_str}")

            for path in parent_paths:
                session.run("""
                    MATCH (d:Directory {path: $path})
                    WHERE NOT (d)-[:CONTAINS]->()
                    DETACH DELETE d
                """, path=path)

    def delete_repository_from_graph(self, repo_path: str) -> bool:
        """Deletes a repository and all its contents from the graph using batched deletes.
        Avoids the OPTIONAL MATCH [:CONTAINS*] cartesian-product explosion for large repos.
        Returns True if deleted, False if not found."""
        repo_path_str = str(Path(repo_path).resolve())
        path_prefix = repo_path_str + "/"
        with self.driver.session() as session:
            # Check if it exists
            result = session.run("MATCH (r:Repository {path: $path}) RETURN count(r) as cnt", path=repo_path_str).single()
            if not result or result["cnt"] == 0:
                warning_logger(f"Attempted to delete non-existent repository: {repo_path_str}")
                return False

        # Step 1: Delete all CALLS/INHERITS relationships in batches (avoids ConstraintValidationFailed on later node delete)
        for rel_type in ("CALLS", "INHERITS", "IMPORTS"):
            while True:
                with self.driver.session() as session:
                    result = session.run(
                        f"MATCH (a)-[r:{rel_type}]->(b) "
                        "WHERE a.path STARTS WITH $prefix OR b.path STARTS WITH $prefix "
                        "WITH r LIMIT 5000 DELETE r RETURN count(r) AS deleted",
                        prefix=path_prefix,
                    ).single()
                    deleted = result["deleted"] if result else 0
                if deleted == 0:
                    break
                info_logger(f"[DELETE] Removed {deleted} {rel_type} rels for {repo_path_str}")

        # Step 2: Delete CONTAINS relationships in batches
        while True:
            with self.driver.session() as session:
                result = session.run(
                    "MATCH (a)-[r:CONTAINS]->(b) "
                    "WHERE a.path STARTS WITH $prefix OR a.path = $path "
                    "WITH r LIMIT 10000 DELETE r RETURN count(r) AS deleted",
                    prefix=path_prefix, path=repo_path_str,
                ).single()
                deleted = result["deleted"] if result else 0
            if deleted == 0:
                break
            info_logger(f"[DELETE] Removed {deleted} CONTAINS rels for {repo_path_str}")

        # Step 3: Delete Function/Class/File nodes in batches by path prefix
        for label in ("Function", "Class", "File"):
            while True:
                with self.driver.session() as session:
                    result = session.run(
                        f"MATCH (n:{label}) WHERE n.path STARTS WITH $prefix "
                        "WITH n LIMIT 10000 DETACH DELETE n RETURN count(n) AS deleted",
                        prefix=path_prefix,
                    ).single()
                    deleted = result["deleted"] if result else 0
                if deleted == 0:
                    break
                info_logger(f"[DELETE] Removed {deleted} {label} nodes for {repo_path_str}")

        # Step 4: Delete the Repository node itself
        with self.driver.session() as session:
            session.run("MATCH (r:Repository {path: $path}) DETACH DELETE r", path=repo_path_str)

        info_logger(f"Deleted repository and its contents from graph: {repo_path_str}")
        return True

    def get_caller_file_paths(self, file_path_str: str) -> set:
        """Return file paths that have CALLS relationships targeting nodes in the given file.
        Used before deleting the file's nodes so we know which callers need re-linking."""
        with self.driver.session() as session:
            result = session.run(
                "MATCH (caller)-[:CALLS]->(callee) "
                "WHERE callee.path = $path "
                "RETURN DISTINCT coalesce(caller.path, '') AS p",
                path=file_path_str,
            )
            return {r["p"] for r in result if r["p"] and r["p"] != file_path_str}

    def get_inheritance_neighbor_paths(self, file_path_str: str) -> set:
        """Return file paths connected by INHERITS to nodes in the given file."""
        with self.driver.session() as session:
            result = session.run(
                "MATCH (a)-[:INHERITS]->(b) "
                "WHERE a.path = $path OR b.path = $path "
                "RETURN DISTINCT CASE WHEN a.path = $path THEN b.path ELSE a.path END AS p",
                path=file_path_str,
            )
            return {r["p"] for r in result if r["p"] and r["p"] != file_path_str}

    def delete_outgoing_calls_from_files(self, file_paths: list):
        """Delete all CALLS relationships originating from the given files.
        Used in incremental mode before re-creating CALLS for affected caller files."""
        with self.driver.session() as session:
            result = session.run(
                "MATCH (a)-[r:CALLS]->(b) WHERE a.path IN $paths DELETE r RETURN count(r) AS cnt",
                paths=file_paths,
            ).single()
            cnt = result["cnt"] if result else 0
        info_logger(f"[RELINK] Deleted {cnt} outgoing CALLS from {len(file_paths)} caller files")

    def delete_inherits_for_files(self, file_paths: list):
        """Delete INHERITS relationships where either end is in the given files."""
        with self.driver.session() as session:
            result = session.run(
                "MATCH (a)-[r:INHERITS]->(b) WHERE a.path IN $paths OR b.path IN $paths "
                "DELETE r RETURN count(r) AS cnt",
                paths=file_paths,
            ).single()
            cnt = result["cnt"] if result else 0
        info_logger(f"[RELINK] Deleted {cnt} INHERITS for {len(file_paths)} affected files")

    def get_repo_class_lookup(self, repo_path: Path) -> dict:
        """Query Neo4j for all Class nodes in the repo.
        Returns {file_path: set_of_class_names} — a full-repo file_class_lookup built without
        re-parsing any files. Used by the incremental watcher update path."""
        prefix = str(repo_path.resolve()) + "/"
        result_map: Dict[str, set] = {}
        with self.driver.session() as session:
            result = session.run(
                "MATCH (c:Class) WHERE c.path STARTS WITH $prefix "
                "RETURN c.name AS name, c.path AS path",
                prefix=prefix,
            )
            for record in result:
                path = record["path"]
                if path not in result_map:
                    result_map[path] = set()
                result_map[path].add(record["name"])
        return result_map

    def delete_relationship_links(self, repo_path: Path):
        """Delete all CALLS and INHERITS relationships for a repo before re-linking.
        
        Called by the watcher before _create_all_function_calls/_create_all_inheritance_links
        to prevent duplicate relationship accumulation on incremental updates.
        """
        repo_path_str = str(repo_path.resolve()) + "/"
        with self.driver.session() as session:
            result = session.run(
                "MATCH (a)-[r:CALLS]->(b) WHERE a.path STARTS WITH $prefix DELETE r RETURN count(r) AS cnt",
                prefix=repo_path_str
            ).single()
            calls_deleted = result["cnt"] if result else 0

            result = session.run(
                "MATCH (a)-[r:INHERITS]->(b) WHERE a.path STARTS WITH $prefix DELETE r RETURN count(r) AS cnt",
                prefix=repo_path_str
            ).single()
            inherits_deleted = result["cnt"] if result else 0

        info_logger(f"[RELINK] Cleared {calls_deleted} CALLS and {inherits_deleted} INHERITS before re-linking: {repo_path}")

    def update_file_in_graph(self, path: Path, repo_path: Path, imports_map: dict):
        """Updates a single file's nodes in the graph."""
        file_path_str = str(path.resolve())
        repo_name = repo_path.name
        
        self.delete_file_from_graph(file_path_str)

        if path.exists():
            file_data = self.parse_file(repo_path, path)
            
            if "error" not in file_data:
                self.add_file_to_graph(file_data, repo_name, imports_map)
                return file_data
            else:
                error_logger(f"Skipping graph add for {file_path_str} due to parsing error: {file_data['error']}")
                return None
        else:
            return {"deleted": True, "path": file_path_str}

    def parse_file(self, repo_path: Path, path: Path, is_dependency: bool = False) -> Dict:
        """Parses a file with the appropriate language parser and extracts code elements."""
        parser = self.get_parser(path.suffix)
        if not parser:
            warning_logger(f"No parser found for file extension {path.suffix}. Skipping {path}")
            return {"path": str(path), "error": f"No parser for {path.suffix}"}

        debug_log(f"[parse_file] Starting parsing for: {path} with {parser.language_name} parser")
        try:
            index_source = (get_config_value("INDEX_SOURCE") or "false").lower() == "true"
            if parser.language_name == 'python':
                is_notebook = path.suffix == '.ipynb'
                file_data = parser.parse(
                    path,
                    is_dependency,
                    is_notebook=is_notebook,
                    index_source=index_source
                )
            else:
                file_data = parser.parse(
                    path,
                    is_dependency,
                    index_source=index_source
                )
            file_data['repo_path'] = str(repo_path)
            return file_data
        except Exception as e:
            error_logger(f"Error parsing {path} with {parser.language_name} parser: {e}")
            debug_log(f"[parse_file] Error parsing {path}: {e}")
            return {"path": str(path), "error": str(e)}

    def estimate_processing_time(self, path: Path) -> Optional[Tuple[int, float]]:
        """Estimate processing time and file count"""
        try:
            supported_extensions = self.parsers.keys()
            if path.is_file():
                if path.suffix in supported_extensions:
                    files = [path]
                else:
                    return 0, 0.0 # Not a supported file type
            else:
                all_files = path.rglob("*")
                files = [f for f in all_files if f.is_file() and f.suffix in supported_extensions]

                # Filter default ignored directories
                ignore_dirs_str = get_config_value("IGNORE_DIRS") or ""
                if ignore_dirs_str:
                    ignore_dirs = {d.strip().lower() for d in ignore_dirs_str.split(',') if d.strip()}
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
            estimated_time = total_files * 0.05 # tree-sitter is faster
            return total_files, estimated_time
        except Exception as e:
            error_logger(f"Could not estimate processing time for {path}: {e}")
            return None

    async def _build_graph_from_scip(
        self, path: Path, is_dependency: bool, job_id: Optional[str], lang: str
    ):
        """
        SCIP-based indexing path. Activated only when SCIP_INDEXER=true and
        a scip-<lang> binary is available.

        Steps:
          1. Run scip-<lang> CLI → index.scip
          2. Parse index.scip → nodes + reference edges
          3. Write nodes to graph (same MERGE queries as Tree-sitter path)
          4. Tree-sitter supplement: add source text + cyclomatic_complexity
          5. Write SCIP CALLS edges (precise, no heuristics)
        """
        import tempfile
        from .scip_indexer import ScipIndexer, ScipIndexParser
        from .graph_builder import TreeSitterParser  # supplement pass

        if job_id:
            self.job_manager.update_job(job_id, status=JobStatus.RUNNING)

        self.add_repository_to_graph(path, is_dependency)
        repo_name = path.name

        try:
            # Step 1: Run SCIP indexer
            with tempfile.TemporaryDirectory(prefix="cgc_scip_") as tmpdir:
                scip_file = ScipIndexer().run(path, lang, Path(tmpdir))

                if not scip_file:
                    warning_logger(
                        f"SCIP indexer produced no output for {path}. "
                        "Falling back to Tree-sitter."
                    )
                    # Hand off to Tree-sitter pipeline by re-calling without SCIP flag
                    # (the flag is checked at the start; override is not needed because
                    # we return here — caller will not re-enter this branch)
                    raise RuntimeError("SCIP produced no index — triggering Tree-sitter fallback")

                # Step 2: Parse index.scip
                scip_data = ScipIndexParser().parse(scip_file, path)
            
            if not scip_data:
                raise RuntimeError("SCIP parse returned empty result")

            files_data = scip_data.get("files", {})
            file_paths = [Path(p) for p in files_data.keys() if Path(p).exists()]
            
            # Step 3: Pre-scan for imports to correctly associate external modules/classes
            imports_map = self._pre_scan_for_imports(file_paths)

            if job_id:
                self.job_manager.update_job(job_id, total_files=len(files_data))

            # Step 4: Write nodes to graph using existing add_file_to_graph()
            processed = 0
            index_root = path.resolve()
            for abs_path_str, file_data in files_data.items():
                file_path = Path(abs_path_str)
                if file_path.is_file() and file_path_has_ignore_dir_segment(file_path, index_root):
                    continue
                file_data["repo_path"] = str(index_root)
                if job_id:
                    self.job_manager.update_job(job_id, current_file=abs_path_str)

                # Step 5: Tree-sitter supplement — add source text, complexity, imports and bases
                ts_parser = self.get_parser(file_path.suffix)
                if file_path.exists() and ts_parser:
                    try:
                        ts_data = ts_parser.parse(file_path, is_dependency, index_source=True)
                        if "error" not in ts_data:
                            # 1. Functions: complexity, source, decorators
                            ts_funcs = {f["name"]: f for f in ts_data.get("functions", [])}
                            for f in file_data.get("functions", []):
                                ts_f = ts_funcs.get(f["name"])
                                if ts_f:
                                    f.update({
                                        "source": ts_f.get("source"),
                                        "cyclomatic_complexity": ts_f.get("cyclomatic_complexity", 1),
                                        "decorators": ts_f.get("decorators", [])
                                    })
                            
                            # 2. Classes: bases (inheritance)
                            ts_classes = {c["name"]: c for c in ts_data.get("classes", [])}
                            for c in file_data.get("classes", []):
                                ts_c = ts_classes.get(c["name"])
                                if ts_c:
                                    c["bases"] = ts_c.get("bases", [])
                            
                            # 3. Imports: critical for cross-file resolution
                            file_data["imports"] = ts_data.get("imports", [])
                            
                            # 4. Variables/Other: value, etc.
                            file_data["variables"] = ts_data.get("variables", [])
                    except Exception as e:
                        debug_log(f"Tree-sitter supplement failed for {abs_path_str}: {e}")

                self.add_file_to_graph(file_data, repo_name, imports_map)

                processed += 1
                if job_id:
                    self.job_manager.update_job(job_id, processed_files=processed)
                if processed % 50 == 0:
                    await asyncio.sleep(0)

            # Step 6: Create INHERITS relationships (Supplemented from Tree-sitter)
            self._create_all_inheritance_links(list(files_data.values()), imports_map)

            # Step 7: Write SCIP CALLS edges — precise cross-file resolution
            with self.driver.session() as session:
                for file_data in files_data.values():
                    for edge in file_data.get("function_calls_scip", []):
                        try:
                            # Use line numbers for precise matching in case of duplicates
                            session.run("""
                                MATCH (caller:Function {name: $caller_name, path: $caller_file, line_number: $caller_line})
                                MATCH (callee:Function {name: $callee_name, path: $callee_file, line_number: $callee_line})
                                MERGE (caller)-[:CALLS {line_number: $ref_line, source: 'scip'}]->(callee)
                            """,
                            caller_name=self._name_from_symbol(edge["caller_symbol"]),
                            caller_file=edge["caller_file"],
                            caller_line=edge["caller_line"],
                            callee_name=edge["callee_name"],
                            callee_file=edge["callee_file"],
                            callee_line=edge["callee_line"],
                            ref_line=edge["ref_line"],
                            )
                        except Exception:
                            pass  # best-effort: node might not be indexed yet

            if job_id:
                self.job_manager.update_job(job_id, status=JobStatus.COMPLETED, end_time=datetime.now())

        except RuntimeError as e:
            # Graceful fallback to Tree-sitter when SCIP fails
            warning_logger(f"SCIP path failed ({e}), re-running with Tree-sitter...")
            # Temporarily disable the flag in-memory so the recursive call goes straight to TS
            # (we do this by calling the internal Tree-sitter steps directly)
            if job_id:
                self.job_manager.update_job(job_id, status=JobStatus.RUNNING)
            # Re-enter the async flow without SCIP check — handled by caller returning early
            # For simplicity, we just let the exception propagate to the outer handler so the
            # job is marked FAILED with a meaningful message rather than silently degrading.
            raise

        except Exception as e:
            error_logger(f"SCIP indexing failed for {path}: {e}")
            if job_id:
                self.job_manager.update_job(
                    job_id, status=JobStatus.FAILED, end_time=datetime.now(), errors=[str(e)]
                )

    def _name_from_symbol(self, symbol: str) -> str:
        """Extract human-readable name from a SCIP symbol ID string."""
        import re
        s = symbol.rstrip(".#")
        s = re.sub(r"\(\)\.?$", "", s) # Remove trailing () or ().
        parts = re.split(r'[/#]', s)
        last = parts[-1] if parts else symbol
        return last or symbol


    async def build_graph_from_path_async(
        self, path: Path, is_dependency: bool = False, job_id: str = None, cgcignore_path: str = None
    ):
        """Builds graph from a directory or file path."""
        try:
            # ------------------------------------------------------------------
            # SCIP feature flag: SCIP_INDEXER=true in ~/.codegraphcontext/.env
            # When enabled (and the binary is installed), SCIP handles the
            # indexing for supported languages. SCIP_INDEXER=false (default)
            # means this entire block is a no-op and existing behaviour is kept.
            # ------------------------------------------------------------------
            scip_enabled = (get_config_value("SCIP_INDEXER") or "false").lower() == "true"
            if scip_enabled:
                from .scip_indexer import ScipIndexer, ScipIndexParser, detect_project_lang, is_scip_available
                scip_langs_str = get_config_value("SCIP_LANGUAGES") or "python,typescript,go,rust,java"
                scip_languages = [l.strip() for l in scip_langs_str.split(",") if l.strip()]
                detected_lang = detect_project_lang(path, scip_languages)

                if detected_lang and is_scip_available(detected_lang):
                    info_logger(f"SCIP_INDEXER=true — using SCIP for language: {detected_lang}")
                    await self._build_graph_from_scip(path, is_dependency, job_id, detected_lang)
                    return   # SCIP handled it; skip Tree-sitter pipeline below
                else:
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
            # ------------------------------------------------------------------
            # Existing Tree-sitter pipeline (unchanged)
            # ------------------------------------------------------------------
            if job_id:
                self.job_manager.update_job(job_id, status=JobStatus.RUNNING)
            
            self.add_repository_to_graph(path, is_dependency)
            repo_name = path.name

            # ignore_root is always the indexed path itself so that file paths
            # are matched relative to the project being indexed.  A parent
            # .cgcignore is still loaded (for monorepo support), but anchoring
            # to its directory would make patterns like "website/" incorrectly
            # filter out every file when indexing the website sub-directory.
            ignore_root = path.resolve() if path.is_dir() else path.resolve().parent

            spec = None
            resolved_cgcignore = None
            try:
                spec, resolved_cgcignore = build_ignore_spec(
                    ignore_root=ignore_root,
                    default_patterns=DEFAULT_IGNORE_PATTERNS,
                    explicit_path=cgcignore_path,
                )
                if resolved_cgcignore:
                    debug_log(f"Using .cgcignore at {resolved_cgcignore} (filtering relative to {ignore_root})")
            except OSError as e:
                warning_logger(f"Could not load/create .cgcignore: {e}")

            supported_extensions = self.parsers.keys()
            all_files = path.rglob("*") if path.is_dir() else [path]

            # Previously only files with supported extensions were indexed.
            # Updated to include all files so that unsupported file types
            # can still be represented as minimal File nodes in the graph.
            files = [f for f in all_files if f.is_file()]

            # Filter default ignored directories
            ignore_dirs_str = get_config_value("IGNORE_DIRS") or ""
            if ignore_dirs_str and path.is_dir():
                ignore_dirs = {d.strip().lower() for d in ignore_dirs_str.split(',') if d.strip()}
                if ignore_dirs:
                    kept_files = []
                    for f in files:
                        try:
                            # Check if any parent directory in the relative path is in ignore list
                            parts = set(p.lower() for p in f.relative_to(path).parent.parts)
                            if not parts.intersection(ignore_dirs):
                                kept_files.append(f)
                            else:
                                # debug_log(f"Skipping default ignored file: {f}")
                                pass
                        except ValueError:
                             kept_files.append(f)
                    files = kept_files
            
            if spec:
                filtered_files = []
                for f in files:
                    try:
                        # Match relative to the indexed project path.
                        rel_path = f.relative_to(ignore_root).as_posix()
                        if not spec.match_file(rel_path):
                            filtered_files.append(f)
                        else:
                            debug_log(f"Ignored file based on .cgcignore: {rel_path}")
                    except ValueError:
                        # Should not happen if ignore_root is a parent, but safety fallback
                        filtered_files.append(f)
                files = filtered_files
            if job_id:
                self.job_manager.update_job(job_id, total_files=len(files))
            
            debug_log("Starting pre-scan to build imports map...")
            imports_map = self._pre_scan_for_imports(files)
            debug_log(f"Pre-scan complete. Found {len(imports_map)} definitions.")

            all_file_data = []

            # Resolve repo path string once here — passed into add_file_to_graph to
            # skip a DB round-trip per file (was one MATCH query per file before).
            resolved_repo_path_str = str(path.resolve()) if path.is_dir() else str(path.parent.resolve())

            processed_count = 0
            for file in files:
                if file.is_file():
                    if job_id:
                        self.job_manager.update_job(job_id, current_file=str(file))
                    repo_path = path.resolve() if path.is_dir() else file.parent.resolve()
                    file_data = self.parse_file(repo_path, file, is_dependency)
                    # Previously only files with supported extensions were indexed.
                    # Updated to include all files so that unsupported file types
                    # can still be represented as minimal File nodes in the graph.
                    if "error" not in file_data:
                        self.add_file_to_graph(file_data, repo_name, imports_map, repo_path_str=resolved_repo_path_str)
                        all_file_data.append(file_data)

                    # Previously only files with supported extensions were indexed.
                    # Updated to include all files so that unsupported file types
                    # can still be represented as minimal File nodes in the graph.
                    else:
                        # create minimal node if parser not available
                        self.add_minimal_file_node(file, repo_path, is_dependency)
                    processed_count += 1

                    if job_id:
                        self.job_manager.update_job(job_id, processed_files=processed_count)
                    # Yield to event loop every 50 files instead of every file.
                    # Old: 28,600 files × 10ms = ~286s of dead wait for nucleus.
                    if processed_count % 50 == 0:
                        await asyncio.sleep(0)

            info_logger(f"File processing complete. {len(all_file_data)} files parsed. "
                       f"Starting post-processing phase (inheritance + function calls)...")
            
            import time as _time
            t0 = _time.time()
            self._create_all_inheritance_links(all_file_data, imports_map)
            t1 = _time.time()
            info_logger(f"Inheritance links created in {t1 - t0:.1f}s. Starting function calls...")
            
            self._create_all_function_calls(all_file_data, imports_map)
            t2 = _time.time()
            info_logger(f"Function calls created in {t2 - t1:.1f}s. Total post-processing: {t2 - t0:.1f}s")
            
            if job_id:
                self.job_manager.update_job(job_id, status=JobStatus.COMPLETED, end_time=datetime.now())
        except Exception as e:
            error_message=str(e)
            error_logger(f"Failed to build graph for path {path}: {error_message}")
            if job_id:
                '''checking if the repo got deleted '''
                if "no such file found" in error_message or "deleted" in error_message or "not found" in error_message:
                    status=JobStatus.CANCELLED
                    
                else:
                    status=JobStatus.FAILED

                self.job_manager.update_job(
                    job_id, status=status, end_time=datetime.now(), errors=[str(e)]
                )

    # Create a minimal File node for unsupported file types.
    # These files do not contain parsed entities but should still
    # appear in the repository graph as requested in issue #707.
    def add_minimal_file_node(self, file_path: Path, repo_path: Path, is_dependency: bool = False):

        file_path_str = str(file_path.resolve())
        file_name = file_path.name
        repo_name = repo_path.name
        repo_path_str = str(repo_path.resolve())

        with self.driver.session() as session:

            session.run(
                """
                MERGE (r:Repository {path: $repo_path})
                SET r.name = $repo_name
                """,
                repo_path=repo_path_str,
                repo_name=repo_name
            )

            session.run(
                """
                MERGE (f:File {path: $file_path})
                SET f.name = $file_name,
                    f.is_dependency = $is_dependency
                """,
                file_path=file_path_str,
                file_name=file_name,
                is_dependency=is_dependency
            )

            # Establish directory structure
            file_path_obj = Path(file_path_str)
            repo_path_obj = Path(repo_path_str)
            try:
                relative_path_to_file = file_path_obj.relative_to(repo_path_obj)
            except ValueError:
                # Fallback if not relative
                relative_path_to_file = Path(file_path_obj.name)
            
            parent_path = repo_path_str
            parent_label = 'Repository'

            for part in relative_path_to_file.parts[:-1]:
                current_path = Path(parent_path) / part
                current_path_str = str(current_path)
                
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
                MATCH (f:File {{path: $file_path}})
                MERGE (p)-[:CONTAINS]->(f)
            """, parent_path=parent_path, file_path=file_path_str)
