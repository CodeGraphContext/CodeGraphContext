import os
import tempfile
import nbformat
from nbconvert import PythonExporter
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import ast
import logging
import warnings
from codegraphcontext.utils.debug_log import debug_log, info_logger, error_logger, warning_logger, debug_logger
from codegraphcontext.utils.tree_sitter_manager import execute_query

# Suppress verbose traitlets/nbconvert DEBUG logs
logging.getLogger('traitlets').setLevel(logging.WARNING)
logging.getLogger('nbconvert').setLevel(logging.WARNING)

# Suppress IPython UserWarning from nbconvert
warnings.filterwarnings('ignore', message='.*IPython is needed to transform IPython syntax.*')


PY_QUERIES = {
    "imports": """
        (import_statement name: (_) @import)
        (import_from_statement) @from_import_stmt
    """,
    "classes": """
        (class_definition
            name: (identifier) @name
            superclasses: (argument_list)? @superclasses
            body: (block) @body)
    """,
    "functions": """
        (function_definition
            name: (identifier) @name
            parameters: (parameters) @parameters
            body: (block) @body
            return_type: (_)? @return_type)
    """,
    "calls": """
        (call
            function: (identifier) @name)
        (call
            function: (attribute attribute: (identifier) @name) @full_call)
    """,
    "variables": """
        (assignment
            left: (identifier) @name)
    """,
    "lambda_assignments": """
        (assignment
            left: (identifier) @name
            right: (lambda) @lambda_node)
    """,
    "docstrings": """
        (expression_statement (string) @docstring)
    """,
    "dict_method_refs": """
        (dictionary
            (pair
                key: (_) @key
                value: (attribute) @method_ref))
    """,
}

