from pathlib import Path
from typing import Dict
from codegraphcontext.utils.debug_log import debug_log, info_logger, error_logger, warning_logger, debug_logger
from codegraphcontext.utils.tree_sitter_manager import execute_query
# NOTE:
# .d.ts files only contain declaration-level information.
# We intentionally index only interfaces, type aliases, enums,
# and function signatures, and skip all runtime-specific constructs.


TS_QUERIES = {
    "functions": """
        (function_declaration
            name: (identifier) @name
            parameters: (formal_parameters) @params
        ) @function_node

        (variable_declarator
            name: (identifier) @name
            value: (function_expression
                parameters: (formal_parameters) @params
            ) @function_node
        )

        (variable_declarator
            name: (identifier) @name
            value: (arrow_function
                parameters: (formal_parameters) @params
            ) @function_node
        )

        (variable_declarator
            name: (identifier) @name
            value: (arrow_function
                parameter: (identifier) @single_param
            ) @function_node
        )

        (method_definition
            name: (property_identifier) @name
            parameters: (formal_parameters) @params
        ) @function_node

        (assignment_expression
            left: (member_expression
                property: (property_identifier) @name
            )
            right: (function_expression
                parameters: (formal_parameters) @params
            ) @function_node
        )

        (assignment_expression
            left: (member_expression
                property: (property_identifier) @name
            )
            right: (arrow_function
                parameters: (formal_parameters) @params
            ) @function_node
        )
    """,
    "classes": """
        (class_declaration) @class
        (abstract_class_declaration) @class
        (class) @class
    """,
    "interfaces": """
        (interface_declaration
            name: (type_identifier) @name
        ) @interface_node
    """,
    "type_aliases": """
        (type_alias_declaration
            name: (type_identifier) @name
        ) @type_alias_node
    """,
    "imports": """
        (import_statement) @import
        (call_expression
            function: (identifier) @require_call (#eq? @require_call "require")
        ) @import
    """,
    "calls": """
        (call_expression function: (identifier) @name)
        (call_expression function: (member_expression property: (property_identifier) @name))
        (new_expression constructor: (identifier) @name)
        (new_expression constructor: (member_expression property: (property_identifier) @name))
    """,
    "variables": """
        (variable_declarator name: (identifier) @name)
    """,
    "docstrings": """
        (comment) @docstring_comment
    """,
}

def is_typescript_file(file_path: Path) -> bool:
    return file_path.suffix in {".ts", ".tsx"}

