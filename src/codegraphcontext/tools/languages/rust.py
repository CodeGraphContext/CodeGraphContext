# src/codegraphcontext/tools/languages/rust.py
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import re
from codegraphcontext.utils.debug_log import debug_log, info_logger, error_logger, warning_logger, debug_logger
from codegraphcontext.utils.tree_sitter_manager import execute_query

RUST_QUERIES = {
    "functions": """
        (function_item
            name: (identifier) @name
            parameters: (parameters) @params
        ) @function_node
    """,
    "classes": """
        [
            (struct_item name: (type_identifier) @name)
            (enum_item name: (type_identifier) @name)
            (trait_item name: (type_identifier) @name)
        ] @type_node
    """,
    "imports": """
        (use_declaration) @import
    """,
    "calls": """
        (call_expression
            function: [
                (identifier) @name
                (field_expression field: (field_identifier) @name)
                (scoped_identifier name: (identifier) @name)
            ]
        )
    """,
}

class RustTreeSitterParser:
    """A Rust-specific parser using tree-sitter."""

    def __init__(self, generic_parser_wrapper: Any):
        self.generic_parser_wrapper = generic_parser_wrapper
        self.language_name = "rust"
        self.language = generic_parser_wrapper.language
        self.parser = generic_parser_wrapper.parser

    def _get_node_text(self, node: Any) -> str:
        return node.text.decode("utf-8")

    def parse(self, path: Path, is_dependency: bool = False, index_source: bool = False) -> Dict[str, Any]:
        """Parses a Rust file and returns its structure."""
        self.index_source = index_source
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            source_code = f.read()

        tree = self.parser.parse(bytes(source_code, "utf8"))
        root_node = tree.root_node

        functions = self._find_functions(root_node)
        structs, enums, traits = self._find_types(root_node)
        imports = self._find_imports(root_node)
        function_calls = self._find_calls(root_node)

        return {
            "path": str(path),
            "functions": functions,
            "structs": structs,
            "enums": enums,
            "traits": traits,
            "variables": [],
            "imports": imports,
            "function_calls": function_calls,
            "is_dependency": is_dependency,
            "lang": self.language_name,
        }

    def _get_parent_context(self, node: Any, types: Tuple[str, ...] = ("function_item", "struct_item", "enum_item", "trait_item", "impl_item")) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        curr = node.parent
        while curr:
            if curr.type in types:
                name_node = curr.child_by_field_name("name")
                if not name_node and curr.type == "impl_item":
                    # For impl blocks, use the type name
                    # impl Trait for Type { ... } -> we want Type
                    # impl Type { ... } -> we want Type
                    # Let's find the last type_identifier before the block
                    for child in reversed(curr.children):
                        if child.type == "type_identifier":
                            name_node = child
                            break
                
                return (
                    self._get_node_text(name_node) if name_node else None,
                    curr.type,
                    curr.start_point[0] + 1,
                )
            curr = curr.parent
        return None, None, None

    def _parse_function_args(self, params_node: Any) -> list[Dict[str, Any]]:
        """Helper to parse function arguments from a (parameters) node."""
        args = []
        for param in params_node.named_children:
            arg_info: Dict[str, Any] = {"name": "", "type": None}
            if param.type == "parameter":
                pattern_node = param.child_by_field_name("pattern")
                type_node = param.child_by_field_name("type")
                if pattern_node:
                    arg_info["name"] = self._get_node_text(pattern_node)
                if type_node:
                    arg_info["type"] = self._get_node_text(type_node)
                args.append(arg_info)
            elif param.type == "self_parameter":
                arg_info["name"] = self._get_node_text(param)
                arg_info["type"] = "self"
                args.append(arg_info)
        return args

    def _module_path_for_node(self, node: Any) -> Optional[str]:
        parts: list[str] = []
        curr = node
        while curr:
            if curr.type == "mod_item":
                name_node = curr.child_by_field_name("name")
                if name_node:
                    parts.append(self._get_node_text(name_node))
            curr = curr.parent
        return "::".join(reversed(parts)) if parts else None

    def _find_functions(self, root_node: Any) -> list[Dict[str, Any]]:
        functions = []
        query_str = "(function_item) @f"
        seen_ids: set[int] = set()

        for func_node, cap in execute_query(self.language, query_str, root_node):
            if func_node.id in seen_ids:
                continue
            seen_ids.add(func_node.id)

            name_node = func_node.child_by_field_name("name")
            params_node = func_node.child_by_field_name("parameters")

            if name_node:
                name = self._get_node_text(name_node)
                # Convert args to a list of strings for Neo4j property compatibility
                raw_args = self._parse_function_args(params_node) if params_node else []
                params = []
                for arg in raw_args:
                    arg_str = arg["name"]
                    if arg["type"]:
                        arg_str += f": {arg['type']}"
                    params.append(arg_str)

                module_context = self._module_path_for_node(func_node)
                func_data = {
                    "name": name,
                    "line_number": name_node.start_point[0] + 1,
                    "end_line": func_node.end_point[0] + 1,
                    "params": params,
                    "args": params,
                    "module_context": module_context,
                    "is_extern": False,
                    "lang": self.language_name,
                    "is_dependency": False,
                }

                if self.index_source:
                    func_data["source"] = self._get_node_text(func_node)
                
                functions.append(func_data)

        for node, _ in execute_query(self.language, "(foreign_mod_item) @fm", root_node):
            extern_nodes: list[Any] = []

            def collect_extern_functions(item_node: Any) -> None:
                if item_node.type in ("function_item", "function_signature_item"):
                    extern_nodes.append(item_node)
                    return
                for child in item_node.children:
                    collect_extern_functions(child)

            collect_extern_functions(node)
            for child in extern_nodes:
                if child.id in seen_ids:
                    continue
                seen_ids.add(child.id)
                name_node = child.child_by_field_name("name")
                if not name_node:
                    for sub in child.children:
                        if sub.type == "identifier":
                            name_node = sub
                            break
                if not name_node:
                    continue
                name = self._get_node_text(name_node)
                params_node = child.child_by_field_name("parameters")
                raw_args = self._parse_function_args(params_node) if params_node else []
                params = []
                for arg in raw_args:
                    arg_str = arg["name"]
                    if arg["type"]:
                        arg_str += f": {arg['type']}"
                    params.append(arg_str)
                functions.append({
                    "name": name,
                    "line_number": name_node.start_point[0] + 1,
                    "end_line": child.end_point[0] + 1,
                    "params": params,
                    "args": params,
                    "module_context": self._module_path_for_node(child),
                    "is_extern": True,
                    "lang": self.language_name,
                    "is_dependency": False,
                })

        return functions

    def _find_types(self, root_node: Any) -> Tuple[list, list, list]:
        types_map = {}
        trait_names = set()
        
        # 1. Find all struct, enum, and trait definitions
        query_items = """
        [
            (struct_item) @s
            (enum_item) @e
            (trait_item) @t
        ]
        """
        for item_node, cap in execute_query(self.language, query_items, root_node):
            name_node = item_node.child_by_field_name("name")
            if not name_node:
                for child in item_node.children:
                    if child.type == "type_identifier":
                        name_node = child
                        break
            
            if name_node:
                name = self._get_node_text(name_node)
                bases = []
                # For traits, extract supertraits: trait A: B + C
                if cap == "t":
                    trait_names.add(name)
                    # Tree-sitter-rust: trait_item -> trait_bounds child?
                    # Let's check node children for ':'
                    has_colon = False
                    for child in item_node.children:
                        if child.type == ":":
                            has_colon = True
                        if has_colon and child.type == "trait_bounds":
                            for bound in child.children:
                                if bound.type == "type_identifier":
                                    bases.append(self._get_node_text(bound))

                if cap == "t":
                    category = "trait"
                elif cap == "e":
                    category = "enum"
                else:
                    category = "struct"

                types_map[name] = {
                    "name": name,
                    "line_number": name_node.start_point[0] + 1,
                    "end_line": item_node.end_point[0] + 1,
                    "bases": bases,
                    "type": category
                }
                if self.index_source:
                    types_map[name]["source"] = self._get_node_text(item_node)

        # 2. Find all impl blocks and extract traits as bases
        query_impls = "(impl_item) @i"
        for impl_node, _ in execute_query(self.language, query_impls, root_node):
            identifiers = [c for c in impl_node.children if c.type == "type_identifier"]
            has_for = any(c.type == "for" for c in impl_node.children)
            
            if has_for and len(identifiers) >= 2:
                trait_name = self._get_node_text(identifiers[0])
                type_name = self._get_node_text(identifiers[1])
                if type_name in types_map:
                    types_map[type_name]["bases"].append(trait_name)
                    
        structs = [v for v in types_map.values() if v["type"] == "struct"]
        enums = [v for v in types_map.values() if v["type"] == "enum"]
        traits = [v for v in types_map.values() if v["type"] == "trait"]
        for s in structs: s.pop("type")
        for e in enums: e.pop("type")
        for t in traits: t.pop("type")
        
        return structs, enums, traits

    def _find_imports(self, root_node: Any) -> list[Dict[str, Any]]:
        imports = []
        query_str = RUST_QUERIES["imports"]
        for node, _ in execute_query(self.language, query_str, root_node):
            full_import_name = self._get_node_text(node)
            alias = None

            alias_match = re.search(r"as\s+(\w+)\s*;?$", full_import_name)
            if alias_match:
                alias = alias_match.group(1)
                name = alias
            else:
                cleaned_path = re.sub(r";$", "", full_import_name).strip()
                last_part = cleaned_path.split("::")[-1]
                if last_part.strip() == "*":
                    name = "*"
                else:
                    name_match = re.findall(r"(\w+)", last_part)
                    name = name_match[-1] if name_match else last_part

            imports.append(
                {
                    "name": name,
                    "full_import_name": full_import_name,
                    "line_number": node.start_point[0] + 1,
                    "alias": alias,
                }
            )
        return imports

    def _find_calls(self, root_node: Any) -> list[Dict[str, Any]]:
        """Finds all function and method calls."""
        calls = []
        query_str = RUST_QUERIES["calls"]
        for node, capture_name in execute_query(self.language, query_str, root_node):
            if capture_name == "name":
                # Find the call_expression
                call_node = node.parent
                while call_node and call_node.type != 'call_expression' and call_node.type != 'source_file':
                    call_node = call_node.parent
                
                call_name = self._get_node_text(node)
                
                # Extract arguments
                args = []
                if call_node and call_node.type == 'call_expression':
                    args_node = call_node.child_by_field_name('arguments')
                    if args_node:
                        for child in args_node.children:
                            if child.type not in ('(', ')', ','):
                                args.append(self._get_node_text(child))

                calls.append(
                    {
                        "name": call_name,
                        "full_name": self._get_node_text(call_node) if call_node else call_name,
                        "line_number": node.start_point[0] + 1,
                        "args": args,
                        "context": self._get_parent_context(node),
                        "lang": self.language_name,
                        "is_dependency": False,
                    }
                )
        return calls

def pre_scan_rust(files: list[Path], parser_wrapper) -> dict:
    """Scans Rust files to create a map of function/struct/enum/trait names to their file paths."""
    imports_map = {}
    query_str = """
        (function_item name: (identifier) @name)
        (struct_item name: (type_identifier) @name)
        (enum_item name: (type_identifier) @name)
        (trait_item name: (type_identifier) @name)
    """
    

    for path in files:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                tree = parser_wrapper.parser.parse(bytes(f.read(), "utf8"))

            for capture, _ in execute_query(parser_wrapper.language, query_str, tree.root_node):
                name = capture.text.decode('utf-8')
                if name not in imports_map:
                    imports_map[name] = []
                imports_map[name].append(str(path.resolve()))
        except Exception as e:
            warning_logger(f"Tree-sitter pre-scan failed for {path}: {e}")
    return imports_map
