# src/codegraphcontext/core/database_spanner.py
import os
import re
import json
import threading
from typing import Optional, Tuple, Dict, Any, List

from codegraphcontext.utils.debug_log import debug_log, info_logger, error_logger, warning_logger

NODE_TABLES = {
    "Repository": {"schema": "path STRING(MAX) NOT NULL, name STRING(MAX), is_dependency BOOL, properties JSON", "pk": "path"},
    "File": {"schema": "path STRING(MAX) NOT NULL, name STRING(MAX), relative_path STRING(MAX), is_dependency BOOL, properties JSON", "pk": "path"},
    "Directory": {"schema": "path STRING(MAX) NOT NULL, name STRING(MAX), properties JSON", "pk": "path"},
    "Module": {"schema": "name STRING(MAX) NOT NULL, lang STRING(MAX), full_import_name STRING(MAX), properties JSON", "pk": "name"},
    "Function": {"schema": "uid STRING(MAX) NOT NULL, name STRING(MAX), path STRING(MAX), line_number INT64, end_line INT64, source STRING(MAX), docstring STRING(MAX), lang STRING(MAX), cyclomatic_complexity INT64, is_dependency BOOL, properties JSON, decorators ARRAY<STRING(MAX)> AS (JSON_VALUE_ARRAY(properties, '$.decorators')) STORED, args ARRAY<STRING(MAX)> AS (JSON_VALUE_ARRAY(properties, '$.args')) STORED, context STRING(MAX) AS (JSON_VALUE(properties, '$.context')) STORED, context_type STRING(MAX) AS (JSON_VALUE(properties, '$.context_type')) STORED, class_context STRING(MAX) AS (JSON_VALUE(properties, '$.class_context')) STORED", "pk": "uid"},
    "Class": {"schema": "uid STRING(MAX) NOT NULL, name STRING(MAX), path STRING(MAX), line_number INT64, end_line INT64, source STRING(MAX), docstring STRING(MAX), lang STRING(MAX), is_dependency BOOL, properties JSON, decorators ARRAY<STRING(MAX)> AS (JSON_VALUE_ARRAY(properties, '$.decorators')) STORED, context STRING(MAX) AS (JSON_VALUE(properties, '$.context')) STORED, context_type STRING(MAX) AS (JSON_VALUE(properties, '$.context_type')) STORED, class_context STRING(MAX) AS (JSON_VALUE(properties, '$.class_context')) STORED", "pk": "uid"},
    "Variable": {"schema": "uid STRING(MAX) NOT NULL, name STRING(MAX), path STRING(MAX), line_number INT64, end_line INT64, source STRING(MAX), docstring STRING(MAX), lang STRING(MAX), value STRING(MAX), type STRING(MAX), is_dependency BOOL, properties JSON, decorators ARRAY<STRING(MAX)> AS (JSON_VALUE_ARRAY(properties, '$.decorators')) STORED, context STRING(MAX) AS (JSON_VALUE(properties, '$.context')) STORED, class_context STRING(MAX) AS (JSON_VALUE(properties, '$.class_context')) STORED", "pk": "uid"},
    "Trait": {"schema": "uid STRING(MAX) NOT NULL, name STRING(MAX), path STRING(MAX), line_number INT64, end_line INT64, source STRING(MAX), docstring STRING(MAX), lang STRING(MAX), is_dependency BOOL, properties JSON, decorators ARRAY<STRING(MAX)> AS (JSON_VALUE_ARRAY(properties, '$.decorators')) STORED, context STRING(MAX) AS (JSON_VALUE(properties, '$.context')) STORED, context_type STRING(MAX) AS (JSON_VALUE(properties, '$.context_type')) STORED, class_context STRING(MAX) AS (JSON_VALUE(properties, '$.class_context')) STORED", "pk": "uid"},
    "Interface": {"schema": "uid STRING(MAX) NOT NULL, name STRING(MAX), path STRING(MAX), line_number INT64, end_line INT64, source STRING(MAX), docstring STRING(MAX), lang STRING(MAX), is_dependency BOOL, properties JSON, decorators ARRAY<STRING(MAX)> AS (JSON_VALUE_ARRAY(properties, '$.decorators')) STORED, context STRING(MAX) AS (JSON_VALUE(properties, '$.context')) STORED, context_type STRING(MAX) AS (JSON_VALUE(properties, '$.context_type')) STORED, class_context STRING(MAX) AS (JSON_VALUE(properties, '$.class_context')) STORED", "pk": "uid"},
    "Macro": {"schema": "uid STRING(MAX) NOT NULL, name STRING(MAX), path STRING(MAX), line_number INT64, end_line INT64, source STRING(MAX), docstring STRING(MAX), lang STRING(MAX), is_dependency BOOL, properties JSON, decorators ARRAY<STRING(MAX)> AS (JSON_VALUE_ARRAY(properties, '$.decorators')) STORED, context STRING(MAX) AS (JSON_VALUE(properties, '$.context')) STORED, context_type STRING(MAX) AS (JSON_VALUE(properties, '$.context_type')) STORED, class_context STRING(MAX) AS (JSON_VALUE(properties, '$.class_context')) STORED", "pk": "uid"},
    "Struct": {"schema": "uid STRING(MAX) NOT NULL, name STRING(MAX), path STRING(MAX), line_number INT64, end_line INT64, source STRING(MAX), docstring STRING(MAX), lang STRING(MAX), is_dependency BOOL, properties JSON, decorators ARRAY<STRING(MAX)> AS (JSON_VALUE_ARRAY(properties, '$.decorators')) STORED, context STRING(MAX) AS (JSON_VALUE(properties, '$.context')) STORED, context_type STRING(MAX) AS (JSON_VALUE(properties, '$.context_type')) STORED, class_context STRING(MAX) AS (JSON_VALUE(properties, '$.class_context')) STORED", "pk": "uid"},
    "Enum": {"schema": "uid STRING(MAX) NOT NULL, name STRING(MAX), path STRING(MAX), line_number INT64, end_line INT64, source STRING(MAX), docstring STRING(MAX), lang STRING(MAX), is_dependency BOOL, properties JSON, decorators ARRAY<STRING(MAX)> AS (JSON_VALUE_ARRAY(properties, '$.decorators')) STORED, context STRING(MAX) AS (JSON_VALUE(properties, '$.context')) STORED, context_type STRING(MAX) AS (JSON_VALUE(properties, '$.context_type')) STORED, class_context STRING(MAX) AS (JSON_VALUE(properties, '$.class_context')) STORED", "pk": "uid"},
    "Union": {"schema": "uid STRING(MAX) NOT NULL, name STRING(MAX), path STRING(MAX), line_number INT64, end_line INT64, source STRING(MAX), docstring STRING(MAX), lang STRING(MAX), is_dependency BOOL, properties JSON, decorators ARRAY<STRING(MAX)> AS (JSON_VALUE_ARRAY(properties, '$.decorators')) STORED, context STRING(MAX) AS (JSON_VALUE(properties, '$.context')) STORED, context_type STRING(MAX) AS (JSON_VALUE(properties, '$.context_type')) STORED, class_context STRING(MAX) AS (JSON_VALUE(properties, '$.class_context')) STORED", "pk": "uid"},
    "Annotation": {"schema": "uid STRING(MAX) NOT NULL, name STRING(MAX), path STRING(MAX), line_number INT64, end_line INT64, source STRING(MAX), docstring STRING(MAX), lang STRING(MAX), is_dependency BOOL, properties JSON, decorators ARRAY<STRING(MAX)> AS (JSON_VALUE_ARRAY(properties, '$.decorators')) STORED, context STRING(MAX) AS (JSON_VALUE(properties, '$.context')) STORED, context_type STRING(MAX) AS (JSON_VALUE(properties, '$.context_type')) STORED, class_context STRING(MAX) AS (JSON_VALUE(properties, '$.class_context')) STORED", "pk": "uid"},
    "Record": {"schema": "uid STRING(MAX) NOT NULL, name STRING(MAX), path STRING(MAX), line_number INT64, end_line INT64, source STRING(MAX), docstring STRING(MAX), lang STRING(MAX), is_dependency BOOL, properties JSON, decorators ARRAY<STRING(MAX)> AS (JSON_VALUE_ARRAY(properties, '$.decorators')) STORED, context STRING(MAX) AS (JSON_VALUE(properties, '$.context')) STORED, context_type STRING(MAX) AS (JSON_VALUE(properties, '$.context_type')) STORED, class_context STRING(MAX) AS (JSON_VALUE(properties, '$.class_context')) STORED", "pk": "uid"},
    "Property": {"schema": "uid STRING(MAX) NOT NULL, name STRING(MAX), path STRING(MAX), line_number INT64, end_line INT64, source STRING(MAX), docstring STRING(MAX), lang STRING(MAX), is_dependency BOOL, properties JSON, decorators ARRAY<STRING(MAX)> AS (JSON_VALUE_ARRAY(properties, '$.decorators')) STORED, context STRING(MAX) AS (JSON_VALUE(properties, '$.context')) STORED, context_type STRING(MAX) AS (JSON_VALUE(properties, '$.context_type')) STORED, class_context STRING(MAX) AS (JSON_VALUE(properties, '$.class_context')) STORED", "pk": "uid"},
    "Parameter": {"schema": "uid STRING(MAX) NOT NULL, name STRING(MAX), path STRING(MAX), function_line_number INT64, properties JSON", "pk": "uid"},
}

