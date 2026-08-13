# src/codegraphcontext/tools/indexing/resolution/inheritance.py
"""Resolve class inheritance into INHERITS row payloads (no DB I/O for non-C# batch)."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def resolve_inheritance_link(
    class_item: Dict[str, Any],
    base_class_str: str,
    caller_file_path: str,
    local_class_names: set,
    local_imports: dict,
    imports_map: dict,
) -> Optional[Dict[str, Any]]:
    """Resolve a single inheritance link. Returns row dict or None."""
    import re
    if base_class_str == "object":
        return None

    if not base_class_str:
        return None

    # Unwrap JS/TS mixins like Swimmable(Flyable(Person)) -> Person
    m = re.search(r'([A-Za-z0-9_.]+)(?:\s*\))*$', base_class_str)
    if m:
        base_class_str = m.group(1)

    resolved_path = None
    target_class_name = base_class_str.split(".")[-1]

    if "." in base_class_str:
        lookup_name = base_class_str.split(".")[0]
        if lookup_name in local_imports:
            full_import_name = local_imports[lookup_name]
            possible_paths = imports_map.get(target_class_name, [])
            for path in possible_paths:
                if full_import_name.replace(".", "/") in path:
                    resolved_path = path
                    break
    else:
        lookup_name = base_class_str
        if lookup_name in local_class_names:
            resolved_path = caller_file_path
        elif lookup_name in local_imports:
            full_import_name = local_imports[lookup_name]
            possible_paths = imports_map.get(target_class_name, [])
            for path in possible_paths:
                if full_import_name.replace(".", "/") in path:
                    resolved_path = path
                    break
        elif lookup_name in imports_map:
            possible_paths = imports_map[lookup_name]
            if len(possible_paths) == 1:
                resolved_path = possible_paths[0]

    if resolved_path:
        return {
            "child_name": class_item["name"],
            "path": caller_file_path,
            "parent_name": target_class_name,
            "resolved_parent_file_path": resolved_path,
            "confidence_label": "EXTRACTED",
        }
    return {
        "child_name": class_item["name"],
        "path": caller_file_path,
        "parent_name": target_class_name,
        "resolved_parent_file_path": "__external__",
        "confidence_label": "INFERRED",
    }



def build_inheritance_and_csharp_files(
    all_file_data: List[Dict[str, Any]], imports_map: dict
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Returns (inheritance_batch_rows, csharp_file_data_list)."""
    inheritance_batch: List[Dict[str, Any]] = []
    csharp_files: List[Dict[str, Any]] = []

    for file_data in all_file_data:
        if file_data.get("lang") == "c_sharp":
            csharp_files.append(file_data)
            continue

        caller_file_path = str(Path(file_data["path"]).resolve().as_posix())
        local_class_names = set()
        for key in ["classes", "structs", "traits", "interfaces", "mixins", "enums", "extensions", "variables"]:
            for item in file_data.get(key, []):
                local_class_names.add(item["name"])

        local_imports = {
            imp.get("alias") or (imp.get("name") or "").split(".")[-1]: imp.get("name")
            for imp in file_data.get("imports", [])
            if imp.get("name")
        }

        for key in ["classes", "structs", "traits", "interfaces", "mixins", "enums", "extensions", "variables"]:
            for class_item in file_data.get(key, []):
                if not class_item.get("bases"):
                    continue
                for base_class_str in class_item["bases"]:
                    resolved = resolve_inheritance_link(
                        class_item,
                        base_class_str,
                        caller_file_path,
                        local_class_names,
                        local_imports,
                        imports_map,
                    )
                    if resolved:
                        inheritance_batch.append(resolved)

    return inheritance_batch, csharp_files


