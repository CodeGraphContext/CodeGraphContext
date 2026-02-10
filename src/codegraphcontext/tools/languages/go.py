from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from codegraphcontext.utils.debug_log import debug_log, info_logger, error_logger, warning_logger
from codegraphcontext.utils.tree_sitter_manager import execute_query


GO_QUERIES = {
    "functions": """
        (function_declaration
            name: (identifier) @name
            parameters: (parameter_list) @params
        ) @function_node
        
        (method_declaration
            receiver: (parameter_list) @receiver
            name: (field_identifier) @name
            parameters: (parameter_list) @params
        ) @function_node
    """,
    "structs": """
        (type_declaration
            (type_spec
                name: (type_identifier) @name
                type: (struct_type) @struct_body
            )
        ) @struct_node
    """,
    "interfaces": """
        (type_declaration
            (type_spec
                name: (type_identifier) @name
                type: (interface_type) @interface_body
            )
        ) @interface_node
    """,
    "imports": """
        (import_declaration
            (import_spec
                path: (interpreted_string_literal) @path
            )
        ) @import
        
        (import_declaration
            (import_spec
                name: (package_identifier) @alias
                path: (interpreted_string_literal) @path
            )
        ) @import_alias
    """,
    "calls": """
        (call_expression
            function: (identifier) @name
        )
        (call_expression
            function: (selector_expression
                field: (field_identifier) @name
            )
        )
    """,
    "variables": """
        (var_declaration
            (var_spec
                name: (identifier) @name
            )
        )
        (short_var_declaration
            left: (expression_list
                (identifier) @name
            )
        )
    """,
}

