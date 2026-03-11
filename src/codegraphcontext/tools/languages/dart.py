from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List
import logging
from codegraphcontext.utils.debug_log import debug_log, info_logger, error_logger, warning_logger
from codegraphcontext.utils.tree_sitter_manager import execute_query

DART_QUERIES = {
    "functions": """
        (function_signature
            name: (identifier) @name
            (formal_parameter_list) @params
        ) @function_node
        (constructor_signature
            name: (identifier) @name
            (formal_parameter_list) @params
        ) @function_node
    """,
    "classes": """
        [
            (class_definition name: (identifier) @name)
            (mixin_declaration name: (identifier) @name)
            (extension_declaration name: (identifier) @name)
            (enum_declaration name: (identifier) @name)
        ] @class
    """,
    "imports": """
        (library_import) @import
        (library_export) @import
    """,
    "calls": """
        (expression_statement
            (identifier) @name
        ) @call
        (selector
            (argument_part (arguments))
        ) @call
    """,
    "variables": """
        (local_variable_declaration
            (initialized_variable_definition
                name: (identifier) @name
            )
        ) @variable
        (declaration
            (initialized_identifier_list
                (initialized_identifier
                    (identifier) @name
                )
            )
        ) @variable
    """,
}

class DartTreeSitterParser:
    """A Dart-specific parser using tree-sitter, encapsulating language-specific logic."""

    def __init__(self, generic_parser_wrapper):
        self.generic_parser_wrapper = generic_parser_wrapper
        self.language_name = "dart"
        self.language = generic_parser_wrapper.language
        self.parser = generic_parser_wrapper.parser
        self.index_source = False

    def _get_node_text(self, node) -> str:
        if not node: return ""
        return node.text.decode('utf-8')

    def _get_parent_context(self, node, types=('function_signature', 'class_definition', 'mixin_declaration', 'extension_declaration')):
        curr = node.parent
        while curr:
            if curr.type in types:
                name_node = curr.child_by_field_name('name')
                return self._get_node_text(name_node) if name_node else None, curr.type, curr.start_point[0] + 1
            curr = curr.parent
        return None, None, None

    def _calculate_complexity(self, node):
        complexity_nodes = {
            "if_statement", "for_statement", "while_statement", "do_statement",
            "switch_statement", "switch_case", "if_element", "for_element",
            "conditional_expression", "binary_expression", "catch_clause"
        }
        count = 1
        
        def traverse(n):
            nonlocal count
            if n.type in complexity_nodes:
                if n.type == "binary_expression":
                    op = n.child_by_field_name("operator")
                    if op and self._get_node_text(op) in ("&&", "||"):
                        count += 1
                else:
                    count += 1
            for child in n.children:
                traverse(child)
        
        traverse(node)
        return count

    def parse(self, path: Path, is_dependency: bool = False, index_source: bool = False) -> Dict:
        """Parses a Dart file and returns its structure in a standardized dictionary format."""
        self.index_source = index_source
        try:
            with open(path, "r", encoding="utf-8", errors='ignore') as f:
                source_code = f.read()
            
            tree = self.parser.parse(bytes(source_code, "utf8"))
            root_node = tree.root_node

            functions = self._find_functions(root_node)
            classes = self._find_classes(root_node)
            imports = self._find_imports(root_node, source_code)
            function_calls = self._find_calls(root_node)
            variables = self._find_variables(root_node)

            return {
                "path": str(path),
                "functions": functions,
                "classes": classes,
                "variables": variables,
                "imports": imports,
                "function_calls": function_calls,
                "is_dependency": is_dependency,
                "lang": self.language_name,
            }
        except Exception as e:
            error_logger(f"Failed to parse Dart file {path}: {e}")
            return {"path": str(path), "error": str(e)}

    def _find_functions(self, root_node):
        functions = []
        seen_nodes = set()
        query_str = DART_QUERIES['functions']
        
        for node, capture_name in execute_query(self.language, query_str, root_node):
            if capture_name == "function_node":
                node_id = (node.start_byte, node.end_byte)
                if node_id in seen_nodes: continue
                seen_nodes.add(node_id)

                name_node = node.child_by_field_name('name')
                if not name_node: continue
                
                name = self._get_node_text(name_node)
                params_node = node.child_by_field_name('parameters') or node.child_by_field_name('formal_parameter_list')
                
                args = []
                if params_node:
                    for child in params_node.children:
                        if child.type == 'formal_parameter':
                            # Extract parameter name
                            # can be 'int x', 'var x', 'final x', 'x', 'this.x'
                            p_name = self._extract_param_name(child)
                            if p_name: args.append(p_name)

                # Find body to get complexity and end_line
                # In Dart, body is often a sibling of signature
                body_node = None
                parent = node.parent
                if parent:
                    # Look for function_body among siblings after the signature
                    found_sig = False
                    for child in parent.children:
                        if child == node:
                            found_sig = True
                            continue
                        if found_sig:
                            if child.type == 'function_body':
                                body_node = child
                                break
                            elif child.type in ('function_signature', 'method_signature', 'declaration', 'class_definition'):
                                # Hit another signature or declaration, stop looking
                                break

                context, context_type, context_line = self._get_parent_context(node)
                # Check if it's in a class
                class_context = None
                curr = node.parent
                while curr:
                    if curr.type == 'class_definition':
                        cn = curr.child_by_field_name('name')
                        class_context = self._get_node_text(cn) if cn else None
                        break
                    curr = curr.parent

                func_data = {
                    "name": name,
                    "line_number": node.start_point[0] + 1,
                    "end_line": (body_node or node).end_point[0] + 1,
                    "args": args,
                    "cyclomatic_complexity": self._calculate_complexity(body_node) if body_node else 1,
                    "context": context,
                    "context_type": context_type,
                    "class_context": class_context,
                    "lang": self.language_name,
                    "is_dependency": False,
                }
                if self.index_source:
                    func_data["source"] = self._get_node_text(node) + (self._get_node_text(body_node) if body_node else "")
                
                functions.append(func_data)
        return functions

    def _extract_param_name(self, param_node) -> Optional[str]:
        # formal_parameter -> normal_parameter -> ... -> identifier
        # or formal_parameter -> constructor_param -> this.identifier
        def find_id(n):
            if n.type == 'identifier':
                return self._get_node_text(n)
            for child in n.children:
                res = find_id(child)
                if res: return res
            return None
        return find_id(param_node)

    def _find_classes(self, root_node):
        classes = []
        query_str = DART_QUERIES['classes']
        for node, capture_name in execute_query(self.language, query_str, root_node):
            if capture_name == "class":
                name_node = node.child_by_field_name('name')
                if not name_node: continue
                
                name = self._get_node_text(name_node)
                
                # Bases (implements, extends, with)
                bases = []
                # This is simplified, can be improved by navigating children
                for child in node.children:
                    if child.type in ('superclass', 'interfaces', 'mixins'):
                        for sub in child.children:
                            if sub.type in ('type_identifier', 'type_not_void'):
                                bases.append(self._get_node_text(sub))

                class_data = {
                    "name": name,
                    "line_number": node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1,
                    "bases": bases,
                    "lang": self.language_name,
                    "is_dependency": False,
                }
                if self.index_source:
                    class_data["source"] = self._get_node_text(node)
                
                classes.append(class_data)
        return classes

    def _find_imports(self, root_node, source_code):
        imports = []
        query_str = DART_QUERIES['imports']
        for node, capture_name in execute_query(self.language, query_str, root_node):
            if capture_name == "import":
                # Find URI
                uri_node = None
                def find_uri(n):
                    nonlocal uri_node
                    if n.type == 'uri':
                        uri_node = n
                        return
                    for child in n.children:
                        find_uri(child)
                        if uri_node: return
                
                find_uri(node)
                if uri_node:
                    uri_text = self._get_node_text(uri_node).strip("'\"")
                    
                    # Handle 'as' alias
                    alias = None
                    for child in node.children:
                        if child.type == 'import_specification':
                            for sub in child.children:
                                if sub.type == 'prefix':
                                    alias_node = sub.child_by_field_name('identifier')
                                    if alias_node:
                                        alias = self._get_node_text(alias_node)
                    
                    imports.append({
                        "name": uri_text,
                        "full_import_name": uri_text,
                        "line_number": node.start_point[0] + 1,
                        "alias": alias,
                        "lang": self.language_name,
                        "is_dependency": False,
                    })
        return imports

    def _find_calls(self, root_node):
        calls = []
        seen_calls = set()
        query_str = DART_QUERIES['calls']
        
        for node, capture_name in execute_query(self.language, query_str, root_node):
            if capture_name in ("name", "call"):
                # Ensure we are at the right node level
                target_node = node
                if capture_name == "call":
                    # For call capture, find the name identifier
                    # selector -> argument_part -> arguments
                    # we want the name before this selector
                    pass 

                # Deduplicate by start byte
                node_id = target_node.start_byte
                if node_id in seen_calls: continue
                seen_calls.add(node_id)

                name = self._get_node_text(target_node)
                
                # Find arguments
                args = []
                # Logic to find arguments node from selector or expression_statement
                
                context, context_type, context_line = self._get_parent_context(target_node)
                
                calls.append({
                    "name": name,
                    "full_name": name, # Simplified for now
                    "line_number": target_node.start_point[0] + 1,
                    "args": args,
                    "context": (context, context_type, context_line),
                    "lang": self.language_name,
                    "is_dependency": False,
                })
        return calls

    def _find_variables(self, root_node):
        variables = []
        query_str = DART_QUERIES['variables']
        for node, capture_name in execute_query(self.language, query_str, root_node):
            if capture_name == "name":
                name = self._get_node_text(node)
                context, _, _ = self._get_parent_context(node)
                
                variables.append({
                    "name": name,
                    "line_number": node.start_point[0] + 1,
                    "context": context,
                    "lang": self.language_name,
                    "is_dependency": False,
                })
        return variables

def pre_scan_dart(files: List[Path], parser_wrapper) -> Dict[str, List[str]]:
    """Scans Dart files to create a map of class/function names to their file paths."""
    name_to_files = {}
    query_str = """
        [
            (class_definition name: (identifier) @name)
            (mixin_declaration name: (identifier) @name)
            (extension_declaration name: (identifier) @name)
            (function_signature name: (identifier) @name)
        ]
    """
    for path in files:
        try:
            with open(path, "r", encoding="utf-8", errors='ignore') as f:
                content = f.read()
            tree = parser_wrapper.parser.parse(bytes(content, "utf8"))
            for node, _ in execute_query(parser_wrapper.language, query_str, tree.root_node):
                name = node.text.decode('utf-8')
                if name not in name_to_files:
                    name_to_files[name] = []
                name_to_files[name].append(str(path.resolve()))
        except Exception as e:
            warning_logger(f"Error pre-scanning Dart file {path}: {e}")
    return name_to_files
