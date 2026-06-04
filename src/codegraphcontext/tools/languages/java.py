# src/codegraphcontext/tools/languages/java.py
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import re
from codegraphcontext.utils.debug_log import debug_log, info_logger, error_logger, warning_logger
from codegraphcontext.utils.tree_sitter_manager import execute_query

# Spring stereotype annotations → canonical label written to the graph (#887)
_SPRING_CLASS_STEREOTYPES: Dict[str, str] = {
    "Controller": "CONTROLLER",
    "RestController": "REST_CONTROLLER",
    "Service": "SERVICE",
    "Repository": "REPOSITORY",
    "Component": "COMPONENT",
    "Configuration": "CONFIGURATION",
    "ControllerAdvice": "CONTROLLER_ADVICE",
    "RestControllerAdvice": "REST_CONTROLLER_ADVICE",
}

# Spring HTTP mapping annotations → HTTP method string (#887)
_SPRING_HTTP_MAPPINGS: Dict[str, Optional[str]] = {
    "RequestMapping": None,   # method determined from `method` attribute
    "GetMapping": "GET",
    "PostMapping": "POST",
    "PutMapping": "PUT",
    "DeleteMapping": "DELETE",
    "PatchMapping": "PATCH",
}

# Annotations that indicate dependency injection (#887)
_SPRING_INJECT_ANNOTATIONS = frozenset({"Autowired", "Inject", "Resource"})

# ── ORM / Datasource annotation constants (#843) ─────────────────────────────

# JPA / Hibernate class-level annotations that map a class to a DB table
_JPA_TABLE_ANNOTATIONS = frozenset({"Entity", "Table"})

# Spring Data Cassandra class-level annotations
_CASSANDRA_TABLE_ANNOTATIONS = frozenset({"CassandraTable", "PrimaryTable"})
# @Table is shared between JPA and Cassandra — resolved by import context

# Spring Data Redis
_REDIS_HASH_ANNOTATIONS = frozenset({"RedisHash"})

# MyBatis / Spring Data @Query — methods that carry raw SQL or CQL strings
_SQL_QUERY_ANNOTATIONS = frozenset({"Query", "Select", "Insert", "Update", "Delete",
                                     "NamedQuery", "NamedNativeQuery"})

# Determines READ vs WRITE from a SQL/CQL string
_WRITE_PREFIXES = ("INSERT", "UPDATE", "DELETE", "MERGE", "TRUNCATE", "REPLACE")

# Spring Data repository base interfaces — presence means the interface is a repo
_SPRING_DATA_REPO_BASES = frozenset({
    "JpaRepository", "CrudRepository", "PagingAndSortingRepository",
    "ListCrudRepository", "ListPagingAndSortingRepository",
    "MongoRepository", "ReactiveMongoRepository",
    "CassandraRepository", "ReactiveCassandraRepository",
    "R2dbcRepository", "CoroutineCrudRepository",
})

# Spring Data derived-query method prefixes → READS
_SPRING_DATA_READS_PREFIXES = (
    "findby", "findall", "findfirst", "findtop", "finddistinct",
    "readby", "getby", "queryby", "searchby",
    "countby", "existsby",
    "find", "read", "get", "count", "exists", "fetch", "load", "retrieve",
)

# Spring Data derived-query method prefixes → WRITES
_SPRING_DATA_WRITES_PREFIXES = (
    "saveall", "saveandflushthem", "saveandflush", "saveallandflush",
    "save", "insertall", "insert", "updateall", "update",
    "deleteall", "deletebyid", "deleteallinbatch", "deleteinbatch",
    "deleteby", "delete", "removeall", "removeby", "remove",
    "flush", "create",
)


def _parse_sql_tables(sql: str) -> List[str]:
    """Extract table names from a SQL/CQL string without a full parser.

    Handles: FROM x, JOIN x, INTO x, UPDATE x, TABLE x
    Returns lowercase table names.
    """
    sql_upper = sql.upper()
    tables = []
    for kw in ("FROM", "JOIN", "INTO", "UPDATE", "TABLE"):
        for m in re.finditer(rf"\b{kw}\s+([`'\"]?)([\w.]+)\1", sql_upper):
            raw = m.group(2)
            # Strip schema prefix: schema.table → table
            tables.append(raw.split(".")[-1].lower())
    return list(dict.fromkeys(tables))  # deduplicate preserving order


def _sql_operation(sql: str) -> str:
    """Return 'READS' or 'WRITES' based on SQL DML prefix."""
    stripped = sql.strip().upper()
    for prefix in _WRITE_PREFIXES:
        if stripped.startswith(prefix):
            return "WRITES"
    return "READS"


def _extract_annotation_path(args_text: str) -> Optional[str]:
    """Extract the first string literal from annotation arguments, e.g. '("/api/users")' -> '/api/users'."""
    m = re.search(r'"([^"]*)"', args_text)
    return m.group(1) if m else None

