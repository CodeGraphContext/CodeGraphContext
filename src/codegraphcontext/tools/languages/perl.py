from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List
import logging
from codegraphcontext.utils.debug_log import debug_log, info_logger, error_logger, warning_logger
from codegraphcontext.utils.tree_sitter_manager import execute_query

PERL_QUERIES = {
    "functions": """
        (subroutine_declaration_statement
            name: (bareword) @name
        ) @function_node
    """,
    "classes": """
        (package_statement
            name: (package) @name
        ) @class
    """,
    "imports": """
        (use_statement
            (package) @import
        ) @import_node
    """,
    "calls": """
        (method_call_expression
            method: (method) @name
        ) @call
        (ambiguous_function_call_expression
            function: (function) @name
        ) @call
        (function_call_expression
            function: (function) @name
        ) @call
    """,
    "variables": """
        (variable_declaration
            [
                (scalar (varname) @name)
                (array (varname) @name)
                (hash (varname) @name)
            ]
        ) @variable
    """,
}

class PerlTreeSitterParser:
    """A Perl-specific parser using tree-sitter, encapsulating language-specific logic."""

    def __init__(self, generic_parser_wrapper):
        self.generic_parser_wrapper = generic_parser_wrapper
        self.language_name = "perl"
        self.language = generic_parser_wrapper.language
        self.parser = generic_parser_wrapper.parser
        self.index_source = False

    def _get_node_text(self, node) -> str:
        if not node: return ""
        return node.text.decode('utf-8')

    def _get_parent_context(self, node, types=('subroutine_declaration_statement', 'package_statement')):
        curr = node.parent
        while curr:
            if curr.type in types:
                name_node = curr.child_by_field_name('name')
                return self._get_node_text(name_node) if name_node else None, curr.type, curr.start_point[0] + 1
            curr = curr.parent
        return None, None, None

    def _calculate_complexity(self, node):
        complexity_nodes = {
            "if_statement", "unless_statement", "for_statement", "foreach_statement",
            "while_statement", "until_statement", "conditional_expression",
            "logical_expression", "binary_expression"
        }
        count = 1
        
        def traverse(n):
            nonlocal count
            if n.type in complexity_nodes:
                if n.type == "binary_expression":
                    op_node = None
                    for child in n.children:
                        if child.type in ("&&", "||") or (hasattr(child, 'text') and child.text and child.text.decode("utf-8") in ("&&", "||", "and", "or")):
                            op_node = child
                            break
                    if not op_node:
                        return
                count += 1
            for child in n.children:
                traverse(child)
        
        traverse(node)
        return count

    def parse(self, path: Path, is_dependency: bool = False, index_source: bool = False) -> Dict:
        """Parses a Perl file and returns its structure in a standardized dictionary format."""
        self.index_source = index_source
        try:
            with open(path, "r", encoding="utf-8", errors='ignore') as f:
                source_code = f.read()
            
            tree = self.parser.parse(bytes(source_code, "utf8"))
            root_node = tree.root_node

            functions = self._find_functions(root_node)
            classes = self._find_classes(root_node)
            imports = self._find_imports(root_node)
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
            error_logger(f"Failed to parse Perl file {path}: {e}")
            return {"path": str(path), "error": str(e)}

    def _find_functions(self, root_node):
        functions = []
        seen_nodes = set()
        query_str = PERL_QUERIES['functions']
        
        for node, capture_name in execute_query(self.language, query_str, root_node):
            if capture_name == "function_node":
                node_id = (node.start_byte, node.end_byte)
                if node_id in seen_nodes: continue
                seen_nodes.add(node_id)

                name_node = node.child_by_field_name('name')
                if not name_node: continue
                
                name = self._get_node_text(name_node)
                body_node = node.child_by_field_name('body')

                context, context_type, context_line = self._get_parent_context(node)
                
                func_data = {
                    "name": name,
                    "line_number": node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1,
                    "args": [], # Perl args are dynamic, usually @_ processing
                    "cyclomatic_complexity": self._calculate_complexity(body_node) if body_node else 1,
                    "context": context,
                    "context_type": context_type,
                    "lang": self.language_name,
                    "is_dependency": False,
                }
                if self.index_source:
                    func_data["source"] = self._get_node_text(node)
                
                functions.append(func_data)
        return functions

    def _find_classes(self, root_node):
        classes = []
        query_str = PERL_QUERIES['classes']
        for node, capture_name in execute_query(self.language, query_str, root_node):
            name_node = node.child_by_field_name('name')
            if not name_node: continue
            
            name = self._get_node_text(name_node)
            classes.append({
                "name": name,
                "line_number": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "bases": [], # Bases are often set via 'use base' or 'use parent'
                "lang": self.language_name,
                "is_dependency": False,
            })
        return classes

    def _find_imports(self, root_node):
        imports = []
        seen_nodes = set()
        query_str = PERL_QUERIES['imports']
        for node, capture_name in execute_query(self.language, query_str, root_node):
            if capture_name == "import":
                node_id = (node.start_byte, node.end_byte)
                if node_id in seen_nodes: continue
                seen_nodes.add(node_id)

                import_name = self._get_node_text(node)
                line_number = node.start_point[0] + 1
                
                # Try to get line number from parent use_statement if possible
                if node.parent and node.parent.type == "use_statement":
                    line_number = node.parent.start_point[0] + 1

                imports.append({
                    "name": import_name,
                    "full_import_name": import_name,
                    "line_number": line_number,
                    "alias": None,
                    "lang": self.language_name,
                    "is_dependency": False,
                })
        return imports

    def _find_calls(self, root_node):
        calls = []
        query_str = PERL_QUERIES['calls']
        for node, capture_name in execute_query(self.language, query_str, root_node):
            name = self._get_node_text(node)
            context, context_type, context_line = self._get_parent_context(node)
            
            calls.append({
                "name": name,
                "full_name": name,
                "line_number": node.start_point[0] + 1,
                "args": [],
                "context": (context, context_type, context_line),
                "lang": self.language_name,
                "is_dependency": False,
            })
        return calls

    def _find_variables(self, root_node):
        variables = []
        query_str = PERL_QUERIES['variables']
        for node, capture_name in execute_query(self.language, query_str, root_node):
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

def pre_scan_perl(files: List[Path], parser_wrapper) -> Dict[str, List[str]]:
    """Scans Perl files to create a map of package/subroutine names to their file paths."""
    name_to_files = {}
    query_str = """
        [
            (package_statement name: (package) @name)
            (subroutine_declaration_statement name: (bareword) @name)
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
            warning_logger(f"Error pre-scanning Perl file {path}: {e}")
    return name_to_files
