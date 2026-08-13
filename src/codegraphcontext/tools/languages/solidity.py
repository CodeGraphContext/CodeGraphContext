# src/codegraphcontext/tools/languages/solidity.py
"""Solidity tree-sitter parser (tree-sitter-language-pack ``solidity`` grammar)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from codegraphcontext.utils.debug_log import error_logger, warning_logger
from codegraphcontext.utils.tree_sitter_manager import execute_query
from codegraphcontext.tools.languages.solidity_remappings import (
    find_solidity_project_root,
    load_solidity_remappings,
    resolve_solidity_import_path,
)

# Built-in free-call names filtered from the call graph (v1).
SOLIDITY_BUILT_INS: Set[str] = {
    "require",
    "assert",
    "revert",
    "keccak256",
    "sha256",
    "ripemd160",
    "ecrecover",
    "addmod",
    "mulmod",
    "blockhash",
    "blobhash",
    "gasleft",
    "selfdestruct",
    "suicide",
}

# Receivers whose member calls are usually harness / language noise.
SOLIDITY_BUILTIN_RECEIVERS: Set[str] = {
    "vm",
    "msg",
    "block",
    "tx",
    "abi",
    "type",
}

TYPE_CONTAINER_TYPES = (
    "contract_declaration",
    "interface_declaration",
    "library_declaration",
    "struct_declaration",
    "enum_declaration",
)

FUNCTION_LIKE_TYPES = (
    "function_definition",
    "constructor_definition",
    "modifier_definition",
    "fallback_receive_definition",
)

SOLIDITY_QUERIES = {
    # Keep patterns simple: field-optional / `?` forms break some pack grammars.
    # Names and parameter lists are extracted from the captured nodes in Python.
    "functions": """
        (function_definition) @function_node
        (constructor_definition) @function_node
        (modifier_definition) @function_node
        (fallback_receive_definition) @function_node
    """,
    "classes": """
        (contract_declaration) @class
        (interface_declaration) @class
        (library_declaration) @class
        (struct_declaration) @class
        (enum_declaration) @class
        (event_definition) @class
        (error_declaration) @class
    """,
    "imports": """
        (import_directive) @import
    """,
    "calls": """
        (call_expression) @call_node
    """,
    "variables": """
        (state_variable_declaration) @variable
        (variable_declaration) @variable
    """,
    "using": """
        (using_directive) @using
    """,
    "modifiers": """
        (modifier_invocation) @modifier_invocation
    """,
    "emits": """
        (emit_statement) @emit
    """,
    "reverts": """
        (revert_statement) @revert
    """,
}


class SolidityTreeSitterParser:
    """A Solidity-specific parser using tree-sitter."""

    def __init__(self, generic_parser_wrapper: Any):
        self.generic_parser_wrapper = generic_parser_wrapper
        self.language_name = "solidity"
        self.language = generic_parser_wrapper.language
        self.parser = generic_parser_wrapper.parser
        self.index_source = False
        self._repo_path: Optional[Path] = None
        self._file_path: Optional[Path] = None
        self._project_root: Optional[Path] = None
        self._remappings = None

    def _get_node_text(self, node: Any) -> str:
        if not node:
            return ""
        return node.text.decode("utf-8")

    def _get_parent_context(
        self, node: Any, types: Tuple[str, ...] = FUNCTION_LIKE_TYPES + TYPE_CONTAINER_TYPES
    ) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        curr = node.parent
        while curr:
            if curr.type in types:
                if curr.type == "constructor_definition":
                    return "constructor", curr.type, curr.start_point[0] + 1
                if curr.type == "fallback_receive_definition":
                    return self._fallback_receive_name(curr), curr.type, curr.start_point[0] + 1
                name_node = curr.child_by_field_name("name")
                if name_node is None:
                    for child in curr.children:
                        if child.type == "identifier":
                            name_node = child
                            break
                return (
                    self._get_node_text(name_node) if name_node else None,
                    curr.type,
                    curr.start_point[0] + 1,
                )
            curr = curr.parent
        return None, None, None

    def _enclosing_type_name(self, node: Any) -> Optional[str]:
        name, typ, _ = self._get_parent_context(node, TYPE_CONTAINER_TYPES)
        return name if typ in TYPE_CONTAINER_TYPES else None

    def _fallback_receive_name(self, node: Any) -> str:
        text = self._get_node_text(node)
        if re.search(r"\breceive\b", text):
            return "receive"
        if re.search(r"\bfallback\b", text):
            return "fallback"
        return "fallback"

    def _calculate_complexity(self, node: Any) -> int:
        from codegraphcontext.tools.indexing.constants import MAX_AST_DEPTH

        decision_types = {
            "if_statement",
            "for_statement",
            "while_statement",
            "do_while_statement",
            "try_statement",
            "catch_clause",
            "ternary_expression",
            "yul_if",
            "yul_for_statement",
            "yul_switch_statement",
        }
        count = 1
        skipped = False

        def traverse(n: Any, depth: int = 0) -> None:
            nonlocal count, skipped
            if depth > MAX_AST_DEPTH:
                skipped = True
                return
            if n.type in decision_types:
                count += 1
            elif n.type == "binary_expression":
                op = n.child_by_field_name("operator")
                if op and self._get_node_text(op) in ("&&", "||"):
                    count += 1
            for child in n.children:
                traverse(child, depth + 1)

        traverse(node)
        if skipped:
            warning_logger(
                f"AST depth exceeded {MAX_AST_DEPTH} levels; "
                "complexity count may be underestimated."
            )
        return count

    def _get_docstring(self, node: Any) -> Optional[str]:
        prev = node.prev_sibling
        chunks: List[str] = []
        while prev and prev.type in ("comment", "natSpec"):
            text = self._get_node_text(prev).strip()
            if text.startswith("///") or text.startswith("/**") or text.startswith("//"):
                chunks.append(text)
            prev = prev.prev_sibling
        if not chunks:
            return None
        chunks.reverse()
        return "\n".join(chunks)

    def parse(
        self, path: Path, is_dependency: bool = False, index_source: bool = False, **kwargs: Any
    ) -> Dict[str, Any]:
        self.index_source = index_source
        repo_path_arg = kwargs.get("repo_path")
        self._repo_path = Path(repo_path_arg) if repo_path_arg else None
        self._file_path = Path(path)
        self._project_root = find_solidity_project_root(self._file_path) or self._repo_path
        self._remappings = (
            load_solidity_remappings(self._project_root) if self._project_root else None
        )
        empty = {
            "path": str(path),
            "functions": [],
            "classes": [],
            "interfaces": [],
            "structs": [],
            "enums": [],
            "variables": [],
            "imports": [],
            "function_calls": [],
            "using_directives": [],
            "is_dependency": is_dependency,
            "lang": self.language_name,
        }
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                source_code = handle.read()

            if not source_code.strip():
                warning_logger(f"Empty or whitespace-only file: {path}")
                return empty

            tree = self.parser.parse(bytes(source_code, "utf8"))
            root = tree.root_node

            # Extract sections independently so one bad query does not wipe the file.
            try:
                functions = self._find_functions(root, path)
            except Exception as exc:
                error_logger(f"Solidity functions extract failed for {path}: {exc}")
                functions = []
            try:
                type_groups = self._find_types(root, path)
            except Exception as exc:
                error_logger(f"Solidity types extract failed for {path}: {exc}")
                type_groups = {
                    "classes": [],
                    "interfaces": [],
                    "structs": [],
                    "enums": [],
                }
            try:
                imports = self._find_imports(root, path)
            except Exception as exc:
                error_logger(f"Solidity imports extract failed for {path}: {exc}")
                imports = []
            try:
                variables = self._find_variables(root, path)
            except Exception as exc:
                error_logger(f"Solidity variables extract failed for {path}: {exc}")
                variables = []
            try:
                using_directives = self._find_using_directives(root)
            except Exception as exc:
                error_logger(f"Solidity using-for extract failed for {path}: {exc}")
                using_directives = []
            try:
                calls = self._find_calls(root, variables=variables, using_directives=using_directives)
                calls.extend(self._find_modifier_invocations(root))
                calls.extend(self._find_emit_statements(root))
                calls.extend(self._find_revert_statements(root))
            except Exception as exc:
                error_logger(f"Solidity calls extract failed for {path}: {exc}")
                calls = []

            return {
                "path": str(path),
                "functions": functions,
                "classes": type_groups["classes"],
                "interfaces": type_groups["interfaces"],
                "structs": type_groups["structs"],
                "enums": type_groups["enums"],
                "variables": variables,
                "imports": imports,
                "function_calls": calls,
                "using_directives": using_directives,
                "is_dependency": is_dependency,
                "lang": self.language_name,
            }
        except Exception as exc:
            error_logger(f"Error parsing Solidity file {path}: {exc}")
            return empty

    def _extract_parameters(self, func_node: Any) -> List[str]:
        """Collect parameter names from a function-like node.

        tree-sitter-solidity exposes parameters as direct ``parameter``
        children of the function/modifier/constructor node (not always a
        ``parameter_list`` wrapper).
        """
        if func_node is None:
            return []
        names: List[str] = []

        def add_from_parameter(param_node: Any) -> None:
            name_node = param_node.child_by_field_name("name")
            if name_node is None:
                for child in param_node.children:
                    if child.type == "identifier":
                        name_node = child
                        break
            if name_node is not None:
                names.append(self._get_node_text(name_node))

        params_wrapper = func_node.child_by_field_name("parameters")
        if params_wrapper is not None:
            for child in params_wrapper.named_children:
                if child.type == "parameter":
                    add_from_parameter(child)
            if names:
                return names

        for child in func_node.children:
            if child.type == "parameter":
                add_from_parameter(child)
            elif child.type == "parameter_list":
                for nested in child.named_children:
                    if nested.type == "parameter":
                        add_from_parameter(nested)
        return names

    def _find_functions(self, root_node: Any, path: Path) -> List[Dict[str, Any]]:
        functions: List[Dict[str, Any]] = []
        seen: Set[Tuple[int, int, str]] = set()

        for node, capture_name in execute_query(
            self.language, SOLIDITY_QUERIES["functions"], root_node
        ):
            if capture_name != "function_node":
                continue
            node_id = (node.start_byte, node.end_byte, node.type)
            if node_id in seen:
                continue
            seen.add(node_id)

            if node.type == "constructor_definition":
                func_name = "constructor"
            elif node.type == "fallback_receive_definition":
                func_name = self._fallback_receive_name(node)
            else:
                name_node = node.child_by_field_name("name")
                if not name_node:
                    continue
                func_name = self._get_node_text(name_node)

            parameters = self._extract_parameters(node)
            class_context = self._enclosing_type_name(node)

            func_data: Dict[str, Any] = {
                "name": func_name,
                "parameters": parameters,
                "args": parameters,
                "line_number": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "path": str(path),
                "lang": self.language_name,
                "context": class_context,
                "class_context": class_context,
                "decorators": [],
                "is_dependency": False,
                "cyclomatic_complexity": self._calculate_complexity(node),
                "kind": node.type,
            }
            if self.index_source:
                func_data["source"] = self._get_node_text(node)
                func_data["docstring"] = self._get_docstring(node)
            functions.append(func_data)

        return functions

    def _extract_bases(self, type_node: Any) -> List[str]:
        bases: List[str] = []
        for child in type_node.children:
            if child.type != "inheritance_specifier":
                continue
            ancestor = child.child_by_field_name("ancestor")
            if ancestor is None:
                # Fallback: first user_defined_type / identifier under specifier.
                for sub in child.children:
                    if sub.type in ("user_defined_type", "identifier", "type_name"):
                        ancestor = sub
                        break
            if ancestor is None:
                continue
            text = self._get_node_text(ancestor).strip()
            # user_defined_type may be `Foo` or nested; take last identifier segment.
            simple = text.split(".")[-1].strip()
            if simple and simple not in bases:
                bases.append(simple)
        return bases

    def _find_types(self, root_node: Any, path: Path) -> Dict[str, List[Dict[str, Any]]]:
        results: Dict[str, List[Dict[str, Any]]] = {
            "classes": [],
            "interfaces": [],
            "structs": [],
            "enums": [],
        }
        seen: Set[Tuple[int, int, str]] = set()

        for node, capture_name in execute_query(
            self.language, SOLIDITY_QUERIES["classes"], root_node
        ):
            if capture_name != "class":
                continue
            node_id = (node.start_byte, node.end_byte, node.type)
            if node_id in seen:
                continue
            seen.add(node_id)

            name_node = node.child_by_field_name("name")
            if not name_node:
                continue
            name = self._get_node_text(name_node)

            if node.type == "interface_declaration":
                category = "interfaces"
                label = "Interface"
            elif node.type == "struct_declaration":
                category = "structs"
                label = "Struct"
            elif node.type == "enum_declaration":
                category = "enums"
                label = "Enum"
            elif node.type in ("event_definition", "error_declaration"):
                # Keep events/errors as Class-like nodes for discoverability.
                category = "classes"
                label = "Class"
            else:
                # contracts + libraries
                category = "classes"
                label = "Class"

            class_data: Dict[str, Any] = {
                "name": name,
                "line_number": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "bases": self._extract_bases(node),
                "path": str(path),
                "lang": self.language_name,
                "is_dependency": False,
                "node_label": label,
                "solidity_kind": node.type,
            }
            if self.index_source:
                class_data["source"] = self._get_node_text(node)
                class_data["docstring"] = self._get_docstring(node)
            results[category].append(class_data)

        return results

    def _strip_quotes(self, raw: str) -> str:
        return raw.strip().strip("'\"")

    def _import_source_path(self, import_node: Any) -> Optional[str]:
        source = import_node.child_by_field_name("source")
        if source is not None and source.type == "string":
            return self._strip_quotes(self._get_node_text(source))
        for child in import_node.children:
            if child.type == "string":
                return self._strip_quotes(self._get_node_text(child))
        return None

    def _find_imports(self, root_node: Any, path: Path) -> List[Dict[str, Any]]:
        imports: List[Dict[str, Any]] = []
        seen: Set[Tuple[int, str]] = set()

        for node, capture_name in execute_query(
            self.language, SOLIDITY_QUERIES["imports"], root_node
        ):
            if capture_name != "import":
                continue
            source = self._import_source_path(node)
            if not source:
                continue

            effective_source, resolved_fs = resolve_solidity_import_path(
                source,
                importer_file=Path(path),
                repo_path=self._repo_path or self._project_root,
                config=self._remappings,
            )

            line_number = node.start_point[0] + 1
            # Named symbols: import {Foo, Bar as B} from "...";
            symbols: List[Tuple[str, Optional[str]]] = []
            for child in node.children:
                if child.type == "import_declaration":
                    origin = child.child_by_field_name("import_origin") or child.child_by_field_name(
                        "name"
                    )
                    alias = child.child_by_field_name("import_alias") or child.child_by_field_name(
                        "alias"
                    )
                    if origin:
                        symbols.append(
                            (
                                self._get_node_text(origin),
                                self._get_node_text(alias) if alias else None,
                            )
                        )

            import_text = self._get_node_text(node)
            brace_match = re.search(r"\{([^}]+)\}", import_text)
            if brace_match and not symbols:
                for part in brace_match.group(1).split(","):
                    part = part.strip()
                    if not part:
                        continue
                    if " as " in part:
                        origin, alias = [p.strip() for p in part.split(" as ", 1)]
                        symbols.append((origin, alias))
                    else:
                        symbols.append((part, None))

            as_match = re.search(
                r'import\s+(?:\*\s+as\s+(\w+)|(\w+)\s+as\s+(\w+))\s+from\s+["\']',
                import_text,
            )
            path_as = re.search(
                r'import\s+["\'][^"\']+["\']\s+as\s+(\w+)',
                import_text,
            )

            def _row(name: str, alias: Optional[str]) -> Dict[str, Any]:
                return {
                    "name": name,
                    "full_import_name": effective_source,
                    "source": effective_source,
                    "raw_source": source,
                    "alias": alias,
                    "line_number": line_number,
                    "lang": self.language_name,
                    "is_dependency": False,
                    "context": (None, None),
                    "resolved_path": resolved_fs,
                    "remapped": effective_source != source,
                }

            if symbols:
                for origin, alias in symbols:
                    key = (line_number, f"{origin}->{alias}:{effective_source}")
                    if key in seen:
                        continue
                    seen.add(key)
                    imports.append(_row(origin, alias))
            else:
                alias = None
                if as_match:
                    alias = as_match.group(1) or as_match.group(3)
                elif path_as:
                    alias = path_as.group(1)
                stem = Path(effective_source).stem
                key = (line_number, f"*->{alias}:{effective_source}")
                if key in seen:
                    continue
                seen.add(key)
                imports.append(_row(stem, alias))

        return imports

    def _normalize_type_name(self, raw: str) -> str:
        t = re.sub(r"\s+", " ", raw).strip()
        if t == "*":
            return "*"
        aliases = {
            "uint": "uint256",
            "int": "int256",
            "ufixed": "ufixed128x18",
            "fixed": "fixed128x18",
        }
        return aliases.get(t, t)

    def _type_name_from_node(self, type_node: Optional[Any]) -> Optional[str]:
        if type_node is None:
            return None
        if type_node.type == "type_name" and type_node.named_child_count > 0:
            return self._type_name_from_node(type_node.named_child(0))
        if type_node.type in ("primitive_type", "elementary_type_name"):
            return self._normalize_type_name(self._get_node_text(type_node))
        if type_node.type == "any_source_type":
            return "*"
        if type_node.type == "user_defined_type":
            text = self._get_node_text(type_node)
            return self._normalize_type_name(text.split(".")[-1])
        if type_node.type == "identifier":
            return self._normalize_type_name(self._get_node_text(type_node))
        return self._normalize_type_name(self._get_node_text(type_node))

    def _find_using_directives(self, root_node: Any) -> List[Dict[str, Any]]:
        directives: List[Dict[str, Any]] = []
        try:
            captures = list(
                execute_query(self.language, SOLIDITY_QUERIES["using"], root_node)
            )
        except Exception:
            # Fallback: walk AST if query unsupported.
            captures = []
            stack = [root_node]
            while stack:
                node = stack.pop()
                if node.type == "using_directive":
                    captures.append((node, "using"))
                stack.extend(reversed(list(node.children)))

        for node, capture_name in captures:
            if capture_name != "using":
                continue
            lib_name: Optional[str] = None
            type_key: Optional[str] = None
            for child in node.named_children:
                if child.type == "type_alias":
                    inner = child.named_child(0) if child.named_child_count else child
                    lib_name = self._get_node_text(inner).strip()
                elif child.type in (
                    "type_name",
                    "any_source_type",
                    "user_defined_type",
                    "primitive_type",
                    "elementary_type_name",
                ):
                    type_key = self._type_name_from_node(child)
                elif child.type == "identifier" and lib_name is None:
                    lib_name = self._get_node_text(child).strip()

            # Text fallback: `using MathLib for uint256;`
            if lib_name is None or type_key is None:
                text = self._get_node_text(node)
                m = re.search(
                    r"using\s+(\w+)\s+for\s+(\*|[\w\[\]]+)",
                    text,
                )
                if m:
                    lib_name = lib_name or m.group(1)
                    type_key = type_key or self._normalize_type_name(m.group(2))

            if not lib_name or not type_key:
                continue
            owner = self._enclosing_type_name(node)
            directives.append(
                {
                    "library": lib_name,
                    "type": type_key,
                    "class_context": owner,
                    "line_number": node.start_point[0] + 1,
                    "lang": self.language_name,
                }
            )
        return directives

    def _find_modifier_invocations(self, root_node: Any) -> List[Dict[str, Any]]:
        calls: List[Dict[str, Any]] = []
        seen: Set[str] = set()
        try:
            captures = list(
                execute_query(self.language, SOLIDITY_QUERIES["modifiers"], root_node)
            )
        except Exception:
            captures = []
            stack = [root_node]
            while stack:
                node = stack.pop()
                if node.type == "modifier_invocation":
                    captures.append((node, "modifier_invocation"))
                stack.extend(reversed(list(node.children)))

        for node, capture_name in captures:
            if capture_name != "modifier_invocation":
                continue
            name_node = node.child_by_field_name("name")
            if name_node is None:
                for child in node.children:
                    if child.type == "identifier":
                        name_node = child
                        break
            if name_node is None:
                # `nonEmpty(name)` — first identifier
                text = self._get_node_text(node)
                m = re.match(r"([A-Za-z_][\w]*)", text.strip())
                mod_name = m.group(1) if m else None
            else:
                mod_name = self._get_node_text(name_node)
            if not mod_name:
                continue

            ctx_name, ctx_type, ctx_line = self._get_parent_context(node, FUNCTION_LIKE_TYPES)
            if not ctx_name:
                continue
            class_context = self._enclosing_type_name(node)
            line_number = node.start_point[0] + 1
            key = f"mod:{mod_name}:{ctx_name}:{line_number}"
            if key in seen:
                continue
            seen.add(key)
            calls.append(
                {
                    "name": mod_name,
                    "full_name": mod_name,
                    "line_number": line_number,
                    "args": [],
                    "inferred_obj_type": None,
                    "context": (ctx_name, ctx_type, ctx_line),
                    "class_context": class_context,
                    "lang": self.language_name,
                    "is_dependency": False,
                    "call_kind": "modifier_invocation",
                }
            )
        return calls

    def _emit_or_revert_name(self, node: Any) -> Optional[str]:
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            text = self._get_node_text(name_node).strip()
            return text.split(".")[-1] if text else None
        for child in node.children:
            if child.type in ("identifier", "user_defined_type", "expression"):
                text = self._get_node_text(child).strip()
                if text and text not in ("emit", "revert"):
                    return text.split("(")[0].split(".")[-1].strip()
        text = self._get_node_text(node)
        m = re.search(r"\b(?:emit|revert)\s+([A-Za-z_][\w]*)", text)
        return m.group(1) if m else None

    def _find_emit_statements(self, root_node: Any) -> List[Dict[str, Any]]:
        return self._find_special_statements(
            root_node,
            query_key="emits",
            capture_name="emit",
            node_type="emit_statement",
            call_kind="emit",
        )

    def _find_revert_statements(self, root_node: Any) -> List[Dict[str, Any]]:
        return self._find_special_statements(
            root_node,
            query_key="reverts",
            capture_name="revert",
            node_type="revert_statement",
            call_kind="revert_error",
        )

    def _find_special_statements(
        self,
        root_node: Any,
        *,
        query_key: str,
        capture_name: str,
        node_type: str,
        call_kind: str,
    ) -> List[Dict[str, Any]]:
        calls: List[Dict[str, Any]] = []
        seen: Set[str] = set()
        try:
            captures = list(
                execute_query(self.language, SOLIDITY_QUERIES[query_key], root_node)
            )
        except Exception:
            captures = []
            stack = [root_node]
            while stack:
                node = stack.pop()
                if node.type == node_type:
                    captures.append((node, capture_name))
                stack.extend(reversed(list(node.children)))

        for node, cap in captures:
            if cap != capture_name:
                continue
            event_or_error = self._emit_or_revert_name(node)
            if not event_or_error:
                continue
            ctx_name, ctx_type, ctx_line = self._get_parent_context(node, FUNCTION_LIKE_TYPES)
            if not ctx_name:
                # Allow file-level / modifier-body contexts via broader walk.
                ctx_name, ctx_type, ctx_line = self._get_parent_context(node)
            class_context = self._enclosing_type_name(node)
            line_number = node.start_point[0] + 1
            key = f"{call_kind}:{event_or_error}:{ctx_name}:{line_number}"
            if key in seen:
                continue
            seen.add(key)
            calls.append(
                {
                    "name": event_or_error,
                    "full_name": event_or_error,
                    "line_number": line_number,
                    "args": [],
                    "inferred_obj_type": None,
                    "context": (ctx_name, ctx_type, ctx_line),
                    "class_context": class_context,
                    "lang": self.language_name,
                    "is_dependency": False,
                    "call_kind": call_kind,
                }
            )
        return calls

    def _match_using_library(
        self,
        attachments: List[Dict[str, Any]],
        receiver_type: str,
        class_context: Optional[str],
    ) -> Optional[str]:
        norm = self._normalize_type_name(receiver_type)
        scoped = [
            a
            for a in attachments
            if a.get("class_context") in (None, class_context) or a.get("class_context") == class_context
        ]
        pool = scoped or attachments
        for item in pool:
            if item["type"] == norm:
                return item["library"]
        for item in pool:
            if item["type"] == "*":
                return item["library"]
        return None

    def _call_name_and_receiver(self, call_node: Any) -> Tuple[Optional[str], Optional[str], str]:
        """Return (callee_name, receiver_name, full_name)."""
        function_node = call_node.child_by_field_name("function")
        if function_node is None and call_node.named_child_count > 0:
            function_node = call_node.named_child(0)

        if function_node is None:
            return None, None, ""

        if function_node.type == "member_expression":
            prop = function_node.child_by_field_name("property")
            obj = function_node.child_by_field_name("object")
            if prop is None:
                for child in reversed(list(function_node.children)):
                    if child.type == "identifier":
                        prop = child
                        break
            if obj is None and function_node.named_child_count >= 1:
                obj = function_node.named_child(0)
            name = self._get_node_text(prop) if prop else None
            receiver = None
            if obj is not None:
                if obj.type == "identifier":
                    receiver = self._get_node_text(obj)
                else:
                    for child in reversed(list(obj.children)):
                        if child.type == "identifier":
                            receiver = self._get_node_text(child)
                            break
                    if receiver is None:
                        receiver = self._get_node_text(obj).split(".")[-1]
            full = self._get_node_text(function_node)
            return name, receiver, full

        if function_node.type == "identifier":
            name = self._get_node_text(function_node)
            return name, None, name

        if function_node.type == "expression":
            for child in function_node.children:
                if child.type == "identifier":
                    name = self._get_node_text(child)
                    return name, None, name
                if child.type == "member_expression":
                    return self._call_name_and_receiver_from_member(child)

        text = self._get_node_text(function_node)
        name = text.split(".")[-1] if text else None
        receiver = text.split(".")[0] if "." in text else None
        return name, receiver, text

    def _call_name_and_receiver_from_member(
        self, member_node: Any
    ) -> Tuple[Optional[str], Optional[str], str]:
        prop = member_node.child_by_field_name("property")
        obj = member_node.child_by_field_name("object")
        name = self._get_node_text(prop) if prop else None
        receiver = self._get_node_text(obj) if obj and obj.type == "identifier" else None
        if receiver is None and obj is not None:
            receiver = self._get_node_text(obj).split(".")[-1]
        return name, receiver, self._get_node_text(member_node)

    def _find_calls(
        self,
        root_node: Any,
        variables: Optional[List[Dict[str, Any]]] = None,
        using_directives: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        calls: List[Dict[str, Any]] = []
        seen: Set[str] = set()
        var_type_map: Dict[str, str] = {}
        for var in variables or []:
            name = var.get("name")
            vtype = var.get("type")
            if name and vtype and vtype != "Unknown":
                var_type_map[name] = self._normalize_type_name(vtype)
        attachments = using_directives or []

        for node, capture_name in execute_query(
            self.language, SOLIDITY_QUERIES["calls"], root_node
        ):
            if capture_name != "call_node":
                continue
            name, receiver, full_name = self._call_name_and_receiver(node)
            if not name:
                continue
            if name in SOLIDITY_BUILT_INS and receiver is None:
                continue
            if receiver in SOLIDITY_BUILTIN_RECEIVERS:
                continue

            line_number = node.start_point[0] + 1
            call_key = f"{full_name or name}_{line_number}_{node.start_byte}"
            if call_key in seen:
                continue
            seen.add(call_key)

            ctx_name, ctx_type, ctx_line = self._get_parent_context(node)
            class_context = self._enclosing_type_name(node)

            inferred_obj_type = None
            rewritten_full = full_name or name
            # Explicit Library.fn already carries library receiver.
            if receiver and receiver[:1].isupper():
                inferred_obj_type = receiver
            # using Lib for T: rewrite x.fn → Lib.fn when x's type matches.
            elif receiver and attachments:
                receiver_type = var_type_map.get(receiver)
                if receiver_type:
                    lib = self._match_using_library(attachments, receiver_type, class_context)
                    if lib:
                        inferred_obj_type = lib
                        rewritten_full = f"{lib}.{name}"
                        receiver = lib

            args: List[str] = []
            args_node = node.child_by_field_name("arguments")
            if args_node is None:
                args_node = next(
                    (c for c in node.children if c.type == "call_argument_list"), None
                )
            if args_node is not None:
                for arg in args_node.named_children:
                    args.append(self._get_node_text(arg))

            calls.append(
                {
                    "name": name,
                    "full_name": rewritten_full,
                    "line_number": line_number,
                    "args": args,
                    "inferred_obj_type": inferred_obj_type,
                    "context": (ctx_name, ctx_type, ctx_line),
                    "class_context": class_context,
                    "lang": self.language_name,
                    "is_dependency": False,
                }
            )

        return calls

    def _find_variables(self, root_node: Any, path: Path) -> List[Dict[str, Any]]:
        variables: List[Dict[str, Any]] = []
        seen: Set[int] = set()

        for node, capture_name in execute_query(
            self.language, SOLIDITY_QUERIES["variables"], root_node
        ):
            if capture_name != "variable":
                continue
            name_node = node.child_by_field_name("name")
            if name_node is None:
                for child in node.children:
                    if child.type == "identifier":
                        name_node = child
                        break
            if name_node is None:
                continue
            if name_node.start_byte in seen:
                continue
            seen.add(name_node.start_byte)

            var_name = self._get_node_text(name_node)
            type_node = node.child_by_field_name("type")
            if type_node is None:
                type_node = next(
                    (
                        c
                        for c in node.children
                        if c.type
                        in (
                            "type_name",
                            "elementary_type_name",
                            "user_defined_type",
                            "mapping",
                            "array_type",
                            "primitive_type",
                        )
                    ),
                    None,
                )
            var_type = self._get_node_text(type_node) if type_node else "Unknown"
            class_context = self._enclosing_type_name(node)
            variables.append(
                {
                    "name": var_name,
                    "type": var_type,
                    "line_number": name_node.start_point[0] + 1,
                    "path": str(path),
                    "lang": self.language_name,
                    "context": class_context,
                    "class_context": class_context,
                }
            )

        return variables


def pre_scan_solidity(files: list[Path], parser_wrapper: Any) -> dict:
    """Map contract/interface/library/struct/enum names to defining file paths."""
    name_to_files: Dict[str, List[str]] = {}
    pattern = re.compile(
        r"^\s*(?:abstract\s+)?(contract|interface|library|struct|enum)\s+(\w+)",
        re.MULTILINE,
    )

    for path in files:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            error_logger(f"Error pre-scanning Solidity file {path}: {exc}")
            continue

        for match in pattern.finditer(content):
            symbol = match.group(2)
            name_to_files.setdefault(symbol, [])
            path_str = str(path)
            if path_str not in name_to_files[symbol]:
                name_to_files[symbol].append(path_str)

        # Also map file stem for path-style imports (`import "./Foo.sol"`).
        stem = path.stem
        name_to_files.setdefault(stem, [])
        path_str = str(path)
        if path_str not in name_to_files[stem]:
            name_to_files[stem].append(path_str)

    return name_to_files
