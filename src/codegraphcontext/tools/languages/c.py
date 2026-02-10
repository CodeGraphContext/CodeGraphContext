from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from codegraphcontext.utils.debug_log import debug_log, info_logger, error_logger, warning_logger
from codegraphcontext.utils.tree_sitter_manager import execute_query

C_QUERIES = {
    "functions": """
        (function_definition
            declarator: (function_declarator
                declarator: (identifier) @name
            )
        ) @function_node
        
        (function_definition
            declarator: (function_declarator
                declarator: (pointer_declarator
                    declarator: (identifier) @name
                )
            )
        ) @function_node
    """,
    "structs": """
        (struct_specifier
            name: (type_identifier) @name
        ) @struct
    """,
    "unions": """
        (union_specifier
            name: (type_identifier) @name
        ) @union
    """,
    "enums": """
        (enum_specifier
            name: (type_identifier) @name
        ) @enum
    """,
    "typedefs": """
        (type_definition
            declarator: (type_identifier) @name
        ) @typedef
    """,
    "imports": """
        (preproc_include
            path: [
                (string_literal) @path
                (system_lib_string) @path
            ]
        ) @import
    """,
    "calls": """
        (call_expression
            function: (identifier) @name
        )
    """,
    "variables": """
        (declaration
            declarator: (init_declarator
                declarator: (identifier) @name
            )
        )
        
        (declaration
            declarator: (init_declarator
                declarator: (pointer_declarator
                    declarator: (identifier) @name
                )
            )
        )
        
        (declaration
            declarator: (identifier) @name
        )
        
        (declaration
            declarator: (pointer_declarator
                declarator: (identifier) @name
            )
        )
    """,
    "macros": """
        (preproc_def
            name: (identifier) @name
        ) @macro
    """,
}

