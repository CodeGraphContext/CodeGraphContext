from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from codegraphcontext.utils.debug_log import warning_logger

# In Elixir's tree-sitter grammar, most constructs are `call` nodes
# with identifiers like `defmodule`, `def`, `defp`, etc.

ELIXIR_QUERIES = {
    "modules": """
        (call
            target: (identifier) @keyword
            (arguments (alias) @name)
            (do_block)
        ) @module_node
    """,
    "functions": """
        (call
            target: (identifier) @keyword
            (arguments
                (call
                    target: (identifier) @name
                )
            )
        ) @function_node
    """,
    "imports": """
        (call
            target: (identifier) @keyword
            (arguments (alias) @path)
        ) @import_node
    """,
    "calls": """
        (call
            target: (dot
                left: (_) @receiver
                right: (identifier) @name
            )
            (arguments) @args
        ) @call_node
    """,
    "simple_calls": """
        (call
            target: (identifier) @name
            (arguments) @args
        ) @call_node
    """,
    "module_attributes": """
        (unary_operator
            operator: "@"
            operand: (call
                target: (identifier) @attr_name
                (arguments (_) @attr_value)
            )
        ) @attribute
    """,
    "comments": """
        (comment) @comment
    """,
}

# Keywords that define modules/namespaces
MODULE_KEYWORDS = {"defmodule", "defprotocol", "defimpl"}

# Keywords that define functions
FUNCTION_KEYWORDS = {"def", "defp", "defmacro", "defmacrop", "defguard", "defguardp", "defdelegate"}

# Keywords that represent imports/dependencies
IMPORT_KEYWORDS = {"use", "import", "alias", "require"}

# Keywords to exclude from general call detection
ELIXIR_KEYWORDS = MODULE_KEYWORDS | FUNCTION_KEYWORDS | IMPORT_KEYWORDS | {
    "quote", "unquote", "case", "cond", "if", "unless", "for", "with",
    "try", "receive", "raise", "reraise", "throw", "super",
}