class PythonTreeSitterParser:
    """A Python-specific parser using tree-sitter, encapsulating language-specific logic."""

    def __init__(self, generic_parser_wrapper):
        self.generic_parser_wrapper = generic_parser_wrapper
        self.language_name = generic_parser_wrapper.language_name
        self.language = generic_parser_wrapper.language
        self.parser = generic_parser_wrapper.parser

    def _get_node_text(self, node) -> str:
        return node.text.decode('utf-8')

    def _get_parent_context(self, node, types=('function_definition', 'class_definition')):
        curr = node.parent
        while curr:
            if curr.type in types:
                name_node = curr.child_by_field_name('name')
                return self._get_node_text(name_node) if name_node else None, curr.type, curr.start_point[0] + 1
            curr = curr.parent
        return None, None, None

    def _calculate_complexity(self, node):
        complexity_nodes = {
            "if_statement", "for_statement", "while_statement", "except_clause",
            "with_statement", "boolean_operator", "list_comprehension", 
            "generator_expression", "case_clause"
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
        if body_node and body_node.child_count > 0:
            first_child = body_node.children[0]
            if first_child.type == 'expression_statement' and first_child.children[0].type == 'string':
                try:
                    return ast.literal_eval(self._get_node_text(first_child.children[0]))
                except (ValueError, SyntaxError):
                    return self._get_node_text(first_child.children[0])
        return None

    def parse(self, file_path: Path, is_dependency: bool = False, is_notebook: bool = False, index_source: bool = False) -> Dict:
        """Parses a file and returns its structure in a standardized dictionary format."""
        original_file_path = file_path
        temp_py_file = None
        source_code = None
        self.index_source = index_source

        try:
            if is_notebook:
                info_logger(f"Converting notebook {file_path} to temporary Python file.")
                with open(file_path, 'r', encoding='utf-8') as f:
                    notebook_node = nbformat.read(f, as_version=4)
                
                exporter = PythonExporter()
                python_code, _ = exporter.from_notebook_node(notebook_node)

                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py', encoding='utf-8') as tf:
                    tf.write(python_code)
                    temp_py_file = Path(tf.name)
                
                # The file to be parsed is now the temporary file
                file_path = temp_py_file

            with open(file_path, "r", encoding="utf-8") as f:
                source_code = f.read()
            
            tree = self.parser.parse(bytes(source_code, "utf8"))
            root_node = tree.root_node

            functions = self._find_functions(root_node)
            functions.extend(self._find_lambda_assignments(root_node, index_source))
            classes = self._find_classes(root_node)
            imports = self._find_imports(root_node)
            function_calls = self._find_calls(root_node)
            variables = self._find_variables(root_node)

            return {
                "file_path": str(original_file_path), # Always return the original path
                "functions": functions,
                "classes": classes,
                "variables": variables,
                "imports": imports,
                "function_calls": function_calls,
                "is_dependency": is_dependency,
                "lang": self.language_name,
            }
        except Exception as e:
            error_logger(f"Failed to parse {original_file_path}: {e}")
            return {"file_path": str(original_file_path), "error": str(e)}
        finally:
            if temp_py_file and temp_py_file.exists():
                os.remove(temp_py_file)
                info_logger(f"Removed temporary file: {temp_py_file}")

    def _find_lambda_assignments(self, root_node, index_source: bool = False):
        functions = []
        query_str = PY_QUERIES.get('lambda_assignments')
        if not query_str: return []

        for match in execute_query(self.language, query_str, root_node):
            capture_name = match[1]
            node = match[0]

            if capture_name == 'name':
                assignment_node = node.parent
                lambda_node = assignment_node.child_by_field_name('right')
                name = self._get_node_text(node)
                params_node = lambda_node.child_by_field_name('parameters')
                
                context, context_type, _ = self._get_parent_context(assignment_node)
                class_context, _, _ = self._get_parent_context(assignment_node, types=('class_definition',))

                func_data = {
                    "name": name,
                    "line_number": node.start_point[0] + 1,
                    "end_line": assignment_node.end_point[0] + 1,
                    "args": [p for p in [self._get_node_text(p) for p in params_node.children if p.type == 'identifier'] if p] if params_node else [],
                    "cyclomatic_complexity": 1,
                    "context": context,
                    "context_type": context_type,
                    "class_context": class_context,
                    "decorators": [],
                    "lang": self.language_name,
                    "is_dependency": False,
                }
                if self.index_source:
                    func_data["source"] = self._get_node_text(assignment_node)
                    func_data["docstring"] = None

                functions.append(func_data)
        return functions

    def _find_functions(self, root_node, index_source: bool = False):
        functions = []
        query_str = PY_QUERIES['functions']
        for match in execute_query(self.language, query_str, root_node):
            capture_name = match[1]
            node = match[0]

            if capture_name == 'name':
                func_node = node.parent
                name = self._get_node_text(node)
                params_node = func_node.child_by_field_name('parameters')
                body_node = func_node.child_by_field_name('body')
                
                decorators = [self._get_node_text(child) for child in func_node.children if child.type == 'decorator']

                context, context_type, _ = self._get_parent_context(func_node)
                class_context, _, _ = self._get_parent_context(func_node, types=('class_definition',))

                args = []
                if params_node:
                    for p in params_node.children:
                        arg_text = None
                        if p.type == 'identifier':
                            # Simple parameter: def foo(x)
                            arg_text = self._get_node_text(p)
                        elif p.type == 'default_parameter':
                            # Parameter with default: def foo(x=5)
                            name_node = p.child_by_field_name('name')
                            if name_node:
                                arg_text = self._get_node_text(name_node)
                        elif p.type == 'typed_parameter':
                            # Typed parameter: def foo(x: int)
                            name_node = p.child_by_field_name('name')
                            if name_node:
                                arg_text = self._get_node_text(name_node)
                        elif p.type == 'typed_default_parameter':
                            # Typed parameter with default: def foo(x: int = 5) or def foo(x: str = typer.Argument(...))
                            name_node = p.child_by_field_name('name')
                            if name_node:
                                arg_text = self._get_node_text(name_node)
                        elif p.type == 'list_splat_pattern' or p.type == 'dictionary_splat_pattern':
                            # *args or **kwargs
                            arg_text = self._get_node_text(p)
                        
                        if arg_text:
                            args.append(arg_text)

                func_data = {
                    "name": name,
                    "line_number": node.start_point[0] + 1,
                    "end_line": func_node.end_point[0] + 1,
                    "args": args,
                    "cyclomatic_complexity": self._calculate_complexity(func_node),
                    "context": context,
                    "context_type": context_type,
                    "class_context": class_context,
                    "decorators": [d for d in decorators if d],
                    "lang": self.language_name,
                    "is_dependency": False,
                }

                if self.index_source:
                    func_data["source"] = self._get_node_text(func_node)
                    func_data["docstring"] = self._get_docstring(body_node)

                functions.append(func_data)
        return functions

    def _find_classes(self, root_node, index_source: bool = False):
        classes = []
        query_str = PY_QUERIES['classes']
        for match in execute_query(self.language, query_str, root_node):
            capture_name = match[1]
            node = match[0]

            if capture_name == 'name':
                class_node = node.parent
                name = self._get_node_text(node)
                body_node = class_node.child_by_field_name('body')
                superclasses_node = class_node.child_by_field_name('superclasses')
                
                bases = []
                if superclasses_node:
                    bases = [self._get_node_text(child) for child in superclasses_node.children if child.type in ('identifier', 'attribute')]

                decorators = [self._get_node_text(child) for child in class_node.children if child.type == 'decorator']

                context, _, _ = self._get_parent_context(class_node)

                class_data = {
                    "name": name,
                    "line_number": node.start_point[0] + 1,
                    "end_line": class_node.end_point[0] + 1,
                    "bases": [b for b in bases if b],
                    "context": context,
                    "decorators": [d for d in decorators if d],
                    "lang": self.language_name,
                    "is_dependency": False,
                }
                if self.index_source:
                    class_data["source"] = self._get_node_text(class_node)
                    class_data["docstring"] = self._get_docstring(body_node)

                classes.append(class_data)
        return classes

    def _find_imports(self, root_node):
        imports = []
        seen_modules = set()
        query_str = PY_QUERIES['imports']
        for node, capture_name in execute_query(self.language, query_str, root_node):
            if capture_name in ('import', 'from_import_stmt'):
                # For 'import_statement'
                if capture_name == 'import':
                    node_text = self._get_node_text(node)
                    alias = None
                    if ' as ' in node_text:
                        parts = node_text.split(' as ')
                        full_name = parts[0].strip()
                        alias = parts[1].strip()
                    else:
                        full_name = node_text.strip()

                    if full_name in seen_modules:
                        continue
                    seen_modules.add(full_name)

                    import_data = {
                        "name": full_name,
                        "full_import_name": full_name,
                        "line_number": node.start_point[0] + 1,
                        "alias": alias,
                        "context": self._get_parent_context(node)[:2],
                        "lang": self.language_name,
                        "is_dependency": False,
                    }
                    imports.append(import_data)
                # For 'import_from_statement'
                elif capture_name == 'from_import_stmt':
                    module_name_node = node.child_by_field_name('module_name')
                    if not module_name_node: continue
                    
                    module_name = self._get_node_text(module_name_node)
                    
                    # Handle 'from ... import ...'
                    import_list_node = node.child_by_field_name('name')
                    if import_list_node:
                        for child in import_list_node.children:
                            imported_name = None
                            alias = None
                            if child.type == 'aliased_import':
                                name_node = child.child_by_field_name('name')
                                alias_node = child.child_by_field_name('alias')
                                if name_node: imported_name = self._get_node_text(name_node)
                                if alias_node: alias = self._get_node_text(alias_node)
                            elif child.type == 'dotted_name' or child.type == 'identifier':
                                imported_name = self._get_node_text(child)
                            
                            if imported_name:
                                full_import_name = f"{module_name}.{imported_name}"
                                if full_import_name in seen_modules:                                                                                                
                                    continue                                                                                                                        
                                seen_modules.add(full_import_name) 
                                imports.append({
                                    "name": imported_name,
                                    "full_import_name": full_import_name,
                                    "line_number": child.start_point[0] + 1,
                                    "alias": alias,
                                    "context": self._get_parent_context(child)[:2],
                                    "lang": self.language_name,
                                    "is_dependency": False,
                                })

        return imports

    def _find_calls(self, root_node):
        calls = []
        
        # First, find all direct function calls
        query_str = PY_QUERIES['calls']
        for node, capture_name in execute_query(self.language, query_str, root_node):
            if capture_name == 'name':
                call_node = node.parent if node.parent.type == 'call' else node.parent.parent
                full_call_node = call_node.child_by_field_name('function')
                
                args = []
                arguments_node = call_node.child_by_field_name('arguments')
                if arguments_node:
                    for arg in arguments_node.children:
                        arg_text = self._get_node_text(arg)
                        if arg_text and arg_text not in ('(', ')', ','):
                            args.append(arg_text)

                call_data = {
                    "name": self._get_node_text(node),
                    "full_name": self._get_node_text(full_call_node),
                    "line_number": node.start_point[0] + 1,
                    "args": args,
                    "inferred_obj_type": None,
                    "context": self._get_parent_context(node),
                    "class_context": self._get_parent_context(node, types=('class_definition',))[:2],
                    "lang": self.language_name,
                    "is_dependency": False,
                }
                calls.append(call_data)
        
        # Second, find dictionary-based method references (indirect calls)
        # This handles patterns like: tool_map = {"name": self.method, ...}
        # followed by: handler = tool_map.get(name); handler()
        dict_method_calls = self._find_dict_method_references(root_node)
        calls.extend(dict_method_calls)
        
        return calls
    
    def _find_dict_method_references(self, root_node):
        """
        Detects indirect function calls through dictionary mappings.
        
        Example pattern:
            tool_map = {
                "add_code": self.add_code_to_graph_tool,
                "find_code": self.find_code_tool,
            }
            handler = tool_map.get(tool_name)
            if handler:
                handler(**args)
        
        This creates CALLS relationships from the context function to all
        methods referenced in the dictionary.
        """
        calls = []
        query_str = PY_QUERIES.get('dict_method_refs')
        if not query_str:
            return calls
        
        # Track dictionaries that contain method references
        dict_assignments = {}  # dict_var_name -> list of method references
        
        for node, capture_name in execute_query(self.language, query_str, root_node):
            if capture_name == 'method_ref':
                # Found a method reference in a dictionary value
                # Navigate up to find the assignment
                dict_node = node.parent  # pair node
                while dict_node and dict_node.type != 'dictionary':
                    dict_node = dict_node.parent
                
                if dict_node:
                    # Find the assignment node
                    assignment_node = dict_node.parent
                    if assignment_node and assignment_node.type == 'assignment':
                        # Get the variable name being assigned
                        left_node = assignment_node.child_by_field_name('left')
                        if left_node:
                            var_name = self._get_node_text(left_node)
                            method_ref = self._get_node_text(node)
                            
                            # Extract just the method name (remove 'self.')
                            method_name = method_ref.split('.')[-1] if '.' in method_ref else method_ref
                            
                            if var_name not in dict_assignments:
                                dict_assignments[var_name] = {
                                    'methods': [],
                                    'context': self._get_parent_context(assignment_node),
                                    'line_number': assignment_node.start_point[0] + 1
                                }
                            
                            dict_assignments[var_name]['methods'].append({
                                'name': method_name,
                                'full_name': method_ref,
                                'line_number': node.start_point[0] + 1
                            })
        
        # Now create call relationships for each method in the dictionaries
        # The context is the function where the dictionary is defined
        for dict_var, data in dict_assignments.items():
            context, context_type, context_line = data['context']
            class_context, _, _ = (None, None, None)
            
            for method_info in data['methods']:
                call_data = {
                    "name": method_info['name'],
                    "full_name": method_info['full_name'],
                    "line_number": method_info['line_number'],
                    "args": [],  # We don't know the args at this point
                    "inferred_obj_type": None,
                    "context": (context, context_type, context_line),
                    "class_context": (class_context, None),
                    "lang": self.language_name,
                    "is_dependency": False,
                    "is_indirect_call": True,  # Mark as indirect for debugging
                }
                calls.append(call_data)
        
        return calls

    def _find_variables(self, root_node):
        variables = []
        query_str = PY_QUERIES['variables']
        for match in execute_query(self.language, query_str, root_node):
            capture_name = match[1]
            node = match[0]

            if capture_name == 'name':
                assignment_node = node.parent

                # Skip lambda assignments, they are handled by _find_lambda_assignments
                right_node = assignment_node.child_by_field_name('right')
                if right_node and right_node.type == 'lambda':
                    continue

                name = self._get_node_text(node)
                value = self._get_node_text(right_node) if right_node else None
                
                type_node = assignment_node.child_by_field_name('type')
                type_text = self._get_node_text(type_node) if type_node else None

                context, _, _ = self._get_parent_context(node)
                class_context, _, _ = self._get_parent_context(node, types=('class_definition',))

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

def pre_scan_python(files: list[Path], parser_wrapper) -> dict:
    """Scans Python files to create a map of class/function names to their file paths."""
    imports_map = {}
    query_str = """
        (class_definition name: (identifier) @name)
        (function_definition name: (identifier) @name)
    """
    
    for file_path in files:
        temp_py_file = None
        try:
            source_to_parse = ""
            if file_path.suffix == '.ipynb':
                with open(file_path, 'r', encoding='utf-8') as f:
                    notebook_node = nbformat.read(f, as_version=4)
                exporter = PythonExporter()
                python_code, _ = exporter.from_notebook_node(notebook_node)
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py', encoding='utf-8') as tf:
                    tf.write(python_code)
                    temp_py_file = Path(tf.name)
                with open(temp_py_file, "r", encoding="utf-8") as f:
                    source_to_parse = f.read()
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    source_to_parse = f.read()

            tree = parser_wrapper.parser.parse(bytes(source_to_parse, "utf8"))
            
            for capture, _ in execute_query(parser_wrapper.language, query_str, tree.root_node):
                name = capture.text.decode('utf-8')
                if name not in imports_map:
                    imports_map[name] = []
                imports_map[name].append(str(file_path.resolve()))
        except Exception as e:
            warning_logger(f"Tree-sitter pre-scan failed for {file_path}: {e}")
        finally:
            if temp_py_file and temp_py_file.exists():
                os.remove(temp_py_file)
    return imports_map