from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from codegraphcontext.utils.debug_log import warning_logger


LUA_CONTROL_NODES = {
    "if_statement",
    "for_statement",
    "while_statement",
    "repeat_statement",
}


class LuaTreeSitterParser:
    """A Lua-specific parser using tree-sitter."""

    def __init__(self, generic_parser_wrapper):
        self.generic_parser_wrapper = generic_parser_wrapper
        self.language_name = generic_parser_wrapper.language_name
        self.language = generic_parser_wrapper.language
        self.parser = generic_parser_wrapper.parser
        self.index_source = False

    def _get_node_text(self, node: Any) -> str:
        return node.text.decode("utf-8")

    def _iter_nodes(self, node: Any):
        yield node
        for child in node.children:
            if child.is_named:
                yield from self._iter_nodes(child)

    def _split_qualified_name(self, text: str) -> Tuple[str, Optional[str], str]:
        normalized = text.replace(":", ".")
        if "." not in normalized:
            return text, None, text
        context, name = normalized.rsplit(".", 1)
        return name, context, normalized

    def _first_named_child(self, node: Any, types: Optional[set[str]] = None):
        for child in node.children:
            if child.is_named and (types is None or child.type in types):
                return child
        return None

    def _assignment_for_expression_list(self, node: Any):
        current = node.parent
        while current:
            if current.type == "assignment_statement":
                return current
            if current.type not in {"expression_list", "variable_declaration"}:
                return None
            current = current.parent
        return None

    def _assignment_name_nodes(self, assignment: Any) -> list[Any]:
        for child in assignment.children:
            if child.type == "variable_list":
                return [node for node in child.children if node.is_named]

        name_node = assignment.child_by_field_name("name")
        return [name_node] if name_node else []

    def _assignment_value_nodes(self, assignment: Any) -> list[Any]:
        for child in assignment.children:
            if child.type == "expression_list":
                return [node for node in child.children if node.is_named]

        value_node = assignment.child_by_field_name("value")
        return [value_node] if value_node else []

    def _assigned_name_node(self, func_node: Any):
        parent = func_node.parent
        if not parent:
            return None

        if parent.type == "field":
            return parent.child_by_field_name("name") or self._first_named_child(
                parent, {"identifier", "string", "number"}
            )

        assignment = self._assignment_for_expression_list(parent)
        if not assignment:
            return None

        variables = self._assignment_name_nodes(assignment)
        if not variables:
            return None

        expressions = [child for child in parent.children if child.is_named]
        try:
            index = expressions.index(func_node)
        except ValueError:
            index = 0

        if index < len(variables):
            return variables[index]
        return variables[0] if variables else None

    def _table_context_for_field(self, field_node: Any) -> Optional[str]:
        current = field_node.parent
        while current:
            if current.type == "assignment_statement":
                name_node = current.child_by_field_name("name")
                if name_node:
                    return self._get_node_text(name_node).replace(":", ".")
                return None
            current = current.parent
        return None

    def _function_identity(self, func_node: Any) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        if func_node.type == "function_declaration":
            name_node = func_node.child_by_field_name("name")
        else:
            name_node = self._assigned_name_node(func_node)

        if not name_node:
            return None, None, None

        name, class_context, full_name = self._split_qualified_name(self._get_node_text(name_node))

        if func_node.type == "function_definition" and name_node.parent and name_node.parent.type == "field":
            table_context = self._table_context_for_field(name_node.parent)
            if table_context:
                class_context = table_context
                full_name = f"{table_context}.{name}"

        return name, class_context, full_name

    def _extract_parameters(self, func_node: Any) -> list[str]:
        params_node = func_node.child_by_field_name("parameters")
        if not params_node:
            return []

        params = []
        for child in params_node.children:
            if child.type == "identifier":
                params.append(self._get_node_text(child))
            elif child.type in {"vararg_expression", "..."}:
                params.append("...")

        name_node = func_node.child_by_field_name("name")
        if name_node and name_node.type == "method_index_expression" and "self" not in params:
            params.insert(0, "self")

        return params

    def _calculate_complexity(self, node: Any) -> int:
        count = 1

        def traverse(current):
            nonlocal count
            if current.type in LUA_CONTROL_NODES:
                count += 1
            elif current.type == "binary_expression":
                text = self._get_node_text(current)
                if " and " in text or " or " in text:
                    count += 1
            for child in current.children:
                if child.is_named:
                    traverse(child)

        traverse(node)
        return count

    def _get_docstring(self, node: Any) -> Optional[str]:
        prev_sibling = node.prev_sibling
        while prev_sibling:
            if prev_sibling.type == "comment":
                return self._get_node_text(prev_sibling).strip()
            if prev_sibling.is_named:
                break
            prev_sibling = prev_sibling.prev_sibling
        return None

    def _get_parent_context(self, node: Any):
        current = node.parent
        while current:
            if current.type in {"function_declaration", "function_definition"}:
                name, _, _ = self._function_identity(current)
                return name, current.type, current.start_point[0] + 1
            current = current.parent
        return None, None, None

    def parse(self, path: Path, is_dependency: bool = False, index_source: bool = False) -> Dict[str, Any]:
        self.index_source = index_source
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            source_code = f.read()

        tree = self.parser.parse(bytes(source_code, "utf8"))
        root_node = tree.root_node

        return {
            "path": str(path),
            "functions": self._find_functions(root_node),
            "classes": [],
            "variables": self._find_variables(root_node),
            "imports": self._find_imports(root_node),
            "function_calls": self._find_calls(root_node),
            "is_dependency": is_dependency,
            "lang": self.language_name,
        }

    def _find_functions(self, root_node: Any) -> list[Dict[str, Any]]:
        functions = []
        seen = set()

        for node in self._iter_nodes(root_node):
            if node.type not in {"function_declaration", "function_definition"}:
                continue
            if node.id in seen:
                continue

            name, class_context, full_name = self._function_identity(node)
            if not name:
                continue

            seen.add(node.id)
            func_data = {
                "name": name,
                "full_name": full_name,
                "line_number": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "args": self._extract_parameters(node),
                "context": None,
                "context_type": None,
                "class_context": class_context,
                "decorators": [],
                "lang": self.language_name,
                "is_dependency": False,
                "cyclomatic_complexity": self._calculate_complexity(node),
            }
            context, context_type, _ = self._get_parent_context(node)
            if context:
                func_data["context"] = context
                func_data["context_type"] = context_type

            if self.index_source:
                func_data["source"] = self._get_node_text(node)
                func_data["docstring"] = self._get_docstring(node)

            functions.append(func_data)

        return functions

    def _find_imports(self, root_node: Any) -> list[Dict[str, Any]]:
        imports = []
        seen = set()

        for node in self._iter_nodes(root_node):
            if node.type != "function_call":
                continue
            name_node = node.child_by_field_name("name")
            if not name_node or self._get_node_text(name_node) != "require":
                continue

            module_name = self._first_string_argument(node)
            if not module_name:
                continue

            alias = self._require_alias(node)
            key = (module_name, node.start_point[0])
            if key in seen:
                continue
            seen.add(key)

            imports.append(
                {
                    "name": module_name,
                    "full_import_name": f"require '{module_name}'",
                    "line_number": node.start_point[0] + 1,
                    "alias": alias,
                    "lang": self.language_name,
                    "is_dependency": False,
                }
            )

        return imports

    def _find_calls(self, root_node: Any) -> list[Dict[str, Any]]:
        calls = []
        seen = set()

        for node in self._iter_nodes(root_node):
            if node.type != "function_call":
                continue

            name_node = node.child_by_field_name("name")
            if not name_node:
                continue

            name, _, full_name = self._split_qualified_name(self._get_node_text(name_node))
            key = (full_name, node.start_point[0], node.start_point[1])
            if key in seen:
                continue
            seen.add(key)

            context, context_type, context_line = self._get_parent_context(node)
            calls.append(
                {
                    "name": name,
                    "full_name": full_name,
                    "line_number": node.start_point[0] + 1,
                    "args": self._extract_call_args(node),
                    "inferred_obj_type": None,
                    "context": (context, context_type, context_line),
                    "class_context": None,
                    "lang": self.language_name,
                    "is_dependency": False,
                }
            )

        return calls

    def _find_variables(self, root_node: Any) -> list[Dict[str, Any]]:
        variables = []

        for node in self._iter_nodes(root_node):
            if node.type != "assignment_statement":
                continue

            value_nodes = self._assignment_value_nodes(node)
            if any(value.type == "function_definition" for value in value_nodes):
                continue

            variable_nodes = self._assignment_name_nodes(node)
            if not variable_nodes:
                continue

            context, _, _ = self._get_parent_context(node)
            declaration_type = "local" if node.parent and node.parent.type == "variable_declaration" else None
            value = ", ".join(self._get_node_text(value_node) for value_node in value_nodes) if value_nodes else None

            for child in variable_nodes:
                variables.append(
                    {
                        "name": self._get_node_text(child),
                        "line_number": child.start_point[0] + 1,
                        "value": value,
                        "type": declaration_type,
                        "context": context,
                        "class_context": None,
                        "lang": self.language_name,
                        "is_dependency": False,
                    }
                )

        return variables

    def _first_string_argument(self, call_node: Any) -> Optional[str]:
        args_node = call_node.child_by_field_name("arguments")
        if not args_node:
            return None

        for node in self._iter_nodes(args_node):
            if node.type == "string_content":
                return self._get_node_text(node)
            if node.type == "string":
                return self._get_node_text(node).strip("\"'")
        return None

    def _require_alias(self, call_node: Any) -> Optional[str]:
        assignment = self._assignment_for_expression_list(call_node.parent)
        if not assignment:
            return None

        variable_nodes = self._assignment_name_nodes(assignment)
        if not variable_nodes:
            return None

        return self._get_node_text(variable_nodes[0])

    def _extract_call_args(self, call_node: Any) -> list[str]:
        args_node = call_node.child_by_field_name("arguments")
        if not args_node:
            return []

        args = []
        for child in args_node.children:
            if child.is_named:
                args.append(self._get_node_text(child))
        return args


def pre_scan_lua(files: list[Path], parser_wrapper) -> dict:
    """Scans Lua files to create a map of function names to their file paths."""
    imports_map = {}
    if parser_wrapper is None:
        return imports_map

    parser = LuaTreeSitterParser(parser_wrapper)

    for path in files:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                tree = parser_wrapper.parser.parse(bytes(f.read(), "utf8"))

            for function in parser._find_functions(tree.root_node):
                resolved_path = str(path.resolve())
                names = {function["name"]}
                if function.get("full_name"):
                    names.add(function["full_name"])

                for name in names:
                    imports_map.setdefault(name, []).append(resolved_path)
        except Exception as e:
            warning_logger(f"Tree-sitter pre-scan failed for {path}: {e}")

    return imports_map