class ElixirTreeSitterParser:
    """An Elixir-specific parser using tree-sitter."""

    def __init__(self, generic_parser_wrapper: Any):
        self.generic_parser_wrapper = generic_parser_wrapper
        self.language_name = "elixir"
        self.language = generic_parser_wrapper.language
        self.parser = generic_parser_wrapper.parser
        self.index_source = False

    def _get_node_text(self, node: Any) -> str:
        return node.text.decode("utf-8")

    def _get_parent_context(self, node: Any):
        """Find parent module or function context."""
        curr = node.parent
        while curr:
            if curr.type == 'call':
                # Check if it's a defmodule/def/defp etc
                for child in curr.children:
                    if child.type == 'identifier':
                        keyword = self._get_node_text(child)
                        if keyword in MODULE_KEYWORDS:
                            # Get module name from arguments
                            for arg_child in curr.children:
                                if arg_child.type == 'arguments':
                                    for ac in arg_child.children:
                                        if ac.type == 'alias':
                                            return self._get_node_text(ac), 'module', curr.start_point[0] + 1
                        elif keyword in FUNCTION_KEYWORDS:
                            for arg_child in curr.children:
                                if arg_child.type == 'arguments':
                                    for ac in arg_child.children:
                                        if ac.type == 'call':
                                            name_node = ac.child_by_field_name('target')
                                            if name_node:
                                                return self._get_node_text(name_node), 'function', curr.start_point[0] + 1
                        break
            curr = curr.parent
        return None, None, None

    def _enclosing_module_name(self, node: Any) -> Optional[str]:
        """Find the enclosing module name."""
        curr = node.parent
        while curr:
            if curr.type == 'call':
                for child in curr.children:
                    if child.type == 'identifier':
                        keyword = self._get_node_text(child)
                        if keyword in MODULE_KEYWORDS:
                            for arg_child in curr.children:
                                if arg_child.type == 'arguments':
                                    for ac in arg_child.children:
                                        if ac.type == 'alias':
                                            return self._get_node_text(ac)
                        break
            curr = curr.parent
        return None

    def _calculate_complexity(self, node: Any) -> int:
        """Calculate cyclomatic complexity for Elixir constructs."""
        complexity_keywords = {
            "if", "unless", "case", "cond", "with", "for", "try",
            "receive", "and", "or", "&&", "||", "when",
        }
        count = 1

        def traverse(n):
            nonlocal count
            if n.type == 'identifier' and self._get_node_text(n) in complexity_keywords:
                count += 1
            elif n.type in ('binary_operator',):
                op_text = self._get_node_text(n)
                if '&&' in op_text or '||' in op_text or ' and ' in op_text or ' or ' in op_text:
                    count += 1
            for child in n.children:
                traverse(child)

        traverse(node)
        return count

    def _get_docstring(self, node: Any) -> Optional[str]:
        """Extract @doc or @moduledoc attribute as docstring."""
        prev = node.prev_sibling
        while prev:
            if prev.type == 'unary_operator':
                text = self._get_node_text(prev)
                if text.startswith('@doc') or text.startswith('@moduledoc'):
                    return text.strip()
            elif prev.type == 'comment':
                return self._get_node_text(prev).strip()
            else:
                break
            prev = prev.prev_sibling
        return None

    def parse(self, path: Path, is_dependency: bool = False, index_source: bool = False) -> Dict[str, Any]:
        """Parses an Elixir file and returns its structure."""
        self.index_source = index_source
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            source_code = f.read()

        tree = self.parser.parse(bytes(source_code, "utf8"))
        root_node = tree.root_node

        functions = self._find_functions(root_node)
        modules = self._find_modules(root_node)
        imports = self._find_imports(root_node)
        function_calls = self._find_calls(root_node)
        variables = []  # Elixir uses pattern matching, not traditional assignments

        return {
            "path": str(path),
            "functions": functions,
            "classes": [],  # Elixir doesn't have classes
            "variables": variables,
            "imports": imports,
            "function_calls": function_calls,
            "is_dependency": is_dependency,
            "lang": self.language_name,
            "modules": modules,
        }

    def _find_modules(self, root_node: Any) -> list[Dict[str, Any]]:
        """Find all defmodule, defprotocol, defimpl definitions."""
        modules = []
        self._find_modules_recursive(root_node, modules)
        return modules

    def _find_modules_recursive(self, node: Any, modules: list):
        """Recursively find module definitions."""
        if node.type == 'call':
            keyword = None
            name = None
            has_do_block = False

            for child in node.children:
                if child.type == 'identifier':
                    kw = self._get_node_text(child)
                    if kw in MODULE_KEYWORDS:
                        keyword = kw
                elif child.type == 'arguments' and keyword:
                    for ac in child.children:
                        if ac.type == 'alias':
                            name = self._get_node_text(ac)
                            break
                elif child.type == 'do_block':
                    has_do_block = True

            if keyword and name and has_do_block:
                module_data = {
                    "name": name,
                    "line_number": node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1,
                    "lang": self.language_name,
                    "is_dependency": False,
                    "type": keyword,  # defmodule, defprotocol, defimpl
                }
                if self.index_source:
                    module_data["source"] = self._get_node_text(node)
                modules.append(module_data)

        for child in node.children:
            self._find_modules_recursive(child, modules)

    def _find_functions(self, root_node: Any) -> list[Dict[str, Any]]:
        """Find all def, defp, defmacro, etc. definitions."""
        functions = []
        self._find_functions_recursive(root_node, functions)
        return functions

    def _find_functions_recursive(self, node: Any, functions: list):
        """Recursively find function definitions."""
        if node.type == 'call':
            keyword = None
            func_name = None
            args = []

            for child in node.children:
                if child.type == 'identifier':
                    kw = self._get_node_text(child)
                    if kw in FUNCTION_KEYWORDS:
                        keyword = kw
                elif child.type == 'arguments' and keyword:
                    for ac in child.children:
                        if ac.type == 'call':
                            # The function head: name(arg1, arg2)
                            target = ac.child_by_field_name('target')
                            if target:
                                func_name = self._get_node_text(target)
                            # Extract arguments
                            for acc in ac.children:
                                if acc.type == 'arguments':
                                    for arg in acc.children:
                                        if arg.type not in (',', '(', ')'):
                                            args.append(self._get_node_text(arg))
                        elif ac.type == 'identifier' and not func_name:
                            # Zero-arity function: def my_func, do: ...
                            func_name = self._get_node_text(ac)

            if keyword and func_name:
                module_name = self._enclosing_module_name(node)
                docstring = self._get_docstring(node)

                func_data = {
                    "name": func_name,
                    "line_number": node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1,
                    "args": args,
                    "lang": self.language_name,
                    "is_dependency": False,
                    "visibility": "private" if keyword.endswith("p") else "public",
                    "type": keyword,  # def, defp, defmacro, etc.
                }
                if self.index_source:
                    func_data["source"] = self._get_node_text(node)
                    func_data["docstring"] = docstring
                if module_name:
                    func_data["context"] = module_name
                    func_data["context_type"] = "module"
                    func_data["class_context"] = module_name

                functions.append(func_data)

        for child in node.children:
            self._find_functions_recursive(child, functions)

    def _find_imports(self, root_node: Any) -> list[Dict[str, Any]]:
        """Find all use, import, alias, require statements."""
        imports = []
        self._find_imports_recursive(root_node, imports)
        return imports

    def _find_imports_recursive(self, node: Any, imports: list):
        """Recursively find import-like statements."""
        if node.type == 'call':
            keyword = None
            path = None

            for child in node.children:
                if child.type == 'identifier':
                    kw = self._get_node_text(child)
                    if kw in IMPORT_KEYWORDS:
                        keyword = kw
                elif child.type == 'arguments' and keyword:
                    for ac in child.children:
                        if ac.type == 'alias':
                            path = self._get_node_text(ac)
                            break

            if keyword and path:
                imports.append({
                    "name": path,
                    "full_import_name": f"{keyword} {path}",
                    "line_number": node.start_point[0] + 1,
                    "alias": path.split('.')[-1] if keyword == 'alias' else None,
                    "lang": self.language_name,
                    "is_dependency": False,
                    "import_type": keyword,  # use, import, alias, require
                })

        for child in node.children:
            self._find_imports_recursive(child, imports)

    def _find_calls(self, root_node: Any) -> list[Dict[str, Any]]:
        """Find all function calls (excluding def/defmodule/etc keywords)."""
        calls = []
        self._find_calls_recursive(root_node, calls)
        return calls

    def _find_calls_recursive(self, node: Any, calls: list):
        """Recursively find function calls."""
        if node.type == 'call':
            target = None
            receiver = None
            name = None
            args = []

            for child in node.children:
                if child.type == 'dot':
                    # Module.function() style call
                    left = child.child_by_field_name('left')
                    right = child.child_by_field_name('right')
                    if left:
                        receiver = self._get_node_text(left)
                    if right:
                        name = self._get_node_text(right)
                elif child.type == 'identifier' and target is None:
                    target = self._get_node_text(child)
                elif child.type == 'arguments':
                    for arg in child.children:
                        if arg.type not in (',', '(', ')'):
                            args.append(self._get_node_text(arg))

            # Dot-call: Module.func(args)
            if name and receiver:
                full_name = f"{receiver}.{name}"
                context_name, context_type, context_line = self._get_parent_context(node)
                class_context = context_name if context_type == 'module' else None
                if context_type == 'function':
                    class_context = self._enclosing_module_name(node)

                calls.append({
                    "name": name,
                    "full_name": full_name,
                    "line_number": node.start_point[0] + 1,
                    "args": args,
                    "inferred_obj_type": receiver,
                    "context": (context_name, context_type, context_line),
                    "class_context": class_context,
                    "lang": self.language_name,
                    "is_dependency": False,
                })
            # Simple call: func(args), but skip Elixir keywords
            elif target and target not in ELIXIR_KEYWORDS:
                context_name, context_type, context_line = self._get_parent_context(node)
                class_context = context_name if context_type == 'module' else None
                if context_type == 'function':
                    class_context = self._enclosing_module_name(node)

                calls.append({
                    "name": target,
                    "full_name": target,
                    "line_number": node.start_point[0] + 1,
                    "args": args,
                    "inferred_obj_type": None,
                    "context": (context_name, context_type, context_line),
                    "class_context": class_context,
                    "lang": self.language_name,
                    "is_dependency": False,
                })

        for child in node.children:
            self._find_calls_recursive(child, calls)


