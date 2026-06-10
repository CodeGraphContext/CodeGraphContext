from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from codegraphcontext.utils.debug_log import error_logger, warning_logger

ELISP_QUERIES = {
    "functions": """
        [
          (function_definition
            name: (symbol) @name
            parameters: (list) @parameters
            docstring: (string)? @docstring) @function_node
          (macro_definition
            name: (symbol) @name
            parameters: (list) @parameters
            docstring: (string)? @docstring) @function_node
          ((list
            . (symbol) @kind
            . (symbol) @name
            . (list) @parameters) @function_node
            (#eq? @kind "cl-defun"))
        ]
    """,
    "variables": """
        (special_form
          "defvar" @kind
          (symbol) @name) @variable_node
        (special_form
          "defconst" @kind
          (symbol) @name) @variable_node
        ((list
          . (symbol) @kind
          . (symbol) @name) @variable_node
          (#eq? @kind "defcustom"))
        (special_form
          "setq" @kind
          (symbol) @name) @variable_node
    """,
    "features": """
        ((list
          . (symbol) @kind
          . (quote (symbol) @feature)) @feature_node
          (#match? @kind "^(require|provide)$"))
        ((list
          . (symbol) @kind
          . (quote (symbol) @autoloaded_name)
          . (string) @source_file) @autoload_node
          (#eq? @kind "autoload"))
    """,
    "calls": """
        [
          (list
            . (symbol) @name) @call_node
          (quote
            (symbol) @quoted_name) @quote_node
        ]
    """,
}


FUNCTION_FORMS = {"defun", "defsubst", "defmacro", "cl-defun"}
VARIABLE_FORMS = {"defvar", "defconst", "defcustom"}
IMPORT_FORMS = {"require", "provide", "autoload"}
SPECIAL_FORMS = {
    "and",
    "catch",
    "cond",
    "condition-case",
    "declare",
    "if",
    "interactive",
    "lambda",
    "let",
    "let*",
    "dolist",
    "dotimes",
    "or",
    "prog1",
    "prog2",
    "progn",
    "quote",
    "save-current-buffer",
    "save-excursion",
    "save-restriction",
    "setq",
    "throw",
    "unwind-protect",
    "when",
    "while",
    "unless",
}
BINDING_FORMS = {"let", "let*", "dolist", "dotimes"}
CALL_EXCLUDED_FORMS = (
    FUNCTION_FORMS | VARIABLE_FORMS | IMPORT_FORMS | SPECIAL_FORMS | BINDING_FORMS
)
CONTROL_FORMS = {
    "and",
    "catch",
    "cond",
    "condition-case",
    "dolist",
    "dotimes",
    "if",
    "or",
    "unwind-protect",
    "when",
    "while",
    "unless",
}


