# src/codegraphcontext/tools/indexing/resolution/calls.py
"""Heuristic resolution of function calls into CALLS edge payloads (no DB I/O)."""

from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

from ....cli.config_manager import get_config_value
from ...type_utils import strip_type_modifiers
from ....utils.debug_log import info_logger


# Confidence score for each resolution tier.
# Higher = more certain the edge points to the correct target.
_TIER_CONFIDENCE: Dict[int, float] = {
    1: 1.00,  # explicit this/self/super receiver — definitionally same-class
    2: 0.95,  # local function or class defined in the same file
    3: 0.88,  # inferred receiver type + FQN import key
    4: 0.72,  # inferred receiver type + short-name/type fallback
    5: 0.90,  # unique short name or same-package lookup
    6: 0.85,  # qualified import/wildcard import lookup
    7: 0.70,  # FQN path-substring match
    8: 0.25,  # alphabetical-first of multiple candidates
    9: 0.08,  # same-file fallback for unresolved obj.method()
}

# Human-readable confidence labels surfaced on graph edges (#885)
def _confidence_label(tier: int, is_unresolved_external: bool) -> str:
    """Map a resolution tier to EXTRACTED / INFERRED / AMBIGUOUS."""
    if is_unresolved_external or tier >= 8:
        return "AMBIGUOUS"
    if tier in (1, 2, 5, 6):
        return "EXTRACTED"
    return "INFERRED"


_SUFFIX_TO_LANG = {
    ".java": "java",
    ".py": "python", ".ipynb": "python",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".cpp": "cpp", ".hpp": "cpp", ".hh": "cpp",
    ".c": "c", ".h": "c",
    ".cs": "c_sharp",
    ".kt": "kotlin",
    ".scala": "scala", ".sc": "scala",
    ".rb": "ruby",
    ".swift": "swift",
    ".php": "php",
    ".dart": "dart",
    ".pl": "perl", ".pm": "perl",
    ".lua": "lua",
    ".hs": "haskell",
    ".ex": "elixir", ".exs": "elixir",
    ".el": "elisp",
}

def detect_lang_from_path(path: str) -> Optional[str]:
    if not path:
        return None
    return _SUFFIX_TO_LANG.get(Path(path).suffix.lower())

def languages_are_compatible(lang1: Optional[str], lang2: Optional[str]) -> bool:
    if not lang1 or not lang2:
        return True
    lang1 = lang1.lower()
    lang2 = lang2.lower()
    if lang1 == lang2:
        return True
    jvm = {"java", "kotlin"}
    if lang1 in jvm and lang2 in jvm:
        return True
    c_cpp = {"c", "cpp"}
    if lang1 in c_cpp and lang2 in c_cpp:
        return True
    js_ts = {"javascript", "typescript"}
    if lang1 in js_ts and lang2 in js_ts:
        return True
    return False