EDGE_TABLES = {
    "CONTAINS": {
        "pairs": [
            ("File", "Function"), ("File", "Class"), ("File", "Variable"), 
            ("File", "Trait"), ("File", "Interface"), ("Macro", "Macro"), 
            ("File", "Macro"), ("File", "Struct"), ("File", "Enum"), 
            ("File", "Union"), ("File", "Annotation"), ("File", "Record"), 
            ("File", "Property"), ("Repository", "Directory"), 
            ("Directory", "Directory"), ("Directory", "File"), 
            ("Repository", "File"), ("Class", "Function"), ("Function", "Function")
        ],
        "properties": ", properties JSON"
    },
    "CALLS": {
        "pairs": [
            ("Function", "Function"), ("Function", "Class"), 
            ("File", "Function"), ("File", "Class"), 
            ("Class", "Function"), ("Class", "Class")
        ],
        "properties": ", line_number INT64, args ARRAY<STRING(MAX)>, full_call_name STRING(MAX), properties JSON"
    },
    "IMPORTS": {
        "pairs": [("File", "Module")],
        "properties": ", alias STRING(MAX), full_import_name STRING(MAX), imported_name STRING(MAX), line_number INT64, properties JSON"
    },
    "INHERITS": {
        "pairs": [("Class", "Class"), ("Record", "Record"), ("Interface", "Interface")],
        "properties": ", properties JSON"
    },
    "HAS_PARAMETER": {
        "pairs": [("Function", "Parameter")],
        "properties": ", properties JSON"
    },
    "INCLUDES": {
        "pairs": [("Class", "Module")],
        "properties": ", properties JSON"
    },
    "IMPLEMENTS": {
        "pairs": [("Class", "Interface"), ("Struct", "Interface"), ("Record", "Interface")],
        "properties": ", properties JSON"
    }
}

