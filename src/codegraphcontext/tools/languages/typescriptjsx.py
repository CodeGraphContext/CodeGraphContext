from pathlib import Path
from typing import Dict, Any
from codegraphcontext.utils.debug_log import warning_logger
from codegraphcontext.utils.tree_sitter_manager import execute_query
from .typescript import TypescriptTreeSitterParser


def pre_scan_typescript(files: list[Path], parser_wrapper) -> dict:
    """
    Scans TypeScript JSX (.tsx) files to create a map of class/function names to their file paths.
    Reuses the logic from TypeScript parser, but can be extended for JSX-specific extraction.
    """
    imports_map = {}
    query_str = """
        (class_declaration name: (type_identifier) @name)
        (function_declaration name: (identifier) @name)
        (variable_declarator name: (identifier) @name value: (function_expression))
        (variable_declarator name: (identifier) @name value: (arrow_function))
        (method_definition name: (property_identifier) @name)
        (interface_declaration name: (type_identifier) @name)
        (type_alias_declaration name: (type_identifier) @name)
    """

    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                tree = parser_wrapper.parser.parse(bytes(f.read(), "utf8"))

            file_path_str = str(path.resolve())
            for capture, _ in execute_query(
                parser_wrapper.language, query_str, tree.root_node
            ):
                name = capture.text.decode("utf-8")
                if name not in imports_map:
                    imports_map[name] = []
                if file_path_str not in imports_map[name]:
                    imports_map[name].append(file_path_str)
        except Exception as e:
            warning_logger(f"Tree-sitter pre-scan failed for {path}: {e}")
    return imports_map


class TypescriptJSXTreeSitterParser(TypescriptTreeSitterParser):
    """
    A parser for TypeScript JSX (.tsx) files.
    """

    def __init__(self, generic_parser_wrapper):
        super().__init__(generic_parser_wrapper)
        self.language_name = "tsx"
        self.jsx_enabled = True

    def parse(
        self, path: Path, is_dependency: bool = False, index_source: bool = False
    ) -> Dict[str, Any]:
        """
        Parse a .tsx file, reusing TypeScript logic and ensuring JSX nodes are handled.
        Indexes components, functions, imports, and exports.
        """
        self.index_source = index_source
        with open(path, "r", encoding="utf-8") as f:
            source_code = f.read()
        tree = self.parser.parse(bytes(source_code, "utf8"))
        root_node = tree.root_node

        # Reuse TypeScript logic for functions, classes, interfaces, type aliases, imports, calls, variables
        functions = self._find_functions(root_node)
        classes = self._find_classes(root_node)
        interfaces = self._find_interfaces(root_node)
        type_aliases = self._find_type_aliases(root_node)
        imports = self._find_imports(root_node)
        function_calls = self._find_calls(root_node)
        variables = self._find_variables(root_node)

        # Index React components (function and class components)
        components = self._find_react_components(root_node)

        return {
            "path": str(path),
            "functions": functions,
            "classes": classes,
            "interfaces": interfaces,
            "type_aliases": type_aliases,
            "variables": variables,
            "imports": imports,
            "function_calls": function_calls,
            "components": components,
            "is_dependency": is_dependency,
            "lang": self.language_name,
        }

    def _find_react_components(self, root_node):
        """
        Find React components in .tsx files (function and class components).
        """
        components = []
        query_str = """
            (class_declaration name: (type_identifier) @name)
            (variable_declarator name: (identifier) @name value: (arrow_function))
            (variable_declarator name: (identifier) @name value: (function_expression))
            (function_declaration name: (identifier) @name)
        """
        for node, capture_name in execute_query(self.language, query_str, root_node):
            if capture_name == "name":
                name = node.text.decode("utf-8")
                line_number = node.start_point[0] + 1
                component_data = {
                    "name": name,
                    "line_number": line_number,
                    "type": "component",
                    "lang": self.language_name,
                }

                if self.index_source:
                    parent = node.parent
                    component_data["source"] = parent.text.decode("utf-8")

                components.append(component_data)
        return components