def resolve_function_call(
    call: Dict[str, Any],
    caller_file_path: str,
    local_names: set,
    local_imports: dict,
    imports_map: dict,
    skip_external: bool,
    local_class_bases: Optional[Dict[str, List[str]]] = None,
    member_return_types: Optional[Dict[Tuple[Optional[str], str], str]] = None,
    member_property_types: Optional[Dict[Tuple[Optional[str], str], str]] = None,
    type_aliases: Optional[Dict[str, str]] = None,
    global_class_bases: Optional[Dict[str, List[str]]] = None,
    class_method_names: Optional[Dict[str, set]] = None,
    function_index: Optional[Dict[Tuple[str, str], List[Dict[str, Any]]]] = None,
    class_index: Optional[Dict[Tuple[str, str], List[Dict[str, Any]]]] = None,
    class_method_index: Optional[Dict[Tuple[str, str], List[Dict[str, Any]]]] = None,
    extension_method_index: Optional[Dict[Tuple[str, str], List[Dict[str, Any]]]] = None,
    diagnostics: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """Resolve a single function call to its target. Returns call params dict or None if skipped."""
    caller_lang = detect_lang_from_path(caller_file_path)
    called_name = call["name"]
    if called_name in __builtins__:
        return None

    resolved_called_name = called_name
    resolved_path = None
    resolution_tier = 9
    full_call = call.get("full_name", called_name)
    base_obj = full_call.split(".")[0] if "." in full_call else None
    caller_package = call.get("package")

    is_chained_call = full_call.count(".") > 1 if "." in full_call else False

    if is_chained_call and base_obj in ("self", "this", "super", "super()", "cls", "@"):
        lookup_name = called_name
    else:
        lookup_name = base_obj if base_obj else called_name

    extension_receiver_type = call.get("extension_receiver_type")
    imported_extension_name = local_imports.get(called_name) if extension_receiver_type else None
    imported_call_name = local_imports.get(called_name)
    same_package_call_name = f"{caller_package}.{called_name}" if caller_package else None
    local_class_bases = local_class_bases or {}
    member_return_types = member_return_types or {}
    member_property_types = member_property_types or {}
    type_aliases = type_aliases or {}
    global_class_bases = global_class_bases or {}
    class_method_names = class_method_names or {}
    function_index = function_index or {}
    class_index = class_index or {}
    class_method_index = class_method_index or {}
    extension_method_index = extension_method_index or {}
    resolved_called_line_number = None
    resolved_called_context = None
    receiver_resolution_failed = False
    unresolved_overloaded_callable_reference = False
    unresolved_overloaded_method = False
    ambiguous_class_target = False
    wildcard_imports = local_imports.get("__wildcards__", [])
    if isinstance(wildcard_imports, str):
        wildcard_imports = [wildcard_imports]

    def record_skip(reason: str, **details: Any) -> None:
        if diagnostics is None:
            return
        caller_context = call.get("context")
        caller_name = (
            caller_context[0]
            if caller_context and len(caller_context) == 3
            else None
        )
        diagnostics.append({
            "reason": reason,
            "caller_name": caller_name,
            "caller_file_path": caller_file_path,
            "line_number": call.get("line_number"),
            "full_call_name": call.get("full_name", called_name),
            "call_kind": call.get("call_kind", "call"),
            **details,
        })

    def canonical_type(type_name: Optional[str]) -> Optional[str]:
        if not type_name:
            return None
        normalized = strip_type_modifiers(type_name)
        if not normalized:
            return None
        candidates = [normalized]
        imported = local_imports.get(normalized)
        if imported:
            candidates.insert(0, imported)
        if caller_package and "." not in normalized:
            candidates.append(f"{caller_package}.{normalized}")

        for candidate in candidates:
            target = type_aliases.get(candidate)
            if target:
                target = strip_type_modifiers(target)
                if not target:
                    return None
                imported_target = local_imports.get(target)
                if imported_target and strip_type_modifiers(imported_target) in imports_map:
                    return strip_type_modifiers(imported_target)
                if "." in target and target in imports_map:
                    return target
                same_package_target = f"{caller_package}.{target}" if caller_package else None
                if same_package_target and same_package_target in imports_map:
                    return same_package_target
                return target.split(".")[-1]
        if imported and strip_type_modifiers(imported) in imports_map:
            return strip_type_modifiers(imported)
        if "." in normalized and normalized in imports_map:
            return normalized
        same_package_name = f"{caller_package}.{normalized}" if caller_package else None
        if same_package_name and same_package_name in imports_map:
            return same_package_name
        return normalized.split(".")[-1]

    def simple_type_key(type_name: Optional[str]) -> Optional[str]:
        if not type_name:
            return None
        normalized = strip_type_modifiers(type_name)
        return normalized.split(".")[-1] if normalized else None

    def unique_lower_camel_receiver_type(
        receiver_types: set,
        receiver_name: str,
    ) -> Optional[str]:
        matches = [
            receiver_type
            for receiver_type in receiver_types
            if lower_camel_type_name(receiver_type) == receiver_name
        ]
        if not matches:
            return None

        simple_names = {simple_type_key(receiver_type) for receiver_type in matches}
        simple_names.discard(None)
        if len(simple_names) != 1:
            return None

        simple_name = next(iter(simple_names))
        imported_or_same_package = canonical_type(simple_name)
        if imported_or_same_package in matches:
            return imported_or_same_package

        fqn_matches = [
            receiver_type
            for receiver_type in matches
            if "." in strip_type_modifiers(receiver_type)
        ]
        if len(fqn_matches) == 1:
            return fqn_matches[0]
        if len(fqn_matches) > 1:
            return None
        return simple_name

    def member_type_for_owner(
        member_types: Dict[Tuple[Optional[str], str], str],
        owner_type: Optional[str],
        member_name: str,
    ) -> Optional[str]:
        for owner_key in (owner_type, simple_type_key(owner_type)):
            if not owner_key:
                continue
            member_type = member_types.get((owner_key, member_name))
            if member_type:
                return member_type
        return None

    def first_import_path(*names: Optional[str]) -> Optional[str]:
        for name in names:
            if not name:
                continue
            possible_paths = imports_map.get(name, [])
            if possible_paths:
                return possible_paths[0]
        return None

    def call_arg_count() -> Optional[int]:
        arg_type_hints = call.get("arg_type_hints")
        if (
            call.get("call_kind") == "callable_reference"
            and isinstance(arg_type_hints, list)
            and arg_type_hints
        ):
            return len(arg_type_hints)
        args = call.get("args")
        return len(args) if isinstance(args, list) else None

    def function_arg_count(func: Dict[str, Any]) -> Optional[int]:
        args = func.get("args")
        if not isinstance(args, list):
            args = func.get("parameters")
        return len(args) if isinstance(args, list) else None

    def function_required_arg_count(func: Dict[str, Any]) -> Optional[int]:
        total = function_arg_count(func)
        if total is None:
            return None
        defaults = func.get("arg_defaults")
        if not isinstance(defaults, list):
            return total
        optional = sum(1 for has_default in defaults[:total] if has_default)
        return max(0, total - optional)

    def simple_type_name(type_name: Optional[str]) -> Optional[str]:
        if not type_name:
            return None
        if "->" in type_name:
            return "Function"
        simple_name = strip_type_modifiers(type_name).split(".")[-1]
        primitive_names = {
            "byte": "Byte",
            "short": "Short",
            "int": "Int",
            "long": "Long",
            "float": "Float",
            "double": "Double",
            "boolean": "Boolean",
            "char": "Char",
        }
        return primitive_names.get(simple_name, simple_name)

    def lower_camel_type_name(type_name: Optional[str]) -> Optional[str]:
        simple_name = simple_type_name(type_name)
        if not simple_name:
            return None
        return simple_name[0].lower() + simple_name[1:]

    def expression_type_hint(arg: str) -> Optional[str]:
        text = arg.strip()
        if not text:
            return None
        if text.startswith("{") and text.endswith("}"):
            return "Function"
        if re.fullmatch(r'"(?:\\.|[^"\\])*"', text):
            return "String"
        if re.fullmatch(r"'(?:\\.|[^'\\])'", text):
            return "Char"
        if text in {"true", "false"}:
            return "Boolean"
        if re.fullmatch(r"-?\d+", text):
            return "Int"
        if re.fullmatch(r"-?\d+\.\d+[fF]", text):
            return "Float"
        if re.fullmatch(r"-?\d+\.\d+", text):
            return "Double"
        constructor_match = re.match(r"\b([A-Z]\w*)\s*\(", text)
        if constructor_match:
            return constructor_match.group(1)
        if re.search(r'\.toSet\s*\(\s*\)$', text) or re.match(r'\b(?:setOf|mutableSetOf|hashSetOf|linkedSetOf)\s*\(', text):
            return "Set"
        if re.search(r'\.toList\s*\(\s*\)$', text) or re.match(r'\b(?:listOf|mutableListOf|arrayListOf)\s*\(', text):
            return "List"
        if re.search(r'\.asSequence\s*\(\s*\)$', text) or re.match(r'\bsequenceOf\s*\(', text):
            return "Sequence"
        if re.search(r'\.keys\b$', text):
            return "Set"
        if re.search(r'\.values\b$', text):
            return "Collection"
        return None

    def function_arg_types(func: Dict[str, Any]) -> List[Optional[str]]:
        arg_types = func.get("arg_types")
        if not isinstance(arg_types, list):
            return []
        return [simple_type_name(type_name) for type_name in arg_types]

    def function_arg_names(func: Dict[str, Any]) -> List[Optional[str]]:
        args = func.get("args")
        if not isinstance(args, list):
            args = func.get("parameters")
        if not isinstance(args, list):
            return []
        return [arg if isinstance(arg, str) else None for arg in args]

    def arity_compatible_function_candidates(
        candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        arg_count = call_arg_count()
        if arg_count is None:
            return candidates
        return [
            candidate
            for candidate in candidates
            if (
                function_required_arg_count(candidate) is not None
                and function_arg_count(candidate) is not None
                and function_required_arg_count(candidate) <= arg_count <= function_arg_count(candidate)
            )
        ]

    def type_compatibility_score(
        arg_type: Optional[str],
        param_type: Optional[str],
    ) -> Optional[int]:
        if not arg_type or not param_type:
            return None

        arg_type = simple_type_name(arg_type)
        param_type = simple_type_name(param_type)
        if not arg_type or not param_type:
            return None

        if arg_type == param_type:
            return 4

        mutable_equivalents = {
            "MutableSet": "Set",
            "LinkedHashSet": "Set",
            "HashSet": "Set",
            "MutableList": "List",
            "ArrayList": "List",
            "MutableCollection": "Collection",
        }
        if mutable_equivalents.get(arg_type) == param_type:
            return 3

        collection_supertypes = {
            "Set": {"Iterable", "Collection"},
            "MutableSet": {"Iterable", "Collection", "MutableCollection"},
            "List": {"Iterable", "Collection"},
            "MutableList": {"Iterable", "Collection", "MutableCollection"},
            "Collection": {"Iterable"},
            "Map": {"Any"},
        }
        if param_type in collection_supertypes.get(arg_type, set()):
            return 1

        return -1

    def split_named_argument(arg: str) -> Tuple[Optional[str], str]:
        text = arg.strip()
        depth_round = depth_square = depth_curly = depth_angle = 0
        for idx, char in enumerate(text):
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
            elif char == "<":
                depth_angle += 1
            elif char == ">":
                depth_angle = max(0, depth_angle - 1)
            elif (
                char == "="
                and depth_round == depth_square == depth_curly == depth_angle == 0
            ):
                prev_char = text[idx - 1] if idx > 0 else ""
                next_char = text[idx + 1] if idx + 1 < len(text) else ""
                if prev_char in {"=", "!", "<", ">"} or next_char in {"=", ">"}:
                    continue
                name = text[:idx].strip()
                expression = text[idx + 1:].strip()
                if re.fullmatch(r"[A-Za-z_]\w*", name) and expression:
                    return name, expression
        return None, text

    def candidate_param_type_for_arg(
        candidate: Dict[str, Any],
        arg_idx: int,
        arg_name: Optional[str],
    ) -> Optional[str]:
        param_names = function_arg_names(candidate)
        param_types = function_arg_types(candidate)
        if arg_name:
            for param_name, param_type in zip(param_names, param_types):
                if param_name == arg_name:
                    return param_type
            return None
        return param_types[arg_idx] if arg_idx < len(param_types) else None

    def score_by_argument_types(
        candidates: List[Dict[str, Any]]
    ) -> Optional[List[Tuple[int, Dict[str, Any]]]]:
        args = call.get("args")
        explicit_arg_hints = call.get("arg_type_hints")
        if not isinstance(explicit_arg_hints, list):
            explicit_arg_hints = []
        if not isinstance(args, list):
            args = []
        if call.get("call_kind") == "callable_reference" and not args and explicit_arg_hints:
            args = [""] * len(explicit_arg_hints)
        if not args:
            return None
        parsed_args = [split_named_argument(arg) for arg in args]
        arg_hints = [
            simple_type_name(explicit_arg_hints[idx])
            if idx < len(explicit_arg_hints) and explicit_arg_hints[idx]
            else expression_type_hint(expression)
            for idx, (_, expression) in enumerate(parsed_args)
        ]
        for idx, (arg_name, expression) in enumerate(parsed_args):
            if arg_hints[idx] and not arg_name:
                continue

            if arg_name:
                inferred_from_named_param = {
                    param_type
                    for candidate in candidates
                    for param_name, param_type in zip(
                        function_arg_names(candidate),
                        function_arg_types(candidate),
                    )
                    if param_name == arg_name
                }
                if len(inferred_from_named_param) == 1:
                    arg_hints[idx] = arg_hints[idx] or inferred_from_named_param.pop()
                continue

            if arg_hints[idx] or not re.fullmatch(r"[A-Za-z_]\w*", expression.strip()):
                continue

            inferred_from_name = {
                param_type
                for candidate in candidates
                for param_type in function_arg_types(candidate)[idx:idx + 1]
                if lower_camel_type_name(param_type) == expression.strip()
            }
            if len(inferred_from_name) == 1:
                arg_hints[idx] = inferred_from_name.pop()
                continue

            inferred_from_param_name = {
                param_type
                for candidate in candidates
                for param_name, param_type in zip(
                    function_arg_names(candidate)[idx:idx + 1],
                    function_arg_types(candidate)[idx:idx + 1],
                )
                if param_name == expression.strip()
            }
            if len(inferred_from_param_name) == 1:
                arg_hints[idx] = inferred_from_param_name.pop()
        if not any(arg_hints):
            return None

        scored_candidates = []
        for candidate in candidates:
            param_types = function_arg_types(candidate)
            if len(param_types) < len(arg_hints):
                continue

            score = 0
            comparable = False
            compatible = True
            for idx, (arg_hint, (arg_name, _)) in enumerate(zip(arg_hints, parsed_args)):
                param_type = candidate_param_type_for_arg(candidate, idx, arg_name)
                if arg_name and param_type is None:
                    compatible = False
                    break
                compatibility = type_compatibility_score(arg_hint, param_type)
                if compatibility is None:
                    continue
                comparable = True
                if compatibility < 0:
                    compatible = False
                    break
                score += compatibility

            if comparable and compatible:
                scored_candidates.append((score, candidate))

        return scored_candidates

    def select_by_argument_types(
        candidates: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        scored_candidates = score_by_argument_types(candidates)
        if not scored_candidates:
            return None

        best_score = max(score for score, _ in scored_candidates)
        best_candidates = [
            candidate
            for score, candidate in scored_candidates
            if score == best_score
        ]
        return best_candidates[0] if len(best_candidates) == 1 else None

    def call_has_argument_type_hints() -> bool:
        args = call.get("args")
        explicit_arg_hints = call.get("arg_type_hints")
        if (
            call.get("call_kind") == "callable_reference"
            and isinstance(explicit_arg_hints, list)
            and explicit_arg_hints
        ):
            return True
        if not isinstance(args, list):
            return False
        if isinstance(explicit_arg_hints, list) and any(explicit_arg_hints):
            return True
        return any(
            expression_type_hint(split_named_argument(arg)[1])
            for arg in args
        )

    def call_has_strict_argument_type_hints() -> bool:
        explicit_arg_hints = call.get("arg_type_hints")
        if (
            call.get("call_kind") == "callable_reference"
            and isinstance(explicit_arg_hints, list)
            and any(explicit_arg_hints)
        ):
            return True
        args = call.get("args")
        if not isinstance(args, list):
            return False
        return any(
            expression_type_hint(split_named_argument(arg)[1])
            for arg in args
        )

    def select_function_candidate(candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not candidates:
            return None

        arg_count = call_arg_count()
        if arg_count is not None:
            arity_compatible = arity_compatible_function_candidates(candidates)
            selected_by_type = select_by_argument_types(arity_compatible)
            if selected_by_type:
                return selected_by_type

            exact_arity = [
                candidate
                for candidate in candidates
                if function_arg_count(candidate) == arg_count
            ]
            if (
                len(exact_arity) == 1
                and len(arity_compatible) <= 1
                and not call_has_strict_argument_type_hints()
            ):
                return exact_arity[0]
            if call_has_argument_type_hints() and any(
                function_arg_types(candidate)
                for candidate in arity_compatible
            ):
                return None
            if len(exact_arity) == 1:
                return exact_arity[0]
            if len(arity_compatible) == 1:
                return arity_compatible[0]

        if len(candidates) == 1:
            return candidates[0]
        return None

    def target_hint_for_function(
        path: Optional[str],
        method_name: str,
        context_hint: Optional[str],
        line_hint: Optional[int],
    ) -> Tuple[Optional[int], Optional[str], bool]:
        if not path:
            return line_hint, context_hint, False

        candidates = function_index.get((str(Path(path).resolve()), method_name), [])
        if not candidates:
            return line_hint, context_hint, False

        if context_hint:
            context_candidates = [
                candidate
                for candidate in candidates
                if candidate.get("context") == context_hint
            ]
            if context_candidates:
                candidates = context_candidates

        owner_line = call_enclosing_class_line()
        if owner_line is not None:
            owner_candidates = [
                candidate
                for candidate in candidates
                if candidate.get("class_context_line") == owner_line
            ]
            if owner_candidates:
                candidates = owner_candidates

        if line_hint is not None:
            return line_hint, context_hint, False

        if context_hint is None:
            top_level_candidates = [
                candidate for candidate in candidates
                if candidate.get("context") is None
            ]
            if len(top_level_candidates) == 1:
                candidates = top_level_candidates

        selected = select_function_candidate(candidates)
        if selected:
            return selected.get("line_number"), selected.get("context") or context_hint, False
        return None, context_hint, len(candidates) > 1

    def target_hint_for_class(
        path: Optional[str],
        class_name: str,
        line_hint: Optional[int],
    ) -> Tuple[Optional[int], bool]:
        if not path:
            return line_hint, False
        if line_hint is not None:
            return line_hint, False

        class_key = simple_type_key(class_name) or class_name
        candidates = class_index.get((str(Path(path).resolve()), class_key), [])
        if not candidates:
            return None, False

        call_class_context = call.get("class_context")
        enclosing_class_line = (
            call_class_context[1]
            if isinstance(call_class_context, tuple) and len(call_class_context) >= 2
            else None
        )
        if enclosing_class_line is not None:
            owner_candidates = [
                candidate
                for candidate in candidates
                if candidate.get("class_context_line") == enclosing_class_line
            ]
            if len(owner_candidates) == 1:
                return owner_candidates[0].get("line_number"), False
            if owner_candidates:
                candidates = owner_candidates

        enclosing_class = call.get("enclosing_class")
        if enclosing_class:
            owner_candidates = [
                candidate
                for candidate in candidates
                if candidate.get("class_context") == enclosing_class
            ]
            if len(owner_candidates) == 1:
                return owner_candidates[0].get("line_number"), False
            if owner_candidates:
                candidates = owner_candidates

        if len(candidates) == 1:
            return candidates[0].get("line_number"), False

        top_level_candidates = [
            candidate
            for candidate in candidates
            if not candidate.get("class_context")
        ]
        if len(top_level_candidates) == 1:
            return top_level_candidates[0].get("line_number"), False

        return None, True

    def call_enclosing_class_line() -> Optional[int]:
        class_context = call.get("class_context")
        if isinstance(class_context, tuple) and len(class_context) >= 2:
            line_number = class_context[1]
            return line_number if isinstance(line_number, int) else None
        return None

    def filter_method_candidates_by_call_owner(
        candidates: List[Dict[str, Any]],
        current_type: Optional[str],
    ) -> List[Dict[str, Any]]:
        owner_line = call_enclosing_class_line()
        if owner_line is None:
            return candidates
        if simple_type_key(current_type) != call.get("enclosing_class"):
            return candidates
        owner_candidates = [
            candidate
            for candidate in candidates
            if candidate.get("class_context_line") == owner_line
        ]
        return owner_candidates or candidates

    def method_target_for_type(
        type_name: Optional[str],
        method_name: str,
    ) -> Tuple[Optional[str], Optional[int], Optional[str]]:
        nonlocal unresolved_overloaded_callable_reference, unresolved_overloaded_method
        if not type_name:
            return None, None, None

        visited = set()
        queue = [type_name]
        method_candidates_by_hierarchy: List[Dict[str, Any]] = []
        extension_candidates_by_hierarchy: List[Dict[str, Any]] = []
        fallback_method_owner_path: Optional[str] = None
        fallback_method_context: Optional[str] = None
        while queue:
            current = canonical_type(queue.pop(0))
            if not current or current in visited:
                continue
            visited.add(current)

            method_candidates = class_method_index.get((current, method_name), [])
            method_candidates = [
                cand for cand in method_candidates
                if languages_are_compatible(caller_lang, cand.get("lang"))
            ]
            if method_candidates:
                filtered_candidates = filter_method_candidates_by_call_owner(
                    method_candidates,
                    current,
                )
                for cand in filtered_candidates:
                    cand_arity = function_arg_count(cand)
                    if cand_arity is None or not any(
                        function_arg_count(existing) == cand_arity
                        and function_arg_types(existing) == function_arg_types(cand)
                        for existing in method_candidates_by_hierarchy
                    ):
                        method_candidates_by_hierarchy.append(cand)

            if not fallback_method_owner_path and method_name in class_method_names.get(current, set()):
                method_owner_path = first_import_path(current)
                if method_owner_path:
                    fallback_method_owner_path = method_owner_path
                    fallback_method_context = simple_type_key(current)

            extension_candidates = extension_method_index.get((current, method_name), [])
            extension_candidates = [
                cand for cand in extension_candidates
                if languages_are_compatible(caller_lang, cand.get("lang"))
            ]
            if extension_candidates:
                for cand in extension_candidates:
                    cand_arity = function_arg_count(cand)
                    if cand_arity is None or not any(
                        function_arg_count(existing) == cand_arity
                        and function_arg_types(existing) == function_arg_types(cand)
                        for existing in extension_candidates_by_hierarchy
                    ):
                        extension_candidates_by_hierarchy.append(cand)

            for base_name in global_class_bases.get(current, []):
                base_type = canonical_type(base_name)
                if base_type and base_type not in visited:
                    queue.append(base_type)

        if method_candidates_by_hierarchy:
            selected = select_function_candidate(method_candidates_by_hierarchy)
            if selected:
                return (
                    selected.get("path"),
                    selected.get("line_number"),
                    selected.get("context") or simple_type_key(type_name),
                )

            arity_compatible_members = arity_compatible_function_candidates(
                method_candidates_by_hierarchy
            )
            member_type_scores = (
                score_by_argument_types(arity_compatible_members)
                if any(function_arg_types(candidate) for candidate in arity_compatible_members)
                else None
            )
            members_are_inapplicable = (
                not arity_compatible_members
                or member_type_scores == []
            )
            if not (extension_candidates_by_hierarchy and members_are_inapplicable):
                if call.get("call_kind") == "callable_reference":
                    unresolved_overloaded_callable_reference = True
                else:
                    unresolved_overloaded_method = True
                return None, None, None

        if fallback_method_owner_path:
            return fallback_method_owner_path, None, fallback_method_context

        if extension_candidates_by_hierarchy:
            selected = select_function_candidate(extension_candidates_by_hierarchy)
            if selected:
                return selected.get("path"), selected.get("line_number"), selected.get("context")
            if call.get("call_kind") == "callable_reference":
                unresolved_overloaded_callable_reference = True
            else:
                unresolved_overloaded_method = True
            return None, None, None

        return None, None, None

    extension_receiver_type = canonical_type(extension_receiver_type)
    if (
        not extension_receiver_type
        and base_obj
        and re.fullmatch(r"[A-Za-z_]\w*", base_obj)
    ):
        receiver_type_candidates = {
            receiver_type
            for receiver_type, method_name in extension_method_index
            if method_name == called_name
        }
        matching_receiver_type = unique_lower_camel_receiver_type(
            receiver_type_candidates,
            base_obj,
        )
        if matching_receiver_type:
            extension_receiver_type = canonical_type(matching_receiver_type)
    extension_receiver_simple = simple_type_key(extension_receiver_type)
    extension_receiver_lookup_types = [
        receiver_type
        for receiver_type in (extension_receiver_type, extension_receiver_simple)
        if receiver_type
    ]
    extension_receiver_lookup_types = list(dict.fromkeys(extension_receiver_lookup_types))
    same_package_extension_names = [
        f"{caller_package}.{receiver_type}.{called_name}"
        for receiver_type in extension_receiver_lookup_types
        if caller_package and "." not in strip_type_modifiers(receiver_type)
    ]
    extension_lookup_names = [
        f"{receiver_type}.{called_name}"
        for receiver_type in extension_receiver_lookup_types
    ]
    wildcard_extension_path = (
        first_import_path(
            *(
                f"{package_name}.{receiver_type}.{called_name}"
                for package_name in wildcard_imports
                for receiver_type in extension_receiver_lookup_types
                if "." not in strip_type_modifiers(receiver_type)
            )
        )
        if extension_receiver_lookup_types and wildcard_imports
        else None
    )
    wildcard_call_path = (
        first_import_path(
            *(f"{package_name}.{called_name}" for package_name in wildcard_imports)
        )
        if wildcard_imports
        else None
    )

    member_receiver_type = None
    receiver_base_type = call.get("receiver_base_type")
    receiver_member_name = call.get("receiver_member_name")
    receiver_member_kind = call.get("receiver_member_kind")
    if receiver_base_type and receiver_member_name:
        receiver_base_type = canonical_type(receiver_base_type)
        if receiver_member_kind == "function":
            member_receiver_type = member_type_for_owner(
                member_return_types,
                receiver_base_type,
                receiver_member_name,
            )
        elif receiver_member_kind == "property":
            member_receiver_type = member_type_for_owner(
                member_property_types,
                receiver_base_type,
                receiver_member_name,
            )
        if member_receiver_type:
            member_receiver_type = canonical_type(member_receiver_type)
        elif receiver_member_kind == "property":
            receiver_type_candidates = {
                receiver_type
                for receiver_type, method_name in extension_method_index
                if method_name == called_name
            }
            matching_receiver_type = unique_lower_camel_receiver_type(
                receiver_type_candidates,
                receiver_member_name,
            )
            if matching_receiver_type:
                member_receiver_type = canonical_type(matching_receiver_type)

    receiver_type = extension_receiver_type or call.get("inferred_obj_type")
    if receiver_type:
        (
            resolved_path,
            resolved_called_line_number,
            resolved_called_context,
        ) = method_target_for_type(receiver_type, called_name)
        if resolved_path:
            fqn = (local_imports.get(receiver_type) if local_imports else None) or (receiver_type if "." in receiver_type else None)
            if fqn and len(imports_map.get(fqn, [])) == 1:
                resolution_tier = 3
            else:
                resolution_tier = 4
        else:
            receiver_resolution_failed = True

    if not resolved_path and imported_extension_name and imported_extension_name in imports_map:
        possible_paths = imports_map[imported_extension_name]
        if possible_paths:
            resolved_path = possible_paths[0]
            resolved_called_name = imported_extension_name.split(".")[-1]
            resolution_tier = 6
    elif not resolved_path and any(name in imports_map for name in same_package_extension_names):
        possible_paths = first_import_path(*same_package_extension_names)
        if possible_paths:
            resolved_path = possible_paths
            resolution_tier = 5
    elif not resolved_path and wildcard_extension_path:
        resolved_path = wildcard_extension_path
        resolution_tier = 6
    elif not resolved_path and any(name in imports_map for name in extension_lookup_names):
        possible_path = first_import_path(*extension_lookup_names)
        if possible_path:
            resolved_path = possible_path
            resolution_tier = 4

    if not resolved_path and call.get("implicit_receiver_type"):
        implicit_type = canonical_type(call["implicit_receiver_type"])
        (
            resolved_path,
            resolved_called_line_number,
            resolved_called_context,
        ) = method_target_for_type(implicit_type, called_name)
        if resolved_path:
            fqn = (local_imports.get(call["implicit_receiver_type"]) if local_imports else None) or (implicit_type if "." in implicit_type else None)
            if fqn and len(imports_map.get(fqn, [])) == 1:
                resolution_tier = 3
            else:
                resolution_tier = 4
        elif unresolved_overloaded_callable_reference or unresolved_overloaded_method:
            record_skip(
                "unresolved_overloaded_callable_reference"
                if unresolved_overloaded_callable_reference
                else "unresolved_overloaded_call",
                receiver_type=implicit_type,
                arg_type_hints=call.get("arg_type_hints", []),
            )
            return None
        else:
            receiver_resolution_failed = True

    if not resolved_path and not base_obj and call.get("enclosing_class"):
        (
            resolved_path,
            resolved_called_line_number,
            resolved_called_context,
        ) = method_target_for_type(call.get("enclosing_class"), called_name)
        if resolved_path:
            resolution_tier = 2
        elif unresolved_overloaded_callable_reference or unresolved_overloaded_method:
            record_skip(
                "unresolved_overloaded_callable_reference"
                if unresolved_overloaded_callable_reference
                else "unresolved_overloaded_call",
                receiver_type=call.get("enclosing_class"),
                arg_type_hints=call.get("arg_type_hints", []),
            )
            return None

    if not resolved_path and (unresolved_overloaded_callable_reference or unresolved_overloaded_method):
        record_skip(
            "unresolved_overloaded_callable_reference"
            if unresolved_overloaded_callable_reference
            else "unresolved_overloaded_call",
            receiver_type=(
                extension_receiver_type
                or canonical_type(call.get("inferred_obj_type"))
                or canonical_type(call.get("implicit_receiver_type"))
                or member_receiver_type
            ),
            arg_type_hints=call.get("arg_type_hints", []),
        )
        return None

    if not resolved_path and receiver_resolution_failed:
        if unresolved_overloaded_callable_reference or unresolved_overloaded_method:
            record_skip(
                "unresolved_overloaded_callable_reference"
                if unresolved_overloaded_callable_reference
                else "unresolved_overloaded_call",
                receiver_type=(
                    extension_receiver_type
                    or canonical_type(call.get("inferred_obj_type"))
                    or canonical_type(call.get("implicit_receiver_type"))
                    or member_receiver_type
                ),
                arg_type_hints=call.get("arg_type_hints", []),
            )
            return None
        receiver_type_for_path = (
            extension_receiver_type
            or canonical_type(call.get("inferred_obj_type"))
            or canonical_type(call.get("implicit_receiver_type"))
            or member_receiver_type
        )
        possible_paths = imports_map.get(receiver_type_for_path, []) if receiver_type_for_path else []
        if possible_paths:
            resolved_path = possible_paths[0]
            raw_receiver_type = (
                extension_receiver_type
                or call.get("inferred_obj_type")
                or call.get("implicit_receiver_type")
            )
            fqn = None
            if raw_receiver_type:
                raw_receiver_type = strip_type_modifiers(raw_receiver_type)
                if local_imports and raw_receiver_type in local_imports:
                    fqn = local_imports[raw_receiver_type]
                elif "." in raw_receiver_type:
                    fqn = raw_receiver_type
            
            if fqn and len(imports_map.get(fqn, [])) == 1:
                resolution_tier = 3
            else:
                resolution_tier = 4
            receiver_resolution_failed = False

    if not resolved_path and receiver_resolution_failed:
        if call.get("call_kind") == "callable_reference":
            record_skip(
                "receiver_resolution_failed",
                receiver_type=(
                    extension_receiver_type
                    or canonical_type(call.get("inferred_obj_type"))
                    or canonical_type(call.get("implicit_receiver_type"))
                    or member_receiver_type
                ),
            )
        return None

    if not resolved_path and member_receiver_type:
        (
            resolved_path,
            resolved_called_line_number,
            resolved_called_context,
        ) = method_target_for_type(member_receiver_type, called_name)
        if resolved_path:
            resolution_tier = 4
        elif unresolved_overloaded_callable_reference or unresolved_overloaded_method:
            record_skip(
                "unresolved_overloaded_callable_reference"
                if unresolved_overloaded_callable_reference
                else "unresolved_overloaded_call",
                receiver_type=member_receiver_type,
                arg_type_hints=call.get("arg_type_hints", []),
            )
            return None
        if not resolved_path:
            possible_paths = imports_map.get(member_receiver_type, [])
            if possible_paths:
                resolved_path = possible_paths[0]
                resolution_tier = 4
        if not resolved_path:
            receiver_resolution_failed = True

    if not resolved_path and (unresolved_overloaded_callable_reference or unresolved_overloaded_method):
        record_skip(
            "unresolved_overloaded_callable_reference"
            if unresolved_overloaded_callable_reference
            else "unresolved_overloaded_call",
            receiver_type=(
                extension_receiver_type
                or canonical_type(call.get("inferred_obj_type"))
                or canonical_type(call.get("implicit_receiver_type"))
                or member_receiver_type
            ),
            arg_type_hints=call.get("arg_type_hints", []),
        )
        return None

    if not resolved_path and imported_call_name and imported_call_name in imports_map:
        possible_paths = imports_map[imported_call_name]
        if possible_paths:
            resolved_path = possible_paths[0]
            resolved_called_name = imported_call_name.split(".")[-1]
            resolution_tier = 6
    elif not resolved_path and same_package_call_name and same_package_call_name in imports_map:
        possible_paths = imports_map[same_package_call_name]
        if possible_paths:
            resolved_path = possible_paths[0]
            resolution_tier = 5
    elif not resolved_path and wildcard_call_path:
        resolved_path = wildcard_call_path
        resolution_tier = 6
    elif not resolved_path and base_obj and base_obj in local_imports:
        full_import_name = local_imports[base_obj]
        possible_paths = imports_map.get(full_import_name, [])
        if possible_paths:
            resolved_path = possible_paths[0]
            resolution_tier = 6
    elif not resolved_path and base_obj == "super":
        enclosing_class = call.get("enclosing_class")
        for base_name in local_class_bases.get(enclosing_class, []):
            base_name = strip_type_modifiers(base_name)
            (
                resolved_path,
                resolved_called_line_number,
                resolved_called_context,
            ) = method_target_for_type(base_name, called_name)
            if resolved_path:
                resolution_tier = 4
                break

            possible_paths = imports_map.get(base_name, [])
            if not possible_paths and caller_package:
                possible_paths = imports_map.get(f"{caller_package}.{base_name}", [])
            if possible_paths:
                resolved_path = possible_paths[0]
                resolved_called_context = simple_type_key(canonical_type(base_name))
                resolution_tier = 4
                break
        if not resolved_path:
            resolved_path = caller_file_path
            resolution_tier = 1
    elif not resolved_path and base_obj in ("self", "this", "super()", "cls", "@") and not is_chained_call:
        resolved_path = caller_file_path
        resolved_called_context = call.get("enclosing_class")
        resolution_tier = 1
    elif not resolved_path and lookup_name in local_names:
        resolved_path = caller_file_path
        resolution_tier = 2
    elif not resolved_path and call.get("inferred_obj_type"):
        raw_obj_type = call["inferred_obj_type"]
        obj_type = canonical_type(raw_obj_type)
        (
            resolved_path,
            resolved_called_line_number,
            resolved_called_context,
        ) = method_target_for_type(obj_type, called_name)
        if resolved_path:
            resolution_tier = 4
        elif unresolved_overloaded_callable_reference or unresolved_overloaded_method:
            record_skip(
                "unresolved_overloaded_callable_reference"
                if unresolved_overloaded_callable_reference
                else "unresolved_overloaded_call",
                receiver_type=obj_type,
                arg_type_hints=call.get("arg_type_hints", []),
            )
            return None
        if not resolved_path and raw_obj_type in local_imports:
            fqn_paths = imports_map.get(local_imports[raw_obj_type], [])
            if len(fqn_paths) == 1:
                resolved_path = fqn_paths[0]
                resolution_tier = 3
        if not resolved_path:
            possible_paths = imports_map.get(obj_type, [])
            if len(possible_paths) > 0:
                resolved_path = possible_paths[0]
                resolution_tier = 4
        if not resolved_path:
            receiver_resolution_failed = True

    if not resolved_path and (unresolved_overloaded_callable_reference or unresolved_overloaded_method):
        record_skip(
            "unresolved_overloaded_callable_reference"
            if unresolved_overloaded_callable_reference
            else "unresolved_overloaded_call",
            receiver_type=(
                extension_receiver_type
                or canonical_type(call.get("inferred_obj_type"))
                or canonical_type(call.get("implicit_receiver_type"))
                or member_receiver_type
            ),
            arg_type_hints=call.get("arg_type_hints", []),
        )
        return None

    if not resolved_path and receiver_resolution_failed:
        if call.get("call_kind") == "callable_reference":
            record_skip(
                "receiver_resolution_failed",
                receiver_type=(
                    extension_receiver_type
                    or canonical_type(call.get("inferred_obj_type"))
                    or canonical_type(call.get("implicit_receiver_type"))
                    or member_receiver_type
                ),
            )
        return None

    if not resolved_path:
        if lookup_name in local_imports:
            resolved_called_name = local_imports[lookup_name]
        possible_paths = imports_map.get(lookup_name, [])
        if not possible_paths and lookup_name in local_imports:
            imported_name = local_imports[lookup_name]
            alias_paths = imports_map.get(imported_name, [])
            if alias_paths:
                possible_paths = alias_paths
                lookup_name = imported_name
                resolved_called_name = imported_name
        if len(possible_paths) == 1:
            resolved_path = possible_paths[0]
            resolution_tier = 5
        elif len(possible_paths) > 1:
            if lookup_name in local_imports:
                full_import_name = local_imports[lookup_name]
                if full_import_name in imports_map:
                    direct_paths = imports_map[full_import_name]
                    if direct_paths and len(direct_paths) == 1:
                        resolved_path = direct_paths[0]
                        resolution_tier = 6
                if not resolved_path:
                    for path in possible_paths:
                        if full_import_name.replace(".", "/") in path:
                            resolved_path = path
                            resolution_tier = 7
                            break

    if not resolved_path:
        is_unresolved_external = True
    else:
        is_unresolved_external = False

    if not resolved_path:
        possible_paths = imports_map.get(lookup_name, [])
        if len(possible_paths) > 0:
            if lookup_name in local_imports:
                pass
            else:
                pass
    if not resolved_path:
        if called_name in local_names:
            resolved_path = caller_file_path
            is_unresolved_external = False
            resolution_tier = 2
        elif called_name in imports_map and imports_map[called_name]:
            candidates = imports_map[called_name]
            for path in candidates:
                for imp_name in local_imports.values():
                    if not isinstance(imp_name, str):
                        continue
                    if imp_name.replace(".", "/") in path:
                        resolved_path = path
                        is_unresolved_external = False
                        resolution_tier = 7
                        break
                if resolved_path:
                    break
            if not resolved_path:
                resolved_path = candidates[0]
                resolution_tier = 8
        else:
            resolved_path = caller_file_path
            resolution_tier = 9

    if skip_external and is_unresolved_external:
        record_skip("skip_external_unresolved")
        return None

    class_target_key = simple_type_key(resolved_called_name) or resolved_called_name
    target_is_class = bool(
        resolved_path
        and class_index.get((str(Path(resolved_path).resolve()), class_target_key), [])
    )
    if target_is_class:
        (
            resolved_called_line_number,
            ambiguous_class_target,
        ) = target_hint_for_class(
            resolved_path,
            resolved_called_name,
            resolved_called_line_number,
        )
        if ambiguous_class_target:
            record_skip(
                "ambiguous_class_target",
                called_name=resolved_called_name,
                called_file_path=resolved_path,
            )
            return None
        resolved_called_name = class_target_key
    else:
        (
            resolved_called_line_number,
            resolved_called_context,
            ambiguous_function_target,
        ) = target_hint_for_function(
            resolved_path,
            resolved_called_name,
            resolved_called_context,
            resolved_called_line_number,
        )
        if ambiguous_function_target:
            record_skip(
                "ambiguous_function_target",
                called_name=resolved_called_name,
                called_file_path=resolved_path,
            )
            return None
    confidence = _TIER_CONFIDENCE.get(resolution_tier, 0.1)
    conf_label = _confidence_label(resolution_tier, is_unresolved_external)

    caller_context = call.get("context")
    if caller_context and len(caller_context) == 3 and caller_context[0] is not None:
        caller_name, caller_type, caller_line_number = caller_context
        if caller_type == "nested_call":
            fp = str(Path(caller_file_path).resolve())
            candidates = function_index.get((fp, caller_name), [])
            if candidates:
                lines = [
                    c["line_number"]
                    for c in candidates
                    if c.get("line_number") is not None
                ]
                if lines:
                    caller_line_number = min(lines)
            elif caller_name == "<module>":
                caller_line_number = 1
        return {
            "type": "function",
            "caller_name": caller_name,
            "caller_file_path": caller_file_path,
            "caller_line_number": caller_line_number,
            "called_name": resolved_called_name,
            "called_file_path": resolved_path,
            "called_line_number": resolved_called_line_number,
            "called_context": resolved_called_context,
            "line_number": call["line_number"],
            "args": call.get("args", []),
            "full_call_name": call.get("full_name", called_name),
            "confidence": confidence,
            "confidence_label": conf_label,
            "resolution_tier": resolution_tier,
        }
    return {
        "type": "file",
        "caller_file_path": caller_file_path,
        "called_name": resolved_called_name,
        "called_file_path": resolved_path,
        "called_line_number": resolved_called_line_number,
        "called_context": resolved_called_context,
        "line_number": call["line_number"],
        "args": call.get("args", []),
        "full_call_name": call.get("full_name", called_name),
        "confidence": confidence,
        "confidence_label": conf_label,
        "resolution_tier": resolution_tier,
    }


def build_function_call_groups(
    all_file_data: List[Dict[str, Any]],
    imports_map: dict,
    file_class_lookup: Optional[Dict[str, set]] = None,
    diagnostics: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Resolve all function calls and return grouped CALLS payloads.

    Return order:
    (fn_to_fn, fn_to_class, fn_to_interface, fn_to_object, file_to_fn, file_to_class, file_to_interface, file_to_object)
    """
    skip_external = (get_config_value("SKIP_EXTERNAL_RESOLUTION") or "false").lower() == "true"

    if file_class_lookup is None:
        file_class_lookup = {}

    # file_symbol_labels: file_path -> {symbol_name -> neo4j_label}
    # Covers every non-Function node type so we can emit label-specific MATCH queries.
    # Symbols absent from this map are assumed to be Function nodes.
    file_symbol_labels: Dict[str, Dict[str, str]] = {}
    for fd in all_file_data:
        fp = str(Path(fd["path"]).resolve())
        sym_labels: Dict[str, str] = {}
        targets = {c["name"] for c in fd.get("classes", [])}
        for name in targets:
            sym_labels[name] = "Class"
        for label, neo4j_label in [
            ("interfaces", "Interface"),
            ("traits", "Trait"),
            ("structs", "Struct"),
            ("enums", "Enum"),
            ("records", "Record"),
            ("unions", "Union"),
            ("objects", "Object"),
        ]:
            for item in fd.get(label, []):
                sym_labels[item["name"]] = neo4j_label
                targets.add(item["name"])
        file_symbol_labels[fp] = sym_labels
        file_class_lookup[fp] = targets

    type_aliases: Dict[str, str] = {}
    for fd in all_file_data:
        for typealias in fd.get("typealiases", []):
            alias_name = typealias.get("name")
            target = typealias.get("target")
            if not alias_name or not target:
                continue
            target = strip_type_modifiers(target)
            type_aliases[alias_name] = target
            package_name = typealias.get("package")
            if package_name:
                type_aliases[f"{package_name}.{alias_name}"] = target

    def canonical_type_for_maps(
        type_name: Optional[str],
        local_imports: Optional[dict] = None,
        package_name: Optional[str] = None,
    ) -> Optional[str]:
        if not type_name:
            return None
        normalized = strip_type_modifiers(type_name)
        if not normalized:
            return None
        candidates = [normalized]
        if local_imports:
            imported = local_imports.get(normalized)
            if imported:
                candidates.insert(0, imported)
        if package_name and "." not in normalized:
            candidates.append(f"{package_name}.{normalized}")

        for candidate in candidates:
            target = type_aliases.get(candidate)
            if target:
                target = strip_type_modifiers(target)
                if not target:
                    return None
                imported_target = local_imports.get(target) if local_imports else None
                if imported_target and strip_type_modifiers(imported_target) in imports_map:
                    return strip_type_modifiers(imported_target)
                if "." in target and target in imports_map:
                    return target
                same_package_target = f"{package_name}.{target}" if package_name else None
                if same_package_target and same_package_target in imports_map:
                    return same_package_target
                return target.split(".")[-1]
        if local_imports:
            imported = local_imports.get(normalized)
            if imported and strip_type_modifiers(imported) in imports_map:
                return strip_type_modifiers(imported)
        if "." in normalized and normalized in imports_map:
            return normalized
        same_package_name = f"{package_name}.{normalized}" if package_name else None
        if same_package_name and same_package_name in imports_map:
            return same_package_name
        return normalized.split(".")[-1]

    def simple_type_key(type_name: Optional[str]) -> Optional[str]:
        if not type_name:
            return None
        normalized = strip_type_modifiers(type_name)
        return normalized.split(".")[-1] if normalized else None

    def type_keys_for_maps(
        type_name: Optional[str],
        local_imports: Optional[dict] = None,
        package_name: Optional[str] = None,
    ) -> List[str]:
        canonical = canonical_type_for_maps(type_name, local_imports, package_name)
        simple = simple_type_key(type_name) or simple_type_key(canonical)
        keys: List[str] = []
        for key in (canonical, simple):
            if key and key not in keys:
                keys.append(key)
        return keys

    def file_local_imports(fd: Dict[str, Any]) -> Dict[str, str]:
        return {
            imp.get("alias") or imp["name"].split(".")[-1]: imp["name"]
            for imp in fd.get("imports", [])
            if not imp["name"].endswith(".*")
        }

    def file_package(fd: Dict[str, Any]) -> Optional[str]:
        return fd.get("package") or fd.get("package_name")

    def normalize_full_type(type_name: Optional[str]) -> Optional[str]:
        if not type_name or type_name == "Unknown":
            return None
        text = str(type_name).strip()
        while text.endswith("?"):
            text = text[:-1].strip()
        return text or None

    def split_generic_args(type_name: str) -> List[str]:
        start = type_name.find("<")
        end = type_name.rfind(">")
        if start == -1 or end == -1 or end <= start:
            return []
        inner = type_name[start + 1:end]
        args: List[str] = []
        current = []
        depth = 0
        for char in inner:
            if char == "<":
                depth += 1
            elif char == ">":
                depth = max(0, depth - 1)
            if char == "," and depth == 0:
                arg = "".join(current).strip()
                if arg:
                    args.append(arg)
                current = []
            else:
                current.append(char)
        arg = "".join(current).strip()
        if arg:
            args.append(arg)
        return args

    def collection_element_type(
        type_name: Optional[str],
        local_imports: Optional[dict] = None,
        package_name: Optional[str] = None,
    ) -> Optional[str]:
        full_type = normalize_full_type(type_name)
        if not full_type:
            return None
        base_type = canonical_type_for_maps(full_type, local_imports, package_name)
        args = split_generic_args(full_type)
        if not args:
            return None
        if simple_type_key(base_type) in {
            "Array",
            "Collection",
            "Flow",
            "Iterable",
            "List",
            "MutableCollection",
            "MutableIterable",
            "MutableList",
            "MutableSet",
            "Sequence",
            "Set",
        }:
            return canonical_type_for_maps(args[0], local_imports, package_name)
        return None

    def collection_type_from_operator(
        source_type: Optional[str],
        operator: Optional[str],
    ) -> Optional[str]:
        element_type = collection_element_type(source_type)
        if not element_type:
            return None
        if operator == "toSet":
            return f"Set<{element_type}>"
        if operator == "asSequence":
            return f"Sequence<{element_type}>"
        return f"List<{element_type}>"

    # Fast path: skip all Kotlin-specific index structures when no Kotlin files present.
    # For pure Java/Python/JS repos this avoids building extension_method_index and
    # class_method_index over hundreds of thousands of functions.
    has_kotlin = any(fd.get("lang") == "kotlin" for fd in all_file_data)

    member_return_types: Dict[Tuple[Optional[str], str], str] = {}
    member_return_types_full: Dict[Tuple[Optional[str], str], str] = {}
    member_property_types: Dict[Tuple[Optional[str], str], str] = {}
    global_class_bases: Dict[str, List[str]] = {}
    class_method_names: Dict[str, set] = {}
    function_index: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    class_index: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    class_method_index: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    extension_method_index: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    global_variable_types: Dict[str, str] = {}

    def companion_owner_context_names(
        fd: Dict[str, Any],
        func: Dict[str, Any],
        package_name: Optional[str],
    ) -> List[str]:
        if func.get("line_number") is None:
            return []

        line_number = func["line_number"]
        companion_objects = [
            class_data
            for class_data in fd.get("classes", []) + fd.get("interfaces", []) + fd.get("objects", [])
            if (
                class_data.get("node_type") == "companion_object"
                or (
                    class_data.get("node_type") is None
                    and class_data.get("name") == "Companion"
                )
            )
            and class_data.get("line_number") is not None
            and class_data.get("end_line") is not None
            and class_data["line_number"] <= line_number <= class_data["end_line"]
        ]
        func_context = func.get("context")
        if isinstance(func_context, tuple) and len(func_context) > 0:
            func_context = func_context[0]
        if not companion_objects or func_context not in {
            companion.get("name") for companion in companion_objects
        }:
            return []

        owners = [
            class_data
            for class_data in fd.get("classes", []) + fd.get("interfaces", []) + fd.get("objects", [])
            if class_data not in companion_objects
            and class_data.get("line_number") is not None
            and class_data.get("end_line") is not None
            and class_data["line_number"] <= line_number <= class_data["end_line"]
        ]
        if not owners:
            return []

        owner = min(
            owners,
            key=lambda class_data: class_data["end_line"] - class_data["line_number"],
        )
        return type_keys_for_maps(owner.get("name"), package_name=package_name)

    def function_context_names_for_maps(
        fd: Dict[str, Any],
        func: Dict[str, Any],
        package_name: Optional[str],
    ) -> List[str]:
        context = func.get("context") or func.get("class_context")
        if isinstance(context, tuple) and len(context) > 0:
            context = context[0]
        context_names = list(type_keys_for_maps(context, package_name=package_name))
        context_names.extend(companion_owner_context_names(fd, func, package_name))
        return list(dict.fromkeys(context_names))

    for fd in all_file_data:
        file_path = str(Path(fd["path"]).resolve())
        package_name = file_package(fd)
        fd_local_imports = file_local_imports(fd)
        for class_data in fd.get("classes", []) + fd.get("interfaces", []) + fd.get("objects", []):
            indexed_class = {**class_data, "path": fd["path"], "package": package_name}
            for class_name in type_keys_for_maps(
                class_data.get("name"),
                package_name=package_name,
            ):
                class_index.setdefault((file_path, class_name), []).append(indexed_class)
            class_keys = type_keys_for_maps(class_data.get("name"), package_name=package_name)
            if not class_keys:
                continue
            base_types = [
                canonical_type_for_maps(base_name, fd_local_imports, package_name)
                for base_name in class_data.get("bases", [])
                if canonical_type_for_maps(base_name, fd_local_imports, package_name)
            ]
            for class_name in class_keys:
                global_class_bases[class_name] = base_types
        for func in fd.get("functions", []):
            indexed_func = {**func, "path": fd["path"], "package": package_name}
            function_index.setdefault((file_path, func["name"]), []).append(indexed_func)
            
            # Index class methods for all languages
            context_names = function_context_names_for_maps(fd, func, package_name)
            for context_name in context_names:
                class_method_names.setdefault(context_name, set()).add(func["name"])
                class_method_index.setdefault((context_name, func["name"]), []).append(
                    indexed_func
                )
            
            # Extension methods (mostly Kotlin/C#)
            receiver_types = type_keys_for_maps(
                func.get("receiver_type"),
                fd_local_imports,
                package_name,
            )
            for receiver_type in receiver_types:
                extension_method_index.setdefault((receiver_type, func["name"]), []).append(
                    indexed_func
                )

        for variable in fd.get("variables", []):
            if variable.get("context"):
                continue
            variable_name = variable.get("name")
            variable_type = canonical_type_for_maps(
                variable.get("type") or variable.get("initializer_inferred_type"),
                fd_local_imports,
                package_name,
            )
            if not variable_name or not variable_type:
                continue
            global_variable_types[variable_name] = variable_type
            if package_name:
                global_variable_types[f"{package_name}.{variable_name}"] = variable_type

    # Single-pass check replacing 4 separate O(n) any() scans.
    needs_member_receiver_types = False
    if has_kotlin:
        for fd in all_file_data:
            is_kotlin = fd.get("lang") == "kotlin"
            for call in fd.get("function_calls", []):
                if (call.get("receiver_base_type") and call.get("receiver_member_name")) or \
                   (is_kotlin and call.get("base_obj")):
                    needs_member_receiver_types = True
                    break
            if needs_member_receiver_types:
                break
            for variable in fd.get("variables", []):
                if (variable.get("initializer_receiver_name") and variable.get("initializer_member_name")) or \
                   (variable.get("initializer_collection_receiver_name") and variable.get("initializer_collection_member_name")):
                    needs_member_receiver_types = True
                    break
            if needs_member_receiver_types:
                break
    if needs_member_receiver_types:
        for fd in all_file_data:
            package_name = file_package(fd)
            fd_local_imports = file_local_imports(fd)
            for func in fd.get("functions", []):
                return_type = func.get("return_type")
                if return_type:
                    return_type_key = canonical_type_for_maps(
                        return_type,
                        fd_local_imports,
                        package_name,
                    )
                    full_return_type = normalize_full_type(
                        func.get("return_type_full") or return_type
                    )
                    for context_name in function_context_names_for_maps(fd, func, package_name):
                        key = (context_name, func["name"])
                        member_return_types[key] = return_type_key
                        if full_return_type:
                            member_return_types_full[key] = full_return_type
            for variable in fd.get("variables", []):
                variable_type = variable.get("type")
                if variable_type:
                    property_type_key = canonical_type_for_maps(
                        variable_type,
                        fd_local_imports,
                        package_name,
                    )
                    for context_name in type_keys_for_maps(
                        variable.get("context"),
                        package_name=package_name,
                    ):
                        member_property_types[(context_name, variable["name"])] = property_type_key

    info_logger(f"[CALLS] Resolving function calls across {len(all_file_data)} files...")
    resolved_calls: List[Dict] = []

    # Pre-build per-language-extension filtered imports_map views.
    _lang_imports_cache: Dict[str, dict] = {}

    def _get_lang_imports(caller_lang: str) -> dict:
        if caller_lang not in _lang_imports_cache:
            _LANG_EXTS: Dict[str, set] = {
                "java":       {".java"},
                "python":     {".py", ".ipynb"},
                "javascript": {".js", ".jsx", ".mjs", ".cjs"},
                "typescript": {".ts", ".tsx"},
                "go":         {".go"},
                "rust":       {".rs"},
                "cpp":        {".cpp", ".h", ".hpp", ".hh"},
                "c":          {".c", ".h"},
                "c_sharp":    {".cs"},
                # Kotlin/JVM projects routinely call Java classes directly; keep
                # Java targets so explicit Java imports can disambiguate receivers.
                "kotlin":     {".kt", ".java"},
                "scala":      {".scala", ".sc"},
                "ruby":       {".rb"},
                "swift":      {".swift"},
                "php":        {".php"},
                "dart":       {".dart"},
                "perl":       {".pl", ".pm"},
                "lua":        {".lua"},
                "haskell":    {".hs"},
                "elixir":     {".ex", ".exs"},
            }
            exts = _LANG_EXTS.get(caller_lang)
            if not exts:
                _lang_imports_cache[caller_lang] = imports_map
            else:
                filtered: dict = {}
                for name, paths in imports_map.items():
                    same_lang = [p for p in paths if Path(p).suffix in exts]
                    if same_lang:
                        filtered[name] = same_lang
                    elif paths:
                        if not any(Path(p).suffix for p in paths):
                            filtered[name] = paths
                _lang_imports_cache[caller_lang] = filtered
        return _lang_imports_cache[caller_lang]

    for idx, file_data in enumerate(all_file_data):
        caller_file_path = str(Path(file_data["path"]).resolve())
        func_names = {f["name"] for f in file_data.get("functions", [])}
        class_names = {c["name"] for c in file_data.get("classes", [])}
        # Pre-sort functions by line range for O(log n) scope lookup via bisect.
        _file_functions_sorted = sorted(
            [f for f in file_data.get("functions", []) if f.get("line_number") is not None and f.get("end_line") is not None],
            key=lambda f: f["line_number"],
        )
        _fn_starts = [f["line_number"] for f in _file_functions_sorted]
        _fn_ends   = [f["end_line"]   for f in _file_functions_sorted]
        # Include other potential callers (methods in traits, interfaces, etc.)
        for label in ["interfaces", "traits", "structs", "records", "unions"]:
            class_names.update({i["name"] for i in file_data.get(label, [])})
            
        local_names = func_names | class_names
        local_class_bases = {
            c["name"]: c.get("bases", []) for c in file_data.get("classes", [])
        }
        local_imports = {
            imp.get("alias") or imp["name"].split(".")[-1]: imp["name"]
            for imp in file_data.get("imports", [])
            if not imp["name"].endswith(".*")
        }
        wildcard_imports = [
            imp["name"][:-2]
            for imp in file_data.get("imports", [])
            if imp["name"].endswith(".*")
        ]
        if wildcard_imports:
            local_imports["__wildcards__"] = wildcard_imports

        caller_lang = file_data.get("lang", "")
        effective_imports_map = _get_lang_imports(caller_lang) if caller_lang else imports_map
        caller_package = file_package(file_data)

        local_variable_types: Dict[Tuple[str, Any], str] = {}
        local_variable_full_types: Dict[Tuple[str, Any], str] = {}
        local_variable_declarations: Dict[Tuple[str, Any], List[Dict[str, Any]]] = {}

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
            # Use bisect on pre-sorted intervals instead of linear scan.
            import bisect
            idx_r = bisect.bisect_right(_fn_starts, line_number)
            for i in range(idx_r - 1, -1, -1):
                fn = _file_functions_sorted[i]
                if fn["line_number"] > line_number:
                    continue
                if fn["end_line"] < line_number:
                    break
                if fn.get("name") == context_name:
                    return function_scope(fn)
            return context_name

        def variable_scope(variable: Dict[str, Any]) -> Any:
            return function_scope_for_line(
                variable.get("context"),
                variable.get("line_number"),
            )

        def call_scope(call: Dict[str, Any]) -> Any:
            context = call.get("context")
            if not context or len(context) != 3:
                return None
            return function_scope_for_line(context[0], context[2])

        def local_type_values(type_name: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
            if not type_name or type_name == "Unknown":
                return None, None
            canonical = canonical_type_for_maps(type_name, local_imports, caller_package)
            if not canonical:
                return None, None
            return canonical, normalize_full_type(type_name)

        def record_local_variable_declaration(
            name: Optional[str],
            context: Any,
            line_number: Optional[int],
            type_name: Optional[str],
        ) -> None:
            if not name:
                return

            canonical, full_type = local_type_values(type_name)
            key = (name, context)
            records = local_variable_declarations.setdefault(key, [])
            for record in records:
                if record.get("line_number") == line_number:
                    if canonical:
                        record["type"] = canonical
                    existing_full_type = record.get("full_type")
                    if full_type and (
                        not existing_full_type
                        or ("<" in full_type and "<" not in existing_full_type)
                    ):
                        record["full_type"] = full_type
                    return
            records.append({
                "line_number": line_number,
                "type": canonical,
                "full_type": full_type,
            })

        def add_local_variable_type(
            name: Optional[str],
            context: Any,
            type_name: Optional[str],
            line_number: Optional[int] = None,
        ) -> bool:
            if not name or not type_name or type_name == "Unknown":
                return False
            canonical, full_type = local_type_values(type_name)
            if not canonical:
                return False
            key = (name, context)
            if local_variable_types.get(key) == canonical:
                return False
            local_variable_types[key] = canonical
            if full_type:
                local_variable_full_types[key] = full_type
            if line_number is not None:
                record_local_variable_declaration(name, context, line_number, type_name)
            return True

        pending_variable_member_hints = []
        pending_variable_candidate_hints = []
        pending_variable_collection_hints = []
        for import_alias, import_name in local_imports.items():
            if import_alias == "__wildcards__":
                continue
            imported_variable_type = global_variable_types.get(import_name)
            if imported_variable_type:
                add_local_variable_type(import_alias, None, imported_variable_type)

        for variable in file_data.get("variables", []):
            scope = variable_scope(variable)
            variable_line = variable.get("line_number")
            record_local_variable_declaration(
                variable.get("name"),
                scope,
                variable_line,
                variable.get("type"),
            )
            add_local_variable_type(
                variable.get("name"),
                scope,
                variable.get("type"),
                variable_line,
            )
            add_local_variable_type(
                variable.get("name"),
                scope,
                variable.get("initializer_inferred_type"),
                variable_line,
            )
            if variable.get("initializer_receiver_name") and variable.get("initializer_member_name"):
                pending_variable_member_hints.append(variable)
            if variable.get("initializer_candidate_names"):
                pending_variable_candidate_hints.append(variable)
            if variable.get("initializer_collection_receiver_name") and variable.get("initializer_collection_member_name"):
                pending_variable_collection_hints.append(variable)

        for function in file_data.get("functions", []):
            scope = function_scope(function)
            for arg_name, arg_type in zip(
                function.get("args", []),
                function.get("arg_types", []),
            ):
                record_local_variable_declaration(
                    arg_name,
                    scope,
                    function.get("line_number"),
                    arg_type,
                )
                add_local_variable_type(arg_name, scope, arg_type, function.get("line_number"))

        def lookup_scoped_declaration_value(
            name: Optional[str],
            context: Any,
            line_number: Optional[int],
            *,
            full: bool = False,
        ) -> Tuple[bool, Optional[str]]:
            if not name or not isinstance(context, tuple) or line_number is None:
                return False, None

            candidates = [
                record
                for record in local_variable_declarations.get((name, context), [])
                if record.get("line_number") is not None
                and record["line_number"] <= line_number
            ]
            if not candidates:
                return False, None

            record = max(candidates, key=lambda item: item.get("line_number") or 0)
            if full:
                return True, record.get("full_type") or record.get("type")
            return True, record.get("type")

        def lookup_declared_variable_type(
            name: Optional[str],
            context: Any,
            line_number: Optional[int],
        ) -> Optional[str]:
            found, value = lookup_scoped_declaration_value(name, context, line_number)
            if found:
                return value
            return local_variable_types.get((name, context))

        def unique_local_value(
            mapping: Dict[Tuple[str, Any], str],
            name: str,
            context: Any = None,
            line_number: Optional[int] = None,
            *,
            full: bool = False,
        ) -> Optional[str]:
            values = set()
            for (variable_name, scope), value in mapping.items():
                if variable_name != name or not value:
                    continue
                if isinstance(context, tuple) and scope == context and line_number is not None:
                    found, scoped_value = lookup_scoped_declaration_value(
                        name,
                        context,
                        line_number,
                        full=full,
                    )
                    if found and scoped_value:
                        values.add(scoped_value)
                    continue
                values.add(value)
            return next(iter(values)) if len(values) == 1 else None

        def inherited_member_property_type(
            class_context: Optional[str],
            property_name: str,
        ) -> Optional[str]:
            if not class_context:
                return None

            queue = [
                canonical_type_for_maps(class_context, local_imports, caller_package),
                simple_type_key(class_context),
            ]
            visited = set()
            while queue:
                current = queue.pop(0)
                if not current or current in visited:
                    continue
                visited.add(current)

                property_type = member_property_types.get((current, property_name))
                if property_type:
                    return property_type

                simple_current = simple_type_key(current)
                if simple_current and simple_current != current:
                    property_type = member_property_types.get((simple_current, property_name))
                    if property_type:
                        return property_type

                bases = []
                bases.extend(local_class_bases.get(simple_current or current, []))
                bases.extend(global_class_bases.get(current, []))
                if simple_current:
                    bases.extend(global_class_bases.get(simple_current, []))
                for base_name in bases:
                    canonical_base = canonical_type_for_maps(
                        base_name,
                        local_imports,
                        caller_package,
                    ) or base_name
                    if canonical_base and canonical_base not in visited:
                        queue.append(canonical_base)
                    simple_base = simple_type_key(base_name)
                    if simple_base and simple_base not in visited:
                        queue.append(simple_base)
            return None

        def lookup_local_variable_type(
            name: Optional[str],
            context: Any,
            line_number: Optional[int] = None,
        ) -> Optional[str]:
            if not name:
                return None
            found, scoped_type = lookup_scoped_declaration_value(
                name,
                context,
                line_number,
            )
            if found:
                return scoped_type
            if not (isinstance(context, tuple) and line_number is not None):
                inferred_type = local_variable_types.get((name, context))
                if inferred_type:
                    return inferred_type
            class_context = context[2] if isinstance(context, tuple) and len(context) >= 3 else None
            inferred_type = local_variable_types.get((name, class_context))
            if inferred_type:
                return inferred_type
            inferred_type = inherited_member_property_type(class_context, name)
            if inferred_type:
                return inferred_type
            inferred_type = local_variable_types.get((name, None))
            if inferred_type:
                return inferred_type
            return unique_local_value(local_variable_types, name, context, line_number)

        def lookup_local_variable_full_type(
            name: Optional[str],
            context: Any,
            line_number: Optional[int] = None,
        ) -> Optional[str]:
            if not name:
                return None
            found, scoped_type = lookup_scoped_declaration_value(
                name,
                context,
                line_number,
                full=True,
            )
            if found:
                return scoped_type
            if not (isinstance(context, tuple) and line_number is not None):
                inferred_type = local_variable_full_types.get((name, context))
                if inferred_type:
                    return inferred_type
            class_context = context[2] if isinstance(context, tuple) and len(context) >= 3 else None
            inferred_type = local_variable_full_types.get((name, class_context))
            if inferred_type:
                return inferred_type
            inferred_type = local_variable_full_types.get((name, None))
            if inferred_type:
                return inferred_type
            inferred_type = unique_local_value(
                local_variable_full_types,
                name,
                context,
                line_number,
                full=True,
            )
            if inferred_type:
                return inferred_type
            inferred_type = lookup_local_variable_type(name, context, line_number)
            return inferred_type

        def lookup_local_expression_type(
            expr: str,
            context: Any,
            line_number: Optional[int] = None,
        ) -> Optional[str]:
            text = expr.strip()
            if re.fullmatch(r"[A-Za-z_]\w*", text):
                return lookup_local_variable_type(text, context, line_number)
            if re.search(r'\.keys\.asSequence\s*\(\s*\)$', text):
                return "Sequence"
            if re.search(r'\.keys\b$', text):
                return "Set"
            if re.search(r'\.values\b$', text):
                return "Collection"

            receiver_match = re.match(r"([A-Za-z_]\w*)\.(map|filter|flatMap|take|drop)\b", text)
            if receiver_match:
                receiver_type = lookup_local_variable_type(
                    receiver_match.group(1),
                    context,
                    line_number,
                )
                receiver_type = canonical_type_for_maps(
                    receiver_type,
                    local_imports,
                    caller_package,
                )
                if receiver_type == "Sequence":
                    return "Sequence"
                if receiver_type:
                    return "List"
            return None

        def class_like_initializer_receiver_type(receiver_name: Optional[str]) -> Optional[str]:
            if not receiver_name:
                return None
            text = receiver_name.strip()
            simple_name = text.rsplit(".", 1)[-1]
            if not re.match(r"[A-Z_]", simple_name):
                return None
            return canonical_type_for_maps(text, local_imports, caller_package)

        max_inference_iterations = (
            len(pending_variable_member_hints)
            + len(pending_variable_candidate_hints)
            + len(pending_variable_collection_hints)
        )
        for _ in range(max_inference_iterations):
            changed = False
            for variable in pending_variable_collection_hints:
                scope = variable_scope(variable)
                variable_line = variable.get("line_number")
                initializer_lookup_line = variable_line - 1 if isinstance(variable_line, int) else None
                if lookup_declared_variable_type(variable.get("name"), scope, variable_line):
                    continue

                receiver_type = lookup_local_variable_type(
                    variable.get("initializer_collection_receiver_name"),
                    scope,
                    initializer_lookup_line,
                )
                if not receiver_type:
                    receiver_type = class_like_initializer_receiver_type(
                        variable.get("initializer_collection_receiver_name")
                    )
                receiver_type = canonical_type_for_maps(
                    receiver_type,
                    local_imports,
                    caller_package,
                )
                if not receiver_type:
                    continue

                member_name = variable.get("initializer_collection_member_name")
                operator = variable.get("initializer_collection_operator")
                full_return_type = member_return_types_full.get((receiver_type, member_name))
                inferred_collection_type = collection_type_from_operator(
                    full_return_type,
                    operator,
                )
                changed = add_local_variable_type(
                    variable.get("name"),
                    scope,
                    inferred_collection_type,
                    variable_line,
                ) or changed

            for variable in pending_variable_member_hints:
                scope = variable_scope(variable)
                variable_line = variable.get("line_number")
                initializer_lookup_line = variable_line - 1 if isinstance(variable_line, int) else None
                if lookup_declared_variable_type(variable.get("name"), scope, variable_line):
                    continue

                receiver_type = lookup_local_variable_type(
                    variable.get("initializer_receiver_name"),
                    scope,
                    initializer_lookup_line,
                )
                if not receiver_type:
                    receiver_type = class_like_initializer_receiver_type(
                        variable.get("initializer_receiver_name")
                    )
                receiver_type = canonical_type_for_maps(
                    receiver_type,
                    local_imports,
                    caller_package,
                )
                if not receiver_type:
                    continue

                member_name = variable.get("initializer_member_name")
                member_kind = variable.get("initializer_member_kind")
                inferred_full_type = None
                if member_kind == "function":
                    inferred_type = member_return_types.get((receiver_type, member_name))
                    inferred_full_type = member_return_types_full.get((receiver_type, member_name))
                elif member_kind == "property":
                    inferred_type = member_property_types.get((receiver_type, member_name))
                else:
                    inferred_type = None

                changed = add_local_variable_type(
                    variable.get("name"),
                    scope,
                    inferred_full_type or inferred_type,
                    variable_line,
                ) or changed

            for variable in pending_variable_candidate_hints:
                scope = variable_scope(variable)
                variable_line = variable.get("line_number")
                initializer_lookup_line = variable_line - 1 if isinstance(variable_line, int) else None
                if lookup_declared_variable_type(variable.get("name"), scope, variable_line):
                    continue

                candidate_types = []
                for candidate_name in variable.get("initializer_candidate_names", []):
                    candidate_type = lookup_local_variable_type(
                        candidate_name,
                        scope,
                        initializer_lookup_line,
                    )
                    candidate_type = canonical_type_for_maps(
                        candidate_type,
                        local_imports,
                        caller_package,
                    )
                    if not candidate_type:
                        candidate_types = []
                        break
                    candidate_types.append(candidate_type)

                if candidate_types and len(set(candidate_types)) == 1:
                    changed = add_local_variable_type(
                        variable.get("name"),
                        scope,
                        candidate_types[0],
                        variable_line,
                    ) or changed
            if not changed:
                break

        for call in file_data.get("function_calls", []):
            call_to_resolve = (
                {**call, "package": caller_package}
                if caller_package and not call.get("package")
                else call
            )
            context = call.get("context")
            context_name = context[0] if context and len(context) == 3 else None
            current_call_scope = call_scope(call)
            call_line = call.get("line_number")
            if caller_lang == "kotlin":
                base_obj = call.get("base_obj")
                if not base_obj:
                    full_name = call.get("full_name", "")
                    base_obj = full_name.split(".", 1)[0] if "." in full_name else None

                if base_obj and re.fullmatch(r"[A-Za-z_]\w*", base_obj):
                    inferred_type = lookup_local_variable_type(
                        base_obj,
                        current_call_scope,
                        call_line,
                    )
                    if not inferred_type and call.get("implicit_receiver_type"):
                        implicit_receiver_type = canonical_type_for_maps(
                            call.get("implicit_receiver_type"),
                            local_imports,
                            caller_package,
                        )
                        inferred_type = member_property_types.get(
                            (implicit_receiver_type, base_obj)
                        )
                    if inferred_type:
                        existing_extension_receiver = call.get("extension_receiver_type")
                        call_to_resolve = {
                            **call,
                            "inferred_obj_type": inferred_type,
                            "extension_receiver_type": (
                                inferred_type
                                if not existing_extension_receiver
                                or existing_extension_receiver == base_obj
                                else existing_extension_receiver
                            ),
                        }

            call_args = call_to_resolve.get("args", [])
            if caller_lang == "kotlin" and isinstance(call_args, list):
                arg_type_hints = [
                    (
                        canonical_type_for_maps(
                            call_to_resolve.get("scope_receiver_type"),
                            local_imports,
                            caller_package,
                        )
                        if arg.strip() == "this" and call_to_resolve.get("scope_receiver_type")
                        else lookup_local_expression_type(arg.strip(), current_call_scope, call_line)
                    )
                    for arg in call_args
                ]
                if any(arg_type_hints):
                    call_to_resolve = {
                        **call_to_resolve,
                        "arg_type_hints": arg_type_hints,
                    }

            if (
                caller_lang == "kotlin"
                and call_to_resolve.get("call_kind") == "callable_reference"
                and not call_to_resolve.get("arg_type_hints")
                and call_to_resolve.get("callable_reference_collection_receiver")
            ):
                collection_receiver = call_to_resolve.get("callable_reference_collection_receiver")
                collection_type = None
                if isinstance(collection_receiver, str):
                    if re.fullmatch(r"[A-Za-z_]\w*", collection_receiver.strip()):
                        collection_type = lookup_local_variable_full_type(
                            collection_receiver.strip(),
                            current_call_scope,
                            call_line,
                        )
                    else:
                        simple_collection_type = lookup_local_expression_type(
                            collection_receiver.strip(),
                            current_call_scope,
                            call_line,
                        )
                        collection_type = simple_collection_type
                element_type = collection_element_type(
                    collection_type,
                    local_imports,
                    caller_package,
                )
                if element_type:
                    call_to_resolve = {
                        **call_to_resolve,
                        "arg_type_hints": [element_type],
                    }

            resolved = resolve_function_call(
                call_to_resolve,
                caller_file_path,
                local_names,
                local_imports,
                effective_imports_map,
                skip_external,
                local_class_bases=local_class_bases,
                member_return_types=member_return_types,
                member_property_types=member_property_types,
                type_aliases=type_aliases,
                global_class_bases=global_class_bases,
                class_method_names=class_method_names,
                function_index=function_index,
                class_index=class_index,
                class_method_index=class_method_index,
                extension_method_index=extension_method_index,
                diagnostics=diagnostics,
            )
            if not resolved:
                continue

            # Annotate C++ calls with concrete Neo4j labels so the writer can use
            # label-specific MATCH queries instead of the slow label-OR scan.
            # Non-C++ languages (Java, Python, etc.) are intentionally excluded —
            # they work correctly with the existing generic query and have no
            # performance issue there.
            _CPP_EXTS = ('.cpp', '.cc', '.cxx', '.c++', '.C', '.h', '.hpp', '.hxx', '.h++')
            if resolved["type"] == "function":
                caller_fp_raw = resolved["caller_file_path"]
                if caller_fp_raw.endswith(_CPP_EXTS):
                    caller_fp = str(Path(caller_fp_raw).resolve())
                    caller_name = resolved["caller_name"]
                    resolved["caller_label"] = file_symbol_labels.get(caller_fp, {}).get(caller_name, "Function")
            called_fp_raw = resolved.get("called_file_path") or ""
            if called_fp_raw.endswith(_CPP_EXTS):
                called_fp = str(Path(called_fp_raw).resolve())
                called_name = resolved["called_name"]
                resolved["called_label"] = file_symbol_labels.get(called_fp, {}).get(called_name, "Function")

            resolved_calls.append(resolved)

        # Resolve Python decorators as virtual calls
        if caller_lang == "python":
            for func in file_data.get("functions", []):
                for dec_raw in func.get("decorators", []):
                    # dec_raw is e.g. "@my_decorator" or "@my_decorator(arg)"
                    dec_name = dec_raw.lstrip("@").split("(")[0].strip()
                    if not dec_name:
                        continue
                    
                    virtual_call = {
                        "name": dec_name,
                        "line_number": func["line_number"],
                        "context": (func["name"], "function_definition", func["line_number"]),
                        "class_context": func.get("class_context"),
                        "full_name": dec_name,
                        "args": [],
                        "call_kind": "decorator",
                    }
                    
                    resolved_dec = resolve_function_call(
                        virtual_call,
                        caller_file_path,
                        local_names,
                        local_imports,
                        effective_imports_map,
                        skip_external,
                        local_class_bases=local_class_bases,
                        member_return_types=member_return_types,
                        member_property_types=member_property_types,
                        type_aliases=type_aliases,
                        global_class_bases=global_class_bases,
                        class_method_names=class_method_names,
                        function_index=function_index,
                        class_index=class_index,
                        class_method_index=class_method_index,
                        extension_method_index=extension_method_index,
                        diagnostics=diagnostics,
                    )
                    if resolved_dec:
                        resolved_calls.append(resolved_dec)


        if (idx + 1) % 1000 == 0:
            info_logger(f"[CALLS] Resolved {idx + 1}/{len(all_file_data)} files... ({len(resolved_calls)} calls)")

    info_logger(f"[CALLS] Resolution complete: {len(resolved_calls)} total CALLS edges identified.")

    fn_to_fn: List[Dict[str, Any]] = []
    fn_to_class: List[Dict[str, Any]] = []
    fn_to_interface: List[Dict[str, Any]] = []
    fn_to_object: List[Dict[str, Any]] = []
    file_to_fn: List[Dict[str, Any]] = []
    file_to_class: List[Dict[str, Any]] = []
    file_to_interface: List[Dict[str, Any]] = []
    file_to_object: List[Dict[str, Any]] = []

    for edge in resolved_calls:
        called_path = str(Path(edge.get("called_file_path", "")).resolve())
        called_name = edge.get("called_name")
        target_label = file_symbol_labels.get(called_path, {}).get(called_name)

        if edge.get("type") == "file":
            if target_label == "Interface":
                file_to_interface.append(edge)
            elif target_label == "Object":
                file_to_object.append(edge)
            elif target_label == "Class":
                file_to_class.append(edge)
            else:
                file_to_fn.append(edge)
        else:
            if target_label == "Interface":
                fn_to_interface.append(edge)
            elif target_label == "Object":
                fn_to_object.append(edge)
            elif target_label == "Class":
                fn_to_class.append(edge)
            else:
                fn_to_fn.append(edge)

    return (
        fn_to_fn, fn_to_class, fn_to_interface, fn_to_object,
        file_to_fn, file_to_class, file_to_interface, file_to_object
    )