class SpannerDBManager:
    """Manages the Google Cloud Spanner database connection as a singleton."""
    _instance = None
    _client = None
    _instance_id = None
    _database_id = None
    _database_obj = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(SpannerDBManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return

        self._instance_id = os.getenv('SPANNER_INSTANCE_ID', 'my-spanner-instance')
        self._database_id = os.getenv('SPANNER_DATABASE_ID', 'my-graph-database')
        self._graph_name = os.getenv('SPANNER_GRAPH_NAME', 'CodeGraph')
        
        self.name = 'spanner'
        self._initialized = True

    def get_driver(self):
        if self._client is None:
            with self._lock:
                if self._client is None:
                    try:
                        from google.cloud import spanner
                        import google.auth
                        
                        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", os.environ.get("GCP_PROJECT", None))
                        info_logger(f"Initializing Spanner at {self._instance_id}/{self._database_id} in {project_id}")
                        self._client = spanner.Client(project=project_id, disable_builtin_metrics=True)
                        
                        instance = self._client.instance(self._instance_id)
                        self._database_obj = instance.database(self._database_id)
                        
                        info_logger("Spanner connection established")
                    except ImportError:
                        error_logger("Google Cloud Spanner is not installed. Run 'pip install google-cloud-spanner'")
                        raise ValueError("google-cloud-spanner missing.")
                    except Exception as e:
                        error_logger(f"Failed to initialize Spanner: {e}")
                        raise

        return SpannerDriverWrapper(self._database_obj, self._graph_name)

    def provision_schema(self, console=None):
        """Creates Node tables, Edge tables, and the Property Graph via DDL if they don't exist."""
        if not self._database_obj:
            self.get_driver()

        def log(msg):
            if console: console.print(msg)
            else: info_logger(msg)

        log(f"[cyan]Provisioning Spanner Property Graph DDL for: [bold]{self._graph_name}[/bold][/cyan]")
        ddl_statements = []

        # 1. Create Node Tables
        for table_name, table_info in NODE_TABLES.items():
            ddl_statements.append(f"""
            CREATE TABLE IF NOT EXISTS `{table_name}` (
                {table_info['schema']}
            ) PRIMARY KEY ({table_info['pk']})
            """)

        # 2. Create physical Edge Tables
        for edge_table, table_info in EDGE_TABLES.items():
            # A universal physical table per edge type
            ddl_statements.append(f"""
            CREATE TABLE IF NOT EXISTS `{edge_table}` (
                id STRING(36) NOT NULL,
                src_id STRING(MAX) NOT NULL,
                dst_id STRING(MAX) NOT NULL{table_info['properties']}
            ) PRIMARY KEY (id)
            """)

        # 3. Create Property Graph
        # Spanner limits CREATE PROPERTY GRAPH to full replacement or initial creation, no IF NOT EXISTS.
        # Check if it exists via information schema first.
        
        # Build node tables clause
        node_tables_clause = ",\n".join([f"    `{node}`" for node in NODE_TABLES.keys()])
        
        # Build edge tables clause
        edge_tables_clauses = []
        for edge_label, edge_data in EDGE_TABLES.items():
            for src_node, dst_node in edge_data['pairs']:
                # The relationship creates a unique edge definition per pair mapped to the SAME physical table
                src_pk = NODE_TABLES[src_node]['pk']
                dst_pk = NODE_TABLES[dst_node]['pk']
                edge_tables_clauses.append(f"""
    `{edge_label}` AS `{edge_label}_{src_node}_{dst_node}`
      SOURCE KEY (src_id) REFERENCES `{src_node}` ({src_pk})
      DESTINATION KEY (dst_id) REFERENCES `{dst_node}` ({dst_pk})
      LABEL `{edge_label}`""")

        edge_tables_clause = ",\n".join(edge_tables_clauses)
        
        graph_ddl = f"""
        CREATE PROPERTY GRAPH `{self._graph_name}`
        NODE TABLES (
{node_tables_clause}
        )
        EDGE TABLES ({edge_tables_clause}
        )
        """

        log("[yellow]Updating DDL. This may take a few minutes...[/yellow]")
        try:
            # We wrap graph creation in a try-except to handle existing graphs, 
            # as Spanner does not support IF NOT EXISTS for CREATE PROPERTY GRAPH.
            # We first run the table creations.
            operation = self._database_obj.update_ddl(ddl_statements)
            operation.result(timeout=120)  # Wait for table creation DDL
            log("[green]✅ Underlying Tables provisioned.[/green]")
        except Exception as e:
            if "Duplicate name" in str(e) or "already exists" in str(e):
                log("[dim]Tables already exist.[/dim]")
            else:
                raise e

        try:
            # Then we run the graph creation
            operation = self._database_obj.update_ddl([graph_ddl])
            operation.result(timeout=120)
            log(f"[green]✅ Property Graph {self._graph_name} provisioned.[/green]")
        except Exception as e:
            if "Duplicate name" in str(e) or "already exists" in str(e):
                log(f"[dim]Property Graph {self._graph_name} already exists.[/dim]")
            else:
                error_logger(f"Failed to create property graph: {e}")
                log(f"[red]❌ Property Graph creation failed: {e}[/red]")

    def close_driver(self):
        if self._client is not None:
            info_logger("Closing Spanner DB connection")
            self._client = None

    def is_connected(self) -> bool:
        if self._client is None or self._database_obj is None: return False
        try:
            with self._database_obj.snapshot() as snapshot:
                snapshot.execute_sql("SELECT 1")
            return True
        except Exception:
            return False
            
    def get_backend_type(self) -> str:
        return 'spanner'

    @staticmethod
    def validate_config() -> Tuple[bool, Optional[str]]:
        if not os.getenv('SPANNER_INSTANCE_ID') or not os.getenv('SPANNER_DATABASE_ID'):
            return False, "SPANNER_INSTANCE_ID and SPANNER_DATABASE_ID must be set."
        return True, None

    @staticmethod
    def test_connection() -> Tuple[bool, Optional[str]]:
        try:
            from google.cloud import spanner
            client = spanner.Client(disable_builtin_metrics=True)
            instance = client.instance(os.getenv('SPANNER_INSTANCE_ID'))
            db = instance.database(os.getenv('SPANNER_DATABASE_ID'))
            with db.snapshot() as snapshot:
                snapshot.execute_sql("SELECT 1")
            return True, None
        except Exception as e:
            return False, f"Spanner connection failed: {e}"


class SpannerRecord:
    def __init__(self, data_dict):
        self._data = data_dict
        self._keys = list(data_dict.keys())
    
    def data(self): return self._data
    def keys(self): return self._keys
    def items(self): return self._data.items()
    def values(self): return list(self._data.values())
    def __len__(self): return len(self._data)
    
    def __getitem__(self, key):
        if isinstance(key, int):
            if 0 <= key < len(self._keys):
                return self._data[self._keys[key]]
            raise IndexError(f"Index {key} out of range")
        return self._data[key]
    
    def get(self, key, default=None):
        return self._data.get(key, default)


class SpannerResultWrapper:
    def __init__(self, result_list):
        self.result_list = result_list
        self._consumed = False
        
    def consume(self):
        self._consumed = True
        return self
        
    def single(self):
        return SpannerRecord(self.result_list[0]) if self.result_list else None
        
    def data_raw(self) -> List[Dict[str, Any]]:
        return self.result_list

    def data(self) -> List[Dict[str, Any]]:
        return self.data_raw()

    def __iter__(self):
        return iter([SpannerRecord(r) for r in self.result_list])

def _auto_alias_return_clause(query: str) -> Tuple[str, Dict[str, str]]:
    """
    Finds the final RETURN clause and ensures every expression has an AS alias (c_0, c_1).
    Returns (aliased_query, alias_map), where alias_map maps auto-generated
    aliases back to the original expression string to simulate Neo4j implicit aliasing parity.
    """
    last_return_pos = -1
    i = 0
    n = len(query)
    in_single = False
    in_double = False
    
    while i < n:
        c = query[i]
        if c == "'":
            if not in_double: in_single = not in_single
        elif c == '"':
            if not in_single: in_double = not in_double
        elif not in_single and not in_double:
            if query[i:i+7].upper() == "RETURN " and (i == 0 or query[i-1].isspace()):
                last_return_pos = i
        i += 1
        
    if last_return_pos == -1:
        return query, {}
        
    prefix = query[:last_return_pos + 7]
    remainder = query[last_return_pos + 7:]
    
    columns = []
    current_col = []
    
    paren_depth = 0
    bracket_depth = 0
    brace_depth = 0
    in_single = False
    in_double = False
    
    i = 0
    m = len(remainder)
    
    def check_keyword(idx, kw):
        if idx + len(kw) <= m:
            if remainder[idx:idx+len(kw)].upper() == kw:
                if idx + len(kw) == m or remainder[idx+len(kw)].isspace():
                    return True
        return False
        
    end_idx = m
    while i < m:
        c = remainder[i]
        
        if c == "'":
            if not in_double: in_single = not in_single
            current_col.append(c)
        elif c == '"':
            if not in_single: in_double = not in_double
            current_col.append(c)
        elif not in_single and not in_double:
            if c == '(': paren_depth += 1
            elif c == ')': paren_depth -= 1
            elif c == '[': bracket_depth += 1
            elif c == ']': bracket_depth -= 1
            elif c == '{': brace_depth += 1
            elif c == '}': brace_depth -= 1
            
            if paren_depth == 0 and bracket_depth == 0 and brace_depth == 0:
                if c == ',':
                    columns.append("".join(current_col))
                    current_col = []
                    i += 1
                    continue
                if (check_keyword(i, "ORDER BY") or 
                    check_keyword(i, "LIMIT") or 
                    check_keyword(i, "SKIP") or
                    check_keyword(i, "OFFSET")):
                    end_idx = i
                    break
            current_col.append(c)
        else:
            current_col.append(c)
        i += 1
        
    if current_col:
        columns.append("".join(current_col))
        
    suffix = remainder[end_idx:]
    
    alias_map = {}
    new_columns = []
    
    for idx, col in enumerate(columns):
        col_str = col.strip()
        if not col_str:
            new_columns.append(col)
            continue
            
        import re
        # Check if user explicitly aliased (AS <alias>)
        match = re.search(r'(?i)\s+AS\s+([a-zA-Z0-9_`]+)$', col_str)
        if match:
            new_columns.append(col)
        else:
            c_alias = f"c_{idx}"
            
            has_distinct = ""
            if idx == 0 and col_str.upper().startswith("DISTINCT "):
                has_distinct = col_str[:9]
                col_str = col_str[9:].lstrip()
            
            alias_map[c_alias] = col_str
            
            if has_distinct:
                new_columns.append(f"{has_distinct}{col_str} AS {c_alias}")
            else:
                new_columns.append(f"{col_str} AS {c_alias}")
                
    if suffix and not suffix[0].isspace():
        suffix = " " + suffix
    final_query = prefix + ", ".join(new_columns) + suffix
    return final_query, alias_map


class SpannerSessionWrapper:
    def __init__(self, database_obj, graph_name):
        self.database = database_obj
        self.graph_name = graph_name
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def _format_gql(self, query, parameters):
        import re
        gql_query = query
        if not gql_query.strip().upper().startswith("GRAPH"):
            gql_query = f"GRAPH {self.graph_name}\n{gql_query}"
            
        # Spanner GQL variables are @var instead of $var
        gql_query = re.sub(r'\$(\w+)', r'@\1', gql_query)
        
        # Translate Cypher string matching operators to Spanner Google SQL equivalents
        expr_pat = r'((?:\w+\([\w\.@\'"]+\))|[\w\.@\'"]+)'
        gql_query = re.sub(rf'(?i){expr_pat}\s+CONTAINS\s+{expr_pat}', r'STRPOS(\1, \2) > 0', gql_query)
        gql_query = re.sub(rf'(?i){expr_pat}\s+STARTS\s+WITH\s+{expr_pat}', r'STARTS_WITH(\1, \2)', gql_query)
        gql_query = re.sub(rf'(?i){expr_pat}\s+ENDS\s+WITH\s+{expr_pat}', r'ENDS_WITH(\1, \2)', gql_query)
        
        # Translate Cypher functions
        gql_query = re.sub(r'(?i)\btoLower\(', 'LOWER(', gql_query)
        
        # Spanner GQL does not support DISTINCT on arrays. For compatibility, strip DISTINCT.
        gql_query = re.sub(r'(?i)\bRETURN\s+DISTINCT\b', 'RETURN', gql_query)
        
        # Wrap all node and edge labels in backticks to prevent reserved word collisions
        gql_query = re.sub(r'\[([a-zA-Z0-9_]*):([a-zA-Z0-9_]+)', r'[\1:`\2`', gql_query)
        gql_query = re.sub(r'\(([a-zA-Z0-9_]*):([a-zA-Z0-9_]+)', r'(\1:`\2`', gql_query)
        
        # Guard against nested dicts leaking into GQL execution engine
        safe_parameters = {}
        for k, v in parameters.items():
            if isinstance(v, (dict, list)):
                safe_parameters[k] = str(v)
            else:
                safe_parameters[k] = v

        return gql_query, safe_parameters

    def run(self, query, **parameters):
        # 0. Alias the return clause to ensure GQL compliance
        aliased_query, col_map = _auto_alias_return_clause(query)

        # 1. Translate Query
        translations, is_sql = self._translate_query(aliased_query, parameters)
        
        try:
            if is_sql:
                if translations == "SYSTEM_DELETE_CASCADE":
                    def execute_cascade_deletes(transaction):
                        path_val = parameters.get("path")
                        if not path_val: return
                        
                        warning_logger(f"Translating unsupported GQL DETACH DELETE into cascading Spanner SQL deletions for path: {path_val}")
                        
                        tables_with_path = [
                            "Function", "Class", "Variable", "Parameter", 
                            "Record", "Interface", "Struct", "Enum", "Union", 
                            "Property", "Annotation", "Trait", "Macro",
                            "File", "Directory", "Repository",
                        ]
                        
                        for table in tables_with_path:
                            try:
                                transaction.execute_update(
                                    f"DELETE FROM `{table}` WHERE STARTS_WITH(path, @path)",
                                    params={"path": path_val}
                                )
                            except Exception:
                                pass # Table might not exist or lacks standard path column
                    
                    self.database.run_in_transaction(execute_cascade_deletes)
                    return SpannerResultWrapper([])
                    
                def execute_mutation(transaction):
                    for sql_op in translations:
                        if isinstance(sql_op, tuple):
                            sql_query, sql_params = sql_op
                            transaction.execute_update(sql_query, params=sql_params)
                        elif isinstance(sql_op, dict) and sql_op.get("type") == "edge_merge":
                            import uuid
                            import json
                            import re
                            prefix = sql_op["match_query_prefix"]
                            src_var, dst_var = sql_op["src_var"], sql_op["dst_var"]
                            src_pk, dst_pk = sql_op["src_pk"], sql_op["dst_pk"]
                            
                            params = sql_op["original_parameters"]
                            
                            # Use bound generated PKs from same-transaction MERGE operations if available
                            src_val = params.get(f"{src_var}_pk", params.get(src_pk))
                            dst_val = params.get(f"{dst_var}_pk", params.get(dst_pk))
                            
                            # Determine mapping values from GQL lookup if not provided directly
                            fields_to_return = []
                            if not src_val:
                                fields_to_return.append(f"{src_var}.{src_pk} AS src_pk_val")
                            if not dst_val:
                                fields_to_return.append(f"{dst_var}.{dst_pk} AS dst_pk_val")
                                
                            rows = []
                            if fields_to_return:
                                match_lines = [line.strip() for line in prefix.split("\n") if re.match(r'^(MATCH|OPTIONAL MATCH|WITH|WHERE)\b', line.strip(), re.IGNORECASE)]
                                gql_prefix = "\n".join(match_lines)
                                if gql_prefix:
                                    gql_query = gql_prefix + "\nRETURN " + ", ".join(fields_to_return)
                                    formatted_gql, formatted_params = self._format_gql(gql_query, params)
                                    results = transaction.execute_sql(formatted_gql, params=formatted_params)
                                    rows = [dict(zip([f.name for f in results.fields], row)) for row in results]
                                    
                            # Fallback if logic is a pure MERGE without MATCH sequence or no rows found
                            if not rows:
                                rows = [{}]

                            for row in rows:
                                final_src_val = src_val or row.get("src_pk_val") or params.get(src_pk) or f"dummy_{src_var}"
                                final_dst_val = dst_val or row.get("dst_pk_val") or params.get(dst_pk) or f"dummy_{dst_var}"
                                    
                                edge_label = sql_op["edge_label"]
                                edge_props_raw = sql_op["edge_props_raw"]
                                edge_id = str(uuid.uuid5(uuid.NAMESPACE_OID, f"{edge_label}_{final_src_val}_{final_dst_val}_{edge_props_raw}"))
                                
                                final_sql_params = sql_op["sql_params"].copy()
                                final_sql_params["id"] = edge_id
                                final_sql_params["src_id"] = final_src_val
                                final_sql_params["dst_id"] = final_dst_val
                                
                                cols, vals = [], []
                                insert_params = {}
                                for c, v in final_sql_params.items():
                                    if isinstance(v, dict):
                                        cols.append(c)
                                        vals.append(f"PARSE_JSON(@{c})")
                                        insert_params[c] = json.dumps(v)
                                    else:
                                        cols.append(c)
                                        vals.append(f"@{c}")
                                        insert_params[c] = v
                                
                                sql = f"INSERT OR UPDATE `{edge_label}` ({', '.join(cols)}) VALUES ({', '.join(vals)})"
                                transaction.execute_update(sql, params=insert_params)

                self.database.run_in_transaction(execute_mutation)
                return SpannerResultWrapper([])
            else:
                gql_query, gql_params = translations
                with self.database.snapshot() as snapshot:
                    results = snapshot.execute_sql(gql_query, params=gql_params)
                    # Convert to list of dicts immediately so we can close snapshot
                    formatted_results = []
                    fields = None
                    for row in results:
                        if fields is None:
                            fields = [f.name for f in results.fields]
                        
                        mapped_fields = [col_map.get(f, f) for f in fields]
                        formatted_results.append(dict(zip(mapped_fields, row)))
                    return SpannerResultWrapper(formatted_results)
                    
        except Exception as e:
            err_str = str(e).lower()
            if "already exists" in err_str:
                return SpannerResultWrapper([])
            if "google.api_core.exceptions" in str(type(e)):
                # Abstract away Spanner syntax/validation errors to the original expected exception
                from neo4j.exceptions import CypherSyntaxError
                error_logger(f"Spanner GQL rejected syntax/properties: {query[:100]}... Error: {e}")
                raise CypherSyntaxError(f"Backend rejected Cypher Query: {str(e)}")
            error_logger(f"Spanner Query failed: {query[:100]}... Error: {e}")
            raise

    def _translate_query(self, query: str, parameters: Dict[str, Any]) -> Tuple[Any, bool]:
        """
        Translates basic openCypher to Spanner GQL or a list of Spanner SQL operations.
        Returns (translations, is_sql).
        If is_sql=True, translations is either 'SYSTEM_DELETE_CASCADE' or List[Tuple[str, dict]].
        """
        # Spanner GQL restricts DML DETACH DELETE. Send it to manual cascade.
        if "DETACH DELETE" in query.upper():
            return "SYSTEM_DELETE_CASCADE", True

        if "MERGE " in query:
            sql_ops = []
            
            # 1. Node MERGE extraction
            # e.g., MERGE (var:Label {pk: $param, ...})
            # Regex expects optionally a variable, then a colon, then the label.
            
            def guess_pk_name(ntype):
                if ntype in ['Repository', 'File', 'Directory']: return 'path'
                if ntype in ['Module']: return 'name'
                return 'uid'
                
            for merge_node_match in re.finditer(r'MERGE\s+\(([a-zA-Z0-9_]+):([a-zA-Z0-9_]+)\s*\{([^}]+)\}\)', query):
                node_var = merge_node_match.group(1)
                node_label = merge_node_match.group(2)
                
                sql_params = {}
                
                # Handle PK mapping
                pk_fields = merge_node_match.group(3).split(',')
                # Sort the fields by key name so UUID generation is deterministic regardless of query order
                sorted_match_criteria = []
                for field in pk_fields:
                    if ':' in field:
                        k, v_raw = field.split(':', 1)
                        k = k.strip()
                        v_raw = v_raw.strip()
                        if v_raw.startswith('$'):
                            val = parameters.get(v_raw[1:])
                        else:
                            val = v_raw.strip('"\'')
                        sql_params[k] = val
                        sorted_match_criteria.append((k, str(val)))
                
                import uuid
                if guess_pk_name(node_label) == 'uid':
                    sorted_match_criteria.sort()
                    hash_payload = f"{node_label}_" + "_".join([f"{k}={v}" for k, v in sorted_match_criteria])
                    if 'uid' not in sql_params:
                        sql_params['uid'] = str(uuid.uuid5(uuid.NAMESPACE_OID, hash_payload))
                    parameters[f"{node_var}_pk"] = sql_params['uid']
                else:
                    pk_name = guess_pk_name(node_label)
                    if pk_name in sql_params:
                        parameters[f"{node_var}_pk"] = sql_params[pk_name]

                # Associated SET statements
                # e.g., SET var += $props
                set_plus_match = re.search(r'SET\s+' + node_var + r'\s*\+=\s*\$([a-zA-Z0-9_]+)', query)
                if set_plus_match:
                    prop_name = set_plus_match.group(1)
                    props_dict = parameters.get(prop_name, {})
                    properties_json = {}
                    
                    # Standard columns we explicitly map (now correctly bounded by DDL declarations instead of a whitelist)
                    actual_table_cols = set()
                    node_schema_raw = NODE_TABLES.get(node_label, {"schema": ""})["schema"]
                    for col_def in node_schema_raw.split(','):
                        col_def = col_def.strip()
                        if not col_def or " AS " in col_def or " properties JSON" in col_def:
                            continue
                        col_name = col_def.split()[0]
                        actual_table_cols.add(col_name)

                    for k, v in props_dict.items():
                        if k in actual_table_cols and not isinstance(v, (dict, list)):
                            sql_params[k] = v
                        else:
                            properties_json[k] = v
                            
                    if properties_json:
                        sql_params['properties'] = properties_json
                        
                # e.g., SET var.prop = $val
                for set_prop_match in re.finditer(r'SET\s+' + node_var + r'\.([a-zA-Z0-9_]+)\s*=\s*\$([a-zA-Z0-9_]+)', query):
                    prop_k = set_prop_match.group(1)
                    prop_v_param = set_prop_match.group(2)
                    if prop_v_param in parameters:
                        sql_params[prop_k] = parameters[prop_v_param]
                        
                cols = []
                vals = []
                final_sql_params = {}
                for c, v in sql_params.items():
                    if isinstance(v, dict):
                        cols.append(c)
                        vals.append(f"PARSE_JSON(@{c})")
                        final_sql_params[c] = json.dumps(v)
                    else:
                        cols.append(c)
                        vals.append(f"@{c}")
                        final_sql_params[c] = v
                        
                sql_query = f"INSERT OR UPDATE `{node_label}` ({', '.join(cols)}) VALUES ({', '.join(vals)})"
                sql_ops.append((sql_query, final_sql_params))

            # 1.5 Extract MATCH clauses to build subqueries for edge resolving if not provided in MERGE
            match_lookups = {}
            for match_node in re.finditer(r'MATCH\s+\(([a-zA-Z0-9_]+):([a-zA-Z0-9_]+)\s*\{([^}]+)\}\)', query):
                mnode_var = match_node.group(1)
                mnode_label = match_node.group(2)
                mpk_fields = match_node.group(3).split(',')
                mpk_name = guess_pk_name(mnode_label)
                
                mwhere = []
                for field in mpk_fields:
                    if ':' in field:
                        k, v_raw = field.split(':', 1)
                        k = k.strip()
                        v_raw = v_raw.strip()
                        if v_raw.startswith('$'):
                            # For parameterized matches, we just pass the param name (e.g. '@context') into the subquery
                            mwhere.append(f"{k} = @{v_raw[1:]}")
                        else:
                            mwhere.append(f"{k} = {v_raw}")
                if mwhere:
                    match_lookups[mnode_var] = f"(SELECT {mpk_name} FROM `{mnode_label}` WHERE {' AND '.join(mwhere)} LIMIT 1)"

            # 2. Edge MERGE extraction
            # e.g., MERGE (a)-[r:LABEL {props}]->(b) or MERGE (a)-[:LABEL]->(b)
            # Regex expects optionally a variable, then a colon, then the label.
            for merge_edge_match in re.finditer(r'MERGE\s+\(([a-zA-Z0-9_]+)\)-\[(?:([a-zA-Z0-9_]+)\s*)?:([a-zA-Z0-9_]+)(?:\s*\{([^}]+)\})?\]->\(([a-zA-Z0-9_]+)\)', query):
                src_var = merge_edge_match.group(1)
                edge_var = merge_edge_match.group(2) # might be None
                edge_label = merge_edge_match.group(3)
                edge_props_raw = merge_edge_match.group(4) or ""
                dst_var = merge_edge_match.group(5)
                
                def get_node_type_from_query(var_name):
                    m = re.search(r'\(\s*' + re.escape(var_name) + r'\s*:\s*([a-zA-Z0-9_]+)', query)
                    if m: return m.group(1)
                    var_mapping = {
                        'r': 'Repository', 'f': 'File', 'd': 'Directory', 'm': 'Module',
                        'c': 'Class', 'fn': 'Function', 'caller': 'Function', 'called': 'Function',
                        'final_target': 'Function', 'final_caller': 'Function', 'child': 'Class', 'parent': 'Class',
                        'p': 'Parameter', 'mod': 'Module', 'outer': 'Module', 'inner': 'Module',
                        'iface': 'Interface', 'outer_fn': 'Function'
                    }
                    return var_mapping.get(var_name, var_name.capitalize())

                src_type = get_node_type_from_query(src_var)
                dst_type = get_node_type_from_query(dst_var)
                
                src_pk = guess_pk_name(src_type)
                dst_pk = guess_pk_name(dst_type)

                # Fetch resolved ID from parameters or fallback to subqueries generated by MATCH
                src_val_direct = parameters.get(f"{src_var}_pk", parameters.get(src_pk))
                if src_val_direct:
                    src_val_sql = f"@{src_var}_pk" if f"{src_var}_pk" in parameters else f"@{src_pk}"
                    src_val_hash = str(src_val_direct)
                elif src_var in match_lookups:
                    src_val_sql = match_lookups[src_var]
                    src_val_hash = f"match_{src_var}"
                else:
                    src_val_sql = f"'dummy_{src_var}'"
                    src_val_hash = f"dummy_{src_var}"

                dst_val_direct = parameters.get(f"{dst_var}_pk", parameters.get(dst_pk))
                if dst_val_direct:
                    dst_val_sql = f"@{dst_var}_pk" if f"{dst_var}_pk" in parameters else f"@{dst_pk}"
                    dst_val_hash = str(dst_val_direct)
                elif dst_var in match_lookups:
                    dst_val_sql = match_lookups[dst_var]
                    dst_val_hash = f"match_{dst_var}"
                else:
                    dst_val_sql = f"'dummy_{dst_var}'"
                    dst_val_hash = f"dummy_{dst_var}"
                
                import uuid
                # Use src_val_hash / dst_val_hash to maintain determinism for uuid.
                # If these edges are re-created via MATCH, clear_repository will have cleaned up the old ones so unique keys don't strictly collide.
                edge_id = str(uuid.uuid5(uuid.NAMESPACE_OID, f"{edge_label}_{src_val_hash}_{dst_val_hash}_{edge_props_raw}"))

                edge_sql_params = {}
                if edge_props_raw:
                    for field in edge_props_raw.split(','):
                        if ':' in field:
                            k, v_raw = field.split(':', 1)
                            k = k.strip()
                            target_param = v_raw.strip()[1:]
                            if target_param in parameters:
                                edge_sql_params[k] = parameters[target_param]
                                
                if edge_var:
                    set_edge_plus_match = re.search(r'SET\s+' + edge_var + r'\s*\+=\s*\$([a-zA-Z0-9_]+)', query)
                    if set_edge_plus_match:
                        prop_name = set_edge_plus_match.group(1)
                        props_dict = parameters.get(prop_name, {})
                        for k, v in props_dict.items():
                            edge_sql_params[k] = v

                actual_edge_cols = set(["id", "src_id", "dst_id"])
                edge_props_raw_ddl = EDGE_TABLES.get(edge_label, {"properties": ""})["properties"]
                for col_def in edge_props_raw_ddl.split(','):
                    col_def = col_def.strip()
                    if not col_def or " AS " in col_def or " properties JSON" in col_def:
                        continue
                    col_name = col_def.split()[0]
                    actual_edge_cols.add(col_name)

                final_edge_sql_params = {}
                edge_properties_json = {}
                for k, v in edge_sql_params.items():
                    if k in actual_edge_cols and not isinstance(v, (dict, list)):
                        final_edge_sql_params[k] = v
                    else:
                        edge_properties_json[k] = v
                        
                if edge_properties_json:
                    final_edge_sql_params["properties"] = edge_properties_json

                sql_ops.append({
                    "type": "edge_merge",
                    "sql_params": final_edge_sql_params,
                    "edge_label": edge_label,
                    "edge_props_raw": edge_props_raw,
                    "src_var": src_var,
                    "dst_var": dst_var,
                    "src_pk": src_pk,
                    "dst_pk": dst_pk,
                    "match_query_prefix": query[:merge_edge_match.start()],
                    "original_parameters": parameters
                })

            if sql_ops:
                return sql_ops, True

        # Pure GQL fallback for reads (MATCH)
        gql_query, safe_parameters = self._format_gql(query, parameters)
        return (gql_query, safe_parameters), False

class SpannerDriverWrapper:
    def __init__(self, database_obj, graph_name):
        self.database = database_obj
        self.graph_name = graph_name
        
    def session(self):
        return SpannerSessionWrapper(self.database, self.graph_name)
        
    def close(self):
        pass