def _expand_go_interface_methods(
    iface_name: str,
    interface_methods: Dict[str, set],
    embedded_bases: Dict[str, List[str]],
    cache: Dict[str, set],
) -> set:
    if iface_name in cache:
        return cache[iface_name]
    required = set(interface_methods.get(iface_name, set()))
    for base in embedded_bases.get(iface_name, []):
        required |= _expand_go_interface_methods(
            base, interface_methods, embedded_bases, cache
        )
    cache[iface_name] = required
    return required


def build_go_implements_links(
    all_file_data: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Infer Go struct->interface IMPLEMENTS edges from method sets."""
    implements_batch: List[Dict[str, Any]] = []

    for file_data in all_file_data:
        if file_data.get("lang") != "go":
            continue

        file_path = str(Path(file_data["path"]).resolve().as_posix())
        struct_methods: Dict[str, set] = {}
        for func in file_data.get("functions", []):
            receiver_type = func.get("receiver_type") or func.get("class_context")
            if not receiver_type:
                continue
            struct_methods.setdefault(receiver_type, set()).add(func["name"])

        interface_methods: Dict[str, set] = {}
        embedded_bases: Dict[str, List[str]] = {}
        for iface in file_data.get("interfaces", []):
            iface_name = iface.get("name")
            if not iface_name:
                continue
            methods = iface.get("methods") or []
            interface_methods[iface_name] = set(methods)
            embedded_bases[iface_name] = list(iface.get("bases") or [])

        expanded_required: Dict[str, set] = {}
        for iface_name in interface_methods:
            _expand_go_interface_methods(
                iface_name, interface_methods, embedded_bases, expanded_required
            )

        for struct in file_data.get("structs", []):
            struct_name = struct.get("name")
            if not struct_name:
                continue
            available = struct_methods.get(struct_name, set())
            for iface_name, required in expanded_required.items():
                if not required or not required.issubset(available):
                    continue
                implements_batch.append({
                    "child_name": struct_name,
                    "child_label": "Struct",
                    "parent_name": iface_name,
                    "parent_label": "Interface",
                    "path": file_path,
                    "resolved_parent_file_path": file_path,
                    "confidence_label": "INFERRED",
                })

    return implements_batch


def build_haskell_implements_links(
    all_file_data: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Create typeclass instance IMPLEMENTS edges (data type -> typeclass)."""
    implements_batch: List[Dict[str, Any]] = []

    for file_data in all_file_data:
        if file_data.get("lang") != "haskell":
            continue
        file_path = str(Path(file_data["path"]).resolve().as_posix())
        for instance in file_data.get("typeclass_instances", []):
            child_name = instance.get("implementing_type")
            parent_name = instance.get("typeclass")
            if not child_name or not parent_name:
                continue
            implements_batch.append({
                "child_name": child_name,
                "child_label": "Class",
                "parent_name": parent_name,
                "parent_label": "Class",
                "path": file_path,
                "resolved_parent_file_path": file_path,
                "confidence_label": "INFERRED",
            })

    return implements_batch


def build_partial_of_links(
    all_file_data: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Link C# partial class declarations across files."""
    partial_of_batch: List[Dict[str, Any]] = []
    groups: Dict[str, List[Dict[str, Any]]] = {}

    for file_data in all_file_data:
        if file_data.get("lang") not in ("csharp", "c_sharp"):
            continue
        file_path = str(Path(file_data["path"]).resolve().as_posix())
        namespace = file_data.get("namespace") or file_data.get("package") or ""
        for cls in file_data.get("classes", []):
            if not cls.get("is_partial"):
                continue
            key = f"{namespace}::{cls.get('name')}"
            groups.setdefault(key, []).append({
                "name": cls.get("name"),
                "path": file_path,
                "line_number": cls.get("line_number"),
            })

    for entries in groups.values():
        if len(entries) < 2:
            continue
        entries.sort(
            key=lambda row: (
                "_Part" in Path(row["path"]).name or "_part" in Path(row["path"]).name,
                row.get("line_number") or 0,
            )
        )
        primary = entries[0]
        for part in entries[1:]:
            partial_of_batch.append({
                "child_name": part["name"],
                "child_label": "Class",
                "parent_name": primary["name"],
                "parent_label": "Class",
                "path": part["path"],
                "resolved_parent_file_path": primary["path"],
                "confidence_label": "INFERRED",
            })

    return partial_of_batch


def build_part_of_links(
    all_file_data: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Link Dart library part files to their library root file."""
    part_of_batch: List[Dict[str, Any]] = []
    seen: set = set()

    part_of_re = re.compile(r"^\s*part\s+of\s+['\"]([^'\"]+)['\"]\s*;", re.MULTILINE)

    for file_data in all_file_data:
        if file_data.get("lang") != "dart":
            continue
        links = list(file_data.get("library_parts", []) or [])
        file_path = Path(file_data["path"])
        if not links and file_path.exists():
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                text = ""
            match = part_of_re.search(text)
            if match:
                links.append({
                    "main_file": str((file_path.parent / match.group(1)).resolve()),
                    "part_file": str(file_path.resolve()),
                    "direction": "part_of",
                })
        for link in links:
            if link.get("direction") != "part_of":
                continue
            child_path = str(Path(link["part_file"]).resolve())
            parent_path = str(Path(link["main_file"]).resolve())
            key = (child_path, parent_path)
            if key in seen:
                continue
            seen.add(key)
            part_of_batch.append({
                "child_path": child_path,
                "parent_path": parent_path,
            })

    return part_of_batch


def _parse_decorator_name(dec_raw: str) -> str:
    dec = dec_raw.strip()
    if dec.startswith("@"):
        dec = dec[1:]
    return dec.split("(")[0].strip()


def _resolve_decorator_path(
    decorator_name: str,
    caller_file_path: str,
    local_names: set,
    local_imports: dict,
    imports_map: dict,
) -> str:
    caller_path = str(Path(caller_file_path).resolve().as_posix())
    if decorator_name in local_names:
        return caller_path
    if decorator_name in local_imports:
        imported = local_imports[decorator_name]
        if not isinstance(imported, str) or not imported:
            return caller_path
        lookup = imported.split(".")[-1]
        paths = imports_map.get(lookup, imports_map.get(imported, []))
        if len(paths) == 1:
            return str(Path(paths[0]).resolve().as_posix())
    paths = imports_map.get(decorator_name, [])
    if len(paths) == 1:
        return str(Path(paths[0]).resolve().as_posix())
    return caller_path


def build_decorated_by_links(
    all_file_data: List[Dict[str, Any]],
    imports_map: dict,
) -> List[Dict[str, Any]]:
    """Build DECORATED_BY rows from parsed decorator metadata on functions/classes."""
    decorated_by_batch: List[Dict[str, Any]] = []
    seen: set = set()

    for file_data in all_file_data:
        caller_file_path = str(Path(file_data["path"]).resolve().as_posix())
        local_names = {
            item["name"]
            for key in ("functions", "classes")
            for item in file_data.get(key, [])
            if item.get("name")
        }
        # Parsed imports carry `name` / `full_import_name`; there is no `source`
        # key, so this mapped every imported symbol to None and made
        # _resolve_decorator_path bail out to the caller's own file before it
        # could consult imports_map. Mirrors the working construction in
        # build_inheritance_links above.
        local_imports = {
            imp.get("alias") or (imp.get("name") or "").split(".")[-1]: (
                imp.get("full_import_name") or imp.get("name")
            )
            for imp in file_data.get("imports", [])
            if imp.get("name") or imp.get("alias")
        }

        for entity_key, context_field in (("functions", "class_context"), ("classes", None)):
            for item in file_data.get(entity_key, []):
                decorators = item.get("decorators") or []
                if not decorators:
                    continue
                decorated_context = item.get(context_field) if context_field else None
                for dec_raw in decorators:
                    dec_name = _parse_decorator_name(dec_raw)
                    if not dec_name:
                        continue
                    dec_path = _resolve_decorator_path(
                        dec_name, caller_file_path, local_names, local_imports, imports_map
                    )
                    key = (
                        item["name"],
                        caller_file_path,
                        item["line_number"],
                        decorated_context or "",
                        dec_name,
                        dec_path,
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    decorated_by_batch.append({
                        "decorated_name": item["name"],
                        "decorated_path": caller_file_path,
                        "decorated_line": item["line_number"],
                        "decorated_context": decorated_context or "",
                        "decorator_name": dec_name,
                        "decorator_path": dec_path,
                        "line_number": item["line_number"],
                    })

    return decorated_by_batch


def build_metaclass_links(
    all_file_data: List[Dict[str, Any]],
    imports_map: dict,
) -> List[Dict[str, Any]]:
    """Build METACLASS rows from Python class metaclass= specifications."""
    metaclass_batch: List[Dict[str, Any]] = []
    seen: set = set()

    for file_data in all_file_data:
        if file_data.get("lang") != "python":
            continue
        caller_file_path = str(Path(file_data["path"]).resolve().as_posix())
        local_class_names = {c["name"] for c in file_data.get("classes", [])}
        # Parsed imports carry `name` / `full_import_name`; there is no `source`
        # key, so this mapped every imported symbol to None and made
        # _resolve_decorator_path bail out to the caller's own file before it
        # could consult imports_map. Mirrors the working construction in
        # build_inheritance_links above.
        local_imports = {
            imp.get("alias") or (imp.get("name") or "").split(".")[-1]: (
                imp.get("full_import_name") or imp.get("name")
            )
            for imp in file_data.get("imports", [])
            if imp.get("name") or imp.get("alias")
        }

        for class_item in file_data.get("classes", []):
            meta_name = class_item.get("metaclass")
            if not meta_name:
                continue
            resolved_path = _resolve_decorator_path(
                meta_name,
                caller_file_path,
                local_class_names,
                local_imports,
                imports_map,
            )
            key = (class_item["name"], caller_file_path, meta_name, resolved_path)
            if key in seen:
                continue
            seen.add(key)
            metaclass_batch.append({
                "child_name": class_item["name"],
                "path": caller_file_path,
                "parent_name": meta_name,
                "resolved_parent_file_path": resolved_path,
                "line_number": class_item["line_number"],
                "confidence_label": "EXTRACTED",
            })

    return metaclass_batch


def build_companion_of_links(
    all_file_data: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Link Kotlin companion objects to their enclosing class."""
    companion_batch: List[Dict[str, Any]] = []
    seen: set = set()

    for file_data in all_file_data:
        if file_data.get("lang") != "kotlin":
            continue
        file_path = str(Path(file_data["path"]).resolve().as_posix())
        classes_by_name = {
            cls["name"]: cls for cls in file_data.get("classes", []) if cls.get("name")
        }

        for obj in file_data.get("objects", []):
            if obj.get("node_type") != "companion_object":
                continue
            owner_name = obj.get("class_context")
            if not owner_name:
                continue
            owner = classes_by_name.get(owner_name)
            if not owner:
                continue
            key = (obj["name"], file_path, obj["line_number"], owner_name, owner["line_number"])
            if key in seen:
                continue
            seen.add(key)
            companion_batch.append({
                "companion_name": obj["name"],
                "companion_path": file_path,
                "companion_line": obj["line_number"],
                "owner_name": owner_name,
                "owner_path": file_path,
                "owner_line": owner["line_number"],
            })

    return companion_batch


def build_embeds_links(
    all_file_data: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Create Go struct embedding EMBEDS edges."""
    embeds_batch: List[Dict[str, Any]] = []
    seen: set = set()

    for file_data in all_file_data:
        if file_data.get("lang") != "go":
            continue
        file_path = str(Path(file_data["path"]).resolve().as_posix())
        struct_names = {s["name"] for s in file_data.get("structs", []) if s.get("name")}

        for struct in file_data.get("structs", []):
            struct_name = struct.get("name")
            if not struct_name:
                continue
            for base in struct.get("bases") or []:
                if not base:
                    continue
                base_name = base.split(".")[-1]
                if base_name not in struct_names:
                    continue
                key = (struct_name, file_path, base_name)
                if key in seen:
                    continue
                seen.add(key)
                embeds_batch.append({
                    "child_name": struct_name,
                    "parent_name": base_name,
                    "path": file_path,
                    "resolved_parent_file_path": file_path,
                    "line_number": struct.get("line_number", 0),
                })

    return embeds_batch


def _resolve_type_name(
    type_name: str,
    caller_file_path: str,
    local_names: set,
    local_imports: dict,
    imports_map: dict,
) -> Tuple[str, str]:
    """Resolve a bare Kotlin type name to a file path plus a confidence
    label, reusing _resolve_decorator_path's resolution order (local
    names -> local imports -> unique global import). Confidence is
    EXTRACTED when that resolution actually found something (either a
    same-file declaration or a real import target), INFERRED when it
    fell all the way back to guessing the caller's own file."""
    resolved_path = _resolve_decorator_path(
        type_name, caller_file_path, local_names, local_imports, imports_map
    )
    caller_path = str(Path(caller_file_path).resolve().as_posix())
    if type_name in local_names or resolved_path != caller_path:
        return resolved_path, "EXTRACTED"
    return resolved_path, "INFERRED"


def build_binds_links(
    all_file_data: List[Dict[str, Any]],
    imports_map: dict,
) -> List[Dict[str, Any]]:
    """Resolve Hilt @Binds/@Provides functions on @Module classes/objects
    into BINDS row payloads for write_binds_links.

    @Binds: source = the function's return_type, target = the single
    arg_types entry (the abstract method's one parameter). Both are
    known statically -- no need to consult function_calls.

    @Provides: source = the function's return_type, target = the type
    constructed in the function body. Kotlin has no `new` keyword, so a
    constructor call is indistinguishable at the syntax level from any
    other call -- function_calls records it with call_kind "call" like
    every other invocation. We locate candidate calls by matching a
    call's context (function name, "function_declaration", function
    line_number) and class_context (enclosing class/object name) back
    to the @Provides function, then require the call's name to resolve
    to a known type (local class/interface/object or an import) so an
    incidental non-constructor call in the body isn't mistaken for the
    binding target. If more than one call in the body resolves to a
    known type, the actually-returned one is ambiguous with the
    information available -- e.g. "val logger = LoggerImpl();
    return ThingImpl(logger)" wants the last call, while
    "return ThingImpl(LoggerImpl())" wants the first (textually) -- so
    no row is emitted rather than guessing. A wrong DI edge is worse
    for impact analysis than a missing one.
    """
    binds_batch: List[Dict[str, Any]] = []
    seen: set = set()

    for file_data in all_file_data:
        if file_data.get("lang") != "kotlin":
            continue

        caller_file_path = str(Path(file_data["path"]).resolve().as_posix())

        # Unlike build_decorated_by_links' local_names (functions/classes
        # only), Hilt bindings routinely name an *interface* as the
        # return_type/arg_types entry, so interfaces must be included or
        # every @Binds row would incorrectly resolve to __external__/INFERRED.
        local_names = {
            item["name"]
            for key in ("classes", "interfaces", "objects")
            for item in file_data.get(key, [])
            if item.get("name")
        }
        local_imports = {
            imp.get("alias") or (imp.get("name") or "").split(".")[-1]: (
                imp.get("full_import_name") or imp.get("name")
            )
            for imp in file_data.get("imports", [])
            if imp.get("name") or imp.get("alias")
        }

        module_names = set()
        for key in ("classes", "objects"):
            for item in file_data.get(key, []):
                for dec_raw in item.get("decorators") or []:
                    if _parse_decorator_name(dec_raw) == "Module":
                        module_names.add(item.get("name"))
                        break

        if not module_names:
            continue

        function_calls = file_data.get("function_calls") or []

        for func in file_data.get("functions", []):
            class_context = func.get("class_context")
            if not class_context or class_context not in module_names:
                continue

            dec_names = {_parse_decorator_name(d) for d in (func.get("decorators") or [])}
            return_type = func.get("return_type")

            if "Binds" in dec_names:
                provider = "Binds"
                arg_types = func.get("arg_types") or []
                if not return_type or len(arg_types) != 1 or not arg_types[0]:
                    continue
                target_type = arg_types[0]
            elif "Provides" in dec_names:
                provider = "Provides"
                if not return_type:
                    continue
                func_name = func.get("name")
                func_line = func.get("line_number")
                candidates = []
                for call in function_calls:
                    ctx = call.get("context") or []
                    call_class_ctx = call.get("class_context") or []
                    if (
                        len(ctx) >= 3
                        and ctx[0] == func_name
                        and ctx[2] == func_line
                        and len(call_class_ctx) >= 1
                        and call_class_ctx[0] == class_context
                    ):
                        call_name = call.get("name")
                        if call_name and (
                            call_name in local_names
                            or call_name in local_imports
                            or call_name in imports_map
                        ):
                            candidates.append(call_name)
                if not candidates:
                    continue
                if len(candidates) > 1:
                    # More than one type-resolvable call in the body -- e.g.
                    # "val logger = LoggerImpl(); return ThingImpl(logger)"
                    # (wanted call is last) vs "return ThingImpl(LoggerImpl())"
                    # (wanted call is first, textually). Neither a first- nor
                    # last-line tie-break is correct in general with the
                    # information available in function_calls, and a wrong DI
                    # edge is worse than a missing one for impact analysis.
                    # Skip rather than guess, mirroring the @Binds arity check
                    # above.
                    continue
                target_type = candidates[0]
            else:
                continue

            source_path, source_conf = _resolve_type_name(
                return_type, caller_file_path, local_names, local_imports, imports_map
            )
            target_path, target_conf = _resolve_type_name(
                target_type, caller_file_path, local_names, local_imports, imports_map
            )
            confidence_label = (
                "EXTRACTED" if source_conf == "EXTRACTED" and target_conf == "EXTRACTED" else "INFERRED"
            )

            key = (return_type, source_path, target_type, target_path, func.get("line_number"), provider)
            if key in seen:
                continue
            seen.add(key)

            binds_batch.append({
                "source_name": return_type,
                "source_path": source_path,
                "target_name": target_type,
                "target_path": target_path,
                "line_number": func.get("line_number"),
                "provider": provider,
                "confidence_label": confidence_label,
            })

    return binds_batch


def build_elixir_implements_links(
    all_file_data: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Create defimpl -> defprotocol IMPLEMENTS edges for Elixir modules."""
    implements_batch: List[Dict[str, Any]] = []
    seen: set = set()

    for file_data in all_file_data:
        if file_data.get("lang") != "elixir":
            continue
        file_path = str(Path(file_data["path"]).resolve().as_posix())
        for module in file_data.get("modules", []):
            if module.get("type") != "defimpl":
                continue
            full_name = module.get("name") or ""
            if "." not in full_name:
                continue
            impl_name, for_type = full_name.rsplit(".", 1)
            key = (for_type, file_path, impl_name, module.get("line_number", 0))
            if key in seen:
                continue
            seen.add(key)
            implements_batch.append({
                "child_name": for_type,
                "child_label": "Module",
                "parent_name": impl_name,
                "parent_label": "Module",
                "path": file_path,
                "resolved_parent_file_path": file_path,
                "line_number": module.get("line_number", 0),
                "confidence_label": "EXTRACTED",
            })

    return implements_batch