class GoTreeSitterParser:
    """A Go-specific parser using tree-sitter, encapsulating language-specific logic."""

    def __init__(self, generic_parser_wrapper):
        self.generic_parser_wrapper = generic_parser_wrapper
        self.language_name = generic_parser_wrapper.language_name
        self.language = generic_parser_wrapper.language
        self.parser = generic_parser_wrapper.parser

    def _get_node_text(self, node) -> str:
        return node.text.decode('utf-8')

    def _get_parent_context(self, node, types=('function_declaration', 'method_declaration', 'type_declaration')):
        curr = node.parent
        while curr:
            if curr.type in types:
                if curr.type == 'type_declaration':
                    type_spec = curr.child_by_field_name('type_spec')
                    if type_spec:
                        name_node = type_spec.child_by_field_name('name')
                        return self._get_node_text(name_node) if name_node else None, curr.type, curr.start_point[0] + 1
                else:
                    name_node = curr.child_by_field_name('name')
                    return self._get_node_text(name_node) if name_node else None, curr.type, curr.start_point[0] + 1
            curr = curr.parent
        return None, None, None

    def _calculate_complexity(self, node):
        complexity_nodes = {
            "if_statement", "for_statement", "switch_statement", "case_clause",
            "expression_switch_statement", "type_switch_statement",
            "binary_expression", "call_expression"
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

    def _get_docstring(self, func_node):
        """Extract Go doc comment preceding the function."""
        prev_sibling = func_node.prev_sibling
        while prev_sibling and prev_sibling.type in ('comment', '\n', ' '):
            if prev_sibling.type == 'comment':
                comment_text = self._get_node_text(prev_sibling)
                if comment_text.startswith('//'):
                    return comment_text.strip()
            prev_sibling = prev_sibling.prev_sibling
        return None

    def parse(self, path: Path, is_dependency: bool = False, index_source: bool = False) -> Dict:
        """Parses a file and returns its structure in a standardized dictionary format."""
        # This method orchestrates the parsing of a single file.
        # It calls specialized `_find_*` methods for each language construct.
        # The returned dictionary should map a specific key (e.g., 'functions', 'interfaces')
        # to a list of dictionaries, where each dictionary represents a single code construct.
        # The GraphBuilder will then use these keys to create nodes with corresponding labels.
        self.index_source = index_source
        with open(path, "r", encoding="utf-8") as f:
            source_code = f.read()

        tree = self.parser.parse(bytes(source_code, "utf8"))
        root_node = tree.root_node

        functions = self._find_functions(root_node)
        structs = self._find_structs(root_node)
        interfaces = self._find_interfaces(root_node)
        imports = self._find_imports(root_node)
        function_calls = self._find_calls(root_node)
        variables = self._find_variables(root_node)

        return {
            "path": str(path),
            "functions": functions,
            "classes": structs,
            "interfaces": interfaces,
            "variables": variables,
            "imports": imports,
            "function_calls": function_calls,
            "is_dependency": is_dependency,
            "lang": self.language_name,
        }

    def _find_functions(self, root_node):
        functions = []
        query_str = GO_QUERIES['functions']

        captures_by_function = {}

        for node, capture_name in execute_query(self.language, query_str, root_node):
            if capture_name == 'function_node':
                func_id = node.id
                if func_id not in captures_by_function:
                    captures_by_function[func_id] = {
                        'node': node,
                        'name': None,
                        'params': None,
                        'receiver': None
                    }
            elif capture_name == 'name':
                func_node = self._find_function_node_for_name(node)
                if func_node:
                    func_id = func_node.id
                    if func_id not in captures_by_function:
                        captures_by_function[func_id] = {
                            'node': func_node,
                            'name': None,
                            'params': None,
                            'receiver': None
                        }
                    captures_by_function[func_id]['name'] = self._get_node_text(node)
            elif capture_name == 'params':
                func_node = self._find_function_node_for_params(node)
                if func_node:
                    func_id = func_node.id
                    if func_id not in captures_by_function:
                        captures_by_function[func_id] = {
                            'node': func_node,
                            'name': None,
                            'params': None,
                            'receiver': None
                        }
                    captures_by_function[func_id]['params'] = node
            elif capture_name == 'receiver':
                func_node = node.parent
                if func_node and func_node.type == 'method_declaration':
                    func_id = func_node.id
                    if func_id not in captures_by_function:
                        captures_by_function[func_id] = {
                            'node': func_node,
                            'name': None,
                            'params': None,
                            'receiver': None
                        }
                    captures_by_function[func_id]['receiver'] = node

        for func_id, data in captures_by_function.items():
            if data['name']:
                func_node = data['node']
                name = data['name']

                args = []
                if data['params']:
                    args = self._extract_parameters(data['params'])

                receiver_type = None
                if data['receiver']:
                    receiver_type = self._extract_receiver(data['receiver'])

                context, context_type, context_line = self._get_parent_context(func_node)
                class_context = receiver_type or (context if context_type == 'type_declaration' else None)

                docstring = self._get_docstring(func_node)

                func_data = {
                    "name": name,
                    "line_number": func_node.start_point[0] + 1,
                    "end_line": func_node.end_point[0] + 1,
                    "args": args,
                    "class_context": class_context,
                    "decorators": [],
                    "lang": self.language_name,
                    "is_dependency": False,
                }
                
                if self.index_source:
                    func_data["source"] = self._get_node_text(func_node)
                    func_data["docstring"] = docstring
                    
                functions.append(func_data)

        return functions

    def _find_function_node_for_name(self, name_node):
        current = name_node.parent
        while current:
            if current.type in ('function_declaration', 'method_declaration'):
                return current
            current = current.parent
        return None

    def _find_function_node_for_params(self, params_node):
        current = params_node.parent
        while current:
            if current.type in ('function_declaration', 'method_declaration'):
                return current
            current = current.parent
        return None

    def _extract_parameters(self, params_node):
        params = []
        if params_node.type == 'parameter_list':
            for child in params_node.children:
                if child.type == 'parameter_declaration':
                    # Handle multiple names for same type: func(x, y int)
                    # We iterate children and find all identifiers that are not the type node.
                    type_node = child.child_by_field_name('type')
                    for grandchild in child.children:
                        if grandchild.type == 'identifier':
                            if grandchild.id != (type_node.id if type_node else None):
                                params.append(self._get_node_text(grandchild))
                elif child.type == 'variadic_parameter_declaration':
                    name_node = child.child_by_field_name('name')
                    if name_node:
                        params.append(f"...{self._get_node_text(name_node)}")
        return params

    def _extract_receiver(self, receiver_node):
        if receiver_node.type == 'parameter_list' and receiver_node.named_child_count > 0:
            param = receiver_node.named_child(0)
            type_node = param.child_by_field_name('type')
            if type_node:
                type_text = self._get_node_text(type_node)
                return type_text.strip('*')
        return None

    def _find_structs(self, root_node):
        structs = []
        struct_query_str = GO_QUERIES['structs']
        for node, capture_name in execute_query(self.language, struct_query_str, root_node):
            if capture_name == 'name':
                struct_node = self._find_type_declaration_for_name(node)
                if struct_node:
                    name = self._get_node_text(node)
                    class_data = {
                        "name": name,
                        "line_number": struct_node.start_point[0] + 1,
                        "end_line": struct_node.end_point[0] + 1,
                        "bases": [],
                        "decorators": [],
                        "lang": self.language_name,
                        "is_dependency": False,
                    }
                    if self.index_source:
                        class_data["source"] = self._get_node_text(struct_node)
                        class_data["docstring"] = self._get_docstring(struct_node)

                    structs.append(class_data)
        return structs

    def _find_interfaces(self, root_node):
        interfaces = []
        interface_query_str = GO_QUERIES['interfaces']
        for node, capture_name in execute_query(self.language, interface_query_str, root_node):
            if capture_name == 'name':
                interface_node = self._find_type_declaration_for_name(node)
                if interface_node:
                    name = self._get_node_text(node)
                    class_data = {
                        "name": name,
                        "line_number": interface_node.start_point[0] + 1,
                        "end_line": interface_node.end_point[0] + 1,
                        "bases": [],
                        "decorators": [],
                        "lang": self.language_name,
                        "is_dependency": False,
                    }
                    if self.index_source:
                        class_data["source"] = self._get_node_text(interface_node)
                        class_data["docstring"] = self._get_docstring(interface_node)
                        
                    interfaces.append(class_data)
        return interfaces

    def _find_type_declaration_for_name(self, name_node):
        current = name_node.parent
        while current:
            if current.type == 'type_declaration':
                return current
            current = current.parent
        return None

    def _find_imports(self, root_node):
        imports = []
        query_str = GO_QUERIES['imports']
        
        for node, capture_name in execute_query(self.language, query_str, root_node):
            line_number = node.start_point[0] + 1
            
            if capture_name == 'path':
                path_text = self._get_node_text(node).strip('"')
                package_name = path_text.split('/')[-1]
                
                alias = None
                import_spec = node.parent
                if import_spec and import_spec.type == 'import_spec':
                    alias_node = import_spec.child_by_field_name('name')
                    if alias_node:
                        alias = self._get_node_text(alias_node)
                
                imports.append({
                    'name': package_name,
                    'source': path_text,
                    'alias': alias,
                    'line_number': line_number,
                    'lang': self.language_name
                })

        return imports

    def _find_calls(self, root_node):
        calls = []
        query_str = GO_QUERIES['calls']
        
        seen_calls = set()

        for node, capture_name in execute_query(self.language, query_str, root_node):
            if capture_name == 'name':
                call_node = node.parent
                while call_node and call_node.type != 'call_expression':
                    call_node = call_node.parent
                
                if call_node:
                    name = self._get_node_text(node)
                    line_number = node.start_point[0] + 1
                    
                    call_key = f"{name}_{line_number}"
                    if call_key in seen_calls:
                        continue
                    seen_calls.add(call_key)
                    
                    full_name = self._get_node_text(call_node.child_by_field_name('function')) if call_node.child_by_field_name('function') else name
                    
                    # Resolve context
                    context_name, context_type, context_line = self._get_parent_context(node)
                    
                    # In Go, methods are defined on types (structs/interfaces). If we are in a method, the context is the method name.
                    # Ideally we might want the receiver type as "class_context", but this requires more complex AST traversal up to the method declaration's receiver.
                    # For now, we reuse the context resolution logic.
                    class_context = None 
                    
                    call_data = {
                        "name": name,
                        "full_name": full_name,
                        "line_number": line_number,
                        "args": [],
                        "inferred_obj_type": None,
                        "context": (context_name, context_type, context_line),
                        "class_context": class_context,
                        "lang": self.language_name,
                        "is_dependency": False,
                    }
                    calls.append(call_data)
        
        return calls

    def _find_variables(self, root_node):
        variables = []
        query_str = GO_QUERIES['variables']
        
        for node, capture_name in execute_query(self.language, query_str, root_node):
            if capture_name == 'name':
                name = self._get_node_text(node)
                
                variable_data = {
                    "name": name,
                    "line_number": node.start_point[0] + 1,
                    "value": None,
                    "type": None,
                    "context": None,
                    "class_context": None,
                    "lang": self.language_name,
                    "is_dependency": False,
                }
                variables.append(variable_data)
        
        return variables

def pre_scan_go(files: list[Path], parser_wrapper) -> dict:
    """Scans Go files to create a map of function/struct names to their file paths."""
    imports_map = {}
    query_str = """
        (function_declaration name: (identifier) @name)
        (method_declaration name: (field_identifier) @name)
        (type_declaration (type_spec name: (type_identifier) @name))
    """
    

    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                tree = parser_wrapper.parser.parse(bytes(f.read(), "utf8"))

            for capture, _ in execute_query(parser_wrapper.language, query_str, tree.root_node):
                name = capture.text.decode('utf-8')
                if name not in imports_map:
                    imports_map[name] = []
                imports_map[name].append(str(path.resolve()))
        except Exception as e:
            warning_logger(f"Tree-sitter pre-scan failed for {path}: {e}")
    
    return imports_map