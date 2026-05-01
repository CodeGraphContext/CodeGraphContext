from pathlib import Path
from typing import Any, Dict
from codegraphcontext.utils.tree_sitter_manager import execute_query

class CSSTreeSitterParser:
    """A parser for CSS files using tree-sitter."""

    def __init__(self, generic_parser_wrapper):
        self.generic_parser_wrapper = generic_parser_wrapper
        self.language = generic_parser_wrapper.language
        self.parser = generic_parser_wrapper.parser
        self.language_name = "css"

    def _get_node_text(self, node) -> str:
        return node.text.decode('utf-8')

    def parse(self, path: Path, is_dependency: bool = False, index_source: bool = False) -> Dict[str, Any]:
        """Parses a CSS file and returns its structure."""
        with open(path, "r", encoding="utf-8") as f:
            source_code = f.read()

        tree = self.parser.parse(bytes(source_code, "utf8"))
        root_node = tree.root_node

        selectors = []
        imports = []
        variables = []

        query_str = """
            (class_selector (class_name) @class_name) @selector
            (id_selector (id_name) @id_name) @selector
            (tag_name) @tag_name
            (import_statement (string_value) @import_path)
            (variable_declaration (variable_name) @var_name (value) @var_value)
        """

        for node, capture_name in execute_query(self.language, query_str, root_node):
            if capture_name == 'class_name':
                selectors.append({
                    "name": "." + self._get_node_text(node),
                    "type": "class",
                    "line_number": node.start_point[0] + 1
                })
            elif capture_name == 'id_name':
                selectors.append({
                    "name": "#" + self._get_node_text(node),
                    "type": "id",
                    "line_number": node.start_point[0] + 1
                })
            elif capture_name == 'tag_name':
                selectors.append({
                    "name": self._get_node_text(node),
                    "type": "tag",
                    "line_number": node.start_point[0] + 1
                })
            elif capture_name == 'import_path':
                imports.append({
                    "name": self._get_node_text(node).strip('\'"'),
                    "source": self._get_node_text(node).strip('\'"'),
                    "line_number": node.start_point[0] + 1
                })
            elif capture_name == 'var_name':
                variables.append({
                    "name": self._get_node_text(node),
                    "value": None, # Value captured separately
                    "line_number": node.start_point[0] + 1
                })
            elif capture_name == 'var_value':
                if variables:
                    variables[-1]["value"] = self._get_node_text(node)

        return {
            "path": str(path),
            "functions": [{"name": s["name"], "line_number": s["line_number"], "type": s["type"]} for s in selectors],
            "classes": [],
            "variables": variables,
            "imports": imports,
            "function_calls": [],
            "is_dependency": is_dependency,
            "lang": self.language_name,
        }

def pre_scan_css(files: list[Path], parser_wrapper) -> dict:
    return {}
