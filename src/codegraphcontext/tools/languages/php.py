from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import re
from codegraphcontext.utils.debug_log import debug_log, info_logger, error_logger, warning_logger
from codegraphcontext.utils.tree_sitter_manager import execute_query

# Reference: https://github.com/tree-sitter/tree-sitter-php/blob/master/queries/tags.scm
PHP_QUERIES = {
    "functions": """
        (function_definition
            name: (name) @name
            parameters: (formal_parameters) @params
        ) @function_node

        (method_declaration
            name: (name) @name
            parameters: (formal_parameters) @params
        ) @function_node
    """,
    "classes": """
        (class_declaration
            name: (name) @name
        ) @class
        
        (interface_declaration
            name: (name) @name
        ) @interface
        
        (trait_declaration
            name: (name) @name
        ) @trait
    """,
    "imports": """
        (use_declaration) @import
    """,
    "calls": """
        (function_call_expression
            function: [
                (qualified_name) @name
                (name) @name
            ]
        ) @call_node
        
        (member_call_expression
            name: (name) @name
        ) @call_node
        
        (scoped_call_expression
            name: (name) @name
        ) @call_node
        
        (object_creation_expression) @call_node
    """,
    "variables": """
        (variable_name) @variable
    """,
}

class PhpTreeSitterParser:
    def __init__(self, generic_parser_wrapper: Any):
        self.generic_parser_wrapper = generic_parser_wrapper
        self.language_name = "php"
        self.language = generic_parser_wrapper.language
        self.parser = generic_parser_wrapper.parser

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
                    "interfaces": [],
                    "traits": [],
                    "variables": [],
                    "imports": [],
                    "function_calls": [],
                    "is_dependency": is_dependency,
                    "lang": self.language_name,
                }

            tree = self.parser.parse(bytes(source_code, "utf8"))

            parsed_functions = []
            parsed_classes = []
            parsed_interfaces = []
            parsed_traits = []
            parsed_variables = []
            parsed_imports = []
            parsed_calls = []

            for capture_name, query in PHP_QUERIES.items():
                results = execute_query(self.language, query, tree.root_node)

                if capture_name == "functions":
                    parsed_functions = self._parse_functions(results, source_code, path)
                elif capture_name == "classes":
                    # We group classes, interfaces, traits here, but separating them is cleaner
                    # Wait, my query combines them. I should verify results.
                    # execute_query returns (node, capture_name)
                    # I can filter inside _parse_classes
                    parsed_classes, parsed_interfaces, parsed_traits = self._parse_types(results, source_code, path)
                elif capture_name == "imports":
                    parsed_imports = self._parse_imports(results, source_code)
                elif capture_name == "calls":
                    parsed_calls = self._parse_calls(results, source_code)
                elif capture_name == "variables":
                    parsed_variables = self._parse_variables(results, source_code, path)

            return {
                "path": str(path),
                "functions": parsed_functions,
                "classes": parsed_classes,
                "interfaces": parsed_interfaces,
                "traits": parsed_traits,
                "variables": parsed_variables,
                "imports": parsed_imports,
                "function_calls": parsed_calls,
                "is_dependency": is_dependency,
                "lang": self.language_name,
            }

        except Exception as e:
            error_logger(f"Error parsing PHP file {path}: {e}")
            return {
                "path": str(path),
                "functions": [],
                "classes": [],
                "interfaces": [],
                "traits": [],
                "variables": [],
                "imports": [],
                "function_calls": [],
                "is_dependency": is_dependency,
                "lang": self.language_name,
            }

    def _get_parent_context(self, node: Any) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        curr = node.parent
        while curr:
            if curr.type in ("function_definition", "method_declaration", "class_declaration", "interface_declaration", "trait_declaration"):
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
                            # PHP parameters: function($a, $b)
                            for child in params_node.children:
                                if "variable_name" in child.type or "simple_parameter" in child.type:
                                     # Extract variable name from simple_parameter
                                     var_node = child if "variable_name" in child.type else child.child_by_field_name("name")
                                     if var_node:
                                         parameters.append(self._get_node_text(var_node))

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
                            "context_type": context_type,
                            "class_context": context_name if context_type and ("class" in context_type or "interface" in context_type or "trait" in context_type) else None
                        }
                        
                        if self.index_source:
                            func_data["source"] = source_text
                        
                        functions.append(func_data)
                        
                except Exception as e:
                    error_logger(f"Error parsing function in {path}: {e}")
                    continue

        return functions

    def _parse_types(self, captures: list, source_code: str, path: Path) -> Tuple[list, list, list]:
        classes = []
        interfaces = []
        traits = []
        seen_nodes = set()

        for node, capture_name in captures:
            if capture_name in ("class", "interface", "trait"):
                node_id = (node.start_byte, node.end_byte, node.type)
                if node_id in seen_nodes:
                    continue
                seen_nodes.add(node_id)
                
                try:
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        type_name = self._get_node_text(name_node)
                        source_text = self._get_node_text(node)
                        
                        bases = []
                        # Look for extends/implements
                        base_clause_node = node.child_by_field_name('base_clause') # extends
                        interfaces_clause_node = node.child_by_field_name('interfaces_clause') # implements
                        
                        if base_clause_node:
                            # Children of base_clause contain identifiers
                            for child in base_clause_node.children:
                                if child.type in ('name', 'qualified_name'):
                                    bases.append(self._get_node_text(child))

                        if interfaces_clause_node:
                            for child in interfaces_clause_node.children:
                                if child.type in ('name', 'qualified_name'):
                                    bases.append(self._get_node_text(child))

                        type_data = {
                            "name": type_name,
                            "line_number": start_line,
                            "end_line": end_line,
                            "bases": bases,
                            "path": str(path),
                            "lang": self.language_name,
                        }
                        if self.index_source:
                            type_data["source"] = source_text
                        
                        if capture_name == "class":
                            classes.append(type_data)
                        elif capture_name == "interface":
                            interfaces.append(type_data)
                        elif capture_name == "trait":
                            traits.append(type_data)
                        
                except Exception as e:
                    error_logger(f"Error parsing type in {path}: {e}")
                    continue

        return classes, interfaces, traits

    def _parse_variables(self, captures: list, source_code: str, path: Path) -> list[Dict[str, Any]]:
        variables = []
        seen_vars = set()
        
        for node, capture_name in captures:
            if capture_name == "variable":
                try:
                     var_name = self._get_node_text(node)
                     start_line = node.start_point[0] + 1
                     
                     start_byte = node.start_byte
                     if start_byte in seen_vars:
                         continue
                     seen_vars.add(start_byte)
                     
                     ctx_name, ctx_type, ctx_line = self._get_parent_context(node)

                     # Infer type from assignment
                     inferred_type = "mixed"
                     parent = node.parent
                     if parent and parent.type == 'assignment_expression':
                         # $var = new Class();
                         left = parent.child_by_field_name('left')
                         right = parent.child_by_field_name('right')
                         
                         # Ensure we are looking at the left side variable
                         if left == node and right and right.type == 'object_creation_expression':
                             # Extract class name from right side
                             for child in right.children:
                                 if child.type in ('name', 'qualified_name'):
                                     inferred_type = self._get_node_text(child)
                                     break
                                     
                     variables.append({
                        "name": var_name,
                        "type": inferred_type,
                        "line_number": start_line,
                        "path": str(path),
                        "lang": self.language_name,
                        "context": ctx_name,
                        "class_context": ctx_name if ctx_type and ("class" in ctx_type or "interface" in ctx_type or "trait" in ctx_type) else None
                     })
                except Exception as e:
                    continue

        return variables

    def _parse_imports(self, captures: list, source_code: str) -> list[dict]:
        imports = []
        
        for node, capture_name in captures:
            if capture_name == "import":
                try:
                    import_text = self._get_node_text(node)
                    # use Foo\Bar as Baz;
                    # Node usually has children: name (qualified_name), optional alias
                    
                    name_node = None
                    alias_node = None
                    
                    for child in node.children:
                        if child.type == "qualified_name" or child.type == "name":
                            name_node = child
                        # Alias in PHP: use X as Y; The 'as' is usually implicit structure or explicit?
                        # Tree sitter grammar: use_declaration -> use_clause -> (use_as_clause (qualified_name) (name))
                    
                    # Assuming simple handling for now, extracting string from text
                    # Regex might be safer given tree complexity for `use`
                    import_match = re.search(r'use\s+([\w\\]+)(?:\s+as\s+(\w+))?', import_text)
                    if import_match:
                        import_path = import_match.group(1).strip()
                        alias = import_match.group(2).strip() if import_match.group(2) else None
                        
                        import_data = {
                            "name": import_path,
                            "full_import_name": import_text,
                            "line_number": node.start_point[0] + 1,
                            "alias": alias,
                            "context": (None, None),
                            "lang": self.language_name,
                            "is_dependency": False,
                        }
                        imports.append(import_data)
                except Exception as e:
                    error_logger(f"Error parsing import: {e}")
                    continue

        return imports

    def _parse_calls(self, captures: list, source_code: str) -> list[dict]:
        calls = []
        seen_calls = set()
        
        for node, capture_name in captures:
            # For object_creation_expression without @name capture on inner node, we catch the whole node as @call_node
            # But the 'calls' query uses @name for function/method calls on the identifier, and @call_node for full expression.
            # My query change: (object_creation_expression) @call_node
            # This means for obj creation, I won't get a separate @name capture. I need to iterate @call_node captures too?
            # actually execute_query returns (node, capture_name).
            
            # Let's handle 'name' capture which gives us the function name
            if capture_name == "name":
                try:
                    call_name = self._get_node_text(node)
                    line_number = node.start_point[0] + 1
                    
                    # Ensure we identify the full call node
                    call_node = node.parent
                    while call_node and call_node.type not in ("function_call_expression", "member_call_expression", "scoped_call_expression"):
                        call_node = call_node.parent
                    
                    if not call_node:
                         continue # It might be a name inside object creation or something we handle otherwise

                    # Avoid duplicates
                    call_key = f"{call_name}_{line_number}"
                    if call_key in seen_calls:
                        continue
                    seen_calls.add(call_key)
                    
                    # Extract arguments
                    args = []
                    args_node = call_node.child_by_field_name('arguments')
                    if args_node:
                        for arg in args_node.children:
                            if arg.type not in ('(', ')', ','):
                                args.append(self._get_node_text(arg))

                    full_name = call_name # Default
                    if call_node.type == 'member_call_expression':
                        # $obj->method()
                        obj_node = call_node.child_by_field_name('object')
                        if obj_node:
                             receiver = self._get_node_text(obj_node)
                             # Normalize -> to . for graph builder compatibility
                             full_name = f"{receiver}.{call_name}"
                    elif call_node.type == 'scoped_call_expression':
                         # Class::method()
                        scope_node = call_node.child_by_field_name('scope')
                        if scope_node:
                            receiver = self._get_node_text(scope_node)
                            # Normalize :: to . for graph builder compatibility
                            full_name = f"{receiver}.{call_name}"

                    ctx_name, ctx_type, ctx_line = self._get_parent_context(node)
                    
                    call_data = {
                        "name": call_name,
                        "full_name": full_name,
                        "line_number": line_number,
                        "args": args,
                        "inferred_obj_type": None,
                        "context": (ctx_name, ctx_type, ctx_line),
                        "class_context": (ctx_name, ctx_line) if ctx_type and ("class" in ctx_type or "interface" in ctx_type or "trait" in ctx_type) else (None, None),
                        "lang": self.language_name,
                        "is_dependency": False,
                    }
                    calls.append(call_data)
                except Exception as e:
                    error_logger(f"Error parsing call: {e}")
                    continue

            # Handle object creation separately as capture is on the whole node
            elif capture_name == "call_node" and node.type == "object_creation_expression":
                 try:
                    line_number = node.start_point[0] + 1
                    
                    # Find class name (child not named 'arguments')
                    class_name = "Unknown"
                    for child in node.children:
                        if child.type in ('name', 'qualified_name'):
                            class_name = self._get_node_text(child)
                            break
                        if child.type == "variable_name": # dynamic new $class()
                             class_name = self._get_node_text(child)
                             break
                    
                    call_key = f"new {class_name}_{line_number}"
                    if call_key in seen_calls:
                        continue
                    seen_calls.add(call_key)

                    args = []
                    args_node = node.child_by_field_name('arguments')
                    if args_node:
                         for arg in args_node.children:
                            if arg.type not in ('(', ')', ','):
                                args.append(self._get_node_text(arg))
                    
                    full_name = class_name # For GraphBuilder to link to Class
                    
                    ctx_name, ctx_type, ctx_line = self._get_parent_context(node)
                    
                    call_data = {
                        "name": class_name,
                        "full_name": full_name, # Usually we want the class name here so GB can link to Class node
                        "line_number": line_number,
                        "args": args,
                        "inferred_obj_type": None,
                        "context": (ctx_name, ctx_type, ctx_line),
                        "class_context": (ctx_name, ctx_line) if ctx_type and ("class" in ctx_type or "interface" in ctx_type or "trait" in ctx_type) else (None, None),
                        "lang": self.language_name,
                        "is_dependency": False,
                    }
                    calls.append(call_data)
                 except Exception:
                     continue

        return calls

def pre_scan_php(files: list[Path], parser_wrapper) -> dict:
    name_to_files = {}
    return name_to_files