JAVA_QUERIES = {
    "functions": """
        (method_declaration
            name: (identifier) @name
            parameters: (formal_parameters) @params
        ) @function_node
        
        (constructor_declaration
            name: (identifier) @name
            parameters: (formal_parameters) @params
        ) @function_node
    """,
    "classes": """
        [
            (class_declaration name: (identifier) @name)
            (interface_declaration name: (identifier) @name)
            (enum_declaration name: (identifier) @name)
            (annotation_type_declaration name: (identifier) @name)
        ] @class
    """,
    "imports": """
        (import_declaration) @import
    """,
    # variables MUST be parsed before calls so we can build var_type_map
    # and populate inferred_obj_type on method-call nodes for cross-file resolution.
    "variables": """
        (local_variable_declaration
            type: (_) @type
            declarator: (variable_declarator
                name: (identifier) @name
            )
        ) @variable
        
        (field_declaration
            type: (_) @type
            declarator: (variable_declarator
                name: (identifier) @name
            )
        ) @variable
    """,
    "calls": """
        (method_invocation
            name: (identifier) @name
        ) @call_node
        
        (object_creation_expression
            type: [
                (type_identifier)
                (scoped_type_identifier)
                (generic_type)
            ] @name
        ) @call_node
    """,
}

class JavaTreeSitterParser:
    def __init__(self, generic_parser_wrapper: Any):
        self.generic_parser_wrapper = generic_parser_wrapper
        self.language_name = "java"
        self.language = generic_parser_wrapper.language
        self.parser = generic_parser_wrapper.parser

    @staticmethod
    def _strip_generic(type_str: str) -> str:
        """Return the raw type name without generic parameters, e.g. 'List<String>' -> 'List'."""
        bracket = type_str.find('<')
        return type_str[:bracket].strip() if bracket != -1 else type_str.strip()

    def parse(self, path: Path, is_dependency: bool = False, index_source: bool = False) -> Dict[str, Any]:
        try:
            self.index_source = index_source
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                source_code = f.read()

            if not source_code.strip():
                warning_logger(f"Empty or whitespace-only file: {path}")
                return {
                    "path": str(path),
                    "functions": [],
                    "classes": [],
                    "variables": [],
                    "imports": [],
                    "function_calls": [],
                    "is_dependency": is_dependency,
                    "lang": self.language_name,
                }

            tree = self.parser.parse(bytes(source_code, "utf8"))

            # Extract package declaration for qualified_name construction and FQN resolution
            package_name = None
            pkg_match = re.search(r'^\s*package\s+([\w.]+)\s*;', source_code, re.MULTILINE)
            if pkg_match:
                package_name = pkg_match.group(1)

            parsed_functions = []
            parsed_classes = []
            parsed_variables = []
            parsed_imports = []
            parsed_calls = []
            # var_type_map is built from the "variables" pass so that the subsequent
            # "calls" pass can resolve the declared type of field/local-variable
            # receivers (e.g. `service.doWork()` -> inferred_obj_type='WorkService').
            var_type_map: Dict[str, str] = {}

            for capture_name, query in JAVA_QUERIES.items():
                results = execute_query(self.language, query, tree.root_node)

                if capture_name == "functions":
                    parsed_functions = self._parse_functions(results, source_code, path, package_name)
                elif capture_name == "classes":
                    all_types = self._parse_classes(results, source_code, path, package_name)
                    parsed_classes = all_types.get("classes", [])
                    parsed_interfaces = all_types.get("interfaces", [])
                    parsed_enums = all_types.get("enums", [])
                elif capture_name == "imports":
                    parsed_imports = self._parse_imports(results, source_code)
                elif capture_name == "variables":
                    parsed_variables = self._parse_variables(results, source_code, path)
                    # Build name->type map for cross-file call resolution
                    var_type_map = {
                        v["name"]: self._strip_generic(v["type"])
                        for v in parsed_variables
                        if v.get("type") and v.get("name")
                    }
                elif capture_name == "calls":
                    parsed_calls = self._parse_calls(results, source_code, var_type_map)

            # Spring injection extraction (#887) — needs tree + all types
            spring_injections = self._extract_spring_injections(tree, path, parsed_classes + parsed_interfaces)

            # ORM / datasource mapping extraction (#843)
            orm_mappings = self._extract_orm_mappings(tree, path, parsed_classes + parsed_interfaces, parsed_functions)

            return {
                "path": str(path),
                "functions": parsed_functions,
                "classes": parsed_classes,
                "interfaces": parsed_interfaces,
                "enums": parsed_enums,
                "variables": parsed_variables,
                "imports": parsed_imports,
                "function_calls": parsed_calls,
                "spring_injections": spring_injections,
                "orm_mappings": orm_mappings,
                "is_dependency": is_dependency,
                "lang": self.language_name,
                "package_name": package_name,
            }

        except Exception as e:
            error_logger(f"Error parsing Java file {path}: {e}")
            return {
                "path": str(path),
                "functions": [],
                "classes": [],
                "variables": [],
                "imports": [],
                "function_calls": [],
                "orm_mappings": [],
                "is_dependency": is_dependency,
                "lang": self.language_name,
            }

    def _get_parent_context(self, node: Any) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        curr = node.parent
        while curr:
            if curr.type in ("method_declaration", "constructor_declaration"):
                name_node = curr.child_by_field_name("name")
                return (
                    self._get_node_text(name_node) if name_node else None,
                    curr.type,
                    curr.start_point[0] + 1,
                )
            if curr.type in ("class_declaration", "interface_declaration", "enum_declaration", "annotation_type_declaration"):
                name_node = curr.child_by_field_name("name")
                return (
                    self._get_node_text(name_node) if name_node else None,
                    curr.type,
                    curr.start_point[0] + 1,
                )
            curr = curr.parent
        return None, None, None

    def _get_node_text(self, node: Any) -> str:
        if not node: return ""
        return node.text.decode("utf-8")

    # ── Annotation helpers (#887) ───────────────────────────────────────────

    def _get_annotation_details(self, ann_node: Any) -> Tuple[str, str]:
        """Return (annotation_name, annotation_args_text) for an annotation/marker_annotation node."""
        name_node = ann_node.child_by_field_name("name")
        args_node = ann_node.child_by_field_name("arguments")
        ann_name = self._get_node_text(name_node) if name_node else ""
        ann_args = self._get_node_text(args_node) if args_node else ""
        return ann_name, ann_args

    def _get_node_annotations(self, node: Any) -> List[Tuple[str, str]]:
        """Return list of (name, args_text) for all annotations on a node's modifiers."""
        # child_by_field_name("modifiers") is unreliable across tree-sitter-java versions;
        # fall back to scanning children by node type.
        modifiers = node.child_by_field_name("modifiers")
        if not modifiers:
            for child in node.children:
                if child.type == "modifiers":
                    modifiers = child
                    break
        if not modifiers:
            return []
        result = []
        for child in modifiers.children:
            if child.type in ("annotation", "marker_annotation"):
                result.append(self._get_annotation_details(child))
        return result

    def _parse_functions(self, captures: list, source_code: str, path: Path, package_name: Optional[str] = None) -> list[Dict[str, Any]]:
        functions = []
        # Group by node identity or stable key to avoid duplicates
        seen_nodes = set()

        for node, capture_name in captures:
            if capture_name == "function_node":
                node_id = (node.start_byte, node.end_byte, node.type)
                if node_id in seen_nodes:
                    continue
                seen_nodes.add(node_id)
                
                try:
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        func_name = self._get_node_text(name_node)
                        
                        params_node = node.child_by_field_name("parameters")
                        parameters = []
                        parameter_types = []
                        if params_node:
                            params_text = self._get_node_text(params_node)
                            parameters = self._extract_parameter_names(params_text)
                            parameter_types = self._extract_parameter_types(params_text)

                        source_text = self._get_node_text(node)
                        
                        # Get class context
                        context_name, context_type, context_line = self._get_parent_context(node)

                        func_data = {
                            "name": func_name,
                            "parameters": parameters,
                            "args": parameters,
                            "arg_types": parameter_types,
                            "line_number": start_line,
                            "end_line": end_line,
                            "path": str(path),
                            "lang": self.language_name,
                            "context": context_name,
                            "class_context": context_name if context_type in ("class_declaration", "interface_declaration", "enum_declaration", "annotation_type_declaration") else None
                        }

                        if package_name:
                            func_data["package_name"] = package_name
                            class_ctx = context_name if context_type in ("class_declaration", "interface_declaration", "enum_declaration", "annotation_type_declaration") else None
                            if class_ctx:
                                func_data["qualified_name"] = f"{package_name}.{class_ctx}.{func_name}"
                            else:
                                func_data["qualified_name"] = f"{package_name}.{func_name}"

                        if self.index_source:
                            func_data["source"] = source_text

                        # Spring HTTP mapping / @Transactional detection (#887)
                        for ann_name, ann_args in self._get_node_annotations(node):
                            if ann_name in _SPRING_HTTP_MAPPINGS:
                                implicit_method = _SPRING_HTTP_MAPPINGS[ann_name]
                                if implicit_method:
                                    func_data["http_method"] = implicit_method
                                else:
                                    # @RequestMapping: try to read method= attribute
                                    m = re.search(r'method\s*=\s*RequestMethod\.(\w+)', ann_args)
                                    func_data["http_method"] = m.group(1) if m else "ANY"
                                func_data["http_path"] = _extract_annotation_path(ann_args)
                            elif ann_name == "Transactional":
                                func_data["transactional"] = True

                        functions.append(func_data)
                        
                except Exception as e:
                    error_logger(f"Error parsing function in {path}: {e}")
                    continue

        return functions

    def _parse_classes(self, captures: list, source_code: str, path: Path, package_name: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        results = {
            "classes": [],
            "interfaces": [],
            "enums": [],
        }
        seen_nodes = set()

        for node, capture_name in captures:
            if capture_name == "class":
                node_id = (node.start_byte, node.end_byte, node.type)
                if node_id in seen_nodes:
                    continue
                seen_nodes.add(node_id)
                
                try:
                    # Map tree-sitter node types to our internal categories
                    if node.type == "interface_declaration":
                        category = "interfaces"
                        label = "Interface"
                    elif node.type == "enum_declaration":
                        category = "enums"
                        label = "Enum"
                    else:
                        category = "classes"
                        label = "Class"
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        class_name = self._get_node_text(name_node)
                        source_text = self._get_node_text(node)
                        
                        bases = []
                        superclass_node = node.child_by_field_name('superclass')
                        if superclass_node:
                            # Search for the actual type inside the superclass node (skipping 'extends')
                            for child in superclass_node.children:
                                if child.type in ('type_identifier', 'generic_type', 'scoped_type_identifier'):
                                    bases.append(self._get_node_text(child))
                                    break

                        # Look for super_interfaces (implements)
                        interfaces_node = node.child_by_field_name('interfaces')
                        if not interfaces_node:
                            interfaces_node = next((c for c in node.children if c.type == 'super_interfaces'), None)
                        
                        if interfaces_node:
                            type_list = interfaces_node.child_by_field_name('list')
                            if not type_list:
                                type_list = next((c for c in interfaces_node.children if c.type == 'type_list'), None)
                            
                            if type_list:
                                for child in type_list.children:
                                    if child.type in ('type_identifier', 'generic_type', 'scoped_type_identifier'):
                                        bases.append(self._get_node_text(child))
                            else:
                                # Fallback to manual scan of super_interfaces children
                                for child in interfaces_node.children:
                                    if child.type in ('type_identifier', 'generic_type', 'scoped_type_identifier'):
                                        bases.append(self._get_node_text(child))


                        # Look for extends_interfaces (interface extends another interface)
                        # Tree-sitter uses a different field for interface_declaration.
                        # Scan by node type since child_by_field_name may not expose it.
                        extends_ifaces_node = (
                            node.child_by_field_name('extends_interfaces')
                            or next(
                                (c for c in node.children if c.type == 'extends_interfaces'),
                                None,
                            )
                        )
                        if extends_ifaces_node:
                            iface_list = next(
                                (c for c in extends_ifaces_node.children
                                 if c.type in ('type_list', 'interface_type_list')),
                                None,
                            )
                            candidates = iface_list.children if iface_list else extends_ifaces_node.children
                            for child in candidates:
                                if child.type in ('type_identifier', 'generic_type', 'scoped_type_identifier'):
                                    bases.append(self._get_node_text(child))

                        class_data = {
                            "name": class_name,
                            "line_number": start_line,
                            "end_line": end_line,
                            "bases": bases,
                            "path": str(path),
                            "lang": self.language_name,
                        }

                        if package_name:
                            class_data["qualified_name"] = f"{package_name}.{class_name}"

                        # Spring stereotype detection (#887)
                        for ann_name, ann_args in self._get_node_annotations(node):
                            if ann_name in _SPRING_CLASS_STEREOTYPES:
                                class_data["spring_stereotype"] = _SPRING_CLASS_STEREOTYPES[ann_name]
                                # @RequestMapping on the class gives a path prefix
                                break
                        # Also check if class-level @RequestMapping is present (path prefix)
                        for ann_name, ann_args in self._get_node_annotations(node):
                            if ann_name == "RequestMapping":
                                class_data["request_mapping_prefix"] = _extract_annotation_path(ann_args)
                                break

                        if self.index_source:
                            class_data["source"] = source_text
                        
                        class_data["node_label"] = label
                        results[category].append(class_data)
                        
                except Exception as e:
                    error_logger(f"Error parsing class in {path}: {e}")
                    continue

        return results

    def _parse_variables(self, captures: list, source_code: str, path: Path) -> list[Dict[str, Any]]:
        variables = []
        seen_vars = set()
        
        for node, capture_name in captures:
            if capture_name == "variable":
                # The capture is on the whole declaration, we look for name/type children or captures
                # But our query captures @name and @type separately on subnodes.
                # Actually, the query structure:
                # (local_variable_declaration ... declarator: (variable_declarator name: (identifier) @name)) @variable
                # This means we get 'variable', 'type', 'name' captures in sequence.
                # We should iterate and group them.
                pass

        # Re-approach: Iterate captures and collect finding.
        # Tree sitter returns a list of (node, capture_name).
        
        # Simpler approach: Iterate 'name' captures that are inside a variable declaration context
        
        current_var = {}
        
        for node, capture_name in captures:
            if capture_name == "name":
                # Check parent to confirm it's a variable declarator
                if node.parent.type == "variable_declarator":
                     var_name = self._get_node_text(node)
                     start_line = node.start_point[0] + 1
                     
                     # Get type? Type is sibling of declarator usually, or child of declaration
                     # local_variable_declaration -> type, variable_declarator
                     declaration = node.parent.parent
                     type_node = declaration.child_by_field_name("type")
                     var_type = self._get_node_text(type_node) if type_node else "Unknown"
                     
                     start_byte = node.start_byte
                     if start_byte in seen_vars:
                         continue
                     seen_vars.add(start_byte)
                     
                     ctx_name, ctx_type, ctx_line = self._get_parent_context(node)

                     variables.append({
                        "name": var_name,
                        "type": var_type,
                        "line_number": start_line,
                        "path": str(path),
                        "lang": self.language_name,
                        "context": ctx_name,
                        "class_context": ctx_name if ctx_type in ("class_declaration", "interface_declaration", "enum_declaration", "annotation_type_declaration") else None
                     })

        return variables

    def _extract_orm_mappings(
        self,
        tree: Any,
        path: Path,
        parsed_classes: List[Dict[str, Any]],
        parsed_functions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Walk the tree and emit ORM mapping records for #843.

        Detects:
        - @Entity + @Table(name=...)  → JPA class→table mapping
        - @Table(value=...)           → Cassandra (Spring Data Cassandra)
        - @RedisHash(value=...)       → Spring Data Redis
        - @Query / @Select / @Insert / @Update / @Delete with SQL strings
        - @NamedQuery / @NamedNativeQuery (class-level named queries)
        - MyBatis @Select / @Insert / @Update / @Delete on methods

        Returns list of dicts with type "class_table" | "method_query":
          class_table: {kind, class_name, class_path, orm_table, line_number}
          method_query: {kind, method_name, class_name, method_path, db_tables, operation, sql, line_number}
        """
        if not (parsed_classes or parsed_functions):
            return []

        # Build quick lookup: line -> class name
        class_ranges = []
        for cls in parsed_classes:
            class_ranges.append((cls["line_number"], cls.get("end_line", 999999), cls["name"]))

        def _class_at_line(line: int) -> Optional[str]:
            for start, end, cname in class_ranges:
                if start <= line <= end:
                    return cname
            return None

        mappings: List[Dict[str, Any]] = []

        def _walk(node: Any) -> None:  # noqa: C901
            # ── CLASS-LEVEL annotations ────────────────────────────────────
            if node.type in ("class_declaration", "interface_declaration", "annotation_type_declaration"):
                annotations = self._get_node_annotations(node)
                ann_map = {n: args for n, args in annotations}
                line = node.start_point[0] + 1

                name_node = node.child_by_field_name("name")
                class_name = self._get_node_text(name_node) if name_node else None

                if "Entity" in ann_map:
                    # JPA entity: look for @Table(name=...)
                    table_name = None
                    if "Table" in ann_map:
                        t_args = ann_map["Table"] or ""
                        m = re.search(r'name\s*=\s*"([^"]+)"', t_args)
                        if not m:
                            m = re.search(r'"([^"]+)"', t_args)
                        table_name = m.group(1) if m else (class_name.lower() if class_name else None)
                    elif class_name:
                        table_name = class_name.lower()  # JPA default: snake_case of class name

                    if class_name and table_name:
                        mappings.append({
                            "kind": "class_table",
                            "datastore": "mysql",
                            "class_name": class_name,
                            "class_path": str(path),
                            "orm_table": table_name,
                            "line_number": line,
                        })

                elif "Table" in ann_map and "Entity" not in ann_map:
                    # Could be Spring Data Cassandra @Table(keyspace="...", name="...") or @Table(value="...")
                    t_args = ann_map["Table"] or ""
                    # Prefer explicit name= attribute (Cassandra uses keyspace+name; name= is the table)
                    m = re.search(r'\bname\s*=\s*"([^"]+)"', t_args)
                    if not m:
                        m = re.search(r'value\s*=\s*"([^"]+)"', t_args)
                    if not m:
                        m = re.search(r'"([^"]+)"', t_args)
                    table_name = m.group(1) if m else (class_name.lower() if class_name else None)
                    if class_name and table_name:
                        mappings.append({
                            "kind": "class_table",
                            "datastore": "cassandra",
                            "class_name": class_name,
                            "class_path": str(path),
                            "orm_table": table_name,
                            "line_number": line,
                        })

                if "RedisHash" in ann_map:
                    rh_args = ann_map["RedisHash"] or ""
                    m = re.search(r'value\s*=\s*"([^"]+)"', rh_args)
                    if not m:
                        m = re.search(r'"([^"]+)"', rh_args)
                    key_prefix = m.group(1) if m else (class_name or "")
                    if class_name:
                        mappings.append({
                            "kind": "class_table",
                            "datastore": "redis",
                            "class_name": class_name,
                            "class_path": str(path),
                            "orm_table": key_prefix,
                            "line_number": line,
                        })

                # @NamedQuery / @NamedNativeQuery on the class
                for ann_name in ("NamedQuery", "NamedNativeQuery"):
                    if ann_name in ann_map:
                        args_text = ann_map[ann_name] or ""
                        m_sql = re.search(r'query\s*=\s*"([^"]+)"', args_text)
                        if m_sql:
                            sql = m_sql.group(1)
                            tables = _parse_sql_tables(sql)
                            op = _sql_operation(sql)
                            if class_name:
                                mappings.append({
                                    "kind": "method_query",
                                    "datastore": "mysql",
                                    "method_name": None,
                                    "class_name": class_name,
                                    "method_path": str(path),
                                    "db_tables": tables,
                                    "operation": op,
                                    "sql": sql[:200],
                                    "line_number": line,
                                })

            # ── METHOD-LEVEL annotations ───────────────────────────────────
            elif node.type in ("method_declaration", "constructor_declaration"):
                annotations = self._get_node_annotations(node)
                ann_map = {n: args for n, args in annotations}
                line = node.start_point[0] + 1
                class_name = _class_at_line(line)

                name_node = node.child_by_field_name("name")
                method_name = self._get_node_text(name_node) if name_node else None

                for ann_name in _SQL_QUERY_ANNOTATIONS:
                    if ann_name in ann_map:
                        args_text = ann_map[ann_name] or ""
                        # Extract raw SQL string: first quoted string in the annotation args
                        m = re.search(r'"([^"]{4,})"', args_text)
                        if m:
                            sql = m.group(1)
                            tables = _parse_sql_tables(sql)
                            op = _sql_operation(sql)
                            if tables or op:
                                mappings.append({
                                    "kind": "method_query",
                                    "datastore": "mysql",
                                    "method_name": method_name,
                                    "class_name": class_name,
                                    "method_path": str(path),
                                    "db_tables": tables,
                                    "operation": op,
                                    "sql": sql[:200],
                                    "line_number": line,
                                })
                            break  # only one SQL annotation per method expected

            for child in node.children:
                _walk(child)

        _walk(tree.root_node)

        # ── Spring Data repository derived-query methods ───────────────────
        # For interfaces extending JpaRepository<Entity, ID> etc., emit
        # READS/WRITES records that the writer resolves via MAPS_TO hop.
        for cls in parsed_classes:
            if str(path) != cls.get("path"):
                continue
            bases = cls.get("bases", [])
            entity_class: Optional[str] = None
            for base_str in bases:
                for repo_base in _SPRING_DATA_REPO_BASES:
                    if repo_base in base_str:
                        # Extract first generic arg: JpaRepository<UserAuth, Long> → UserAuth
                        m = re.search(r'<\s*([A-Za-z][A-Za-z0-9_]*)', base_str)
                        if m:
                            entity_class = m.group(1)
                        break
                if entity_class:
                    break

            if not entity_class:
                continue

            cls_start = cls["line_number"]
            cls_end = cls.get("end_line", 999999)

            for fn in parsed_functions:
                if fn.get("path") != str(path):
                    continue
                fn_line = fn.get("line_number", 0)
                if not (cls_start <= fn_line <= cls_end):
                    continue

                method_name = fn.get("name", "")
                if not method_name:
                    continue

                mn_lower = method_name.lower()
                # Check WRITES first (longer prefixes must come first — handled by tuple order)
                if any(mn_lower.startswith(p) for p in _SPRING_DATA_WRITES_PREFIXES):
                    operation = "WRITES"
                elif any(mn_lower.startswith(p) for p in _SPRING_DATA_READS_PREFIXES):
                    operation = "READS"
                else:
                    continue

                mappings.append({
                    "kind": "spring_data_method",
                    "entity_class": entity_class,
                    "method_name": method_name,
                    "class_name": cls["name"],
                    "method_path": str(path),
                    "operation": operation,
                    "line_number": fn_line,
                })

        return mappings

    def _extract_spring_injections(
        self,
        tree: Any,
        path: Path,
        parsed_classes: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Walk field_declaration nodes and emit injection records for @Autowired/@Inject fields.

        Returns a list of dicts with keys:
            injector_class, injector_path, injected_class, field_name, inject_line
        """
        if not parsed_classes:
            return []

        # Build quick lookup: line range -> class name
        class_ranges = []
        for cls in parsed_classes:
            class_ranges.append((cls["line_number"], cls.get("end_line", 999999), cls["name"]))

        def _class_at_line(line: int) -> Optional[str]:
            for start, end, name in class_ranges:
                if start <= line <= end:
                    return name
            return None

        injections: List[Dict[str, Any]] = []

        def _walk(node: Any) -> None:
            if node.type == "field_declaration":
                annotations = self._get_node_annotations(node)
                ann_names = {n for n, _ in annotations}
                if ann_names & _SPRING_INJECT_ANNOTATIONS:
                    # Get declared type (the field type, e.g. UserService)
                    type_node = node.child_by_field_name("type")
                    if type_node:
                        field_type = self._strip_generic(self._get_node_text(type_node))
                        # Get field variable name
                        for child in node.children:
                            if child.type == "variable_declarator":
                                name_node = child.child_by_field_name("name")
                                if name_node:
                                    field_line = node.start_point[0] + 1
                                    injector_cls = _class_at_line(field_line)
                                    if injector_cls:
                                        injections.append({
                                            "injector_class": injector_cls,
                                            "injector_path": str(path),
                                            "injected_class": field_type,
                                            "field_name": self._get_node_text(name_node),
                                            "inject_line": field_line,
                                        })
            for child in node.children:
                _walk(child)

        _walk(tree.root_node)
        return injections

    def _parse_imports(self, captures: list, source_code: str) -> list[dict]:
        imports = []
        
        for node, capture_name in captures:
            if capture_name == "import":
                try:
                    import_text = self._get_node_text(node)
                    import_match = re.search(r'import\s+(?:static\s+)?([^;]+)', import_text)
                    if import_match:
                        import_path = import_match.group(1).strip()
                        
                        import_data = {
                            "name": import_path,
                            "full_import_name": import_path,
                            "line_number": node.start_point[0] + 1,
                            "alias": None,
                            "context": (None, None),
                            "lang": self.language_name,
                            "is_dependency": False,
                        }
                        imports.append(import_data)
                except Exception as e:
                    error_logger(f"Error parsing import: {e}")
                    continue

        return imports

    def _parse_calls(self, captures: list, source_code: str, var_type_map: Optional[Dict[str, str]] = None) -> list[dict]:
        calls = []
        seen_calls = set()
        if var_type_map is None:
            var_type_map = {}

        debug_log(f"Processing {len(captures)} captures for calls")

        for node, capture_name in captures:
            if capture_name == "name":
                try:
                    call_name = self._get_node_text(node)
                    line_number = node.start_point[0] + 1

                    # Ensure we identify the full call node
                    call_node = node.parent
                    while call_node and call_node.type not in ("method_invocation", "object_creation_expression"):
                        call_node = call_node.parent

                    if not call_node:
                        # fallback if we matched a loose identifier
                        call_node = node

                    # Avoid duplicates
                    call_key = f"{call_name}_{line_number}"
                    if call_key in seen_calls:
                        continue
                    seen_calls.add(call_key)

                    # Extract arguments
                    args = []
                    if call_node:
                        args_node = next((c for c in call_node.children if c.type == 'argument_list'), None)
                        if args_node:
                            for arg in args_node.children:
                                if arg.type not in ('(', ')', ','):
                                    args.append(self._get_node_text(arg))

                    # Extract meaningful full_name and infer the receiver's declared type.
                    # When a method is called on a field or local variable whose type was
                    # declared in this file (e.g. `private WorkService workService;`),
                    # we populate inferred_obj_type so that resolve_function_call can
                    # look it up in imports_map and create an accurate cross-file CALLS edge.
                    full_name = call_name
                    inferred_obj_type = None
                    if call_node.type == 'method_invocation':
                        obj_node = call_node.child_by_field_name('object')
                        if obj_node:
                            obj_text = self._get_node_text(obj_node)
                            full_name = f"{obj_text}.{call_name}"
                            # Only resolve simple identifiers (not chained calls like foo.bar().baz())
                            base_obj = obj_text.split(".")[0]
                            if "(" not in base_obj and base_obj in var_type_map:
                                inferred_obj_type = var_type_map[base_obj]
                    elif call_node.type == 'object_creation_expression':
                        type_node = call_node.child_by_field_name('type')
                        if type_node:
                            full_name = self._get_node_text(type_node)

                    ctx_name, ctx_type, ctx_line = self._get_parent_context(node)

                    debug_log(f"Found call: {call_name} (full_name: {full_name}, inferred_obj_type: {inferred_obj_type}, args: {args}) in context {ctx_name}")

                    call_data = {
                        "name": call_name,
                        "full_name": full_name,
                        "line_number": line_number,
                        "args": args,
                        "inferred_obj_type": inferred_obj_type,
                        "context": (ctx_name, ctx_type, ctx_line),
                        "class_context": (ctx_name, ctx_line) if ctx_type in ("class_declaration", "interface_declaration", "enum_declaration", "annotation_type_declaration") else (None, None),
                        "lang": self.language_name,
                        "is_dependency": False,
                    }
                    calls.append(call_data)
                except Exception as e:
                    error_logger(f"Error parsing call: {e}")
                    continue

        return calls
    

    def _extract_parameter_names(self, params_text: str) -> list[str]:
        params = []
        if not params_text or params_text.strip() == "()":
            return params
            
        params_content = params_text.strip("()")
        if not params_content:
            return params
            
        for param in self._split_parameters(params_text):
            param = self._strip_parameter_annotations_and_modifiers(param)
            if param:
                parts = param.split()
                if len(parts) >= 2:
                    param_name = parts[-1]
                    params.append(param_name)
                    
        return params

    def _split_parameters(self, params_text: str) -> list[str]:
        if not params_text or params_text.strip() == "()":
            return []

        params_content = params_text.strip().strip("()")
        if not params_content:
            return []

        params = []
        current = []
        depth_angle = depth_round = depth_square = depth_curly = 0
        in_string: Optional[str] = None
        escaped = False
        for char in params_content:
            if in_string:
                current.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == in_string:
                    in_string = None
                continue

            if char in {"'", '"'}:
                in_string = char
            elif char == "<":
                depth_angle += 1
            elif char == ">":
                depth_angle = max(0, depth_angle - 1)
            elif char == "(":
                depth_round += 1
            elif char == ")":
                depth_round = max(0, depth_round - 1)
            elif char == "[":
                depth_square += 1
            elif char == "]":
                depth_square = max(0, depth_square - 1)
            elif char == "{":
                depth_curly += 1
            elif char == "}":
                depth_curly = max(0, depth_curly - 1)
            elif char == "," and depth_angle == depth_round == depth_square == depth_curly == 0:
                param = "".join(current).strip()
                if param:
                    params.append(param)
                current = []
                continue
            current.append(char)

        param = "".join(current).strip()
        if param:
            params.append(param)
        return params

    def _matching_paren_index(self, text: str, open_index: int) -> Optional[int]:
        depth = 0
        in_string: Optional[str] = None
        escaped = False
        for idx in range(open_index, len(text)):
            char = text[idx]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == in_string:
                    in_string = None
                continue

            if char in {"'", '"'}:
                in_string = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return idx
        return None

    def _strip_parameter_annotations_and_modifiers(self, param: str) -> str:
        text = param.strip()
        while text:
            final_match = re.match(r"final\b\s*", text)
            if final_match:
                text = text[final_match.end() :].lstrip()
                continue
            if not text.startswith("@"):
                break

            match = re.match(r"@[\w.]+", text)
            if not match:
                break
            idx = match.end()
            while idx < len(text) and text[idx].isspace():
                idx += 1
            if idx < len(text) and text[idx] == "(":
                close_idx = self._matching_paren_index(text, idx)
                if close_idx is None:
                    break
                idx = close_idx + 1
            text = text[idx:].lstrip()
        return text

    def _extract_parameter_types(self, params_text: str) -> list[str]:
        primitive_types = {
            "byte": "Byte",
            "short": "Short",
            "int": "Int",
            "long": "Long",
            "float": "Float",
            "double": "Double",
            "boolean": "Boolean",
            "char": "Char",
        }
        types = []
        for param in self._split_parameters(params_text):
            cleaned = self._strip_parameter_annotations_and_modifiers(param)
            parts = cleaned.split()
            if len(parts) < 2:
                continue
            type_name = " ".join(parts[:-1]).replace("...", "[]").strip()
            while type_name.endswith("[]"):
                type_name = type_name[:-2].strip()
            type_name = self._strip_generic(type_name)
            types.append(primitive_types.get(type_name, type_name))
        return types


def pre_scan_java(files: list[Path], parser_wrapper) -> dict:
    name_to_files = {}
    
    for path in files:
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Extract package for FQN construction (e.g. com.ea.nexus.billing.BillingService)
            pkg_match = re.search(r'^\s*package\s+([\w.]+)\s*;', content, re.MULTILINE)
            file_package = pkg_match.group(1) if pkg_match else None

            class_matches = re.finditer(r'\b(?:public\s+|private\s+|protected\s+)?(?:static\s+)?(?:abstract\s+)?(?:final\s+)?class\s+(\w+)', content)
            for match in class_matches:
                class_name = match.group(1)
                if class_name not in name_to_files:
                    name_to_files[class_name] = []
                name_to_files[class_name].append(str(path))
                # Also register under FQN so Phase 2 qualified-import lookups resolve
                if file_package:
                    fqn = f"{file_package}.{class_name}"
                    if fqn not in name_to_files:
                        name_to_files[fqn] = []
                    name_to_files[fqn].append(str(path))
            
            interface_matches = re.finditer(r'\b(?:public\s+|private\s+|protected\s+)?interface\s+(\w+)', content)
            for match in interface_matches:
                interface_name = match.group(1)
                if interface_name not in name_to_files:
                    name_to_files[interface_name] = []
                name_to_files[interface_name].append(str(path))
                if file_package:
                    fqn = f"{file_package}.{interface_name}"
                    if fqn not in name_to_files:
                        name_to_files[fqn] = []
                    name_to_files[fqn].append(str(path))
                
        except Exception as e:
            error_logger(f"Error pre-scanning Java file {path}: {e}")
            
    return name_to_files