class ElispTreeSitterParser:
    """An Emacs Lisp-specific parser using tree-sitter."""

    def __init__(self, generic_parser_wrapper: Any):
        self.generic_parser_wrapper = generic_parser_wrapper
        self.language_name = "elisp"
        self.language = generic_parser_wrapper.language
        self.parser = generic_parser_wrapper.parser
        self.index_source = False

    def _get_node_text(self, node: Optional[Any]) -> str:
        if node is None:
            return ""
        return node.text.decode("utf-8")

    def _iter_nodes(self, node: Any):
        yield node
        for child in node.children:
            if child.is_named:
                yield from self._iter_nodes(child)

    def _named_children(self, node: Any) -> list[Any]:
        return [child for child in node.children if child.is_named]

    def _form_arguments(self, node: Any) -> list[Any]:
        named = self._named_children(node)
        if node.type == "list" and named and named[0].type == "symbol":
            return named[1:]
        return named

    def _form_head(self, node: Any) -> Optional[str]:
        if node.type in {"function_definition", "macro_definition", "special_form"}:
            for child in node.children:
                if not child.is_named and child.type not in {"(", ")"}:
                    return child.type

        if node.type == "list":
            for child in node.children:
                if child.is_named:
                    if child.type == "symbol":
                        return self._get_node_text(child)
                    return None

        return None

    def _is_cl_defun(self, node: Any) -> bool:
        return node.type == "list" and self._form_head(node) == "cl-defun"

    def _function_identity(
        self, node: Any
    ) -> Tuple[Optional[str], Optional[str], Optional[Any]]:
        kind = self._form_head(node)
        if node.type in {"function_definition", "macro_definition"}:
            name_node = node.child_by_field_name("name")
            return (
                self._get_node_text(name_node) if name_node else None,
                kind,
                name_node,
            )

        if self._is_cl_defun(node):
            named = self._named_children(node)
            if len(named) >= 2 and named[1].type == "symbol":
                return self._get_node_text(named[1]), kind, named[1]

        return None, None, None

    def _parameter_node(self, node: Any) -> Optional[Any]:
        if node.type in {"function_definition", "macro_definition"}:
            return node.child_by_field_name("parameters")

        if self._is_cl_defun(node):
            named = self._named_children(node)
            if len(named) >= 3 and named[2].type == "list":
                return named[2]

        return None

    def _extract_parameters(self, param_node: Optional[Any]) -> list[str]:
        if param_node is None:
            return []

        params: list[str] = []
        seen = set()

        def add_symbol(symbol_node: Any) -> None:
            text = self._get_node_text(symbol_node)
            if not text or text.startswith("&") or text in seen:
                return
            seen.add(text)
            params.append(text)

        for child in self._named_children(param_node):
            if child.type == "symbol":
                add_symbol(child)
            elif child.type == "list":
                for nested in self._named_children(child):
                    if nested.type == "symbol":
                        add_symbol(nested)
                        break

        return params

    def _string_value(self, node: Optional[Any]) -> Optional[str]:
        if node is None or node.type != "string":
            return None
        raw = self._get_node_text(node)
        try:
            value = ast.literal_eval(raw)
            return value if isinstance(value, str) else raw
        except (ValueError, SyntaxError):
            if len(raw) >= 2 and raw[0] == raw[-1] == '"':
                return raw[1:-1]
            return raw

    def _function_docstring(self, node: Any) -> Optional[str]:
        if node.type in {"function_definition", "macro_definition"}:
            return self._string_value(node.child_by_field_name("docstring"))

        if self._is_cl_defun(node):
            named = self._named_children(node)
            for child in named[3:]:
                if child.type == "string":
                    return self._string_value(child)
                if child.is_named:
                    break

        return None

    def _first_symbol_in_quote(self, node: Any) -> Optional[str]:
        if node.type != "quote":
            return None
        for child in self._named_children(node):
            if child.type == "symbol":
                return self._get_node_text(child)
        return None

    def _quoted_symbol_argument(self, node: Any, index: int = 1) -> Optional[str]:
        named = self._named_children(node)
        if len(named) <= index:
            return None
        return self._first_symbol_in_quote(named[index])

    def _enclosing_function(self, node: Any):
        current = node.parent
        while current:
            name, kind, _ = self._function_identity(current)
            if name:
                return name, kind or current.type, current.start_point[0] + 1
            current = current.parent
        return None, None, None

    def _is_parameter_list(self, node: Any) -> bool:
        parent = node.parent
        if parent is None:
            return False

        if parent.type in {"function_definition", "macro_definition"}:
            return parent.child_by_field_name("parameters") == node

        parent_head = self._form_head(parent)
        if parent_head == "lambda":
            args = self._form_arguments(parent)
            return len(args) >= 1 and args[0] == node
        if parent_head == "cl-defun":
            named = self._named_children(parent)
            return len(named) >= 3 and named[2] == node

        return False

    def _has_parameter_list_ancestor(self, node: Any) -> bool:
        current = node
        while current:
            if self._is_parameter_list(current):
                return True
            current = current.parent
        return False

    def _is_binding_list(self, node: Any) -> bool:
        parent = node.parent
        if parent is None:
            return False

        parent_head = self._form_head(parent)
        if parent_head in BINDING_FORMS:
            args = self._form_arguments(parent)
            return len(args) >= 1 and args[0] == node

        grandparent = parent.parent
        if (
            parent.type == "list"
            and grandparent is not None
            and self._form_head(grandparent) in {"let", "let*"}
        ):
            args = self._form_arguments(grandparent)
            return len(args) >= 1 and args[0] == parent

        return False

    def _has_quote_ancestor(self, node: Any) -> bool:
        current = node.parent
        while current:
            if current.type == "quote":
                return True
            current = current.parent
        return False

    def _is_call_node(self, node: Any) -> bool:
        if node.type != "list":
            return False
        if (
            self._has_quote_ancestor(node)
            or self._has_parameter_list_ancestor(node)
            or self._is_binding_list(node)
        ):
            return False

        head = self._form_head(node)
        if not head:
            return False
        if head.startswith(":") or head.startswith("&"):
            return False
        if head in CALL_EXCLUDED_FORMS:
            return False
        return True

    def _extract_call_args(self, call_node: Any, skip_first: int = 1) -> list[str]:
        args = []
        for child in self._named_children(call_node)[skip_first:]:
            args.append(self._get_node_text(child))
        return args

    def _calculate_complexity(self, node: Any) -> int:
        from codegraphcontext.tools.indexing.constants import MAX_AST_DEPTH
        count = 1
        skipped = False

        def traverse(current: Any, depth: int = 0) -> None:
            nonlocal count, skipped
            if depth > MAX_AST_DEPTH:
                skipped = True
                return
            head = self._form_head(current)
            if head in CONTROL_FORMS:
                count += 1
            for child in current.children:
                if child.is_named:
                    traverse(child, depth + 1)

        traverse(node)
        if skipped:
            warning_logger(
                f"AST depth exceeded {MAX_AST_DEPTH} levels; "
                "complexity count may be underestimated."
            )
        return count

    def parse(
        self, path: Path, is_dependency: bool = False, index_source: bool = False
    ) -> Dict[str, Any]:
        """Parse an Emacs Lisp file and return CGC's normalized structure."""
        self.index_source = index_source
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                source_code = f.read()

            tree = self.parser.parse(bytes(source_code, "utf8"))
            root_node = tree.root_node

            return {
                "path": str(path),
                "functions": self._find_functions(root_node, is_dependency),
                "classes": [],
                "variables": self._find_variables(root_node, is_dependency),
                "imports": self._find_imports(root_node, is_dependency),
                "function_calls": self._find_calls(root_node, is_dependency),
                "is_dependency": is_dependency,
                "lang": self.language_name,
            }
        except Exception as e:
            error_logger(f"Failed to parse Emacs Lisp file {path}: {e}")
            return {"path": str(path), "error": str(e)}

    def _find_functions(
        self, root_node: Any, is_dependency: bool
    ) -> list[Dict[str, Any]]:
        functions = []
        seen = set()

        for node in self._iter_nodes(root_node):
            if node.type not in {
                "function_definition",
                "macro_definition",
            } and not self._is_cl_defun(node):
                continue

            name, kind, _ = self._function_identity(node)
            if not name:
                continue
            key = (node.start_byte, node.end_byte)
            if key in seen:
                continue
            seen.add(key)

            func_data = {
                "name": name,
                "full_name": name,
                "line_number": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "args": self._extract_parameters(self._parameter_node(node)),
                "context": None,
                "context_type": None,
                "class_context": None,
                "decorators": [],
                "type": kind,
                "lang": self.language_name,
                "is_dependency": is_dependency,
                "cyclomatic_complexity": self._calculate_complexity(node),
            }

            if self.index_source:
                func_data["source"] = self._get_node_text(node)
                func_data["docstring"] = self._function_docstring(node)

            functions.append(func_data)

        return functions

    def _find_variables(
        self, root_node: Any, is_dependency: bool
    ) -> list[Dict[str, Any]]:
        variables = []
        seen = set()

        for node in self._iter_nodes(root_node):
            head = self._form_head(node)
            if head in {"defvar", "defconst"}:
                named = self._named_children(node)
                if not named or named[0].type != "symbol":
                    continue
                self._append_variable(
                    variables,
                    seen,
                    node,
                    named[0],
                    head,
                    named[1] if len(named) > 1 else None,
                    is_dependency,
                )
            elif head == "defcustom":
                named = self._named_children(node)
                if len(named) < 2 or named[1].type != "symbol":
                    continue
                self._append_variable(
                    variables,
                    seen,
                    node,
                    named[1],
                    head,
                    named[2] if len(named) > 2 else None,
                    is_dependency,
                )
            elif head == "setq":
                named = self._named_children(node)
                index = 0
                while index < len(named):
                    name_node = named[index]
                    value_node = named[index + 1] if index + 1 < len(named) else None
                    if name_node.type == "symbol":
                        self._append_variable(
                            variables,
                            seen,
                            node,
                            name_node,
                            head,
                            value_node,
                            is_dependency,
                        )
                    index += 2

        return variables

    def _append_variable(
        self,
        variables: list[Dict[str, Any]],
        seen: set[Tuple[str, int, int]],
        form_node: Any,
        name_node: Any,
        kind: str,
        value_node: Optional[Any],
        is_dependency: bool,
    ) -> None:
        name = self._get_node_text(name_node)
        key = (name, name_node.start_byte, name_node.end_byte)
        if key in seen:
            return
        seen.add(key)

        context, _, _ = self._enclosing_function(form_node)
        variable_data = {
            "name": name,
            "line_number": name_node.start_point[0] + 1,
            "value": (
                self._get_node_text(value_node) if value_node is not None else None
            ),
            "type": kind,
            "context": context,
            "class_context": None,
            "lang": self.language_name,
            "is_dependency": is_dependency,
        }

        if self.index_source:
            variable_data["source"] = self._get_node_text(form_node)
            variable_data["docstring"] = self._variable_docstring(form_node, kind)

        variables.append(variable_data)

    def _variable_docstring(self, form_node: Any, kind: str) -> Optional[str]:
        named = self._named_children(form_node)
        if kind in {"defvar", "defconst"}:
            for child in named[2:]:
                if child.type == "string":
                    return self._string_value(child)
        elif kind == "defcustom":
            for child in named[3:]:
                if child.type == "string":
                    return self._string_value(child)
        return None

    def _find_imports(
        self, root_node: Any, is_dependency: bool
    ) -> list[Dict[str, Any]]:
        imports = []
        seen = set()

        for node in self._iter_nodes(root_node):
            head = self._form_head(node)
            if head not in IMPORT_FORMS:
                continue

            name = None
            full_import_name = None
            imported_name = None
            if head in {"require", "provide"}:
                name = self._quoted_symbol_argument(node)
                imported_name = name
                full_import_name = f"{head} '{name}" if name else None
            elif head == "autoload":
                name = self._quoted_symbol_argument(node)
                imported_name = name
                named = self._named_children(node)
                source_file = (
                    self._string_value(named[2])
                    if len(named) > 2 and named[2].type == "string"
                    else None
                )
                full_import_name = (
                    f"autoload '{name} from {source_file}"
                    if name and source_file
                    else name
                )

            if not name:
                continue
            key = (head, name, node.start_point[0])
            if key in seen:
                continue
            seen.add(key)

            imports.append(
                {
                    "name": name,
                    "full_import_name": full_import_name or name,
                    "imported_name": imported_name or name,
                    "line_number": node.start_point[0] + 1,
                    "alias": None,
                    "import_type": head,
                    "lang": self.language_name,
                    "is_dependency": is_dependency,
                }
            )

        return imports

    def _find_calls(self, root_node: Any, is_dependency: bool) -> list[Dict[str, Any]]:
        calls = []
        seen = set()

        for node in self._iter_nodes(root_node):
            if not self._is_call_node(node):
                continue

            head = self._form_head(node)
            if not head:
                continue

            if head in {"funcall", "apply"}:
                target = self._quoted_symbol_argument(node)
                if target:
                    self._append_call(
                        calls,
                        seen,
                        node,
                        target,
                        target,
                        is_dependency,
                        call_kind=head,
                        skip_first=2,
                    )
                continue

            self._append_call(calls, seen, node, head, head, is_dependency)

        return calls

    def _append_call(
        self,
        calls: list[Dict[str, Any]],
        seen: set[Tuple[str, int, int, str]],
        node: Any,
        name: str,
        full_name: str,
        is_dependency: bool,
        call_kind: str = "call",
        skip_first: int = 1,
    ) -> None:
        key = (full_name, node.start_point[0], node.start_point[1], call_kind)
        if key in seen:
            return
        seen.add(key)

        context, context_type, context_line = self._enclosing_function(node)
        calls.append(
            {
                "name": name,
                "full_name": full_name,
                "line_number": node.start_point[0] + 1,
                "args": self._extract_call_args(node, skip_first=skip_first),
                "context": (context, context_type, context_line),
                "class_context": None,
                "lang": self.language_name,
                "is_dependency": is_dependency,
                "call_kind": call_kind,
            }
        )


def pre_scan_elisp(files: list[Path], parser_wrapper) -> dict:
    """Scan Emacs Lisp files to map functions, macros, variables, and provided features to file paths."""
    imports_map = {}
    if parser_wrapper is None:
        return imports_map

    parser = ElispTreeSitterParser(parser_wrapper)

    for path in files:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                tree = parser_wrapper.parser.parse(bytes(f.read(), "utf8"))

            resolved_path = str(path.resolve())
            for function in parser._find_functions(tree.root_node, is_dependency=False):
                imports_map.setdefault(function["name"], []).append(resolved_path)

            for variable in parser._find_variables(tree.root_node, is_dependency=False):
                if variable.get("type") in VARIABLE_FORMS:
                    imports_map.setdefault(variable["name"], []).append(resolved_path)

            for imp in parser._find_imports(tree.root_node, is_dependency=False):
                if imp.get("import_type") == "provide":
                    imports_map.setdefault(imp["name"], []).append(resolved_path)
        except Exception as e:
            warning_logger(
                f"Tree-sitter pre-scan failed for Emacs Lisp file {path}: {e}"
            )

    return imports_map
