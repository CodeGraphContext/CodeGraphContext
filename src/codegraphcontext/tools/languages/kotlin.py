# src/codegraphcontext/tools/languages/kotlin.py
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import re
from codegraphcontext.tools.type_utils import strip_type_modifiers
from codegraphcontext.utils.debug_log import debug_log, info_logger, error_logger, warning_logger
from codegraphcontext.utils.tree_sitter_manager import execute_query

KOTLIN_QUERIES = {
    "functions": """
        (function_declaration
            (simple_identifier) @name
            (function_value_parameters) @params
        ) @function_node
    """,
    "classes": """
        [
            (class_declaration (type_identifier) @name)
            (object_declaration (type_identifier) @name)
            (companion_object (type_identifier)? @name)
        ] @class
    """,
    "imports": """
        (import_header) @import
    """,
    "calls": """
        (call_expression) @call_node
        (constructor_invocation) @call_node
        (constructor_delegation_call) @call_node
        (callable_reference) @call_node
    """,
    "variables": """
        (property_declaration
            (variable_declaration
                (simple_identifier) @name
            )
        ) @variable
        (class_parameter
            (binding_pattern_kind)
            (simple_identifier) @name
        ) @variable
        (parameter
            (simple_identifier) @name
        ) @variable
    """,
}