class TypescriptTreeSitterParser:
    """A TypeScript-specific parser using tree-sitter, encapsulating language-specific logic."""

    def __init__(self, generic_parser_wrapper):
        self.generic_parser_wrapper = generic_parser_wrapper
        self.language_name = generic_parser_wrapper.language_name
        self.language = generic_parser_wrapper.language
        self.parser = generic_parser_wrapper.parser

    def _get_node_text(self, node) -> str:
        return node.text.decode('utf-8')

    def _get_parent_context(self, node, types=('function_declaration', 'class_declaration', 'method_definition', 'function_expression', 'arrow_function')):
        curr = node.parent
        while curr:
            if curr.type in types:
                name_node = curr.child_by_field_name('name')
                if not name_node and curr.type in ('function_expression', 'arrow_function'):
                    # Try to find name from variable declaration
                    if curr.parent and curr.parent.type == 'variable_declarator':
                        name_node = curr.parent.child_by_field_name('name')
                    elif curr.parent and curr.parent.type == 'assignment_expression':
                        name_node = curr.parent.child_by_field_name('left')
                    elif curr.parent and curr.parent.type == 'pair': # property: function
                        name_node = curr.parent.child_by_field_name('key')

                return self._get_node_text(name_node) if name_node else None, curr.type, curr.start_point[0] + 1
            curr = curr.parent
        return None, None, None

    def _calculate_complexity(self, node):
        complexity_nodes = {
            "if_statement", "for_statement", "while_statement", "do_statement",
            "switch_statement", "case_statement", "conditional_expression",
            "logical_expression", "binary_expression", "catch_clause"
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

    def _get_docstring(self, body_node):
        return None
    
    def parse(self, file_path: Path, is_dependency: bool = False) -> Dict:
        is_dts = str(file_path).endswith(".d.ts")
        with open(file_path, "r", encoding="utf-8") as f:
            source_code = f.read()
        tree = self.parser.parse(bytes(source_code, "utf8"))
        root_node = tree.root_node
        functions = [] if is_dts else self._find_functions(root_node)
        classes = self._find_classes(root_node)
        interfaces = self._find_interfaces(root_node)
        type_aliases = self._find_type_aliases(root_node)
        imports = self._find_imports(root_node)
        function_calls = [] if is_dts else self._find_calls(root_node)
        variables = [] if is_dts else self._find_variables(root_node)

        return {
            "file_path": str(file_path),
            "functions": functions,
            "classes": classes,
            "interfaces": interfaces,
            "type_aliases": type_aliases,
            "variables": variables,
            "imports": imports,
            "function_calls": function_calls,
            "is_dependency": is_dependency,
            "lang": self.language_name,
        }


    def _find_functions(self, root_node):
        functions = []
        query_str = TS_QUERIES['functions']
        def _fn_for_name(name_node):
            current = name_node.parent
            while current:
                if current.type in ('function_declaration', 'function', 'arrow_function', 'method_definition'):
                    return current
                elif current.type in ('variable_declarator', 'assignment_expression'):
                    for child in current.children:
                        if child.type in ('function', 'arrow_function'):
                            return child
                current = current.parent
            return None
        def _fn_for_params(params_node):
            current = params_node.parent
            while current:
                if current.type in ('function_declaration', 'function', 'arrow_function', 'method_definition'):
                    return current
                current = current.parent
            return None
        def _key(n):
            return (n.start_byte, n.end_byte, n.type)
        captures_by_function = {}
        def _bucket_for(node):
            fid = _key(node)
            return captures_by_function.setdefault(fid, {
                'node': node, 'name': None, 'params': None, 'single_param': None
            })
        for node, capture_name in execute_query(self.language, query_str, root_node):
            if capture_name == 'function_node':
                _bucket_for(node)
            elif capture_name == 'name':
                fn = _fn_for_name(node)
                if fn:
                    b = _bucket_for(fn)
                    b['name'] = self._get_node_text(node)
            elif capture_name == 'params':
                fn = _fn_for_params(node)
                if fn:
                    b = _bucket_for(fn)
                    b['params'] = node
            elif capture_name == 'single_param':
                fn = _fn_for_params(node)
                if fn:
                    b = _bucket_for(fn)
                    b['single_param'] = node
        for _, data in captures_by_function.items():
            func_node = data['node']
            name = data.get('name')
            if not name and func_node.type == 'method_definition':
                nm = func_node.child_by_field_name('name')
                if nm:
                    name = self._get_node_text(nm)
            if not name:
                continue
            args = []
            if data.get('params'):
                args = self._extract_parameters(data['params'])
            elif data.get('single_param'):
                args = [self._get_node_text(data['single_param'])]
            context, context_type, _ = self._get_parent_context(func_node)
            class_context = context if context_type == 'class_declaration' else None
            docstring = None
            func_data = {
                "name": name,
                "line_number": func_node.start_point[0] + 1,
                "end_line": func_node.end_point[0] + 1,
                "args": args,
                "source": self._get_node_text(func_node),

                "docstring": docstring,
                "cyclomatic_complexity": self._calculate_complexity(func_node),
                "context": context,
                "context_type": context_type,
                "class_context": class_context,
                "decorators": [],
                "lang": self.language_name,
                "is_dependency": False,
            }
            functions.append(func_data)
        return functions

    def _extract_parameters(self, params_node):
        params = []
        if params_node.type == 'formal_parameters':
            for child in params_node.children:
                if child.type == 'identifier':
                    params.append(self._get_node_text(child))
                elif child.type == 'required_parameter':
                    # required_parameter -> pattern (identifier) + type_annotation
                    pattern = child.child_by_field_name('pattern')
                    if pattern:
                         params.append(self._get_node_text(pattern))
                    else:
                        # Fallback: first child that is an identifier or pattern
                        for sub in child.children:
                            if sub.type in ('identifier', 'object_pattern', 'array_pattern'):
                                params.append(self._get_node_text(sub))
                                break
                elif child.type == 'optional_parameter':
                    pattern = child.child_by_field_name('pattern')
                    if pattern:
                         params.append(self._get_node_text(pattern))
                elif child.type == 'assignment_pattern':
                    left_child = child.child_by_field_name('left')
                    if left_child and left_child.type == 'identifier':
                        params.append(self._get_node_text(left_child))
                elif child.type == 'rest_pattern':
                    argument = child.child_by_field_name('argument')
                    if argument and argument.type == 'identifier':
                        params.append(f"...{self._get_node_text(argument)}")
        return params

    def _find_classes(self, root_node):
        classes = []
        query_str = TS_QUERIES['classes']
        for class_node, capture_name in execute_query(self.language, query_str, root_node):
            if capture_name == 'class':
                name_node = class_node.child_by_field_name('name')
                if not name_node: continue
                name = self._get_node_text(name_node)
                bases = []
                heritage_node = next((child for child in class_node.children if child.type == 'class_heritage'), None)
                if heritage_node:
                    for child in heritage_node.children:
                        if child.type == 'extends_clause':
                            # extends_clause -> extends identifier
                            for sub in child.children:
                                if sub.type in ('identifier', 'type_identifier', 'member_expression'):
                                    bases.append(self._get_node_text(sub))
                        elif child.type == 'implements_clause':
                            # implements_clause -> implements identifier, identifier...
                            for sub in child.children:
                                if sub.type in ('identifier', 'type_identifier', 'member_expression'):
                                    bases.append(self._get_node_text(sub))
                class_data = {
                    "name": name,
                    "line_number": class_node.start_point[0] + 1,
                    "end_line": class_node.end_point[0] + 1,
                    "bases": bases,
                    "source": self._get_node_text(class_node),
                    "docstring": self._get_docstring(class_node),
                    "context": None,
                    "decorators": [],
                    "lang": self.language_name,
                    "is_dependency": False,
                }
                classes.append(class_data)
        return classes
    
    def _find_interfaces(self, root_node):
        interfaces = []
        query_str = TS_QUERIES['interfaces']
        for node, capture_name in execute_query(self.language, query_str, root_node):
            if capture_name == 'interface_node':
                name_node = node.child_by_field_name('name')
                if not name_node: continue
                
                name = self._get_node_text(name_node)
                interface_data = {
                    "name": name,
                    "line_number": node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1,
                    "source": self._get_node_text(node),
                }
                interfaces.append(interface_data)
        return interfaces

    def _find_type_aliases(self, root_node):
        type_aliases = []
        query_str = TS_QUERIES['type_aliases']
        for node, capture_name in execute_query(self.language, query_str, root_node):
            if capture_name == 'type_alias_node':
                name_node = node.child_by_field_name('name')
                if not name_node: continue

                name = self._get_node_text(name_node)
                type_alias_data = {
                    "name": name,
                    "line_number": node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1,
                    "source": self._get_node_text(node),
                }
                type_aliases.append(type_alias_data)
        return type_aliases

    def _find_imports(self, root_node):
        imports = []
        query_str = TS_QUERIES['imports']
        for node, capture_name in execute_query(self.language, query_str, root_node):
            if capture_name != 'import':
                continue
            line_number = node.start_point[0] + 1
            if node.type == 'import_statement':
                source = self._get_node_text(node.child_by_field_name('source')).strip('\'"')
                import_clause = node.child_by_field_name('import')
                if not import_clause:
                    imports.append({'name': source, 'source': source, 'alias': None, 'line_number': line_number,
                                    'lang': self.language_name})
                    continue
                if import_clause.type == 'identifier':
                    alias = self._get_node_text(import_clause)
                    imports.append({'name': 'default', 'source': source, 'alias': alias, 'line_number': line_number,
                                    'lang': self.language_name})
                elif import_clause.type == 'namespace_import':
                    alias_node = import_clause.child_by_field_name('alias')
                    if alias_node:
                        alias = self._get_node_text(alias_node)
                        imports.append({'name': '*', 'source': source, 'alias': alias, 'line_number': line_number,
                                        'lang': self.language_name})
                elif import_clause.type == 'named_imports':
                    for specifier in import_clause.children:
                        if specifier.type == 'import_specifier':
                            name_node = specifier.child_by_field_name('name')
                            alias_node = specifier.child_by_field_name('alias')
                            original_name = self._get_node_text(name_node)
                            alias = self._get_node_text(alias_node) if alias_node else None
                            imports.append(
                                {'name': original_name, 'source': source, 'alias': alias, 'line_number': line_number,
                                 'lang': self.language_name})
            elif node.type == 'call_expression':
                args = node.child_by_field_name('arguments')
                if not args or args.named_child_count == 0: continue
                source_node = args.named_child(0)
                if not source_node or source_node.type != 'string': continue
                source = self._get_node_text(source_node).strip('\'"')
                alias = None
                if node.parent.type == 'variable_declarator':
                    alias_node = node.parent.child_by_field_name('name')
                    if alias_node:
                        alias = self._get_node_text(alias_node)
                imports.append({'name': source, 'source': source, 'alias': alias, 'line_number': line_number,
                                'lang': self.language_name})
        return imports

    def _find_calls(self, root_node):
        calls = []
        query_str = TS_QUERIES['calls']
        for node, capture_name in execute_query(self.language, query_str, root_node):
            if capture_name == 'name':
                # Traverse up to find the call/new expression
                call_node = node.parent
                while call_node and call_node.type not in ('call_expression', 'new_expression') and call_node.type != 'program':
                    call_node = call_node.parent
                
                name = self._get_node_text(node)

                # Improved args extraction
                args = []
                arguments_node = None
                if call_node and call_node.type in ('call_expression', 'new_expression'):
                    arguments_node = call_node.child_by_field_name('arguments')
                
                if arguments_node:
                    for arg in arguments_node.children:
                        if arg.type not in ('(', ')', ','):
                            args.append(self._get_node_text(arg))

                call_data = {
                    "name": name,
                    "full_name": self._get_node_text(call_node) if call_node else name,
                    "line_number": node.start_point[0] + 1,
                    "args": args,
                    "inferred_obj_type": None,
                    "context": self._get_parent_context(node),
                    "class_context": self._get_parent_context(node, types=('class_declaration', 'abstract_class_declaration')),
                    "lang": self.language_name,
                    "is_dependency": False,
                }
                calls.append(call_data)
        return calls

    def _find_variables(self, root_node):
        variables = []
        query_str = TS_QUERIES['variables']
        for match in execute_query(self.language, query_str, root_node):
            capture_name = match[1]
            node = match[0]
            if capture_name == 'name':
                var_node = node.parent
                name = self._get_node_text(node)
                value = None
                type_text = None

                # Detect if variable assigned to a function
                value_node = var_node.child_by_field_name("value") if var_node else None

                if value_node:
                    value_type = value_node.type

                    # --- Skip variables that are assigned a function ---
                    if value_type in ("function_expression", "arrow_function"):
                        continue
                    
                    if "function" in value_type or "arrow" in value_type:
                        continue

                    # --- Handle various assignment types ---
                    if value_type == "call_expression":
                        func_node = value_node.child_by_field_name("function")
                        value = self._get_node_text(func_node) if func_node else name
                    else:
                        value = self._get_node_text(value_node)

                context, context_type, context_line = self._get_parent_context(node)
                class_context = context if context_type == 'class_declaration' else None

                variable_data = {
                    "name": name,
                    "line_number": node.start_point[0] + 1,
                    "value": value,
                    "type": type_text,
                    "context": context,
                    "class_context": class_context,
                    "lang": self.language_name,
                    "is_dependency": False,
                }
                variables.append(variable_data)
        return variables

def pre_scan_typescript(files: list[Path], parser_wrapper) -> dict:
    """Scans TypeScript files to create a map of class/function names to their file paths."""
    imports_map = {}
    
    # Simplified queries that capture the parent nodes, then extract names manually
    query_strings = [
        "(class_declaration) @class",
        "(function_declaration) @function",
        "(variable_declarator) @var_decl",
        "(method_definition) @method",
        "(interface_declaration) @interface",
        "(type_alias_declaration) @type_alias",
    ]
    
    for file_path in files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source_code = f.read()
                tree = parser_wrapper.parser.parse(bytes(source_code, "utf8"))
            
            # Run each query separately
            for query_str in query_strings:
                try:
                    
                    for node, capture_name in execute_query(parser_wrapper.language, query_str, tree.root_node):
                        name = None
                        
                        # Extract name based on node type
                        if capture_name == 'class':
                            name_node = node.child_by_field_name('name')
                            if name_node:
                                name = name_node.text.decode('utf-8')
                        
                        elif capture_name == 'function':
                            name_node = node.child_by_field_name('name')
                            if name_node:
                                name = name_node.text.decode('utf-8')
                        
                        elif capture_name == 'var_decl':
                            # Check if it's a function or arrow function
                            name_node = node.child_by_field_name('name')
                            value_node = node.child_by_field_name('value')
                            if name_node and value_node:
                                if value_node.type in ('function', 'arrow_function'):
                                    name = name_node.text.decode('utf-8')
                        
                        elif capture_name == 'method':
                            name_node = node.child_by_field_name('name')
                            if name_node:
                                name = name_node.text.decode('utf-8')
                        
                        elif capture_name == 'interface':
                            name_node = node.child_by_field_name('name')
                            if name_node:
                                name = name_node.text.decode('utf-8')
                        
                        elif capture_name == 'type_alias':
                            name_node = node.child_by_field_name('name')
                            if name_node:
                                name = name_node.text.decode('utf-8')
                        
                        # Add to imports map if we found a name
                        if name:
                            if name not in imports_map:
                                imports_map[name] = []
                            file_path_str = str(file_path.resolve())
                            if file_path_str not in imports_map[name]:
                                imports_map[name].append(file_path_str)
                                
                except Exception as query_error:
                    warning_logger(f"Query failed for pattern '{query_str}': {query_error}")
                    
        except Exception as e:
            warning_logger(f"Tree-sitter pre-scan failed for {file_path}: {e}")
    
    return imports_map