def pre_scan_elixir(files: list[Path], parser_wrapper) -> dict:
    """Scans Elixir files to create a map of module/function names to their file paths."""
    imports_map = {}

    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                source = f.read()
            tree = parser_wrapper.parser.parse(bytes(source, "utf8"))
            _pre_scan_recursive(tree.root_node, path, imports_map)
        except Exception as e:
            warning_logger(f"Tree-sitter pre-scan failed for {path}: {e}")

    return imports_map


def _pre_scan_recursive(node, path: Path, imports_map: dict):
    """Recursively scan for module and function names."""
    if node.type == 'call':
        for child in node.children:
            if child.type == 'identifier':
                keyword = child.text.decode('utf-8')
                if keyword in MODULE_KEYWORDS:
                    # Get module name
                    for sib in node.children:
                        if sib.type == 'arguments':
                            for ac in sib.children:
                                if ac.type == 'alias':
                                    name = ac.text.decode('utf-8')
                                    if name not in imports_map:
                                        imports_map[name] = []
                                    imports_map[name].append(str(path.resolve()))
                elif keyword in FUNCTION_KEYWORDS:
                    # Get function name
                    for sib in node.children:
                        if sib.type == 'arguments':
                            for ac in sib.children:
                                if ac.type == 'call':
                                    target = ac.child_by_field_name('target')
                                    if target:
                                        name = target.text.decode('utf-8')
                                        if name not in imports_map:
                                            imports_map[name] = []
                                        imports_map[name].append(str(path.resolve()))
                break

    for child in node.children:
        _pre_scan_recursive(child, path, imports_map)
