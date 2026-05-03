from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import re
from codegraphcontext.utils.debug_log import debug_log, info_logger, error_logger, warning_logger
from codegraphcontext.utils.tree_sitter_manager import execute_query

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
                    parsed_functions = self._parse_functions(results, source_code, path)
                elif capture_name == "classes":
                    parsed_classes = self._parse_classes(results, source_code, path)
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

            return {
                "path": str(path),
                "functions": parsed_functions,
                "classes": parsed_classes,
                "variables": parsed_variables,
                "imports": parsed_imports,
                "function_calls": parsed_calls,
                "is_dependency": is_dependency,
                "lang": self.language_name,
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

    def _parse_functions(self, captures: list, source_code: str, path: Path) -> list[Dict[str, Any]]:
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
                        if params_node:
                            params_text = self._get_node_text(params_node)
                            parameters = self._extract_parameter_names(params_text)

                        source_text = self._get_node_text(node)
                        
                        # Get class context
                        context_name, context_type, context_line = self._get_parent_context(node)

                        func_data = {
                            "name": func_name,
                            "parameters": parameters,
                            "line_number": start_line,
                            "end_line": end_line,
                            "path": str(path),
                            "lang": self.language_name,
                            "context": context_name,
                            "class_context": context_name if context_type and "class" in context_type else None
                        }

                        if self.index_source:
                            func_data["source"] = source_text
                        
                        functions.append(func_data)
                        
                except Exception as e:
                    error_logger(f"Error parsing function in {path}: {e}")
                    continue

        return functions

    def _parse_classes(self, captures: list, source_code: str, path: Path) -> list[Dict[str, Any]]:
        classes = []
        seen_nodes = set()

        for node, capture_name in captures:
            if capture_name == "class":
                node_id = (node.start_byte, node.end_byte, node.type)
                if node_id in seen_nodes:
                    continue
                seen_nodes.add(node_id)
                
                try:
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        class_name = self._get_node_text(name_node)
                        source_text = self._get_node_text(node)
                        
                        bases = []
                        # Look for superclass (extends)
                        superclass_node = node.child_by_field_name('superclass')
                        if superclass_node:
                            # In Java, superclass field usually points to a type node
                            bases.append(self._get_node_text(superclass_node))

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
                                for child in interfaces_node.children:
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

                        if self.index_source:
                            class_data["source"] = source_text
                        
                        classes.append(class_data)
                        
                except Exception as e:
                    error_logger(f"Error parsing class in {path}: {e}")
                    continue

        return classes

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
                        "class_context": ctx_name if ctx_type and "class" in ctx_type else None
                     })

        return variables

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
                        "class_context": (ctx_name, ctx_line) if ctx_type and "class" in ctx_type else (None, None),
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
            
        for param in params_content.split(","):
            param = param.strip()
            if param:
                parts = param.split()
                if len(parts) >= 2:
                    param_name = parts[-1]
                    params.append(param_name)
                    
        return params


def pre_scan_java(files: list[Path], parser_wrapper) -> dict:
    name_to_files = {}
    
    for path in files:
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            class_matches = re.finditer(r'\b(?:public\s+|private\s+|protected\s+)?(?:static\s+)?(?:abstract\s+)?(?:final\s+)?class\s+(\w+)', content)
            for match in class_matches:
                class_name = match.group(1)
                if class_name not in name_to_files:
                    name_to_files[class_name] = []
                name_to_files[class_name].append(str(path))
            
            interface_matches = re.finditer(r'\b(?:public\s+|private\s+|protected\s+)?interface\s+(\w+)', content)
            for match in interface_matches:
                interface_name = match.group(1)
                if interface_name not in name_to_files:
                    name_to_files[interface_name] = []
                name_to_files[interface_name].append(str(path))
                
        except Exception as e:
            error_logger(f"Error pre-scanning Java file {path}: {e}")
            
    return name_to_files
