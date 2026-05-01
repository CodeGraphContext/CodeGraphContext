"""Haskell tree-sitter parser (tree-sitter-haskell grammar)."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import re

from codegraphcontext.utils.debug_log import error_logger, warning_logger
from codegraphcontext.utils.tree_sitter_manager import execute_query

# Node names follow https://github.com/tree-sitter/tree-sitter-haskell
# Top-level: function, class (typeclass), data_type, newtype, type_synomym, import.
# Application uses node type `apply` (function application).
HASKELL_QUERIES = {
    "functions": """
        (function) @function_node
        (bind
            name: (variable) @bind_name) @bind_node
    """,
    "classes": """
        (class) @class_node
        (data_type) @data_type_node
        (newtype) @newtype_node
        (type_synomym) @type_synonym_node
    """,
    "imports": """
        (import) @import
    """,
    "calls": """
        (apply
            function: (variable) @callee) @apply_node
    """,
    # Polymorphic parameters use `variable` under type `function`, not a separate `type_variable` kind
    # in tree-sitter-haskell; keep variables to top-level/type signatures only.
    "variables": """
        (signature
            name: (variable) @name) @signature_node
    """,
}


class HaskellTreeSitterParser:
    """Parse Haskell sources using tree-sitter-haskell."""

    def __init__(self, generic_parser_wrapper: Any):
        self.generic_parser_wrapper = generic_parser_wrapper
        self.language_name = "haskell"
        self.language = generic_parser_wrapper.language
        self.parser = generic_parser_wrapper.parser
        self.index_source = False

    def _get_node_text(self, node: Any) -> str:
        if not node:
            return ""
        return node.text.decode("utf-8")

    def _get_parent_context(
        self,
        node: Any,
        types: Tuple[str, ...] = ("function", "bind", "class", "data_type", "newtype", "instance"),
    ) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        curr = node.parent
        while curr:
            if curr.type in types:
                name_node = curr.child_by_field_name("name")
                if name_node:
                    return (
                        self._get_node_text(name_node),
                        curr.type,
                        curr.start_point[0] + 1,
                    )
                if curr.type == "function":
                    fn_name = curr.child_by_field_name("name")
                    if fn_name:
                        return (
                            self._get_node_text(fn_name),
                            curr.type,
                            curr.start_point[0] + 1,
                        )
                if curr.type == "bind":
                    bn = curr.child_by_field_name("name")
                    if bn and bn.type == "variable":
                        return (
                            self._get_node_text(bn),
                            curr.type,
                            curr.start_point[0] + 1,
                        )
            curr = curr.parent
        return None, None, None

    def _pattern_arg_names(self, patterns_node: Any) -> List[str]:
        if not patterns_node:
            return []
        names: List[str] = []

        def walk(n: Any) -> None:
            if n.type == "variable":
                names.append(self._get_node_text(n))
                return
            for c in n.children:
                walk(c)

        walk(patterns_node)
        return names

    def parse(self, path: Path, is_dependency: bool = False, index_source: bool = False) -> Dict[str, Any]:
        self.index_source = index_source
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                source_code = f.read()
            if not source_code.strip():
                warning_logger(f"Empty or whitespace-only file: {path}")
                return self._empty_result(path, is_dependency)

            tree = self.parser.parse(bytes(source_code, "utf8"))
            root = tree.root_node

            parsed_variables: List[Dict[str, Any]] = []
            if "variables" in HASKELL_QUERIES:
                var_caps = execute_query(self.language, HASKELL_QUERIES["variables"], root)
                parsed_variables = self._parse_variables(var_caps, source_code, path)

            parsed_functions: List[Dict[str, Any]] = []
            parsed_classes: List[Dict[str, Any]] = []
            parsed_imports: List[Dict[str, Any]] = []
            parsed_calls: List[Dict[str, Any]] = []

            for capture_name, query in HASKELL_QUERIES.items():
                if capture_name == "variables":
                    continue
                results = execute_query(self.language, query, root)
                if capture_name == "functions":
                    parsed_functions.extend(self._parse_functions(results, source_code, path))
                elif capture_name == "classes":
                    parsed_classes.extend(self._parse_classes(results, source_code, path))
                elif capture_name == "imports":
                    parsed_imports.extend(self._parse_imports(results, source_code))
                elif capture_name == "calls":
                    parsed_calls.extend(self._parse_calls(results, source_code, path))

            return {
                "path": str(path),
                "functions": parsed_functions,
                "classes": parsed_classes,
                "variables": parsed_variables,
                "imports": parsed_imports,
                "function_calls": parsed_calls,
                "is_dependency": is_dependency,
                "lang": self.language_name,
            }
        except Exception as e:
            error_logger(f"Error parsing Haskell file {path}: {e}")
            return self._empty_result(path, is_dependency)

    def _empty_result(self, path: Path, is_dependency: bool) -> Dict[str, Any]:
        return {
            "path": str(path),
            "functions": [],
            "classes": [],
            "variables": [],
            "imports": [],
            "function_calls": [],
            "is_dependency": is_dependency,
            "lang": self.language_name,
        }

    def _parse_functions(
        self, captures: List[Tuple[Any, str]], source_code: str, path: Path
    ) -> List[Dict[str, Any]]:
        functions: List[Dict[str, Any]] = []
        seen: set = set()

        for node, cap in captures:
            if cap == "function_node" and node.type == "function":
                name_node = node.child_by_field_name("name")
                if not name_node:
                    continue
                func_name = self._get_node_text(name_node)
                key = ("fn", node.start_byte, node.end_byte)
                if key in seen:
                    continue
                seen.add(key)
                patterns = node.child_by_field_name("patterns")
                parameters = self._pattern_arg_names(patterns)
                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1
                ctx_name, ctx_type, ctx_line = self._get_parent_context(node)
                func_data: Dict[str, Any] = {
                    "name": func_name,
                    "args": parameters,
                    "line_number": start_line,
                    "end_line": end_line,
                    "path": str(path),
                    "lang": self.language_name,
                    "context": ctx_name,
                    "class_context": ctx_name
                    if ctx_type and ctx_type in ("class", "instance")
                    else None,
                }
                if self.index_source:
                    func_data["source"] = self._get_node_text(node)
                functions.append(func_data)

            elif cap == "bind_node" and node.type == "bind":
                name_node = node.child_by_field_name("name")
                if not name_node or name_node.type != "variable":
                    continue
                func_name = self._get_node_text(name_node)
                key = ("bind", node.start_byte, node.end_byte)
                if key in seen:
                    continue
                seen.add(key)
                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1
                ctx_name, ctx_type, ctx_line = self._get_parent_context(node)
                func_data = {
                    "name": func_name,
                    "args": [],
                    "line_number": start_line,
                    "end_line": end_line,
                    "path": str(path),
                    "lang": self.language_name,
                    "context": ctx_name,
                    "class_context": ctx_name
                    if ctx_type and ctx_type in ("class", "instance")
                    else None,
                }
                if self.index_source:
                    func_data["source"] = self._get_node_text(node)
                functions.append(func_data)

        return functions

    def _parse_classes(
        self, captures: List[Tuple[Any, str]], source_code: str, path: Path
    ) -> List[Dict[str, Any]]:
        classes: List[Dict[str, Any]] = []
        seen: set = set()

        for node, cap in captures:
            node_id = (node.start_byte, node.end_byte, node.type)
            if node_id in seen:
                continue
            seen.add(node_id)

            name_node = node.child_by_field_name("name")
            if not name_node:
                continue
            class_name = self._get_node_text(name_node)
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1

            kind = node.type
            if cap == "class_node":
                kind = "typeclass"

            class_data: Dict[str, Any] = {
                "name": class_name,
                "line_number": start_line,
                "end_line": end_line,
                "bases": [],
                "path": str(path),
                "lang": self.language_name,
                "kind": kind,
            }
            if self.index_source:
                class_data["source"] = self._get_node_text(node)
            classes.append(class_data)

        return classes

    def _parse_variables(
        self, captures: List[Tuple[Any, str]], source_code: str, path: Path
    ) -> List[Dict[str, Any]]:
        variables: List[Dict[str, Any]] = []
        seen: set = set()

        for node, cap in captures:
            if cap == "signature_node":
                name_node = node.child_by_field_name("name")
                if not name_node:
                    continue
                var_name = self._get_node_text(name_node)
                key = ("sig", node.start_byte, node.end_byte)
                if key in seen:
                    continue
                seen.add(key)
                type_node = node.child_by_field_name("type")
                var_type = self._get_node_text(type_node) if type_node else "Unknown"
                start_line = node.start_point[0] + 1
                ctx_name, ctx_type, ctx_line = self._get_parent_context(node)
                variables.append(
                    {
                        "name": var_name,
                        "type": var_type,
                        "line_number": start_line,
                        "path": str(path),
                        "lang": self.language_name,
                        "context": ctx_name,
                        "class_context": ctx_name
                        if ctx_type and ctx_type in ("class", "instance")
                        else None,
                    }
                )
                # Type parameters like `a` in `f :: a -> b` appear as `variable` under the type subtree.
                if type_node:
                    for tv in self._variables_in_type_ast(type_node):
                        tv_key = ("tv", tv.start_byte, tv.end_byte)
                        if tv_key in seen:
                            continue
                        seen.add(tv_key)
                        tctx_name, tctx_type, _ = self._get_parent_context(tv)
                        variables.append(
                            {
                                "name": self._get_node_text(tv),
                                "type": "type_variable",
                                "line_number": tv.start_point[0] + 1,
                                "path": str(path),
                                "lang": self.language_name,
                                "context": tctx_name,
                                "class_context": tctx_name
                                if tctx_type and tctx_type in ("class", "instance")
                                else None,
                            }
                        )
        return variables

    def _variables_in_type_ast(self, type_root: Any) -> List[Any]:
        """Collect `variable` nodes that appear in a type (tree-sitter-haskell type parameters)."""
        found: List[Any] = []

        def walk(n: Any) -> None:
            if n.type == "variable":
                found.append(n)
                return
            for c in n.children:
                walk(c)

        walk(type_root)
        return found

    def _parse_imports(self, captures: List[Tuple[Any, str]], source_code: str) -> List[Dict[str, Any]]:
        imports: List[Dict[str, Any]] = []
        for node, cap in captures:
            if cap != "import" or node.type != "import":
                continue
            try:
                mod = node.child_by_field_name("module")
                path_str = self._get_node_text(mod).strip() if mod else ""
                alias_node = node.child_by_field_name("alias")
                alias = self._get_node_text(alias_node).strip() if alias_node else None
                imports.append(
                    {
                        "name": path_str,
                        "full_import_name": path_str,
                        "line_number": node.start_point[0] + 1,
                        "alias": alias,
                        "context": (None, None),
                        "lang": self.language_name,
                        "is_dependency": False,
                    }
                )
            except Exception:
                continue
        return imports

    def _parse_calls(
        self, captures: List[Tuple[Any, str]], source_code: str, path: Path
    ) -> List[Dict[str, Any]]:
        calls: List[Dict[str, Any]] = []
        seen_calls: set = set()

        for node, cap in captures:
            if cap != "apply_node" or node.type != "apply":
                continue
            callee = node.child_by_field_name("function")
            if not callee or callee.type != "variable":
                continue
            call_name = self._get_node_text(callee)
            if not call_name:
                continue
            key = (node.start_byte, node.end_byte)
            if key in seen_calls:
                continue
            seen_calls.add(key)

            start_line = node.start_point[0] + 1
            ctx_name, ctx_type, ctx_line = self._get_parent_context(node)
            calls.append(
                {
                    "name": call_name,
                    "full_name": call_name,
                    "line_number": start_line,
                    "args": [],
                    "inferred_obj_type": None,
                    "context": (ctx_name, ctx_type, ctx_line),
                    "class_context": (ctx_name, ctx_line)
                    if ctx_type and ctx_type in ("class", "instance")
                    else (None, None),
                    "lang": self.language_name,
                    "is_dependency": False,
                }
            )
        return calls


def pre_scan_haskell(files: list[Path], parser_wrapper) -> dict:
    """Map declared names to file paths using lightweight regex (no full parse)."""
    name_to_files: dict = {}
    patterns = [
        (re.compile(r"^(\w+)\s*::", re.MULTILINE), None),
        (re.compile(r"^data\s+(\w+)", re.MULTILINE), None),
        (re.compile(r"^class\s+(\w+)", re.MULTILINE), None),
        (re.compile(r"^newtype\s+(\w+)", re.MULTILINE), None),
        (re.compile(r"^type\s+(\w+)", re.MULTILINE), None),
    ]
    for path in files:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            for rx, _ in patterns:
                for m in rx.finditer(content):
                    name = m.group(1)
                    name_to_files.setdefault(name, []).append(str(path))
        except Exception:
            pass
    return name_to_files