class CTreeSitterParser:
    """A C-specific parser using tree-sitter."""

    def __init__(self, generic_parser_wrapper: Any):
        self.generic_parser_wrapper = generic_parser_wrapper
        self.language_name = "c"
        self.language = generic_parser_wrapper.language
        self.parser = generic_parser_wrapper.parser

    def _get_node_text(self, node: Any) -> str:
        return node.text.decode("utf-8")

    def parse(self, path: Path, is_dependency: bool = False, index_source: bool = False) -> Dict[str, Any]:
        """Parses a C file and returns its structure."""
        self.index_source = index_source
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            source_code = f.read()

        tree = self.parser.parse(bytes(source_code, "utf8"))
        root_node = tree.root_node

        functions = self._find_functions(root_node)
        classes = self._find_structs_unions_enums(root_node)
        imports = self._find_imports(root_node)
        function_calls = self._find_calls(root_node)
        variables = self._find_variables(root_node)
        macros = self._find_macros(root_node)

        return {
            "path": str(path),
            "functions": functions,
            "classes": classes,
            "variables": variables,
            "imports": imports,
            "function_calls": function_calls,
            "macros": macros,
            "is_dependency": is_dependency,
            "lang": self.language_name,
        }

    def _get_parent_context(self, node: Any, types: tuple = ('function_definition', 'struct_specifier', 'union_specifier', 'enum_specifier')) -> tuple:
        """Get parent context for nested constructs."""
        curr = node.parent
        while curr:
            if curr.type in types:
                if curr.type == 'function_definition':
                    # Traverse declarator to find name and use its line number
                    decl = curr.child_by_field_name('declarator')
                    while decl:
                        if decl.type == 'identifier':
                             return self._get_node_text(decl), curr.type, decl.start_point[0] + 1
                        
                        # Handle recursive declarators (function, pointer, array, parenthesized)
                        child = decl.child_by_field_name('declarator')
                        if child:
                            decl = child
                        else:
                            # Fallback if structure is different
                            break
                else:
                    name_node = curr.child_by_field_name('name')
                    if name_node:
                        return self._get_node_text(name_node), curr.type, name_node.start_point[0] + 1
            curr = curr.parent
        return None, None, None

    def _calculate_complexity(self, node: Any) -> int:
        """Calculate cyclomatic complexity for C functions."""
        complexity_nodes = {
            "if_statement", "for_statement", "while_statement", "do_statement",
            "switch_statement", "case_statement", "conditional_expression",
            "logical_expression", "binary_expression", "goto_statement"
        }
        count = 1
        
        def traverse(n):
            nonlocal count
            if n.type in complexity_nodes:
                count += 1
            for child in n.children:
                traverse(child)
        
        traverse(node)
        return count

    def _get_docstring(self, node: Any) -> Optional[str]:
        """Extract comments as documentation."""
        # Look for comments before the node
        if node.parent:
            for child in node.parent.children:
                if child.type == 'comment' and child.start_point[0] < node.start_point[0]:
                    return self._get_node_text(child)
        return None

    def _parse_function_args(self, params_node: Any) -> list[Dict[str, Any]]:
        """Enhanced helper to parse function arguments from a (parameter_list) node."""
        args = []
        if not params_node:
            return args
            
        for param in params_node.named_children:
            if param.type == "parameter_declaration":
                arg_info: Dict[str, Any] = {"name": "", "type": None, "is_pointer": False, "is_array": False}
                
                # Find the declarator (variable name)
                declarator = param.child_by_field_name("declarator")
                if declarator:
                    if declarator.type == "identifier":
                        arg_info["name"] = self._get_node_text(declarator)
                    elif declarator.type == "pointer_declarator":
                        arg_info["is_pointer"] = True
                        inner_declarator = declarator.child_by_field_name("declarator")
                        if inner_declarator and inner_declarator.type == "identifier":
                            arg_info["name"] = self._get_node_text(inner_declarator)
                    elif declarator.type == "array_declarator":
                        arg_info["is_array"] = True
                        inner_declarator = declarator.child_by_field_name("declarator")
                        if inner_declarator and inner_declarator.type == "identifier":
                            arg_info["name"] = self._get_node_text(inner_declarator)
                
                # Find the type
                type_node = param.child_by_field_name("type")
                if type_node:
                    arg_info["type"] = self._get_node_text(type_node)
                
                # Handle variadic arguments
                if param.type == "variadic_parameter":
                    arg_info["name"] = "..."
                    arg_info["type"] = "variadic"
                
                args.append(arg_info)
        return args

    def _find_functions(self, root_node: Any) -> list[Dict[str, Any]]:
        functions = []
        query_str = C_QUERIES["functions"]
        for match in execute_query(self.language, query_str, root_node):
            capture_name = match[1]
            node = match[0]
            if capture_name == 'name':
                func_node = node.parent.parent.parent
                name = self._get_node_text(node)
                
                # Find parameters
                params_node = None
                body_node = None
                for child in func_node.children:
                    if child.type == "function_declarator":
                        params_node = child.child_by_field_name("parameters")
                    elif child.type == "compound_statement":
                        body_node = child
                
                args = self._parse_function_args(params_node) if params_node else []
                context, context_type, _ = self._get_parent_context(func_node)

                func_data = {
                    "name": name,
                    "line_number": node.start_point[0] + 1,
                    "end_line": func_node.end_point[0] + 1,
                    "args": [arg["name"] for arg in args if arg["name"]],  # Simplified args for compatibility
                    "docstring": self._get_docstring(func_node),
                    "cyclomatic_complexity": self._calculate_complexity(func_node),
                    "context": context,
                    "context_type": context_type,
                    "class_context": None,
                    "decorators": [],
                    "lang": self.language_name,
                    "is_dependency": False,
                    "detailed_args": args,  # Keep detailed args for future use
                }

                if self.index_source:
                    func_data["source"] = self._get_node_text(func_node)
                
                functions.append(func_data)
        return functions

    def _find_structs_unions_enums(self, root_node: Any) -> list[Dict[str, Any]]:
        """Find structs, unions, and enums (treated as classes in C)."""
        classes = []
        
        # Find structs
        query_str = C_QUERIES["structs"]
        for match in execute_query(self.language, query_str, root_node):
            capture_name = match[1]
            node = match[0]
            if capture_name == 'name':
                struct_node = node.parent
                name = self._get_node_text(node)
                context, context_type, _ = self._get_parent_context(struct_node)
                
                struct_data = {
                    "name": name,
                    "line_number": node.start_point[0] + 1,
                    "end_line": struct_node.end_point[0] + 1,
                    "bases": [],  # C doesn't have inheritance
                    "docstring": self._get_docstring(struct_node),
                    "context": context,
                    "decorators": [],
                    "lang": self.language_name,
                    "is_dependency": False,
                    "type": "struct",
                }

                if self.index_source:
                    struct_data["source"] = self._get_node_text(struct_node)
                
                classes.append(struct_data)

        # Find unions
        query_str = C_QUERIES["unions"]
        for match in execute_query(self.language, query_str, root_node):
            capture_name = match[1]
            node = match[0]
            if capture_name == 'name':
                union_node = node.parent
                name = self._get_node_text(node)
                context, context_type, _ = self._get_parent_context(union_node)
                
                union_data = {
                    "name": name,
                    "line_number": node.start_point[0] + 1,
                    "end_line": union_node.end_point[0] + 1,
                    "bases": [],
                    "docstring": self._get_docstring(union_node),
                    "context": context,
                    "decorators": [],
                    "lang": self.language_name,
                    "is_dependency": False,
                    "type": "union",
                }

                if self.index_source:
                    union_data["source"] = self._get_node_text(union_node)
                
                classes.append(union_data)

        # Find enums
        query_str = C_QUERIES["enums"]
        for match in execute_query(self.language, query_str, root_node):
            capture_name = match[1]
            node = match[0]
            if capture_name == 'name':
                enum_node = node.parent
                name = self._get_node_text(node)
                context, context_type, _ = self._get_parent_context(enum_node)
                
                enum_data = {
                    "name": name,
                    "line_number": node.start_point[0] + 1,
                    "end_line": enum_node.end_point[0] + 1,
                    "bases": [],
                    "docstring": self._get_docstring(enum_node),
                    "context": context,
                    "decorators": [],
                    "lang": self.language_name,
                    "is_dependency": False,
                    "type": "enum",
                }

                if self.index_source:
                    enum_data["source"] = self._get_node_text(enum_node)
                
                classes.append(enum_data)

        return classes

    def _find_imports(self, root_node: Any) -> list[Dict[str, Any]]:
        imports = []
        query_str = C_QUERIES["imports"]
        for match in execute_query(self.language, query_str, root_node):
            capture_name = match[1]
            node = match[0]
            if capture_name == 'path':
                path = self._get_node_text(node).strip('"<>')
                context, context_type, _ = self._get_parent_context(node)
                
                imports.append({
                    "name": path,
                    "full_import_name": path,
                    "line_number": node.start_point[0] + 1,
                    "alias": None,
                    "context": context,
                    "lang": self.language_name,
                    "is_dependency": False,
                })
        return imports

    def _find_calls(self, root_node: Any) -> list[Dict[str, Any]]:
        """Enhanced function call detection."""
        calls = []
        query_str = C_QUERIES["calls"]
        for match in execute_query(self.language, query_str, root_node):
            capture_name = match[1]
            node = match[0]
            if capture_name == "name":
                call_node = node.parent if node.parent.type == "call_expression" else node.parent.parent
                call_name = self._get_node_text(node)
                
                # Extract arguments
                args = []
                args_node = call_node.child_by_field_name("arguments")
                if args_node:
                    for child in args_node.children:
                        if child.type not in ['(', ')', ',']:
                            args.append(self._get_node_text(child))
                
                context_name, context_type, context_line = self._get_parent_context(call_node)
                
                # print(f"DEBUG_C_PARSER: Call {call_name} context: {context_name}, {context_type}, {context_line}")

                calls.append({
                    "name": call_name,
                    "full_name": call_name,  # For C, function name is the same as full name
                    "line_number": node.start_point[0] + 1,
                    "args": args,
                    "inferred_obj_type": None,
                    "context": (context_name, context_type, context_line),
                    "class_context": None,
                    "lang": self.language_name,
                    "is_dependency": False,
                })
        return calls

    def _find_variables(self, root_node: Any) -> list[Dict[str, Any]]:
        """Enhanced variable declaration detection."""
        variables = []
        query_str = C_QUERIES["variables"]
        for match in execute_query(self.language, query_str, root_node):
            capture_name = match[1]
            node = match[0]
            if capture_name == "name":
                var_name = self._get_node_text(node)
                
                # Find the declaration node
                decl_node = node.parent
                while decl_node and decl_node.type != "declaration":
                    decl_node = decl_node.parent
                
                # Extract type information
                var_type = None
                is_pointer = False
                is_array = False
                value = None
                
                if decl_node:
                    # Find type
                    for child in decl_node.children:
                        if child.type in ["primitive_type", "type_identifier", "sized_type_specifier"]:
                            var_type = self._get_node_text(child)
                        elif child.type == "init_declarator":
                            # Check for pointer/array
                            if child.child_by_field_name("declarator"):
                                declarator = child.child_by_field_name("declarator")
                                if declarator.type == "pointer_declarator":
                                    is_pointer = True
                                elif declarator.type == "array_declarator":
                                    is_array = True
                            
                            # Check for initial value
                            if child.child_by_field_name("value"):
                                value = self._get_node_text(child.child_by_field_name("value"))
                
                context, context_type, _ = self._get_parent_context(node)
                class_context, _, _ = self._get_parent_context(node, types=('struct_specifier', 'union_specifier', 'enum_specifier'))
                
                variables.append({
                    "name": var_name,
                    "line_number": node.start_point[0] + 1,
                    "value": value,
                    "type": var_type,
                    "context": context,
                    "class_context": class_context,
                    "lang": self.language_name,
                    "is_dependency": False,
                    "is_pointer": is_pointer,
                    "is_array": is_array,
                })
        return variables

    def _find_macros(self, root_node: Any) -> list[Dict[str, Any]]:
        """Enhanced preprocessor macro detection."""
        macros = []
        query_str = C_QUERIES["macros"]
        for match in execute_query(self.language, query_str, root_node):
            capture_name = match[1]
            node = match[0]
            if capture_name == 'name':
                macro_node = node.parent
                name = self._get_node_text(node)
                
                # Extract macro value
                value = None
                if macro_node.child_by_field_name("value"):
                    value = self._get_node_text(macro_node.child_by_field_name("value"))
                
                # Extract parameters for function-like macros
                params = []
                if macro_node.child_by_field_name("parameters"):
                    params_node = macro_node.child_by_field_name("parameters")
                    for child in params_node.children:
                        if child.type == "identifier":
                            params.append(self._get_node_text(child))
                
                context, context_type, _ = self._get_parent_context(macro_node)
                
                macro_data = {
                    "name": name,
                    "line_number": node.start_point[0] + 1,
                    "end_line": macro_node.end_point[0] + 1,
                    "value": value,
                    "params": params,
                    "context": context,
                    "lang": self.language_name,
                    "is_dependency": False,
                }

                if self.index_source:
                    macro_data["source"] = self._get_node_text(macro_node)
                
                macros.append(macro_data)
        return macros


def pre_scan_c(files: list[Path], parser_wrapper) -> dict:
    """Scans C files to create a map of function/struct/union/enum names to their file paths."""
    imports_map = {}
    query_str = """
        (function_definition
            declarator: (function_declarator
                declarator: (identifier) @name
            )
        )
        
        (function_definition
            declarator: (function_declarator
                declarator: (pointer_declarator
                    declarator: (identifier) @name
                )
            )
        )
        
        (struct_specifier
            name: (type_identifier) @name
        )
        
        (union_specifier
            name: (type_identifier) @name
        )
        
        (enum_specifier
            name: (type_identifier) @name
        )
        
        (type_definition
            declarator: (type_identifier) @name
        )
        
        (preproc_def
            name: (identifier) @name
        )
    """
    
    
    for path in files:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                tree = parser_wrapper.parser.parse(bytes(f.read(), "utf8"))
            
            for capture, _ in execute_query(parser_wrapper.language, query_str, tree.root_node):
                name = capture.text.decode('utf-8')
                if name not in imports_map:
                    imports_map[name] = []
                imports_map[name].append(str(path.resolve()))
        except Exception as e:
            warning_logger(f"Tree-sitter pre-scan failed for {path}: {e}")
    return imports_map