class KotlinTreeSitterParser:
    def __init__(self, generic_parser_wrapper: Any):
        self.generic_parser_wrapper = generic_parser_wrapper
        self.language_name = "kotlin"
        self.language = generic_parser_wrapper.language
        self.parser = generic_parser_wrapper.parser

    @staticmethod
    def _strip_type_modifiers(type_str: str) -> str:
        """Return the receiver type CGC can resolve, e.g. 'List<T>?' -> 'List'."""
        return strip_type_modifiers(type_str)

    @staticmethod
    def _extract_package_name(source_code: str) -> str:
        match = re.search(r'^\s*package\s+([\w\.]+)', source_code, re.MULTILINE)
        return match.group(1) if match else ""

    def parse(self, path: Path, is_dependency: bool = False, index_source: bool = False) -> Dict[str, Any]:
        try:
            self.index_source = index_source
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                source_code = f.read()

            if not source_code.strip():
                warning_logger(f"Empty or whitespace-only file: {path}")
                return {
                    "path": str(path),
                    "functions": [],
                    "classes": [],
                    "variables": [],
                    "typealiases": [],
                    "imports": [],
                    "function_calls": [],
                    "is_dependency": is_dependency,
                    "lang": self.language_name,
                    "package": "",
                }

            tree = self.parser.parse(bytes(source_code, "utf8"))

            parsed_functions = []
            parsed_classes = []
            parsed_variables = []
            parsed_imports = []
            parsed_calls = []
            package_name = self._extract_package_name(source_code)
            parsed_typealiases = self._parse_typealiases(source_code, path, package_name)

            if 'functions' in KOTLIN_QUERIES:
                results = execute_query(self.language, KOTLIN_QUERIES['functions'], tree.root_node)
                parsed_functions.extend(self._parse_functions(results, source_code, path))

            # Parse Variables after functions so fallback destructuring can keep function scope.
            if 'variables' in KOTLIN_QUERIES:
                results = execute_query(self.language, KOTLIN_QUERIES['variables'], tree.root_node)
                parsed_variables = self._parse_variables(results, source_code, path, parsed_functions)

            for capture_name, query in KOTLIN_QUERIES.items():
                if capture_name in {'functions', 'variables'}: continue # Already done
                results = execute_query(self.language, query, tree.root_node)

                if capture_name == "classes":
                    all_types = self._parse_classes(results, source_code, path)
                    parsed_classes = all_types.get("classes", [])
                    parsed_interfaces = all_types.get("interfaces", [])
                    parsed_objects = all_types.get("objects", [])
                elif capture_name == "imports":
                    parsed_imports.extend(self._parse_imports(results, source_code))
                elif capture_name == "calls":
                    parsed_calls.extend(self._parse_calls(results, source_code, path, parsed_variables, parsed_functions))

            return {
                "path": str(path),
                "functions": parsed_functions,
                "classes": parsed_classes,
                "interfaces": parsed_interfaces,
                "objects": parsed_objects,
                "variables": parsed_variables,
                "typealiases": parsed_typealiases,
                "imports": parsed_imports,
                "function_calls": parsed_calls,
                "is_dependency": is_dependency,
                "lang": self.language_name,
                "package": package_name,
            }

        except Exception as e:
            error_logger(f"Error parsing Kotlin file {path}: {e}")
            return {
                "path": str(path),
                "functions": [],
                "classes": [],
                "variables": [],
                "typealiases": [],
                "imports": [],
                "function_calls": [],
                "is_dependency": is_dependency,
                "lang": self.language_name,
                "package": "",
            }

    def _get_parent_context(self, node: Any) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        curr = node.parent
        while curr:
            if curr.type in ("function_declaration",):
                name_node = None
                for child in curr.children:
                    if child.type == "simple_identifier":
                        name_node = child
                        break
                return (
                    self._get_node_text(name_node) if name_node else None,
                    curr.type,
                    curr.start_point[0] + 1,
                )
            if curr.type in ("class_declaration", "interface_declaration", "object_declaration"):
                for child in curr.children:
                    if child.type in ("simple_identifier", "type_identifier"):
                         return (
                            self._get_node_text(child),
                            curr.type,
                            curr.start_point[0] + 1,
                        )
                # Check for secondary constructors
                if curr.type == "secondary_constructor":
                    return (
                        "constructor",
                        curr.type,
                        curr.start_point[0] + 1
                    )
                    
            if curr.type == "companion_object":
                 name = "Companion"
                 for child in curr.children:
                     if child.type in ("simple_identifier", "type_identifier"): 
                         name = self._get_node_text(child)
                         break
                 return (
                    name,
                    curr.type,
                    curr.start_point[0] + 1,
                )
            
            # Handle anonymous objects (object_literal)
            if curr.type == "object_literal":
                 # checking if it is assigned to a variable to get a name?
                 # or simply "AnonymousObject"
                 # It's usually hard to name them without variable context.
                 # We can check if parent is property/variable declaration
                 name = "AnonymousObject"
                 return (
                    name,
                    curr.type,
                    curr.start_point[0] + 1
                 )

            curr = curr.parent
        return None, None, None

    def _get_node_text(self, node: Any) -> str:
        if not node: return ""
        return node.text.decode("utf-8")

    def _get_enclosing_class_context(self, node: Any) -> Tuple[Optional[str], Optional[int]]:
        curr = node.parent
        while curr:
            if curr.type in ("class_declaration", "interface_declaration", "object_declaration"):
                for child in curr.children:
                    if child.type in ("simple_identifier", "type_identifier"):
                        return self._get_node_text(child), curr.start_point[0] + 1
            curr = curr.parent
        return None, None

    def _lookup_scoped_declaration_type(
        self,
        declarations: Optional[Dict[Tuple[str, Any], list[Tuple[Optional[int], Optional[str]]]]],
        name: str,
        context: Any,
        line_number: Optional[int],
    ) -> Tuple[bool, Optional[str]]:
        if not declarations or not isinstance(context, tuple) or line_number is None:
            return False, None

        candidates = [
            (decl_line, decl_type)
            for decl_line, decl_type in declarations.get((name, context), [])
            if decl_line is not None and decl_line <= line_number
        ]
        if not candidates:
            return False, None

        _, decl_type = max(candidates, key=lambda item: item[0] or 0)
        return True, decl_type

    def _unique_variable_type(
        self,
        var_map: Dict[Tuple[str, Any], str],
        name: str,
        context: Any = None,
        line_number: Optional[int] = None,
        declarations: Optional[Dict[Tuple[str, Any], list[Tuple[Optional[int], Optional[str]]]]] = None,
    ) -> Optional[str]:
        values = set()
        for (vname, scope), vtype in var_map.items():
            if vname != name or not vtype or vtype == "Unknown":
                continue
            if isinstance(context, tuple) and scope == context and line_number is not None:
                found, scoped_type = self._lookup_scoped_declaration_type(
                    declarations,
                    name,
                    context,
                    line_number,
                )
                if found and scoped_type:
                    values.add(scoped_type)
                continue
            values.add(vtype)
        return next(iter(values)) if len(values) == 1 else None

    def _lookup_variable_type(
        self,
        var_map: Dict[Tuple[str, Any], str],
        name: str,
        context: Any,
        declarations: Optional[Dict[Tuple[str, Any], list[Tuple[Optional[int], Optional[str]]]]] = None,
        line_number: Optional[int] = None,
    ) -> Optional[str]:
        found, scoped_type = self._lookup_scoped_declaration_type(
            declarations,
            name,
            context,
            line_number,
        )
        if found:
            return scoped_type

        if not (isinstance(context, tuple) and line_number is not None):
            inferred_type = var_map.get((name, context))
            if inferred_type:
                return inferred_type
        class_context = context[2] if isinstance(context, tuple) and len(context) >= 3 else None
        inferred_type = var_map.get((name, class_context))
        if inferred_type:
            return inferred_type
        inferred_type = var_map.get((name, None))
        if inferred_type:
            return inferred_type
        return self._unique_variable_type(
            var_map,
            name,
            context,
            line_number,
            declarations,
        )

    def _lookup_raw_variable_type(
        self,
        var_map: Dict[Tuple[str, Any], str],
        name: str,
        context: Any,
        enclosing_class: Optional[str] = None,
        declarations: Optional[Dict[Tuple[str, Any], list[Tuple[Optional[int], Optional[str]]]]] = None,
        line_number: Optional[int] = None,
    ) -> Optional[str]:
        found, scoped_type = self._lookup_scoped_declaration_type(
            declarations,
            name,
            context,
            line_number,
        )
        if found:
            return scoped_type

        keys = [(name, enclosing_class), (name, None)]
        if not (isinstance(context, tuple) and line_number is not None):
            keys.insert(0, (name, context))

        for key in keys:
            inferred_type = var_map.get(key)
            if inferred_type and inferred_type != "Unknown":
                return inferred_type
        return self._unique_variable_type(
            var_map,
            name,
            context,
            line_number,
            declarations,
        )

    def _generic_type_args(self, type_name: Optional[str]) -> list[str]:
        if not type_name or "<" not in type_name or ">" not in type_name:
            return []
        inner = type_name[type_name.find("<") + 1:type_name.rfind(">")]
        return [arg.strip() for arg in self._split_parameters(inner) if arg.strip()]

    def _map_value_type(self, type_name: Optional[str]) -> Optional[str]:
        args = self._generic_type_args(type_name)
        if len(args) < 2:
            return None
        return self._strip_type_modifiers(args[1])

    def _collection_element_type(self, type_name: Optional[str]) -> Optional[str]:
        args = self._generic_type_args(type_name)
        if not args:
            return None
        return self._strip_type_modifiers(args[0])

    def _indexed_access_value_type(
        self,
        expr: str,
        context: Any,
        enclosing_class: Optional[str],
        raw_var_map: Dict[Tuple[str, Any], str],
        raw_declarations: Optional[Dict[Tuple[str, Any], list[Tuple[Optional[int], Optional[str]]]]] = None,
        line_number: Optional[int] = None,
    ) -> Optional[str]:
        match = re.match(r"([A-Za-z_]\w*)\s*\[", expr.strip())
        if not match:
            return None
        receiver_type = self._lookup_raw_variable_type(
            raw_var_map,
            match.group(1),
            context,
            enclosing_class,
            raw_declarations,
            line_number,
        )
        return self._map_value_type(receiver_type)

    def _collection_lambda_hint(
        self,
        node: Any,
        context: Any,
        enclosing_class: Optional[str],
        raw_var_map: Dict[Tuple[str, Any], str],
        raw_declarations: Optional[Dict[Tuple[str, Any], list[Tuple[Optional[int], Optional[str]]]]] = None,
        line_number: Optional[int] = None,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        curr = node.parent
        while curr:
            text = self._get_node_text(curr)
            if "{" not in text:
                curr = curr.parent
                continue
            receiver_match = re.search(
                r"([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*\.\s*(forEach|any|map|mapValues)\s*\{",
                text,
                re.S,
            )
            if not receiver_match:
                curr = curr.parent
                continue

            receiver_expr = receiver_match.group(1)
            function_name = receiver_match.group(2)
            param_match = re.search(r"\{\s*([A-Za-z_]\w*)\s*->", text)
            param_name = param_match.group(1) if param_match else "it"

            if receiver_expr.endswith(".values"):
                base_name = receiver_expr.rsplit(".", 1)[0]
                receiver_type = self._lookup_raw_variable_type(
                    raw_var_map,
                    base_name,
                    context,
                    enclosing_class,
                    raw_declarations,
                    line_number,
                )
                return param_name, self._map_value_type(receiver_type), None

            receiver_type = self._lookup_raw_variable_type(
                raw_var_map,
                receiver_expr,
                context,
                enclosing_class,
                raw_declarations,
                line_number,
            )
            if function_name == "mapValues":
                return param_name, None, self._map_value_type(receiver_type)

            return param_name, self._collection_element_type(receiver_type), None

        return None, None, None

    def _parse_typealiases(
        self,
        source_code: str,
        path: Path,
        package_name: str,
    ) -> list[Dict[str, Any]]:
        typealiases = []
        pattern = re.compile(
            r'^[ \t]*typealias\s+([A-Za-z_]\w*)\s*=\s*([A-Za-z_][\w\.]*(?:<[^>\n]+>)?\??)',
            re.MULTILINE,
        )
        for match in pattern.finditer(source_code):
            typealiases.append(
                {
                    "name": match.group(1),
                    "target": match.group(2).strip(),
                    "line_number": source_code.count("\n", 0, match.start()) + 1,
                    "path": str(path),
                    "package": package_name,
                    "lang": self.language_name,
                }
            )
        return typealiases

    def _infer_receiver_type(
        self,
        expression: str,
        context: Any,
        enclosing_class: Optional[str],
        var_map: Dict[Tuple[str, Any], str],
        function_return_map: Dict[Tuple[Optional[str], str], str],
        declarations: Optional[Dict[Tuple[str, Any], list[Tuple[Optional[int], Optional[str]]]]] = None,
        line_number: Optional[int] = None,
    ) -> Optional[str]:
        context_name = context[0] if isinstance(context, tuple) and context else context
        expr = self._normalize_receiver_expression(expression)
        cast_type = self._extract_cast_type(expr)
        if cast_type:
            return self._strip_type_modifiers(cast_type)

        generic_factory_type = self._extract_generic_factory_type(expr)
        if generic_factory_type:
            return self._strip_type_modifiers(generic_factory_type)

        candidate_type = self._common_type_for_candidate_names(
            self._initializer_candidate_names(expr),
            context,
            var_map,
            declarations,
            line_number,
        )
        if candidate_type:
            return candidate_type

        if expr == "this":
            return enclosing_class
        if expr == "super":
            return None
        if re.fullmatch(r"[A-Za-z_]\w*", expr):
            variable_type = self._lookup_variable_type(
                var_map,
                expr,
                context,
                declarations,
                line_number,
            )
            if variable_type:
                return variable_type
            if re.fullmatch(r"[A-Z][A-Za-z_]\w*", expr):
                return expr

        call_target = self._call_target_without_value_args(expr)
        if call_target:
            if "." in call_target:
                base_expr, member_name = call_target.rsplit(".", 1)
                member_name = member_name.split("<", 1)[0]
                if member_name == "spanBuilder":
                    return "SpanBuilder"
                if member_name in {"startSpan", "current"} and base_expr.endswith("Span"):
                    return "Span"
                base_type = self._infer_receiver_type(
                    base_expr,
                    context,
                    enclosing_class,
                    var_map,
                    function_return_map,
                    declarations,
                    line_number,
                )
                if base_type:
                    return function_return_map.get((base_type, member_name))
            inner = call_target.split("<", 1)[0]
            return (
                function_return_map.get((enclosing_class, inner))
                or function_return_map.get((context_name, inner))
                or function_return_map.get((None, inner))
            )

        if "." in expr:
            base_expr, member_name = expr.rsplit(".", 1)
            base_type = self._infer_receiver_type(
                base_expr,
                context,
                enclosing_class,
                var_map,
                function_return_map,
                declarations,
                line_number,
            )
            if base_type:
                if re.fullmatch(r"[A-Z][A-Z0-9_]*", member_name):
                    return base_type
                return (
                    var_map.get((member_name, base_type))
                    or function_return_map.get((base_type, member_name))
                )

        return None

    def _receiver_member_hint(
        self,
        expression: str,
        context: Any,
        enclosing_class: Optional[str],
        var_map: Dict[Tuple[str, Any], str],
        function_return_map: Dict[Tuple[Optional[str], str], str],
        declarations: Optional[Dict[Tuple[str, Any], list[Tuple[Optional[int], Optional[str]]]]] = None,
        line_number: Optional[int] = None,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        expr = self._normalize_receiver_expression(expression)
        if self._extract_cast_type(expr) or self._extract_generic_factory_type(expr):
            return None, None, None

        member_kind = None
        target = expr
        call_target = self._call_target_without_value_args(expr)
        if call_target:
            target = call_target
            member_kind = "function"
        elif "." in expr:
            member_kind = "property"

        if "." not in target or member_kind is None:
            return None, None, None

        base_expr, member_name = target.rsplit(".", 1)
        member_name = member_name.split("<", 1)[0]
        base_type = self._infer_receiver_type(
            base_expr,
            context,
            enclosing_class,
            var_map,
            function_return_map,
            declarations,
            line_number,
        )
        return base_type, member_name, member_kind

    def _strip_outer_parentheses(self, expression: str) -> str:
        expr = expression.strip()
        while expr.startswith("(") and expr.endswith(")"):
            depth = 0
            wraps_entire_expression = True
            for idx, char in enumerate(expr):
                if char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1
                    if depth == 0 and idx != len(expr) - 1:
                        wraps_entire_expression = False
                        break
            if not wraps_entire_expression:
                break
            expr = expr[1:-1].strip()
        return expr

    def _normalize_receiver_expression(self, expression: str) -> str:
        expr = expression.replace("?.", ".").strip()
        expr = self._strip_outer_parentheses(expr)
        while expr.endswith("!!"):
            expr = self._strip_outer_parentheses(expr[:-2].strip())
        return expr

    def _extract_cast_type(self, expression: str) -> Optional[str]:
        expr = self._normalize_receiver_expression(expression)
        match = re.search(
            r'\b(?:as|as\?)\s+([A-Za-z_][\w\.]*(?:<[^>\n]+>)?\??)\s*$',
            expr,
        )
        return match.group(1) if match else None

    def _extract_generic_factory_type(self, expression: str) -> Optional[str]:
        expr = self._normalize_receiver_expression(expression)
        target = self._call_target_without_value_args(expr)
        if not target:
            return None

        member_name = target.rsplit(".", 1)[-1]
        match = re.fullmatch(
            r'([A-Za-z_]\w*)\s*<\s*([A-Za-z_][\w\.]*(?:<[^>\n]+>)?\??)\s*>',
            member_name,
        )
        if not match:
            return None

        factory_names = {
            "get",
            "getInstance",
            "inject",
            "instance",
            "resolve",
            "service",
        }
        if match.group(1) not in factory_names:
            return None
        return match.group(2)

    def _call_target_without_value_args(self, expression: str) -> Optional[str]:
        expr = self._normalize_receiver_expression(expression)
        if not expr.endswith(")"):
            return None

        depth = 0
        for idx in range(len(expr) - 1, -1, -1):
            char = expr[idx]
            if char == ")":
                depth += 1
            elif char == "(":
                depth -= 1
                if depth == 0:
                    return expr[:idx].strip() or None
        return None

    def _initializer_member_hint(
        self,
        initializer: str,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        expr = self._normalize_receiver_expression(initializer)
        if self._extract_cast_type(expr) or self._extract_generic_factory_type(expr):
            return None, None, None

        call_target = self._call_target_without_value_args(expr)
        if call_target and "." in call_target:
            receiver_name, member_name = call_target.rsplit(".", 1)
            if re.fullmatch(r"[A-Za-z_]\w*", receiver_name):
                return receiver_name, member_name.split("<", 1)[0], "function"
        elif "." in expr:
            receiver_name, member_name = expr.rsplit(".", 1)
            if re.fullmatch(r"[A-Za-z_]\w*", receiver_name):
                return receiver_name, member_name, "property"

        return None, None, None

    def _initializer_collection_return_hint(
        self,
        initializer: str,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        expr = self._normalize_receiver_expression(initializer)
        match = re.search(
            r'\b([A-Za-z_]\w*)\s*\.\s*([A-Za-z_]\w*)\s*\(.*?\)\s*'
            r'\.\s*(toCollection|toList|toSet|asSequence)\s*\(',
            expr,
            re.DOTALL,
        )
        if not match:
            return None, None, None
        return match.group(1), match.group(2), match.group(3)

    def _callable_reference_collection_hint(
        self,
        node: Any,
    ) -> Tuple[Optional[str], Optional[str]]:
        if node.type != "callable_reference":
            return None, None

        current = node.parent
        reference_text = self._get_node_text(node)
        while current is not None:
            if current.type == "call_expression":
                call_text = self._get_node_text(current)
                if reference_text not in call_text:
                    current = current.parent
                    continue

                call_target = self._call_target_without_value_args(call_text)
                if call_target and "." in call_target:
                    receiver_expr, member_name = call_target.rsplit(".", 1)
                    if member_name in {
                        "all",
                        "any",
                        "count",
                        "filter",
                        "filterNot",
                        "find",
                        "first",
                        "firstOrNull",
                        "flatMap",
                        "forEach",
                        "last",
                        "lastOrNull",
                        "map",
                        "none",
                        "onEach",
                        "partition",
                    }:
                        return receiver_expr.strip(), member_name
            current = current.parent
        return None, None

    def _split_top_level_operator(self, expression: str, operator: str) -> list[str]:
        parts = []
        current = []
        depth_round = depth_square = depth_curly = 0
        idx = 0
        while idx < len(expression):
            char = expression[idx]
            if char == "(":
                depth_round += 1
            elif char == ")":
                depth_round = max(0, depth_round - 1)
            elif char == "[":
                depth_square += 1
            elif char == "]":
                depth_square = max(0, depth_square - 1)
            elif char == "{":
                depth_curly += 1
            elif char == "}":
                depth_curly = max(0, depth_curly - 1)

            at_top_level = (
                depth_round == 0
                and depth_square == 0
                and depth_curly == 0
            )
            if at_top_level and expression.startswith(operator, idx):
                parts.append("".join(current).strip())
                current = []
                idx += len(operator)
                continue

            current.append(char)
            idx += 1

        if current:
            parts.append("".join(current).strip())
        return parts

    def _initializer_candidate_names(self, initializer: Optional[str]) -> list[str]:
        if not initializer:
            return []

        expr = self._normalize_receiver_expression(initializer)
        if re.fullmatch(r"[A-Za-z_]\w*", expr):
            return [expr]

        elvis_parts = self._split_top_level_operator(expr, "?:")
        if len(elvis_parts) > 1:
            candidates = []
            for part in elvis_parts:
                part_candidates = self._initializer_candidate_names(part)
                if not part_candidates:
                    return []
                candidates.extend(part_candidates)
            return candidates

        if_candidates = self._if_expression_candidate_names(expr)
        if if_candidates:
            return if_candidates

        if expr.startswith("when"):
            candidates = re.findall(r'->\s*([A-Za-z_]\w*)\b', expr)
            return candidates if len(candidates) > 1 else []

        return []

    def _if_expression_candidate_names(self, expression: str) -> list[str]:
        expr = expression.strip()
        if not expr.startswith("if"):
            return []

        idx = 2
        while idx < len(expr) and expr[idx].isspace():
            idx += 1
        if idx >= len(expr) or expr[idx] != "(":
            return []

        depth = 0
        close_idx = None
        for pos in range(idx, len(expr)):
            if expr[pos] == "(":
                depth += 1
            elif expr[pos] == ")":
                depth -= 1
                if depth == 0:
                    close_idx = pos
                    break
        if close_idx is None:
            return []

        rest = expr[close_idx + 1:].strip()
        match = re.fullmatch(
            r'([A-Za-z_]\w*)\s+else\s+([A-Za-z_]\w*)',
            rest,
            re.DOTALL,
        )
        return [match.group(1), match.group(2)] if match else []

    def _common_type_for_candidate_names(
        self,
        candidate_names: list[str],
        context: Any,
        var_map: Dict[Tuple[str, Any], str],
        declarations: Optional[Dict[Tuple[str, Any], list[Tuple[Optional[int], Optional[str]]]]] = None,
        line_number: Optional[int] = None,
    ) -> Optional[str]:
        if not candidate_names:
            return None

        candidate_types = []
        for candidate_name in candidate_names:
            candidate_type = self._lookup_variable_type(
                var_map,
                candidate_name,
                context,
                declarations,
                line_number,
            )
            if not candidate_type:
                return None
            candidate_types.append(self._strip_type_modifiers(candidate_type))

        unique_types = set(candidate_types)
        return candidate_types[0] if len(unique_types) == 1 else None

    def _extract_initializer_type(self, initializer: str) -> Optional[str]:
        expr = self._normalize_receiver_expression(initializer)
        cast_type = self._extract_cast_type(expr)
        if cast_type:
            return self._strip_type_modifiers(cast_type)

        generic_factory_type = self._extract_generic_factory_type(expr)
        if generic_factory_type:
            return self._strip_type_modifiers(generic_factory_type)

        call_target = self._call_target_without_value_args(expr)
        if call_target:
            member_name = call_target.rsplit(".", 1)[-1].split("<", 1)[0]
            if member_name == "spanBuilder":
                return "SpanBuilder"
            if member_name == "startSpan" or call_target.endswith("Span.current"):
                return "Span"

        builder_match = re.match(r'\b([A-Z]\w*)\.newBuilder\s*\(', expr)
        if builder_match and re.search(r'\.build\s*\(\s*\)', expr):
            return builder_match.group(1)

        constructor_match = re.match(
            r'\b([A-Z]\w*(?:<[^>\n]+>)?)\s*\(',
            expr,
        )
        if constructor_match:
            return constructor_match.group(1)

        if re.search(r'\.partition\s*\{', expr):
            return "List"
        if re.match(r'\b(?:buildMap|mapOf|mutableMapOf|hashMapOf|linkedMapOf)\s*(?:<[^>]+>)?\s*[\({]', expr):
            return "Map"
        if re.match(r'\b(?:buildList|listOf|mutableListOf|arrayListOf)\s*(?:<[^>]+>)?\s*[\({]', expr):
            return "List"
        if re.search(r'\.associateBy\s*\{', expr):
            return "Map"
        if re.search(r'\.asSequence\s*\(\s*\).*\.map\s*\{', expr):
            return "Sequence"
        if re.search(r'\.map\s*\{', expr):
            return "List"

        if re.search(r'\.asSequence\s*\(', expr) or re.match(r'\bsequenceOf\s*\(', expr):
            return "Sequence"
        if re.search(r'\.toSet\s*\(', expr) or re.match(r'\b(?:setOf|mutableSetOf|hashSetOf|linkedSetOf)\s*\(', expr):
            return "Set"
        if re.search(r'\.toList\s*\(', expr) or re.match(r'\b(?:listOf|mutableListOf|arrayListOf)\s*\(', expr):
            return "List"
        if re.search(r'\.keys\b', expr):
            return "Set"
        if re.search(r'\.values\b', expr):
            return "Collection"

        constructor_match = re.fullmatch(
            r'(?:[A-Za-z_][\w\.]*\.)?([A-Z][A-Za-z_]\w*)\s*(?:<[^>\n]+>)?\s*\(.*\)',
            expr,
            re.DOTALL,
        )
        return constructor_match.group(1) if constructor_match else None

    def _extract_initializer_text(self, declaration_text: str) -> Optional[str]:
        if "=" not in declaration_text:
            return None
        return declaration_text.split("=", 1)[1].strip().rstrip(";")

    def _extract_call_parts(self, node: Any) -> Tuple[str, Optional[str]]:
        if not node.children:
            return "unknown", None

        first_child = node.children[0]
        if node.type == "callable_reference":
            name_node = next(
                (
                    child
                    for child in reversed(node.children)
                    if child.type in ("simple_identifier", "type_identifier")
                ),
                None,
            )
            if name_node is None:
                return "unknown", None
            receiver_text = None
            if len(node.children) >= 3 and first_child is not name_node:
                receiver_text = self._get_node_text(first_child).strip()
                if receiver_text == "::":
                    receiver_text = None
            return self._get_node_text(name_node), receiver_text

        if node.type == "constructor_invocation":
            for child in node.children:
                if child.type == "user_type":
                    return self._strip_type_modifiers(self._get_node_text(child)), None
            return "unknown", None

        if first_child.type == "simple_identifier":
            return self._get_node_text(first_child), None

        if first_child.type == "navigation_expression":
            nav_children = first_child.children
            if len(nav_children) < 2:
                return "unknown", None

            operand = nav_children[0]
            suffix = nav_children[-1]
            call_name = "unknown"
            if suffix.type == "navigation_suffix":
                for child in suffix.children:
                    if child.type == "simple_identifier":
                        call_name = self._get_node_text(child)
                        break
            elif suffix.type == "simple_identifier":
                call_name = self._get_node_text(suffix)

            return call_name, self._get_node_text(operand)

        return "unknown", None

    def _extract_first_argument(self, call_text: str) -> Optional[str]:
        open_paren = call_text.find("(")
        if open_paren == -1:
            return None

        depth = 0
        arg_chars = []
        for char in call_text[open_paren + 1:]:
            if char == "(":
                depth += 1
            elif char == ")":
                if depth == 0:
                    break
                depth -= 1
            elif char == "," and depth == 0:
                break
            arg_chars.append(char)

        arg = "".join(arg_chars).strip()
        return arg or None

    def _extract_call_arguments(self, node: Any) -> list[str]:
        args = []
        for child in node.children:
            if child.type == "call_suffix":
                for suffix_child in child.children:
                    if suffix_child.type == "value_arguments":
                        args.extend(
                            self._get_node_text(arg)
                            for arg in suffix_child.children
                            if arg.type == "value_argument"
                        )
                    elif suffix_child.type in ("annotated_lambda", "lambda_literal"):
                        args.append(self._get_node_text(suffix_child))
            elif child.type == "value_arguments":
                args.extend(
                    self._get_node_text(arg)
                    for arg in child.children
                    if arg.type == "value_argument"
                )
            elif child.type in ("annotated_lambda", "lambda_literal"):
                args.append(self._get_node_text(child))
        return args

    def _extract_lambda_parameter(self, call_text: str) -> Optional[str]:
        match = re.search(r'\{\s*([A-Za-z_]\w*)\s*->', call_text, re.DOTALL)
        return match.group(1) if match else None

    def _scope_function_receiver_hint(
        self,
        node: Any,
        context: Any,
        enclosing_class: Optional[str],
        var_map: Dict[Tuple[str, Any], str],
        function_return_map: Dict[Tuple[Optional[str], str], str],
        declarations: Optional[Dict[Tuple[str, Any], list[Tuple[Optional[int], Optional[str]]]]] = None,
        line_number: Optional[int] = None,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        def contains_node(container: Any, target: Any) -> bool:
            return (
                container.start_byte <= target.start_byte
                and target.end_byte <= container.end_byte
            )

        def is_inside_scope_lambda(scope_call: Any, target: Any) -> bool:
            stack = list(scope_call.children)
            while stack:
                child = stack.pop()
                if child.type in ("annotated_lambda", "lambda_literal") and contains_node(child, target):
                    return True
                stack.extend(child.children)
            return False

        curr = node.parent
        while curr:
            if curr.type == "call_expression" and (
                curr.start_byte != node.start_byte or curr.end_byte != node.end_byte
            ):
                if not is_inside_scope_lambda(curr, node):
                    curr = curr.parent
                    continue

                scope_name, scope_base = self._extract_call_parts(curr)
                receiver_expression = None
                if scope_name in {"apply", "run", "let", "also"} and scope_base:
                    receiver_expression = scope_base
                elif scope_name == "with":
                    receiver_expression = self._extract_first_argument(self._get_node_text(curr))

                if receiver_expression:
                    receiver_type = self._infer_receiver_type(
                        receiver_expression,
                        context,
                        enclosing_class,
                        var_map,
                        function_return_map,
                        declarations,
                        line_number,
                    )
                    if receiver_type:
                        return (
                            scope_name,
                            self._strip_type_modifiers(receiver_type),
                            self._extract_lambda_parameter(self._get_node_text(curr)),
                        )

            curr = curr.parent

        return None, None, None

    def _smart_cast_receiver_hint(
        self,
        node: Any,
        receiver_name: Optional[str],
    ) -> Optional[str]:
        if not receiver_name or not re.fullmatch(r"[A-Za-z_]\w*", receiver_name):
            return None

        curr = node.parent
        while curr:
            if curr.type == "if_expression":
                cast_type = self._smart_cast_type_from_if(curr, node, receiver_name)
                if cast_type:
                    return cast_type
            elif curr.type == "when_entry":
                cast_type = self._smart_cast_type_from_when_entry(curr, node, receiver_name)
                if cast_type:
                    return cast_type

            curr = curr.parent

        return None

    def _smart_cast_type_from_if(
        self,
        if_node: Any,
        call_node: Any,
        receiver_name: str,
    ) -> Optional[str]:
        check_node = None
        positive_body = None
        for child in if_node.children:
            if child.type == "check_expression":
                check_node = child
            elif child.type == "control_structure_body" and positive_body is None:
                positive_body = child

        if not check_node or not positive_body:
            return None
        if not (positive_body.start_byte <= call_node.start_byte <= positive_body.end_byte):
            return None

        return self._type_from_positive_check(check_node, receiver_name)

    def _smart_cast_type_from_when_entry(
        self,
        when_entry: Any,
        call_node: Any,
        receiver_name: str,
    ) -> Optional[str]:
        body = None
        type_test = None
        check_node = None
        for child in when_entry.children:
            if child.type == "control_structure_body":
                body = child
            elif child.type == "when_condition":
                for condition_child in child.children:
                    if condition_child.type == "type_test":
                        type_test = condition_child
                    elif condition_child.type == "check_expression":
                        check_node = condition_child

        if not body or not (body.start_byte <= call_node.start_byte <= body.end_byte):
            return None

        if check_node:
            return self._type_from_positive_check(check_node, receiver_name)

        subject_name = self._when_subject_name(when_entry.parent)
        if subject_name == receiver_name and type_test:
            return self._type_from_type_test(type_test)

        return None

    def _when_subject_name(self, when_node: Any) -> Optional[str]:
        if not when_node or when_node.type != "when_expression":
            return None
        for child in when_node.children:
            if child.type == "when_subject":
                for subject_child in child.children:
                    if subject_child.type == "simple_identifier":
                        return self._get_node_text(subject_child)
        return None

    def _type_from_type_test(self, type_test_node: Any) -> Optional[str]:
        text = self._get_node_text(type_test_node)
        if text.lstrip().startswith("!is"):
            return None
        for child in type_test_node.children:
            if child.type in ("user_type", "nullable_type"):
                return self._strip_type_modifiers(self._get_node_text(child))
        match = re.search(
            r'\bis\s+([A-Za-z_][\w\.]*(?:<[^>\n]+>)?\??)',
            text,
        )
        return self._strip_type_modifiers(match.group(1)) if match else None

    def _type_from_positive_check(
        self,
        check_node: Any,
        receiver_name: str,
    ) -> Optional[str]:
        text = self._get_node_text(check_node)
        escaped_name = re.escape(receiver_name)
        if "||" in text:
            return None
        if re.search(rf'!\s*\(\s*{escaped_name}\s+is\b', text):
            return None
        if re.search(rf'\b{escaped_name}\s+!is\b', text):
            return None
        match = re.search(
            rf'\b{escaped_name}\s+is\s+([A-Za-z_][\w\.]*(?:<[^>\n]+>)?\??)',
            text,
        )
        return self._strip_type_modifiers(match.group(1)) if match else None

    def _parse_functions(self, captures: list, source_code: str, path: Path) -> list[Dict[str, Any]]:
        functions = []
        seen_nodes = set()

        for node, capture_name in captures:
            if capture_name == "function_node":
                node_id = (node.start_byte, node.end_byte, node.type)
                if node_id in seen_nodes:
                    continue
                seen_nodes.add(node_id)
                
                try:
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    
                    # Manual child lookup
                    name_node = None
                    for child in node.children:
                        if child.type == "simple_identifier":
                            name_node = child
                            break
                            
                    if name_node:
                        func_name = self._get_node_text(name_node)
                        
                        params_node = None
                        for child in node.children:
                            if child.type == "function_value_parameters":
                                params_node = child
                                break
                                
                        parameters = []
                        parameter_types = []
                        parameter_defaults = []
                        if params_node:
                            params_text = self._get_node_text(params_node)
                            parameters = self._extract_parameter_names(params_text)
                            parameter_types = self._extract_parameter_types(params_text)
                            parameter_defaults = self._extract_parameter_defaults(params_text)

                        source_text = self._get_node_text(node)
                        
                        context_name, context_type, context_line = self._get_parent_context(node)
                        is_class_context = bool(
                            context_type
                            and (
                                "class" in context_type
                                or "interface" in context_type
                                or "object" in context_type
                            )
                        )

                        func_data = {
                            "name": func_name,
                            "args": parameters,
                            "arg_types": parameter_types,
                            "arg_defaults": parameter_defaults,
                            "line_number": start_line,
                            "end_line": end_line,
                            "path": str(path),
                            "lang": self.language_name,
                            "context": context_name,
                            "class_context": context_name if is_class_context else None,
                        }
                        if is_class_context and context_line is not None:
                            func_data["class_context_line"] = context_line

                        for child in node.children:
                            if child.type == "receiver_type":
                                func_data["receiver_type"] = self._strip_type_modifiers(self._get_node_text(child))
                                break

                        for child in node.children:
                            if child.type in ("user_type", "nullable_type"):
                                raw_return_type = self._get_node_text(child)
                                func_data["return_type"] = self._strip_type_modifiers(raw_return_type)
                                func_data["return_type_full"] = raw_return_type
                                break

                        if "return_type" not in func_data:
                            found_eq = False
                            for child in node.children:
                                if child.type == "=":
                                    found_eq = True
                                    continue
                                if found_eq and child.type.endswith("expression"):
                                    expr_text = self._get_node_text(child).strip()
                                    inferred = self._extract_initializer_type(expr_text)
                                    if inferred:
                                        func_data["return_type"] = inferred
                                    break
                        
                        if self.index_source:
                            func_data["source"] = source_text
                        
                        functions.append(func_data)
                        
                except Exception as e:
                    error_logger(f"Error parsing function in {path}: {e}")
                    continue

        return functions

    def _parse_classes(self, captures: list, source_code: str, path: Path) -> Dict[str, List[Dict[str, Any]]]:
        results = {
            "classes": [],
            "interfaces": [],
            "objects": [],
        }
        seen_nodes = set()

        for node, capture_name in captures:
            if capture_name == "class":
                node_id = (node.start_byte, node.end_byte, node.type)
                if node_id in seen_nodes:
                    continue
                seen_nodes.add(node_id)
                
                try:
                    if node.type in ("object_declaration", "companion_object"):
                        category = "objects"
                        label = "Object"
                    else:
                        # For class_declaration, check if it's an interface
                        is_interface = any(c.type == "interface" for c in node.children)
                        if is_interface:
                            category = "interfaces"
                            label = "Interface"
                        else:
                            category = "classes"
                            label = "Class"
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    
                    # Find name child (type_identifier or simple_identifier)
                    class_name = "Anonymous"
                    if node.type == "companion_object":
                        class_name = "Companion" # Default name
                    
                    for child in node.children:
                        if child.type in ("type_identifier", "simple_identifier"):
                            class_name = self._get_node_text(child)
                            break
                            
                    source_text = self._get_node_text(node)
                    context_name, context_type, context_line = self._get_parent_context(node)
                    is_nested_class = bool(
                        context_type
                        and (
                            "class" in context_type
                            or "interface" in context_type
                            or "object" in context_type
                        )
                    )
                    
                    bases = []
                    # Check for delegation specifiers
                    # class_declaration -> delegation_specifier
                    
                    for child in node.children:
                        if child.type == "delegation_specifier":
                             # children: constructor_invocation or user_type
                             for specifier in child.children:
                                 # constructor_invocation -> user_type -> type_identifier
                                 # user_type -> type_identifier
                                 
                                 # We want the text of the type
                                 if specifier.type == "constructor_invocation":
                                     # child 0 is typically user_type
                                      for sub in specifier.children:
                                          if sub.type == "user_type":
                                              bases.append(self._get_node_text(sub))
                                              break
                                 elif specifier.type == "user_type":
                                     bases.append(self._get_node_text(specifier))
                                 elif specifier.type == "explicit_delegation":
                                     # Not handling simple yet, uses 'by'
                                     pass


                    class_data = {
                        "name": class_name,
                        "node_type": node.type,
                        "line_number": start_line,
                        "end_line": end_line,
                        "bases": bases,
                        "path": str(path),
                        "lang": self.language_name,
                    }
                    if is_nested_class:
                        class_data["class_context"] = context_name
                        if context_line is not None:
                            class_data["class_context_line"] = context_line

                    if self.index_source:
                        class_data["source"] = source_text
                    
                    class_data["node_label"] = label
                    results[category].append(class_data)
                        
                except Exception as e:
                    error_logger(f"Error parsing class in {path}: {e}")
                    continue

        return results

    def _parse_variables(
        self,
        captures: list,
        source_code: str,
        path: Path,
        functions: Optional[list[Dict[str, Any]]] = None,
    ) -> list[Dict[str, Any]]:
        variables = []
        seen_vars = set()
        
        for node, capture_name in captures:
            if capture_name == "variable":
                try:
                    start_line = node.start_point[0] + 1
                    ctx_name, ctx_type, ctx_line = self._get_parent_context(node)
                    node_text = self._get_node_text(node)

                    # Destructuring declaration
                    destructuring_match = re.match(
                        r'\s*(?:val|var)\s*\(([^)]+)\)\s*=\s*(.+)',
                        node_text,
                        re.S,
                    )
                    if destructuring_match:
                        initializer_text = destructuring_match.group(2).strip()
                        initializer_inferred_type = self._extract_initializer_type(initializer_text)
                        for raw_name in destructuring_match.group(1).split(","):
                            var_name = raw_name.strip()
                            if not var_name or var_name == "_":
                                continue
                            variable_data = {
                                "name": var_name,
                                "type": initializer_inferred_type or "Unknown",
                                "line_number": start_line,
                                "path": str(path),
                                "lang": self.language_name,
                                "context": ctx_name,
                                "class_context": ctx_name if ctx_type and ("class" in ctx_type or "interface" in ctx_type or "object" in ctx_type) else None
                            }
                            if initializer_inferred_type:
                                variable_data["initializer_inferred_type"] = initializer_inferred_type
                            variables.append(variable_data)
                        continue

                    # Regular property/variable
                    var_name = "unknown"
                    var_type = "Unknown"
                    
                    var_decl = node if node.type in ("class_parameter", "parameter") else None
                    if var_decl is None:
                        for child in node.children:
                            if child.type == "variable_declaration":
                                var_decl = child
                                break
                    
                    if var_decl:
                        # Check for name and type in variable_declaration
                        for child in var_decl.children:
                            if child.type == "simple_identifier":
                                var_name = self._get_node_text(child)
                            
                            if child.type in ("user_type", "nullable_type"):
                                var_type = self._get_node_text(child)

                    # Attempt inference from initializer if type is unknown
                    if var_type == "Unknown":
                        # property_declaration -> expression (e.g. call_expression)
                        for child in node.children:
                            if child.type == "call_expression":
                                # call_expression -> simple_identifier (constructor)
                                for sub in child.children:
                                    if sub.type == "simple_identifier":
                                        candidate_type = self._get_node_text(sub)
                                        if re.match(r"[A-Z]", candidate_type):
                                            var_type = candidate_type
                                            break
                                if var_type != "Unknown": break

                    if var_name != "unknown":
                        initializer_text = self._extract_initializer_text(self._get_node_text(node))
                        initializer_inferred_type = (
                            self._extract_initializer_type(initializer_text)
                            if initializer_text
                            else None
                        )
                        if var_type == "Unknown" and initializer_inferred_type:
                            var_type = initializer_inferred_type

                        (
                            initializer_receiver_name,
                            initializer_member_name,
                            initializer_member_kind,
                        ) = (
                            self._initializer_member_hint(initializer_text)
                            if initializer_text
                            else (None, None, None)
                        )
                        (
                            initializer_collection_receiver_name,
                            initializer_collection_member_name,
                            initializer_collection_operator,
                        ) = (
                            self._initializer_collection_return_hint(initializer_text)
                            if initializer_text
                            else (None, None, None)
                        )

                        variable_data = {
                            "name": var_name,
                            "type": var_type,
                            "line_number": start_line,
                            "path": str(path),
                            "lang": self.language_name,
                            "context": ctx_name,
                            "class_context": ctx_name if ctx_type and ("class" in ctx_type or "interface" in ctx_type or "object" in ctx_type) else None
                        }
                        if initializer_inferred_type:
                            variable_data["initializer_inferred_type"] = initializer_inferred_type
                        if initializer_receiver_name and initializer_member_name:
                            variable_data["initializer_receiver_name"] = initializer_receiver_name
                            variable_data["initializer_member_name"] = initializer_member_name
                            variable_data["initializer_member_kind"] = initializer_member_kind
                        if initializer_collection_receiver_name and initializer_collection_member_name:
                            variable_data["initializer_collection_receiver_name"] = initializer_collection_receiver_name
                            variable_data["initializer_collection_member_name"] = initializer_collection_member_name
                            variable_data["initializer_collection_operator"] = initializer_collection_operator
                        if initializer_text:
                            variable_data["initializer_text"] = initializer_text
                        initializer_candidate_names = self._initializer_candidate_names(initializer_text)
                        if initializer_candidate_names:
                            variable_data["initializer_candidate_names"] = initializer_candidate_names
                        variables.append(variable_data)
                except Exception as e:
                    continue

        function_ranges = [
            (
                function.get("line_number"),
                function.get("end_line", function.get("line_number")),
                function.get("name"),
                function.get("class_context"),
            )
            for function in (functions or [])
            if function.get("name") and function.get("line_number")
        ]

        for line_number, line in enumerate(source_code.splitlines(), start=1):
            destructuring_match = re.match(
                r'\s*(?:val|var)\s*\(([^)]+)\)\s*=\s*(.+)',
                line,
            )
            if not destructuring_match:
                continue

            initializer_text = destructuring_match.group(2).strip()
            initializer_inferred_type = self._extract_initializer_type(initializer_text)
            context_name = None
            class_context = None
            for start_line, end_line, function_name, function_class_context in function_ranges:
                if start_line <= line_number <= end_line:
                    context_name = function_name
                    class_context = function_class_context
                    break

            for raw_name in destructuring_match.group(1).split(","):
                var_name = raw_name.strip()
                if not var_name or var_name == "_":
                    continue
                if any(
                    existing.get("name") == var_name
                    and existing.get("line_number") == line_number
                    for existing in variables
                ):
                    continue
                variable_data = {
                    "name": var_name,
                    "type": initializer_inferred_type or "Unknown",
                    "line_number": line_number,
                    "path": str(path),
                    "lang": self.language_name,
                    "context": context_name,
                    "class_context": class_context,
                }
                if initializer_inferred_type:
                    variable_data["initializer_inferred_type"] = initializer_inferred_type
                variables.append(variable_data)

        return variables

    def _parse_imports(self, captures: list, source_code: str) -> list[dict]:
        imports = []
        
        for node, capture_name in captures:
            if capture_name == "import":
                try:
                    # import_header -> "import" identifier (import_alias)?
                    text = self._get_node_text(node)
                    # remove 'import '
                    path = text.replace('import ', '').strip().split(' as ')[0].strip()
                    alias = None
                    if ' as ' in text:
                        alias = text.split(' as ')[1].strip()

                    imports.append({
                        "name": path,
                        "full_import_name": path,
                        "line_number": node.start_point[0] + 1,
                        "alias": alias,
                        "context": (None, None),
                        "lang": self.language_name,
                        "is_dependency": False,
                    })
                except Exception as e:
                    continue

        return imports

    def _parse_calls(
        self,
        captures: list,
        source_code: str,
        path: Path,
        variables: list[Dict[str, Any]] = [],
        functions: list[Dict[str, Any]] = [],
    ) -> list[Dict[str, Any]]:
        calls = []
        seen_calls = set()
        package_name = self._extract_package_name(source_code)

        def function_scope(function: Dict[str, Any]) -> Tuple[Optional[str], Optional[int], Optional[str]]:
            return (
                function.get("name"),
                function.get("line_number"),
                function.get("context") or function.get("class_context"),
            )

        def function_scope_for_line(
            context_name: Optional[str],
            line_number: Optional[int],
        ) -> Any:
            if not context_name or line_number is None:
                return context_name
            for function in functions:
                if function.get("name") != context_name:
                    continue
                start_line = function.get("line_number")
                end_line = function.get("end_line", start_line)
                if start_line is None or end_line is None:
                    continue
                if start_line <= line_number <= end_line:
                    return function_scope(function)
            return context_name

        def variable_scope(variable: Dict[str, Any]) -> Any:
            return function_scope_for_line(
                variable.get("context"),
                variable.get("line_number"),
            )
        
        # Index variables for fast lookup: (name, context) -> type
        var_map = {}
        raw_var_map = {}
        var_declarations = {}
        raw_var_declarations = {}

        def record_declaration(
            declarations: Dict[Tuple[str, Any], list[Tuple[Optional[int], Optional[str]]]],
            key: Tuple[str, Any],
            line_number: Optional[int],
            type_name: Optional[str],
        ) -> None:
            declarations.setdefault(key, []).append((line_number, type_name))

        for v in variables:
            key = (v['name'], variable_scope(v))
            raw_type = v.get('type', '')
            record_declaration(
                raw_var_declarations,
                key,
                v.get("line_number"),
                raw_type if raw_type and raw_type != "Unknown" else None,
            )
            if raw_type and raw_type != "Unknown":
                raw_var_map[key] = raw_type
            normalized_type = self._strip_type_modifiers(v.get('type', ''))
            record_declaration(
                var_declarations,
                key,
                v.get("line_number"),
                normalized_type if normalized_type and normalized_type != "Unknown" else None,
            )
            if normalized_type and normalized_type != "Unknown":
                var_map[key] = normalized_type
            # Fallback for null context or partial match could be added
            # For class props: (name, class_context) might work if local lookup fails?

        function_return_map = {}
        function_receiver_map = {}
        for f in functions:
            return_type = f.get("return_type")
            if return_type:
                function_return_map[(f.get("context"), f["name"])] = self._strip_type_modifiers(return_type)
            receiver_type = f.get("receiver_type")
            if receiver_type:
                function_receiver_map[(f["name"], f.get("line_number"))] = self._strip_type_modifiers(receiver_type)

        for node, capture_name in captures:
            if capture_name == "call_node":
                try:
                    # navigation_expression check
                    
                    start_line = node.start_point[0] + 1
                    
                    call_name = "unknown"
                    base_obj = None
                    
                    # call_expression usually has children:
                    # simple_identifier (func name)
                    # or navigation_expression (obj.method)
                    
                    # Heuristic for base object:
                    # If navigation_expression -> child[0] is base, child[1] is suffix (method)
                    
                    # We need to look deeper into the call_expression structure.
                    # call_expression -> (simple_identifier)
                    # OR call_expression -> (navigation_expression (simple_identifier) (navigation_suffix (simple_identifier) ...))
                    # OR call_expression -> (navigation_expression (call_expression) ...)  (chained)

                    # Simplified traversal to find the "function name" and "receiver"
                    
                    # If it's a direct call: foo()
                    # If it's a method call: x.foo()
                    
                    # Tree-sitter struct:
                    # (call_expression (simple_identifier) (call_suffix ...))  -> name = simple_identifier
                    # (call_expression (navigation_expression (simple_identifier) (navigation_suffix (simple_identifier))) (call_suffix))
                    #  -> name = 2nd simple_identifier, base = 1st simple_identifier
                    
                    # Let's verify children
                    children = node.children
                    first_child = children[0]
                    enclosing_class, enclosing_class_line = self._get_enclosing_class_context(node)
                    
                    if node.type == "constructor_invocation":
                        for child in node.children:
                            if child.type == "user_type":
                                call_name = self._strip_type_modifiers(self._get_node_text(child))
                                break
                    elif node.type == "constructor_delegation_call":
                        delegation_target = self._get_node_text(first_child)
                        if delegation_target == "this" and enclosing_class:
                            call_name = enclosing_class
                        elif delegation_target == "super":
                            call_name = "super"
                            base_obj = "super"
                    elif node.type == "callable_reference":
                        call_name, base_obj = self._extract_call_parts(node)
                    else:
                        call_name, base_obj = self._extract_call_parts(node)

                    if call_name == "unknown":
                        continue

                    full_name = f"{base_obj}.{call_name}" if base_obj else call_name

                    ctx_name, ctx_type, ctx_line = self._get_parent_context(node)
                    current_scope = function_scope_for_line(ctx_name, ctx_line)
                    implicit_receiver_type = (
                        function_receiver_map.get((ctx_name, ctx_line))
                        if ctx_type == "function_declaration"
                        else None
                    )
                    
                    # Inference
                    inferred_type = None
                    extension_receiver_type = None
                    receiver_base_type = None
                    receiver_member_name = None
                    receiver_member_kind = None
                    if base_obj:
                        inferred_type = self._infer_receiver_type(
                            base_obj,
                            current_scope,
                            enclosing_class,
                            var_map,
                            function_return_map,
                            var_declarations,
                            start_line,
                        )
                        (
                            receiver_base_type,
                            receiver_member_name,
                            receiver_member_kind,
                        ) = self._receiver_member_hint(
                            base_obj,
                            current_scope,
                            enclosing_class,
                            var_map,
                            function_return_map,
                            var_declarations,
                            start_line,
                        )
                        extension_receiver_type = inferred_type

                        indexed_access_type = self._indexed_access_value_type(
                            base_obj,
                            current_scope,
                            enclosing_class,
                            raw_var_map,
                            raw_var_declarations,
                            start_line,
                        )
                        if indexed_access_type:
                            inferred_type = indexed_access_type
                            extension_receiver_type = indexed_access_type

                        smart_cast_type = self._smart_cast_receiver_hint(node, base_obj)
                        if smart_cast_type:
                            inferred_type = smart_cast_type
                            extension_receiver_type = smart_cast_type

                    scope_name, scope_receiver_type, scope_lambda_parameter = self._scope_function_receiver_hint(
                        node,
                        current_scope,
                        enclosing_class,
                        var_map,
                        function_return_map,
                        var_declarations,
                        start_line,
                    )
                    if scope_receiver_type:
                        is_implicit_receiver_call = (
                            not base_obj
                            and scope_name in {"apply", "run", "with"}
                        )
                        is_this_receiver_call = (
                            base_obj == "this"
                            and scope_name in {"apply", "run", "with"}
                        )
                        is_it_receiver_call = (
                            base_obj == "it"
                            and scope_name in {"let", "also"}
                        )
                        is_named_lambda_receiver_call = (
                            scope_lambda_parameter is not None
                            and base_obj == scope_lambda_parameter
                        )
                        if (
                            is_implicit_receiver_call
                            or is_this_receiver_call
                            or is_it_receiver_call
                            or is_named_lambda_receiver_call
                        ):
                            inferred_type = scope_receiver_type
                            extension_receiver_type = scope_receiver_type

                    (
                        lambda_parameter_name,
                        lambda_parameter_type,
                        lambda_value_type,
                    ) = self._collection_lambda_hint(
                        node,
                        current_scope,
                        enclosing_class,
                        raw_var_map,
                        raw_var_declarations,
                        start_line,
                    )
                    if base_obj and lambda_parameter_name:
                        if base_obj == lambda_parameter_name and lambda_parameter_type:
                            inferred_type = lambda_parameter_type
                            extension_receiver_type = lambda_parameter_type
                        elif base_obj == f"{lambda_parameter_name}.value" and lambda_value_type:
                            inferred_type = lambda_value_type
                            extension_receiver_type = lambda_value_type

                    (
                        callable_collection_receiver,
                        callable_collection_operator,
                    ) = self._callable_reference_collection_hint(node)

                    call_data = {
                        "name": call_name,
                        "full_name": full_name,
                        "base_obj": base_obj,
                        "call_kind": "callable_reference" if node.type == "callable_reference" else "call",
                        "line_number": start_line,
                        "args": self._extract_call_arguments(node),
                        "inferred_obj_type": inferred_type,
                        "extension_receiver_type": extension_receiver_type,
                        "implicit_receiver_type": implicit_receiver_type,
                        "scope_receiver_type": scope_receiver_type,
                        "receiver_base_type": receiver_base_type,
                        "receiver_member_name": receiver_member_name,
                        "receiver_member_kind": receiver_member_kind,
                        "enclosing_class": enclosing_class,
                        "package": package_name,
                        "context": (ctx_name, ctx_type, ctx_line),
                        "class_context": (enclosing_class, enclosing_class_line),
                        "lang": self.language_name,
                        "is_dependency": False
                    }
                    if callable_collection_receiver:
                        call_data["callable_reference_collection_receiver"] = callable_collection_receiver
                        call_data["callable_reference_collection_operator"] = callable_collection_operator
                    calls.append(call_data)
                except Exception as e:
                    continue
        return calls

    def _split_parameters(self, params_text: str) -> list[str]:
        if not params_text:
            return []

        clean = params_text.strip()
        if clean.startswith('(') and clean.endswith(')'):
            clean = clean[1:-1]

        if not clean.strip():
            return []

        current_param = []
        depth_angle = 0
        depth_round = 0
        depth_square = 0
        depth_curly = 0

        raw_params = []

        for char in clean:
            if char == '<':
                depth_angle += 1
            elif char == '>':
                depth_angle = max(0, depth_angle - 1)
            elif char == '(':
                depth_round += 1
            elif char == ')':
                depth_round -= 1
            elif char == '[':
                depth_square += 1
            elif char == ']':
                depth_square -= 1
            elif char == '{':
                depth_curly += 1
            elif char == '}':
                depth_curly -= 1

            if (
                char == ','
                and depth_angle == 0
                and depth_round == 0
                and depth_square == 0
                and depth_curly == 0
            ):
                raw_params.append("".join(current_param).strip())
                current_param = []
            else:
                current_param.append(char)

        if current_param:
            raw_params.append("".join(current_param).strip())

        return raw_params

    def _strip_parameter_default(self, type_text: str) -> str:
        current = []
        depth_angle = 0
        depth_round = 0
        depth_square = 0
        depth_curly = 0

        for char in type_text:
            if char == '<':
                depth_angle += 1
            elif char == '>':
                depth_angle = max(0, depth_angle - 1)
            elif char == '(':
                depth_round += 1
            elif char == ')':
                depth_round -= 1
            elif char == '[':
                depth_square += 1
            elif char == ']':
                depth_square -= 1
            elif char == '{':
                depth_curly += 1
            elif char == '}':
                depth_curly -= 1

            if (
                char == '='
                and depth_angle == 0
                and depth_round == 0
                and depth_square == 0
                and depth_curly == 0
            ):
                break
            current.append(char)

        return "".join(current).strip()

    def _parameter_has_default(self, param_text: str) -> bool:
        depth_angle = 0
        depth_round = 0
        depth_square = 0
        depth_curly = 0

        for char in param_text:
            if char == '<':
                depth_angle += 1
            elif char == '>':
                depth_angle = max(0, depth_angle - 1)
            elif char == '(':
                depth_round += 1
            elif char == ')':
                depth_round = max(0, depth_round - 1)
            elif char == '[':
                depth_square += 1
            elif char == ']':
                depth_square = max(0, depth_square - 1)
            elif char == '{':
                depth_curly += 1
            elif char == '}':
                depth_curly = max(0, depth_curly - 1)

            if (
                char == '='
                and depth_angle == 0
                and depth_round == 0
                and depth_square == 0
                and depth_curly == 0
            ):
                return True
        return False

    def _extract_parameter_defaults(self, params_text: str) -> list[bool]:
        return [
            self._parameter_has_default(param)
            for param in self._split_parameters(params_text)
        ]

    def _extract_parameter_types(self, params_text: str) -> list[str]:
        types = []
        for param in self._split_parameters(params_text):
            colon_index = param.find(':')
            if colon_index == -1:
                types.append("")
                continue
            type_text = self._strip_parameter_default(param[colon_index + 1:])
            types.append(self._strip_type_modifiers(type_text))
        return types

    def _extract_parameter_names(self, params_text: str) -> list[str]:
        """
        Extracts parameter names from a Kotlin parameter list string.
        Handles nested generics like Map<String, Int>.

        Args:
            params_text (str): The text content of function_value_parameters node, e.g. "(a: Int, b: Map<String, Int>)"

        Returns:
            list[str]: List of parameter names.
        """
        params = []
        raw_params = self._split_parameters(params_text)
            
        # Process each raw parameter string to extract name
        # Format: "val x: Int", "override var y: String", "@Ann z: Int", "a: Int = 5"
        for p in raw_params:
            if not p: continue
            
            # Remove default value if present
            # Be careful with '=' inside strings or generic defaults, but usually param defaults are at top level
            # A simple split by '=' might be risky if default value has '=', but for name extraction it's usually safe
            # as the name is on the LHS.
            # But wait, "val x: Type = ..." -> name is before ':'
            
            # Split by ':' to separate name/modifiers from Type
            # Using the first ':' usually works, assuming name doesn't contain ':'
            colon_index = p.find(':')
            if colon_index != -1:
                lhs = p[:colon_index].strip()
            else:
                # Could be a parameter without type? (not common in Kotlin unless lambda destructuring)
                # Or "var x = 5" (unlikely in func params)
                # Just take the whole string if no colon?
                lhs = p.strip()
                
            # LHS contains keywords (val, var), annotations (@Foo), modifiers (crossinline, noinline, vararg)
            # and the parameter name. The parameter name is usually the LAST identifier.
            
            if not lhs: continue
            
            tokens = lhs.split()
            if tokens:
                # The name is the last token
                params.append(tokens[-1])
                
        return params

def pre_scan_kotlin(files: list[Path], parser_wrapper) -> dict:
    name_to_files = {}
    parser = KotlinTreeSitterParser(parser_wrapper)

    def add_symbol(name: str, path: Path):
        if name not in name_to_files:
            name_to_files[name] = []
        name_to_files[name].append(str(path))

    def find_child_text(node, child_type: str) -> Optional[str]:
        for child in node.children:
            if child.type == child_type:
                return parser._get_node_text(child)
        return None

    def is_top_level_function(node) -> bool:
        curr = node.parent
        while curr:
            if curr.type in (
                "class_declaration",
                "object_declaration",
                "companion_object",
                "function_declaration",
            ):
                return False
            curr = curr.parent
        return True

    def walk_top_level_functions(node):
        if node.type == "function_declaration" and is_top_level_function(node):
            yield node
            return
        for child in node.children:
            yield from walk_top_level_functions(child)

    for path in files:
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # 1. Extract package
            # package com.example.project
            package_name = ""
            package_name = parser._extract_package_name(content)
            
            # 2. Extract classes/objects/interfaces/typealiases
            matches = re.finditer(r'\b(class|interface|object|typealias)\s+(\w+)', content)
            
            for match in matches:
                name = match.group(2)
                # Map simple name
                add_symbol(name, path)
                
                # If package exists, map FQN
                if package_name:
                    fqn = f"{package_name}.{name}"
                    add_symbol(fqn, path)

            tree = parser_wrapper.parser.parse(bytes(content, "utf8"))
            for func_node in walk_top_level_functions(tree.root_node):
                func_name = find_child_text(func_node, "simple_identifier")
                if not func_name:
                    continue

                add_symbol(func_name, path)
                if package_name:
                    add_symbol(f"{package_name}.{func_name}", path)

                receiver_type = find_child_text(func_node, "receiver_type")
                if receiver_type:
                    receiver_type = parser._strip_type_modifiers(receiver_type)
                    add_symbol(f"{receiver_type}.{func_name}", path)
                    if package_name:
                        add_symbol(f"{package_name}.{receiver_type}.{func_name}", path)

        except Exception:
            pass
    return name_to_files
