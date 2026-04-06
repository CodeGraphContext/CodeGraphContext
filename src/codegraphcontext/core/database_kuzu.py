# src/codegraphcontext/core/database_kuzu.py
"""
This module provides a thread-safe singleton manager for the KùzuDB database connection.
KùzuDB is an embedded graph database that is cross-platform (including Windows) 
and requires no external server setup.
"""
import os
import time
import threading
import re
import json
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

from codegraphcontext.utils.debug_log import debug_log, info_logger, error_logger, warning_logger

class KuzuDBManager:
    """
    Manages the KùzuDB database connection as a singleton.
    """
    _instance = None
    _db = None
    _conn = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """Standard singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(KuzuDBManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, db_path: Optional[str] = None):
        """
        Initializes the manager with default database path or explicit overrides.
        """
        if hasattr(self, '_initialized') and self.db_path == db_path:
            return
            
        self._initialized = False

        self.name = "kuzudb"
        # Try to load from config manager
        try:
            from codegraphcontext.cli.config_manager import get_config_value
            config_db_path = get_config_value('KUZUDB_PATH')
        except Exception:
            config_db_path = None
        
        # Database path with fallback chain (Explicit > Env > Config/Default)
        self.db_path = db_path or os.getenv(
            'KUZUDB_PATH',
            config_db_path or str(Path.home() / '.codegraphcontext' / 'global' / 'kuzudb')
        )
        
        # Ensure directory exists
        os.makedirs(Path(self.db_path).parent, exist_ok=True)
        
        self._initialized = True

    def get_driver(self):
        """
        Gets the KùzuDB connection. Retries on file-lock errors.
        """
        if self._conn is None:
            with self._lock:
                if self._conn is None:
                    import kuzu
                    max_retries = 5
                    for attempt in range(max_retries):
                        try:
                            info_logger(f"Initializing KùzuDB at {self.db_path}")
                            self._db = kuzu.Database(self.db_path)
                            self._conn = kuzu.Connection(self._db)
                            self._initialize_schema()
                            info_logger("KùzuDB connection established and schema verified")
                            break
                        except ImportError:
                            error_logger("KùzuDB is not installed. Run 'pip install kuzu'")
                            raise ValueError("KùzuDB missing.")
                        except Exception as e:
                            if "lock" in str(e).lower() and attempt < max_retries - 1:
                                wait = 0.5 * (2 ** attempt)
                                warning_logger(f"KùzuDB lock contention, retrying in {wait:.1f}s ({attempt+1}/{max_retries})...")
                                self._db = None
                                self._conn = None
                                time.sleep(wait)
                            else:
                                error_logger(f"Failed to initialize KùzuDB: {e}")
                                raise

        return KuzuDriverWrapper(self._conn)

    def _initialize_schema(self):
        """Creates Node and Rel tables if they don't exist."""
        # Using a set of helper methods to define tables
        # Kuzu's Cypher for checking tables can be limited, 
        # but we can wrap in try-except or check metadata.
        
        node_tables = [
            ("Repository", "path STRING, name STRING, is_dependency BOOLEAN, PRIMARY KEY (path)"),
            ("File", "path STRING, name STRING, relative_path STRING, is_dependency BOOLEAN, PRIMARY KEY (path)"),
            ("Directory", "path STRING, name STRING, PRIMARY KEY (path)"),
            ("Module", "name STRING, lang STRING, full_import_name STRING, PRIMARY KEY (name)"),
            # For types with composite keys (name, path, line_number), we use a 'uid'
            ("Function", "uid STRING, name STRING, path STRING, line_number INT64, end_line INT64, source STRING, docstring STRING, lang STRING, cyclomatic_complexity INT64, context STRING, context_type STRING, class_context STRING, is_dependency BOOLEAN, decorators STRING[], args STRING[], PRIMARY KEY (uid)"),
            ("Class", "uid STRING, name STRING, path STRING, line_number INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, decorators STRING[], PRIMARY KEY (uid)"),
            ("Variable", "uid STRING, name STRING, path STRING, line_number INT64, source STRING, docstring STRING, lang STRING, value STRING, context STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
            ("Trait", "uid STRING, name STRING, path STRING, line_number INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
            ("Interface", "uid STRING, name STRING, path STRING, line_number INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
            ("Macro", "uid STRING, name STRING, path STRING, line_number INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
            ("Struct", "uid STRING, name STRING, path STRING, line_number INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
            ("Enum", "uid STRING, name STRING, path STRING, line_number INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
            ("Union", "uid STRING, name STRING, path STRING, line_number INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
            ("Annotation", "uid STRING, name STRING, path STRING, line_number INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
            ("Record", "uid STRING, name STRING, path STRING, line_number INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
            ("Property", "uid STRING, name STRING, path STRING, line_number INT64, end_line INT64, source STRING, docstring STRING, lang STRING, is_dependency BOOLEAN, PRIMARY KEY (uid)"),
            ("Parameter", "uid STRING, name STRING, path STRING, function_line_number INT64, PRIMARY KEY (uid)")
        ]
        
        # rel_tables: list of (table_name, schema, use_group)
        # use_group=True  -> CREATE REL TABLE GROUP (for multi FROM..TO bindings)
        # use_group=False -> CREATE REL TABLE          (single binding)
        rel_tables = [
            # Note: in KùzuDB, some labels (e.g. `Macro`, `Property`, `Union`) are treated as reserved
            # keywords in CREATE REL TABLE statements. We must escape them with backticks
            # or the rel table creation will fail silently, leading to runtime
            # "Binder exception: Table CONTAINS does not exist".
            ("CONTAINS", "FROM File TO Function, FROM File TO Class, FROM File TO Variable, FROM File TO Trait, FROM File TO Interface, FROM `Macro` TO `Macro`, FROM File TO `Macro`, FROM File TO Struct, FROM File TO Enum, FROM File TO `Union`, FROM File TO Annotation, FROM File TO Record, FROM File TO `Property`, FROM Repository TO Directory, FROM Directory TO Directory, FROM Directory TO File, FROM Repository TO File, FROM Class TO Function, FROM Function TO Function", True),
            ("CALLS", "FROM Function TO Function, FROM Function TO Class, FROM File TO Function, FROM File TO Class, FROM Class TO Function, FROM Class TO Class, line_number INT64, args STRING[], full_call_name STRING", True),
            ("IMPORTS", "FROM File TO Module, alias STRING, full_import_name STRING, imported_name STRING, line_number INT64", False),
            ("INHERITS", "FROM Class TO Class, FROM Record TO Record, FROM Interface TO Interface", True),
            ("HAS_PARAMETER", "FROM Function TO Parameter", False),
            ("INCLUDES", "FROM Class TO Module", False),
            ("IMPLEMENTS", "FROM Class TO Interface, FROM Struct TO Interface, FROM Record TO Interface", True)
        ]

        for table_name, schema in node_tables:
            try:
                self._conn.execute(f"CREATE NODE TABLE `{table_name}`({schema})")
            except Exception as e:
                if "already exists" not in str(e).lower():
                    warning_logger(f"Kuzu Schema Node Error ({table_name}): {e}")
                    debug_log(f"Kuzu Schema Node Error ({table_name}): {e}")

        for table_name, schema, use_group in rel_tables:
            try:
                if use_group:
                    # KùzuDB requires CREATE REL TABLE GROUP for multi-binding relationships
                    self._conn.execute(f"CREATE REL TABLE GROUP `{table_name}`({schema})")
                else:
                    self._conn.execute(f"CREATE REL TABLE `{table_name}`({schema})")
            except Exception as e:
                if "already exists" not in str(e).lower():
                    warning_logger(f"Kuzu Schema Rel Error ({table_name}): {e}")
                    debug_log(f"Kuzu Schema Rel Error ({table_name}): {e}")

    def close_driver(self):
        """Closes the connection."""
        if self._conn is not None:
            info_logger("Closing KùzuDB connection")
            self._conn = None
            self._db = None

    def is_connected(self) -> bool:
        """Checks if the database connection is currently active."""
        if self._conn is None:
            return False
        try:
            self._conn.execute("RETURN 1")
            return True
        except Exception:
            return False
    
    def get_backend_type(self) -> str:
        """Returns the database backend type."""
        return 'kuzudb'

    @staticmethod
    def validate_config(db_path: str = None) -> Tuple[bool, Optional[str]]:
        if db_path:
            db_dir = Path(db_path).parent
            if not os.access(db_dir, os.W_OK) and db_dir.exists():
                return False, f"Cannot write to directory: {db_dir}"
        return True, None

    @staticmethod
    def test_connection(db_path: str = None) -> Tuple[bool, Optional[str]]:
        try:
            import kuzu
            return True, None
        except ImportError:
            return False, "KùzuDB is not installed. Run 'pip install kuzu'"

class KuzuDriverWrapper:
    def __init__(self, conn):
        self.conn = conn
    def session(self):
        return KuzuSessionWrapper(self.conn)
    def close(self):
        pass

class KuzuSessionWrapper:
    def __init__(self, conn):
        self.conn = conn
        self.uid_map = {
            'Function': ['name', 'path', 'line_number'],
            'Class': ['name', 'path', 'line_number'],
            'Variable': ['name', 'path', 'line_number'],
            'Trait': ['name', 'path', 'line_number'],
            'Interface': ['name', 'path', 'line_number'],
            'Macro': ['name', 'path', 'line_number'],
            'Struct': ['name', 'path', 'line_number'],
            'Enum': ['name', 'path', 'line_number'],
            'Union': ['name', 'path', 'line_number'],
            'Annotation': ['name', 'path', 'line_number'],
            'Record': ['name', 'path', 'line_number'],
            'Property': ['name', 'path', 'line_number'],
            'Parameter': ['name', 'path', 'function_line_number']
        }
    
    def __enter__(self):
        """Enter context manager - return self for 'with' statement."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager - KùzuDB auto-commits, so nothing to do here."""
        # KùzuDB uses auto-commit, no explicit commit needed
        return False  # Don't suppress exceptions

    @staticmethod
    def _sanitize_value(v):
        """Recursively coerce Python types that KuzuDB cannot bind (tuples, sets, etc.)."""
        if isinstance(v, tuple):
            return [KuzuSessionWrapper._sanitize_value(i) for i in v]
        if isinstance(v, set):
            return [KuzuSessionWrapper._sanitize_value(i) for i in v]
        if isinstance(v, list):
            return [KuzuSessionWrapper._sanitize_value(i) for i in v]
        if isinstance(v, dict):
            return {k: KuzuSessionWrapper._sanitize_value(val) for k, val in v.items()}
        return v

    def run(self, query, **parameters):
        # 0. Sanitize parameters (convert tuples/sets → lists throughout)
        parameters = {k: self._sanitize_value(v) for k, v in parameters.items()}
        # 1. Translate Query
        debug_log(f"Original Query: {query[:200]}")
        translated_query, translated_params = self._translate_query(query, parameters)
        debug_log(f"Translated Query: {translated_query[:200]}")
        try:
            result = self.conn.execute(translated_query, translated_params)
            return KuzuResultWrapper(result)
        except Exception as e:
            # Silence specific non-errors
            err_str = str(e).lower()
            if "already exists" in err_str:
                return KuzuResultWrapper(None)
            error_logger(f"Kuzu Query failed: {query[:100]}... Error: {e}")
            debug_log(f"Kuzu Query failed: {query[:100]}... Error: {e}")
            raise

    def _translate_query(self, query: str, parameters: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Translates Neo4j Cypher to Kuzu Cypher."""
        
        # 0. Define Schema Map (Strict property filtering)
        SCHEMA_MAP = {
            'Repository': {'path', 'name', 'is_dependency'},
            'File': {'path', 'name', 'relative_path', 'is_dependency'},
            'Directory': {'path', 'name'},
            'Module': {'name', 'lang', 'full_import_name'},
            'Function': {'uid', 'name', 'path', 'line_number', 'end_line', 'source', 'docstring', 'lang', 'cyclomatic_complexity', 'context', 'context_type', 'class_context', 'is_dependency', 'decorators', 'args'},
            'Class': {'uid', 'name', 'path', 'line_number', 'end_line', 'source', 'docstring', 'lang', 'is_dependency', 'decorators'},
            'Variable': {'uid', 'name', 'path', 'line_number', 'source', 'docstring', 'lang', 'value', 'context', 'is_dependency'},
            'Trait': {'uid', 'name', 'path', 'line_number', 'end_line', 'source', 'docstring', 'lang', 'is_dependency'},
            'Interface': {'uid', 'name', 'path', 'line_number', 'end_line', 'source', 'docstring', 'lang', 'is_dependency'},
            'Macro': {'uid', 'name', 'path', 'line_number', 'end_line', 'source', 'docstring', 'lang', 'is_dependency'},
            'Struct': {'uid', 'name', 'path', 'line_number', 'end_line', 'source', 'docstring', 'lang', 'is_dependency'},
            'Enum': {'uid', 'name', 'path', 'line_number', 'end_line', 'source', 'docstring', 'lang', 'is_dependency'},
            'Union': {'uid', 'name', 'path', 'line_number', 'end_line', 'source', 'docstring', 'lang', 'is_dependency'},
            'Annotation': {'uid', 'name', 'path', 'line_number', 'end_line', 'source', 'docstring', 'lang', 'is_dependency'},
            'Record': {'uid', 'name', 'path', 'line_number', 'end_line', 'source', 'docstring', 'lang', 'is_dependency'},
            'Property': {'uid', 'name', 'path', 'line_number', 'end_line', 'source', 'docstring', 'lang', 'is_dependency'},
            'Parameter': {'uid', 'name', 'path', 'function_line_number'}
        }

        # 1. Translate SET n += $props  and  SET n = $props  (map merge/assign)
        if "SET" in query and "= $" in query:
            match = re.search(r'SET\s+(\w+)\s*\+?=\s*\$(\w+)', query)
            if match:
                node_var = match.group(1)
                param_name = match.group(2)
                
                # Determine label used for node_var to filter properties
                def_match = re.search(rf'\({node_var}:(\w+)', query)
                label = def_match.group(1) if def_match else None
                
                props_dict = parameters.get(param_name, {})
                if isinstance(props_dict, dict):
                    set_clauses = []
                    new_params = parameters.copy()
                    
                    allowed_props = SCHEMA_MAP.get(label, set()) if label else None

                    for k, v in props_dict.items():
                        if isinstance(v, (dict, list)) and k != 'args' and k != 'decorators':
                            continue
                        
                        if allowed_props and k not in allowed_props:
                           continue
                           
                        clean_k = f"{param_name}_{k}"
                        set_clauses.append(f"{node_var}.{k} = ${clean_k}")
                        new_params[clean_k] = v
                        
                    if set_clauses:
                        query = query.replace(match.group(0), "SET " + ", ".join(set_clauses))
                        new_params.pop(param_name, None)
                        parameters = new_params
                    else:
                        query = query.replace(match.group(0), "")

        # 1.5: Handle UNWIND-specific patterns before standard UID injection.
        # When queries use UNWIND $batch AS row, two things need translation:
        #   a) SET n += row  (map merge unsupported in KuzuDB) → explicit property SETs
        #   b) MERGE uid injection from row fields (row.name, row.line_number, …)
        unwind_m = re.search(r'UNWIND\s+\$(\w+)\s+AS\s+(\w+)', query)
        if unwind_m:
            batch_param = unwind_m.group(1)
            row_var = unwind_m.group(2)
            batch_data = parameters.get(batch_param)

            if isinstance(batch_data, list) and batch_data:
                # 1.5a: Expand  SET node_var += row_var  →  SET node_var.p1 = row_var.p1, …
                set_plus_re = re.compile(
                    rf'SET\s+(\w+)\s*\+=\s*{re.escape(row_var)}\b'
                )
                set_m = set_plus_re.search(query)
                if set_m:
                    node_var = set_m.group(1)
                    label_m = re.search(rf'\({re.escape(node_var)}:(\w+)', query)
                    label = label_m.group(1).strip('`') if label_m else None
                    allowed = SCHEMA_MAP.get(label, set()) if label else None

                    sample = batch_data[0]
                    parts = []
                    for k in sample:
                        if k == 'uid':
                            continue
                        if allowed and k not in allowed:
                            continue
                        parts.append(f"{node_var}.{k} = {row_var}.{k}")

                    replacement = ("SET " + ", ".join(parts)) if parts else ""
                    query = set_plus_re.sub(replacement, query, count=1)

                # 1.5b: Inject uid into MERGE clauses that reference UNWIND row fields
                merge_re = re.compile(
                    r'MERGE\s+\((\w+):([^\s\{]+)\s*\{([^}]+)\}\)'
                )
                for m in list(merge_re.finditer(query)):
                    var_name, label_raw, props_str = m.groups()
                    label = label_raw.strip('`')
                    if label not in self.uid_map:
                        continue

                    pk_parts = self.uid_map[label]
                    all_ok = True

                    for item in batch_data:
                        uid_components = []
                        for part in pk_parts:
                            row_ref = re.search(
                                rf'\b{part}\s*:\s*{re.escape(row_var)}\.(\w+)',
                                props_str,
                            )
                            param_ref = re.search(
                                rf'\b{part}\s*:\s*\$(\w+)', props_str
                            )
                            if row_ref:
                                val = item.get(row_ref.group(1))
                                if val is not None:
                                    uid_components.append(str(val))
                                else:
                                    all_ok = False
                                    break
                            elif param_ref:
                                val = parameters.get(param_ref.group(1))
                                if val is not None:
                                    uid_components.append(str(val))
                                else:
                                    all_ok = False
                                    break
                            else:
                                all_ok = False
                                break

                        if all_ok:
                            item['uid'] = ''.join(uid_components)
                        else:
                            all_ok = False
                            break

                    if all_ok:
                        old_block = '{' + props_str + '}'
                        new_block = (
                            '{' + props_str + f', uid: {row_var}.uid' + '}'
                        )
                        query = query.replace(old_block, new_block, 1)

                # 1.5c: Strip explicit SET clauses for properties not in the schema
                # (e.g. SET m.alias = row.alias when Module has no 'alias' column)
                def _filter_set_clause(m_set):
                    full = m_set.group(0)
                    assignments = re.split(r',\s*(?=\w+\.\w+\s*=)', full[4:])  # skip "SET "
                    kept = []
                    for a in assignments:
                        a = a.strip()
                        prop_m = re.match(r'(\w+)\.(\w+)\s*=', a)
                        if prop_m:
                            nvar = prop_m.group(1)
                            prop_name = prop_m.group(2)
                            lbl_m = re.search(rf'\({re.escape(nvar)}:(\w+)', query)
                            if lbl_m:
                                lbl = lbl_m.group(1).strip('`')
                                allowed_s = SCHEMA_MAP.get(lbl)
                                if allowed_s and prop_name not in allowed_s:
                                    continue
                        kept.append(a)
                    if kept:
                        return "SET " + ", ".join(kept)
                    return ""

                # Only apply to explicit SET lines (not SET +=, already handled)
                if '+=' not in query:
                    query = re.sub(
                        r'SET\s+\w+\.\w+\s*=\s*[^,\n]+(?:\s*,\s*\w+\.\w+\s*=\s*[^,\n]+)*',
                        _filter_set_clause,
                        query,
                    )

                # 1.5d: Translate ON CREATE SET / ON MATCH SET → plain SET (KuzuDB compat)
                query = re.sub(r'\bON\s+CREATE\s+SET\b', 'SET', query, flags=re.IGNORECASE)
                query = re.sub(r'\bON\s+MATCH\s+SET\b', 'SET', query, flags=re.IGNORECASE)

        # 2. Handle UID injection for MERGE (non-UNWIND queries)
        # We look for MERGE (v:Label {props})
        merge_pattern = r'MERGE\s+\((\w+):([^\s\{]+)\s*\{([^}]+)\}\)'
        matches = list(re.finditer(merge_pattern, query))
        for m in matches:
            var_name, label_raw, props_str = m.groups()
            label = label_raw.strip('`').strip(':')
            if label in self.uid_map:
                # Skip if uid already injected (by UNWIND handler above)
                if 'uid:' in props_str:
                    continue
                pk_parts = self.uid_map[label]
                can_build_uid = True
                uid_val = ""
                for part in pk_parts:
                    p_match = re.search(rf'{part}:\s*\$(\w+)', props_str)
                    if p_match:
                        p_val = parameters.get(p_match.group(1))
                        if p_val is not None:
                            uid_val += str(p_val)
                        else: can_build_uid = False; break
                    else: can_build_uid = False; break
                
                if can_build_uid:
                    uid_param = f"__uid_{var_name}"
                    old_block = f"{{{props_str}}}"
                    new_block = f"{{{props_str}, uid: ${uid_param}}}"
                    if old_block in query:
                         query = query.replace(old_block, new_block)
                    else:
                         warning_logger(f"Kuzu UID injection: could not find props block in query for label '{label}'")
                    
                    parameters[uid_param] = uid_val

        # 3. Escape keywords as labels
        labels_to_escape = ['Macro', 'Union', 'Property', 'CONTAINS', 'CALLS'] # Only critical keywords
        for label in labels_to_escape:
            query = re.sub(rf':{label}\b', f':`{label}`', query)

        # 4. Polymorphic matches and label access
        query = query.replace("labels(n)[0]", "label(n)")
        
        # Translate (n:Label1 OR n:Label2 ...) to label(n) IN ['Label1', 'Label2', ...]
        def poly_replacer(match):
            full_match = match.group(0)
            var_name = match.group(1)
            # Find all labels associated with this variable in the OR chain
            labels = re.findall(rf'{var_name}:([a-zA-Z0-9_]+)', full_match)
            return f"label({var_name}) IN {json.dumps(labels)}"
        
        # Regex to match (n:Label1 OR n:Label2 OR n:Label3)
        query = re.sub(r'\((\w+):[a-zA-Z0-9_]+(?:\s+OR\s+\1:[a-zA-Z0-9_]+)+\)', poly_replacer, query)
        
        # Translate single WHERE n:Label to label(n) = 'Label'
        # This is more complex because we don't want to match MATCH/MERGE
        # For now, we only target where it appears after WHERE or AND/OR
        def single_label_replacer(match):
            prefix = match.group(1)
            var_name = match.group(2)
            label = match.group(3)
            return f"{prefix}label({var_name}) = '{label}'"
            
        query = re.sub(r'(WHERE\s+|AND\s+|OR\s+|WHEN\s+)(\w+):([a-zA-Z0-9_]+)', single_label_replacer, query, flags=re.IGNORECASE)

        # Handle NOT n:Label → NOT label(n) = 'Label'
        def not_label_replacer(match):
            prefix = match.group(1)
            var_name = match.group(2)
            label_name = match.group(3)
            return f"{prefix}NOT label({var_name}) = '{label_name}'"
        query = re.sub(r'(WHERE\s+|AND\s+|OR\s+)NOT\s+(\w+):([a-zA-Z0-9_]+)', not_label_replacer, query, flags=re.IGNORECASE)

        query = query.replace("coalesce(", "COALESCE(")
        query = re.sub(r'\btype\(', 'label(', query)

        # General ON CREATE/MATCH SET → SET (also covers non-UNWIND queries)
        query = re.sub(r'\bON\s+CREATE\s+SET\b', 'SET', query, flags=re.IGNORECASE)
        query = re.sub(r'\bON\s+MATCH\s+SET\b', 'SET', query, flags=re.IGNORECASE)

        if any(x in query.upper() for x in ["CREATE CONSTRAINT", "CREATE INDEX"]):
            return "RETURN 1", {}

        # 5. Cleanup unused parameters (Kuzu is strict)
        used_params = set(re.findall(r'\$(\w+)', query))
        parameters = {k: v for k, v in parameters.items() if k in used_params}

        return query, parameters

    def __enter__(self): return self
    def __exit__(self, exc_type, exc_val, exc_tb): pass

class KuzuRecord:
    def __init__(self, data_dict):
        self._data = data_dict
        self._keys = list(data_dict.keys())
    
    def data(self):
        return self._data
    
    def keys(self):
        return self._keys
    
    def items(self):
        return self._data.items()
    
    def values(self):
        return list(self._data.values())
    
    def __len__(self):
        return len(self._data)
    
    def __getitem__(self, key):
        # Support both dict-style (by name) and list-style (by index) access
        if isinstance(key, int):
            # Integer index - get by position
            if 0 <= key < len(self._keys):
                return self._data[self._keys[key]]
            raise IndexError(f"Index {key} out of range")
        else:
            # String key - get by column name
            return self._data[key]
    
    def get(self, key, default=None):
        return self._data.get(key, default)

class KuzuResultWrapper:
    def __init__(self, result):
        self.result = result
        self._consumed = False
    def consume(self):
        self._consumed = True
        return self
    def single(self):
        records = self.data_raw()
        return KuzuRecord(records[0]) if records else None
    def data_raw(self) -> List[Dict[str, Any]]:
        if not self.result: return []
        records = []
        cols = self.result.get_column_names()
        while self.result.has_next():
            row = self.result.get_next()
            record = {}
            for i, val in enumerate(row):
                # Handle Kuzu Node/Rel objects for visualization compatibility
                processed_val = val
                try:
                    # Kuzu 0.11+ objects often have a specific structure
                    if hasattr(val, '__class__') and 'Node' in str(val.__class__):
                        processed_val = val
                        if not hasattr(processed_val, 'labels'):
                            processed_val.labels = [val.get_label_name()]
                        if not hasattr(processed_val, 'id'):
                           props = val.get_properties()
                           processed_val.id = props.get('uid', props.get('path', str(id(val))))
                        if not hasattr(processed_val, 'properties'):
                            processed_val.properties = val.get_properties()
                    
                    elif hasattr(val, '__class__') and 'Rel' in str(val.__class__):
                        processed_val = val
                        if not hasattr(processed_val, 'type'):
                            processed_val.type = val.get_label_name()
                        if not hasattr(processed_val, 'src_node'):
                            processed_val.src_node = val.get_src_id()['offset']
                        if not hasattr(processed_val, 'dest_node'):
                            processed_val.dest_node = val.get_dst_id()['offset']
                        if not hasattr(processed_val, 'properties'):
                            processed_val.properties = val.get_properties()
                except Exception:
                    pass
                
                record[cols[i]] = processed_val
            records.append(record)
        return records

    def data(self) -> List[Dict[str, Any]]:
        # Return raw dict data, not KuzuRecord.data()
        return self.data_raw()

    def __iter__(self):
        return iter([KuzuRecord(r) for r in self.data_raw()])
