"""Heuristic resolution of function calls into CALLS edge payloads (no DB I/O)."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ....cli.config_manager import get_config_value
from ....utils.debug_log import info_logger


def resolve_function_call(
    call: Dict[str, Any],
    caller_file_path: str,
    local_names: set,
    local_imports: dict,
    imports_map: dict,
    skip_external: bool,
) -> Optional[Dict[str, Any]]:
    """Resolve a single function call to its target. Returns call params dict or None if skipped."""
    called_name = call["name"]
    if called_name in __builtins__:
        return None

    resolved_called_name = called_name
    resolved_path = None
    full_call = call.get("full_name", called_name)
    base_obj = full_call.split(".")[0] if "." in full_call else None

    is_chained_call = full_call.count(".") > 1 if "." in full_call else False

    if is_chained_call and base_obj in ("self", "this", "super", "super()", "cls", "@"):
        lookup_name = called_name
    else:
        lookup_name = base_obj if base_obj else called_name

    if base_obj in ("self", "this", "super", "super()", "cls", "@") and not is_chained_call:
        resolved_path = caller_file_path
    elif lookup_name in local_names:
        resolved_path = caller_file_path
    elif call.get("inferred_obj_type"):
        obj_type = call["inferred_obj_type"]
        possible_paths = imports_map.get(obj_type, [])
        if len(possible_paths) > 0:
            resolved_path = possible_paths[0]

    if not resolved_path:
        possible_paths = imports_map.get(lookup_name, [])
        if not possible_paths and lookup_name in local_imports:
            imported_name = local_imports[lookup_name]
            alias_paths = imports_map.get(imported_name, [])
            if alias_paths:
                possible_paths = alias_paths
                lookup_name = imported_name
                if called_name == base_obj or called_name == call["name"]:
                    resolved_called_name = imported_name
        if len(possible_paths) == 1:
            resolved_path = possible_paths[0]
        elif len(possible_paths) > 1:
            if lookup_name in local_imports:
                full_import_name = local_imports[lookup_name]
                if full_import_name in imports_map:
                    direct_paths = imports_map[full_import_name]
                    if direct_paths and len(direct_paths) == 1:
                        resolved_path = direct_paths[0]
                if not resolved_path:
                    for path in possible_paths:
                        if full_import_name.replace(".", "/") in path:
                            resolved_path = path
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
        elif resolved_called_name in imports_map and imports_map[resolved_called_name]:
            candidates = imports_map[resolved_called_name]
            for path in candidates:
                for imp_name in local_imports.values():
                    if imp_name.replace(".", "/") in path:
                        resolved_path = path
                        is_unresolved_external = False
                        break
                if resolved_path:
                    break
            if not resolved_path:
                resolved_path = candidates[0]
        else:
            resolved_path = caller_file_path

    if skip_external and is_unresolved_external:
        return None

    caller_context = call.get("context")
    if caller_context and len(caller_context) == 3 and caller_context[0] is not None:
        caller_name, _, caller_line_number = caller_context
        return {
            "type": "function",
            "caller_name": caller_name,
            "caller_file_path": caller_file_path,
            "caller_line_number": caller_line_number,
            "called_name": resolved_called_name,
            "called_file_path": resolved_path,
            "line_number": call["line_number"],
            "args": call.get("args", []),
            "full_call_name": call.get("full_name", called_name),
        }
    return {
        "type": "file",
        "caller_file_path": caller_file_path,
        "called_name": resolved_called_name,
        "called_file_path": resolved_path,
        "line_number": call["line_number"],
        "args": call.get("args", []),
        "full_call_name": call.get("full_name", called_name),
    }


def build_function_call_groups(
    all_file_data: List[Dict[str, Any]],
    imports_map: dict,
    file_class_lookup: Optional[Dict[str, set]] = None,
) -> Tuple[
    List[Dict],
    List[Dict],
    List[Dict],
    List[Dict],
    List[Dict],
    List[Dict],
]:
    """Phase 1 of CALLS linking: resolve and bucket by (caller_label, called_label) pair."""
    skip_external = (get_config_value("SKIP_EXTERNAL_RESOLUTION") or "false").lower() == "true"

    if file_class_lookup is None:
        file_class_lookup = {}
    for fd in all_file_data:
        fp = str(Path(fd["path"]).resolve())
        file_class_lookup[fp] = {c["name"] for c in fd.get("classes", [])}

    info_logger(f"[CALLS] Resolving function calls across {len(all_file_data)} files...")
    fn_to_fn: List[Dict] = []
    fn_to_cls: List[Dict] = []
    cls_to_fn: List[Dict] = []
    cls_to_cls: List[Dict] = []
    file_to_fn: List[Dict] = []
    file_to_cls: List[Dict] = []

    # Pre-build per-language-extension filtered imports_map views.
    # When a caller is Java, we only want to resolve against Java files —
    # this prevents false-positive CALLS edges from names that coincidentally
    # exist in another language's file (e.g. Java `add()` -> JS `add`).
    _lang_imports_cache: Dict[str, dict] = {}

    def _get_lang_imports(caller_lang: str) -> dict:
        if caller_lang not in _lang_imports_cache:
            # Map language name to typical file extensions
            _LANG_EXTS: Dict[str, set] = {
                "java":       {".java"},
                "python":     {".py", ".ipynb"},
                "javascript": {".js", ".jsx", ".mjs", ".cjs"},
                "typescript": {".ts", ".tsx"},
                "go":         {".go"},
                "rust":       {".rs"},
                "cpp":        {".cpp", ".h", ".hpp", ".hh"},
                "c":          {".c"},
                "c_sharp":    {".cs"},
                "kotlin":     {".kt"},
                "scala":      {".scala", ".sc"},
                "ruby":       {".rb"},
                "swift":      {".swift"},
                "php":        {".php"},
                "dart":       {".dart"},
                "perl":       {".pl", ".pm"},
                "haskell":    {".hs"},
                "elixir":     {".ex", ".exs"},
            }
            exts = _LANG_EXTS.get(caller_lang)
            if not exts:
                # Unknown language — use full imports_map unchanged
                _lang_imports_cache[caller_lang] = imports_map
            else:
                filtered: dict = {}
                for name, paths in imports_map.items():
                    same_lang = [p for p in paths if Path(p).suffix in exts]
                    if same_lang:
                        filtered[name] = same_lang
                    elif paths:
                        # Keep non-file entries (e.g. package names with no extension)
                        if not any(Path(p).suffix for p in paths):
                            filtered[name] = paths
                _lang_imports_cache[caller_lang] = filtered
        return _lang_imports_cache[caller_lang]

    for idx, file_data in enumerate(all_file_data):
        caller_file_path = str(Path(file_data["path"]).resolve())
        func_names = {f["name"] for f in file_data.get("functions", [])}
        class_names = {c["name"] for c in file_data.get("classes", [])}
        local_names = func_names | class_names
        local_imports = {
            imp.get("alias") or imp["name"].split(".")[-1]: imp["name"]
            for imp in file_data.get("imports", [])
        }

        caller_lang = file_data.get("lang", "")
        effective_imports_map = _get_lang_imports(caller_lang) if caller_lang else imports_map

        for call in file_data.get("function_calls", []):
            resolved = resolve_function_call(
                call, caller_file_path, local_names, local_imports, effective_imports_map, skip_external
            )
            if not resolved:
                continue

            called_path = resolved.get("called_file_path", "")
            called_name = resolved["called_name"]
            called_is_class = called_name in file_class_lookup.get(called_path, set())

            if resolved["type"] == "file":
                if called_is_class:
                    file_to_cls.append(resolved)
                else:
                    file_to_fn.append(resolved)
            else:
                caller_name = resolved["caller_name"]
                caller_is_class = caller_name in class_names
                if caller_is_class:
                    (cls_to_cls if called_is_class else cls_to_fn).append(resolved)
                else:
                    (fn_to_cls if called_is_class else fn_to_fn).append(resolved)

        if (idx + 1) % 1000 == 0:
            total = len(fn_to_fn) + len(fn_to_cls) + len(cls_to_fn) + len(cls_to_cls)
            file_total = len(file_to_fn) + len(file_to_cls)
            info_logger(
                f"[CALLS] Resolved {idx + 1}/{len(all_file_data)} files... "
                f"({total} fn/cls calls, {file_total} file calls)"
            )

    total_all = (
        len(fn_to_fn)
        + len(fn_to_cls)
        + len(cls_to_fn)
        + len(cls_to_cls)
        + len(file_to_fn)
        + len(file_to_cls)
    )
    info_logger(
        f"[CALLS] Resolution complete: fn→fn={len(fn_to_fn)}, fn→cls={len(fn_to_cls)}, "
        f"cls→fn={len(cls_to_fn)}, cls→cls={len(cls_to_cls)}, "
        f"file→fn={len(file_to_fn)}, file→cls={len(file_to_cls)}. Total={total_all}"
    )
    return fn_to_fn, fn_to_cls, cls_to_fn, cls_to_cls, file_to_fn, file_to_cls
