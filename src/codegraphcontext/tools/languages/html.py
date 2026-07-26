# src/codegraphcontext/tools/languages/html.py
from pathlib import Path
from typing import Any, Dict
from codegraphcontext.utils.tree_sitter_manager import execute_query

HTML_QUERIES = {
    "tags": """
        (element
            (start_tag
                (tag_name) @tag_name
            )
        ) @tag_node
    """,
    "attributes": """
        (attribute
            (attribute_name) @attr_name
            (quoted_attribute_value (attribute_value) @attr_value)
        ) @attr_node
    """,
    "scripts": """
        (script_element) @script
    """,
    "links": """
        (link_element) @link
    """
}

class HTMLTreeSitterParser:
    """A parser for HTML files using tree-sitter."""

    def __init__(self, generic_parser_wrapper):
        self.generic_parser_wrapper = generic_parser_wrapper
        self.language = generic_parser_wrapper.language
        self.parser = generic_parser_wrapper.parser
        self.language_name = "html"

    def _get_node_text(self, node) -> str:
        return node.text.decode('utf-8')

    def parse(self, path: Path, is_dependency: bool = False, index_source: bool = False) -> Dict[str, Any]:
        """Parses an HTML file and returns its structure."""
        with open(path, "r", encoding="utf-8") as f:
            source_code = f.read()

        tree = self.parser.parse(bytes(source_code, "utf8"))
        root_node = tree.root_node

        tags = []
        classes = {}  # name -> line number of first occurrence
        ids = {}  # name -> line number of first occurrence
        imports = []

        # Find tags, classes, and ids
        # We can use a simpler traversal or queries
        query_str = """
            (element
                (start_tag
                    (tag_name) @tag_name
                )
            ) @element
            
            (attribute
                (attribute_name) @attr_name
                (quoted_attribute_value (attribute_value) @attr_value)
            ) @attribute
        """
        
        for node, capture_name in execute_query(self.language, query_str, root_node):
            if capture_name == 'tag_name':
                tag_name = self._get_node_text(node).lower()
                tags.append({
                    "name": tag_name,
                    "line_number": node.start_point[0] + 1
                })
            elif capture_name == 'attr_name':
                attr_name = self._get_node_text(node).lower()
                if attr_name == 'class':
                    # Attribute value is the next capture
                    pass 
            elif capture_name == 'attr_value':
                parent_attr = node.parent.parent # quoted_attribute_value -> attribute
                # The HTML grammar exposes no 'name' field on attribute nodes;
                # locate the attribute_name child by type instead.
                attr_name_node = next(
                    (c for c in parent_attr.children if c.type == 'attribute_name'), None
                )
                if attr_name_node:
                    attr_name = self._get_node_text(attr_name_node).lower()
                    attr_value = self._get_node_text(node)
                    line_number = node.start_point[0] + 1
                    if attr_name == 'class':
                        for cls in attr_value.split():
                            classes.setdefault(cls, line_number)
                    elif attr_name == 'id':
                        ids.setdefault(attr_value, line_number)
                    elif attr_name == 'src' or attr_name == 'href':
                        # Check tag name
                        tag_node = parent_attr.parent # start_tag
                        if tag_node:
                            tag_name_node = next(
                                (c for c in tag_node.children if c.type == 'tag_name'), None
                            )
                            if tag_name_node:
                                tag_name = self._get_node_text(tag_name_node).lower()
                                if tag_name in ('script', 'link', 'img', 'a'):
                                    imports.append({
                                        "name": attr_value,
                                        "source": attr_value,
                                        "line_number": node.start_point[0] + 1,
                                        "type": tag_name
                                    })

        # Standardized return format
        # HTML doesn't have "functions" or "classes" in the programming sense,
        # but we can map tags to "functions" or similar if we want them searchable.
        # For now, let's just return them in a way that CodeFinder can use.
        
        return {
            "path": str(path),
            "functions": [], # Maybe map components here?
            "classes": [
                {"name": c, "type": "css_class", "line_number": line,
                 "lang": self.language_name, "is_dependency": is_dependency}
                for c, line in classes.items()
            ],
            "variables": [
                {"name": i, "type": "html_id", "line_number": line,
                 "lang": self.language_name, "is_dependency": is_dependency}
                for i, line in ids.items()
            ],
            "imports": imports,
            "function_calls": [],
            "is_dependency": is_dependency,
            "lang": self.language_name,
            "tags": tags # Custom field
        }

def pre_scan_html(files: list[Path], parser_wrapper) -> dict:
    return {}
