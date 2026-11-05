# src/codegraphcontext/tools/languages/go.py
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
    # `import_spec` is a direct child of `import_declaration` only for a
    # single-line `import "fmt"`. A grouped block — which gofmt produces for
    # any file with more than one import, i.e. nearly all of them — nests the
    # specs inside an `import_spec_list`, so matching only the direct-child
    # shape returned zero imports for those files.
    "imports": """
        (import_declaration
            (import_spec
                path: (interpreted_string_literal) @path
            )
        ) @import

        (import_declaration
            (import_spec_list
                (import_spec
                    path: (interpreted_string_literal) @path
                )
            )
        ) @import

        (import_declaration
            (import_spec
                name: (package_identifier) @alias
                path: (interpreted_string_literal) @path
            )
        ) @import_alias

        (import_declaration
            (import_spec_list
                (import_spec
                    name: (package_identifier) @alias
                    path: (interpreted_string_literal) @path
                )
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
        self.index_source = False

    def _get_node_text(self, node) -> str:
        return node.text.decode('utf-8')

    def _literal_binding(self, literal):
        values = literal.parent
        if values is None or values.type != 'expression_list':
            return None
        declaration = values.parent
        if declaration is None:
            return None
        if declaration.type == 'var_spec':
            names = declaration.children_by_field_name('name')
        elif declaration.type in ('short_var_declaration', 'assignment_statement') and declaration.child_by_field_name('right') == values:
            left = declaration.child_by_field_name('left')
            names = left.named_children if left is not None else []
        else:
            return None
        expressions = values.named_children
        if len(names) != len(expressions):
            return None
        for index, value in enumerate(expressions):
            if value == literal and names[index].type == 'identifier':
                return names[index]
        return None

    def _get_parent_context(self, node, types=('function_declaration', 'method_declaration', 'type_declaration')):
        curr = node.parent
        while curr:
            if curr.type == 'func_literal' and 'function_declaration' in types:
                binding = self._literal_binding(curr)
                if binding is not None:
                    return self._get_node_text(binding), 'func_literal', binding.start_point[0] + 1
            if curr.type in types:
                if curr.type == 'type_declaration':
                    type_spec = curr.child_by_field_name('type_spec')
                    if type_spec:
                        name_node = type_spec.child_by_field_name('name')
                        if name_node:
                            return self._get_node_text(name_node), curr.type, curr.start_point[0] + 1
                else:
                    name_node = curr.child_by_field_name('name')
                    if name_node:
                        return self._get_node_text(name_node), curr.type, curr.start_point[0] + 1
            curr = curr.parent
        return None, None, None

    def _calculate_complexity(self, node):
        from codegraphcontext.tools.indexing.constants import MAX_AST_DEPTH
        """
        Compute a simple cyclomatic complexity score from the Go AST.

        We treat each decision/control-flow construct as +1:
        - if/for/switch/select
        - switch cases (case_clause) and select clauses (comm_clause)
        - logical operators (&&, ||) inside binary_expression as +1
        """
        # Note: tree-sitter-go node types differ from other languages and from
        # what we'd typically expect (e.g. it's `switch`/`case` rather than
        # `switch_statement`/`case_clause`).
        decision_node_types = {
            # top-level control constructs
            "if_statement",
            "for_statement",
            "switch",
            "select_statement",
            "select",
            # switch variants (tree-sitter grammar)
            "expression_switch_statement",
            "type_switch_statement",
            # switch case branches
            "case",
            "expression_case",
            "default_case",
            # select communication branches
            "communication_case",
        }

        count = 1
        skipped = False

        def traverse(n, depth=0):
            nonlocal count, skipped
            if depth > MAX_AST_DEPTH:
                skipped = True
                return
            if n.type in decision_node_types:
                count += 1
                # Still traverse children because nested constructs also contribute.
            elif n.type == "binary_expression":
                # Only count logical operators, not all binary expressions/comparisons.
                # Example patterns: "a && b", "a || b".
                try:
                    txt = self._get_node_text(n)
                except Exception:
                    txt = ""
                if "&&" in txt or "||" in txt:
                    count += 1

            for child in n.children:
                traverse(child, depth + 1)

        traverse(node)
        if skipped:
            warning_logger(
                f"AST depth exceeded {MAX_AST_DEPTH} levels; "
                "complexity count may be underestimated."
            )
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
        self.index_source = index_source
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            source_code = f.read()

        # Extract Go package declaration for package_name field on File nodes
        import re as _re
        pkg_match = _re.search(r'^\s*package\s+(\w+)', source_code, _re.MULTILINE)
        package_name = pkg_match.group(1) if pkg_match else None

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
            "structs": structs,
            "interfaces": interfaces,
            "variables": variables,
            "imports": imports,
            "function_calls": function_calls,
            "is_dependency": is_dependency,
            "lang": self.language_name,
            "package_name": package_name,
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
                    "is_generic": func_node.child_by_field_name('type_parameters') is not None,
                    "line_number": func_node.start_point[0] + 1,
                    "end_line": func_node.end_point[0] + 1,
                    "args": args,
                    "class_context": class_context,
                    "receiver_type": receiver_type,
                    "decorators": [],
                    "lang": self.language_name,
                    "is_dependency": False,
                    "cyclomatic_complexity": self._calculate_complexity(func_node),
                }
                
                if self.index_source:
                    func_data["source"] = self._get_node_text(func_node)
                    func_data["docstring"] = docstring
                    
                functions.append(func_data)

        for literal, _ in execute_query(self.language, '(func_literal) @literal', root_node):
            binding = self._literal_binding(literal)
            if binding is None:
                continue
            context, context_type, context_line = self._get_parent_context(literal)
            parameters = literal.child_by_field_name('parameters')
            function = {
                'name': self._get_node_text(binding),
                'line_number': binding.start_point[0] + 1,
                'end_line': literal.end_point[0] + 1,
                'args': self._extract_parameters(parameters) if parameters is not None else [],
                'context': context, 'context_type': context_type, 'context_line': context_line,
                'class_context': None, 'receiver_type': None,
                'lang': self.language_name, 'is_dependency': False,
                'cyclomatic_complexity': self._calculate_complexity(literal),
            }
            if self.index_source:
                function['source'] = self._get_node_text(literal)
            functions.append(function)
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
                    
                    # Find embedded fields as bases
                    bases = []
                    # In tree-sitter-go, type_declaration usually has a type_spec child
                    type_spec = None
                    for child in struct_node.children:
                        if child.type == 'type_spec':
                            type_spec = child
                            break
                    
                    if type_spec:
                        struct_body = None
                        for child in type_spec.children:
                            if child.type == 'struct_type':
                                struct_body = child
                                break
                        
                        if struct_body:
                            # Find field_declaration_list
                            field_list = None
                            for child in struct_body.children:
                                if child.type == 'field_declaration_list':
                                    field_list = child
                                    break
                            
                            if field_list:
                                for field in field_list.children:
                                    if field.type == 'field_declaration':
                                        # Check if it's an embedded field (no name/identifier)
                                        has_field_name = False
                                        for fchild in field.children:
                                            if fchild.type in ('field_identifier', 'field_identifier_list'):
                                                has_field_name = True
                                                break
                                        
                                        if not has_field_name:
                                            # It's an embedded field. Find the type node.
                                            type_node = None
                                            for fchild in field.children:
                                                if fchild.type in ('type_identifier', 'pointer_type', 'qualified_type'):
                                                    type_node = fchild
                                                    break
                                            
                                            if type_node:
                                                if type_node.type == 'pointer_type':
                                                    inner = type_node.child_by_field_name('content') or type_node.named_child(0)
                                                    type_text = self._get_node_text(inner) if inner else self._get_node_text(type_node).strip('*')
                                                elif type_node.type == 'qualified_type':
                                                    name_child = type_node.child_by_field_name('name')
                                                    type_text = self._get_node_text(name_child) if name_child else self._get_node_text(type_node).split('.')[-1]
                                                else:
                                                    type_text = self._get_node_text(type_node)
                                                
                                                bases.append(type_text)






                    class_data = {
                        "name": name,
                        "line_number": struct_node.start_point[0] + 1,
                        "end_line": struct_node.end_point[0] + 1,
                        "bases": bases,
                        "decorators": [],
                        "lang": self.language_name,
                        "is_dependency": False,
                    }
                    if self.index_source:
                        class_data["source"] = self._get_node_text(struct_node)
                        class_data["docstring"] = self._get_docstring(struct_node)

                    structs.append(class_data)
        return structs


    def _extract_interface_methods(self, interface_type_node: Any) -> tuple[list[str], list[str]]:
        methods: list[str] = []
        embedded: list[str] = []
        if not interface_type_node:
            return methods, embedded
        for child in interface_type_node.children:
            if child.type in ("method_elem", "method_spec"):
                name_node = child.child_by_field_name("name")
                if name_node:
                    methods.append(self._get_node_text(name_node))
            elif child.type == "type_elem":
                for sub in child.children:
                    if sub.type == "type_identifier":
                        embedded.append(self._get_node_text(sub))
        return methods, embedded

    def _find_interfaces(self, root_node):
        interfaces = []
        interface_query_str = GO_QUERIES['interfaces']
        pending: Dict[int, Dict[str, Any]] = {}
        for node, capture_name in execute_query(self.language, interface_query_str, root_node):
            if capture_name == "interface_node":
                pending[node.id] = {"interface_node": node, "name": None, "body": None}
            elif capture_name == "name":
                interface_node = self._find_type_declaration_for_name(node)
                if interface_node:
                    entry = pending.setdefault(
                        interface_node.id,
                        {"interface_node": interface_node, "name": None, "body": None},
                    )
                    entry["name"] = self._get_node_text(node)
            elif capture_name == "interface_body":
                type_spec = node.parent
                interface_node = type_spec.parent if type_spec else None
                if interface_node:
                    entry = pending.setdefault(
                        interface_node.id,
                        {"interface_node": interface_node, "name": None, "body": None},
                    )
                    entry["body"] = node

        for entry in pending.values():
            name = entry.get("name")
            interface_node = entry.get("interface_node")
            if not name or not interface_node:
                continue
            methods, embedded = self._extract_interface_methods(entry.get("body"))
            class_data = {
                "name": name,
                "line_number": interface_node.start_point[0] + 1,
                "end_line": interface_node.end_point[0] + 1,
                "bases": embedded,
                "methods": methods,
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
        # A single-argument generic invocation and a type conversion share a
        # grammar shape. Retain ambiguous candidates explicitly; graph resolution
        # must verify an indexed generic function before creating an edge.
        local_types = {self._get_node_text(n) for n, _ in execute_query(
            self.language, '(type_spec name: (type_identifier) @type)', root_node
        )}
        query = '(call_expression) @call (type_conversion_expression type: (generic_type)) @generic_candidate'
        for call, capture in execute_query(self.language, query, root_node):
            candidate = capture == 'generic_candidate'
            target = call.child_by_field_name('type' if candidate else 'function')
            while target is not None and target.type in ('index_expression', 'generic_type'):
                target = target.child_by_field_name('operand' if target.type == 'index_expression' else 'type')
            if target is None:
                continue
            if target.type in ('identifier', 'type_identifier'):
                name = self._get_node_text(target)
                full_name = name
                receiver = None
            elif target.type in ('selector_expression', 'qualified_type'):
                member = target.child_by_field_name('field' if target.type == 'selector_expression' else 'name')
                receiver_node = target.child_by_field_name('operand' if target.type == 'selector_expression' else 'package')
                if member is None:
                    continue
                name = self._get_node_text(member)
                receiver = self._get_node_text(receiver_node) if receiver_node is not None else None
                full_name = self._get_node_text(target)
            else:
                continue
            if candidate and receiver is None and name in local_types:
                continue
            context = self._get_parent_context(call)
            arguments = call.child_by_field_name('arguments')
            operand = call.child_by_field_name('operand')
            args = [self._get_node_text(n) for n in arguments.named_children] if arguments is not None else (
                [self._get_node_text(operand)] if operand is not None else []
            )
            record = {
                'name': name, 'full_name': full_name,
                'line_number': call.start_point[0] + 1, 'start_byte': call.start_byte,
                'args': args, 'inferred_obj_type': receiver,
                'context': context, 'class_context': None,
                'lang': self.language_name, 'is_dependency': False,
            }
            if candidate:
                record['call_kind'] = 'generic_or_conversion'
            calls.append(record)
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
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                tree = parser_wrapper.parser.parse(bytes(f.read(), "utf8"))

            for capture, _ in execute_query(parser_wrapper.language, query_str, tree.root_node):
                name = capture.text.decode('utf-8')
                if name not in imports_map:
                    imports_map[name] = []
                imports_map[name].append(path.resolve().as_posix())
        except Exception as e:
            warning_logger(f"Tree-sitter pre-scan failed for {path}: {e}")
    
    return imports_map