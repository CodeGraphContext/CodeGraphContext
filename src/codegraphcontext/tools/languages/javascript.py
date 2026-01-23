from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import re
from codegraphcontext.utils.debug_log import debug_log, info_logger, error_logger, warning_logger
from codegraphcontext.utils.tree_sitter_manager import execute_query

# --- Helpers to classify JS methods ---
_GETTER_RE = re.compile(r"^\s*(?:static\s+)?get\b")
_SETTER_RE = re.compile(r"^\s*(?:static\s+)?set\b")
_STATIC_RE = re.compile(r"^\s*static\b")


def _first_line_before_body(text: str) -> str:
    """
    Best-effort header extraction: take text before the first '{'
    (covers class/object methods). Fallback to the first line.
    """
    head = text.split("{", 1)[0]
    if not head.strip():
        return text.splitlines()[0] if text.splitlines() else text
    return head


def _classify_method_kind(header: str) -> Optional[str]:
    """
    Return 'getter' | 'setter' | 'static' | None.
    Prefer 'getter'/'setter' over 'static' when both appear.
    """
    if _GETTER_RE.search(header):
        return "getter"
    if _SETTER_RE.search(header):
        return "setter"
    if _STATIC_RE.search(header):
        return "static"
    return None


JS_QUERIES = {
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
        (class) @class
    """,
    "imports": """
        (import_statement) @import
        (call_expression
            function: (identifier) @require_call (#eq? @require_call "require")
        ) @import
    """,
    "exports": """
        (export_statement) @export
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


class JavascriptTreeSitterParser:
    """A JavaScript-specific parser using tree-sitter, encapsulating language-specific logic."""

    def __init__(self, generic_parser_wrapper):
        self.generic_parser_wrapper = generic_parser_wrapper
        self.language_name = generic_parser_wrapper.language_name
        self.language = generic_parser_wrapper.language
        self.parser = generic_parser_wrapper.parser

    def _get_node_text(self, node) -> str:
        return node.text.decode('utf-8')

    def _get_parent_context(self, node, types=('function_declaration', 'class_declaration', 'function_expression', 'method_definition', 'arrow_function')):
        # JS specific context types
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
        # JS specific complexity nodes
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
        # JS specific docstring extraction (e.g., JSDoc comments)
        # This is a placeholder and needs more sophisticated logic
        return None

    def parse(self, file_path: Path, is_dependency: bool = False) -> Dict:
        """Parses a file and returns its structure in a standardized dictionary format."""
        with open(file_path, "r", encoding="utf-8") as f:
            source_code = f.read()

        tree = self.parser.parse(bytes(source_code, "utf8"))
        root_node = tree.root_node

        functions = self._find_functions(root_node)
        classes = self._find_classes(root_node)
        imports = self._find_imports(root_node)
        exports = self._find_exports(root_node)
        function_calls = self._find_calls(root_node)
        variables = self._find_variables(root_node)

        return {
            "file_path": str(file_path),
            "functions": functions,
            "classes": classes,
            "variables": variables,
            "imports": imports,
            "exports": exports,
            "function_calls": function_calls,
            "is_dependency": is_dependency,
            "lang": self.language_name,
        }

    def _find_functions(self, root_node):
        functions = []
        query_str = JS_QUERIES['functions']

    # Local helpers so we don't depend on class attrs being present
        def _fn_for_name(name_node):
            current = name_node.parent
            while current:
                if current.type in ('function_declaration', 'function', 'arrow_function', 'method_definition', 'function_expression'):
                    return current
                elif current.type in ('variable_declarator', 'assignment_expression'):
                    for child in current.children:
                        if child.type in ('function', 'arrow_function', 'function_expression'):
                            return child
                current = current.parent
            return None

        def _fn_for_params(params_node):
            current = params_node.parent
            while current:
                if current.type in ('function_declaration', 'function', 'arrow_function', 'method_definition', 'function_expression'):
                    return current
                current = current.parent
            return None
        # stable keys so the same function only gets one bucket
        def _key(n):  # start/end byte + type is stable across captures
            return (n.start_byte, n.end_byte, n.type)

        # Collect captures grouped by function node
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

        # Build Function entries
        for _, data in captures_by_function.items():
            func_node = data['node']

            # Backfill name for method_definition if query didn't capture it
            name = data.get('name')
            if not name and func_node.type == 'method_definition':
                nm = func_node.child_by_field_name('name')
                if nm:
                    name = self._get_node_text(nm)
            if not name:
                continue  # skip nameless functions

            # Parameters
            args = []
            if data.get('params'):
                args = self._extract_parameters(data['params'])
            elif data.get('single_param'):
                args = [self._get_node_text(data['single_param'])]

            # Context & docstring
            context, context_type, _ = self._get_parent_context(func_node)
            class_context = context if context_type == 'class_declaration' else None
            docstring = self._get_jsdoc_comment(func_node)

            # Classify getter/setter/static (methods only)
            js_kind = None
            if func_node.type == 'method_definition':
                header = _first_line_before_body(self._get_node_text(func_node))
                js_kind = _classify_method_kind(header)

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
            if js_kind is not None:
                func_data["type"] = js_kind

            functions.append(func_data)

        return functions



    def _find_function_node_for_name(self, name_node):
        """Find the function node that contains this name node."""
        current = name_node.parent
        while current:
            if current.type in ('function_declaration', 'function', 'arrow_function', 'method_definition'):
                return current
            elif current.type in ('variable_declarator', 'assignment_expression'):
                # Check if this declarator/assignment contains a function
                for child in current.children:
                    if child.type in ('function', 'arrow_function'):
                        return child
            current = current.parent
        return None


    def _find_function_node_for_params(self, params_node):
        """Find the function node that contains this parameters node."""
        current = params_node.parent
        while current:
            if current.type in ('function_declaration', 'function', 'arrow_function', 'method_definition'):
                return current
            current = current.parent

        return None


    def _extract_parameters(self, params_node):
        """Extract parameter names from formal_parameters node."""
        params = []
        if params_node.type == 'formal_parameters':
            for child in params_node.children:
                if child.type == 'identifier':
                    params.append(self._get_node_text(child))
                elif child.type == 'assignment_pattern':
                    # Default parameter: param = defaultValue
                    left_child = child.child_by_field_name('left')
                    if left_child and left_child.type == 'identifier':
                        params.append(self._get_node_text(left_child))
                elif child.type == 'rest_pattern':
                    # Rest parameter: ...args
                    argument = child.child_by_field_name('argument')
                    if argument and argument.type == 'identifier':
                        params.append(f"...{self._get_node_text(argument)}")
        return params


    def _get_jsdoc_comment(self, func_node):
        """Extract JSDoc comment preceding the function."""
        # Look for comments before the function
        prev_sibling = func_node.prev_sibling
        while prev_sibling and prev_sibling.type in ('comment', '\n', ' '):
            if prev_sibling.type == 'comment':
                comment_text = self._get_node_text(prev_sibling)
                if comment_text.startswith('/**') and comment_text.endswith('*/'):
                    return comment_text.strip()
            prev_sibling = prev_sibling.prev_sibling
        return None


    def _find_classes(self, root_node):
        classes = []
        query_str = JS_QUERIES['classes']
        for class_node, capture_name in execute_query(self.language, query_str, root_node):
            if capture_name == 'class':
                name_node = class_node.child_by_field_name('name')
                if not name_node: continue
                name = self._get_node_text(name_node)

                bases = []
                heritage_node = next((child for child in class_node.children if child.type == 'class_heritage'), None)
                if heritage_node:
                    if heritage_node.named_child_count > 0:
                        base_expr_node = heritage_node.named_child(0)
                        bases.append(self._get_node_text(base_expr_node))
                    elif heritage_node.child_count > 0:
                        # Fallback for anonymous nodes
                        base_expr_node = heritage_node.child(heritage_node.child_count - 1)
                        bases.append(self._get_node_text(base_expr_node))

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


    def _find_imports(self, root_node):
        imports = []
        query_str = JS_QUERIES['imports']
        for node, capture_name in execute_query(self.language, query_str, root_node):
            if capture_name != 'import':
                continue

            line_number = node.start_point[0] + 1

            if node.type == 'import_statement':
                source = self._get_node_text(node.child_by_field_name('source')).strip('\'"')

                # Look for different import structures
                import_clause = node.child_by_field_name('import')
                if not import_clause:
                    imports.append({'name': source, 'source': source, 'alias': None, 'line_number': line_number,
                                    'lang': self.language_name})
                    continue

                # Default import: import defaultExport from '...'
                if import_clause.type == 'identifier':
                    alias = self._get_node_text(import_clause)
                    imports.append({'name': 'default', 'source': source, 'alias': alias, 'line_number': line_number,
                                    'lang': self.language_name})

                # Namespace import: import * as name from '...'
                elif import_clause.type == 'namespace_import':
                    alias_node = import_clause.child_by_field_name('alias')
                    if alias_node:
                        alias = self._get_node_text(alias_node)
                        imports.append({'name': '*', 'source': source, 'alias': alias, 'line_number': line_number,
                                        'lang': self.language_name})

                # Named imports: import { name, name as alias } from '...'
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

            elif node.type == 'call_expression':  # require('...')
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


    def _find_exports(self, root_node):
        """Extract export statements from JavaScript code."""
        exports = []
        query_str = JS_QUERIES['exports']
        
        for node, capture_name in execute_query(self.language, query_str, root_node):
            if capture_name != 'export':
                continue
            
            line_number = node.start_point[0] + 1
            
            # Check if this is a default export
            has_default = any(child.type == 'default' for child in node.children)
            
            # Handle different export types
            for child in node.children:
                # export default ...
                if child.type == 'default':
                    # Find what comes after 'default'
                    default_export_node = None
                    for sibling in node.children:
                        if sibling.type in ('function_declaration', 'class_declaration', 'identifier', 
                                           'arrow_function', 'function_expression'):
                            default_export_node = sibling
                            break
                    
                    export_name = 'default'
                    original_name = None
                    
                    if default_export_node:
                        if default_export_node.type == 'function_declaration':
                            name_node = default_export_node.child_by_field_name('name')
                            original_name = self._get_node_text(name_node) if name_node else 'default'
                        elif default_export_node.type == 'class_declaration':
                            name_node = default_export_node.child_by_field_name('name')
                            original_name = self._get_node_text(name_node) if name_node else 'default'
                        elif default_export_node.type == 'identifier':
                            original_name = self._get_node_text(default_export_node)
                    
                    exports.append({
                        'name': export_name,
                        'original_name': original_name or 'default',
                        'is_default': True,
                        'line_number': line_number,
                        'lang': self.language_name
                    })
                
                # export function/class declaration (but not if it's a default export)
                elif child.type == 'function_declaration' and not has_default:
                    name_node = child.child_by_field_name('name')
                    if name_node:
                        export_name = self._get_node_text(name_node)
                        exports.append({
                            'name': export_name,
                            'original_name': export_name,
                            'is_default': False,
                            'line_number': line_number,
                            'lang': self.language_name
                        })
                
                elif child.type == 'class_declaration' and not has_default:
                    name_node = child.child_by_field_name('name')
                    if name_node:
                        export_name = self._get_node_text(name_node)
                        exports.append({
                            'name': export_name,
                            'original_name': export_name,
                            'is_default': False,
                            'line_number': line_number,
                            'lang': self.language_name
                        })
                
                # export const/let/var ...
                elif child.type == 'lexical_declaration' or child.type == 'variable_declaration':
                    for declarator in child.children:
                        if declarator.type == 'variable_declarator':
                            name_node = declarator.child_by_field_name('name')
                            if name_node and name_node.type == 'identifier':
                                export_name = self._get_node_text(name_node)
                                exports.append({
                                    'name': export_name,
                                    'original_name': export_name,
                                    'is_default': False,
                                    'line_number': line_number,
                                    'lang': self.language_name
                                })
                
                # export { name1, name2 as alias }
                elif child.type == 'export_clause':
                    for specifier in child.children:
                        if specifier.type == 'export_specifier':
                            name_node = specifier.child_by_field_name('name')
                            alias_node = specifier.child_by_field_name('alias')
                            
                            if name_node:
                                original_name = self._get_node_text(name_node)
                                export_name = self._get_node_text(alias_node) if alias_node else original_name
                                exports.append({
                                    'name': export_name,
                                    'original_name': original_name,
                                    'is_default': False,
                                    'line_number': line_number,
                                    'lang': self.language_name
                                })
        
        return exports


    def _find_calls(self, root_node):
        calls = []
        query_str = JS_QUERIES['calls']
        for node, capture_name in execute_query(self.language, query_str, root_node):
            # Placeholder for JS call extraction logic
            if capture_name == 'name':
                # Traverse up to find the call_expression
                call_node = node.parent
                while call_node and call_node.type != 'call_expression' and call_node.type != 'program':
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
                    "full_name": self._get_node_text(call_node),
                    "line_number": node.start_point[0] + 1,
                    "args": args,
                    "inferred_obj_type": None,
                    "context": self._get_parent_context(node),
                    "class_context": self._get_parent_context(node, types=('class_declaration',))[:2],
                    "lang": self.language_name,
                    "is_dependency": False,
                }
                calls.append(call_data)
        return calls


    def _find_variables(self, root_node):
        variables = []
        query_str = JS_QUERIES['variables']
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
                    
                    # Some grammars might have async_arrow_function or similar
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


def pre_scan_javascript(files: list[Path], parser_wrapper) -> dict:
    """Scans JavaScript files to create a map of class/function names to their file paths."""
    imports_map = {}
    query_str = """
        (class_declaration name: (identifier) @name)
        (function_declaration name: (identifier) @name)
        (variable_declarator name: (identifier) @name value: (function_expression))
        (variable_declarator name: (identifier) @name value: (arrow_function))
        (method_definition name: (property_identifier) @name)
        (assignment_expression
            left: (member_expression 
                property: (property_identifier) @name
            )
            right: (function_expression)
        )
        (assignment_expression
            left: (member_expression 
                property: (property_identifier) @name
            )
            right: (arrow_function)
        )
    """
    

    for file_path in files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                tree = parser_wrapper.parser.parse(bytes(f.read(), "utf8"))

            for capture, _ in execute_query(parser_wrapper.language, query_str, tree.root_node):
                name = capture.text.decode('utf-8')
                if name not in imports_map:
                    imports_map[name] = []
                imports_map[name].append(str(file_path.resolve()))
        except Exception as e:
            warning_logger(f"Tree-sitter pre-scan failed for {file_path}: {e}")
    return imports_map
