"""Resolve class inheritance into INHERITS row payloads (no DB I/O for non-C# batch)."""

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
    if base_class_str == "object":
        return None

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
        }
    return None


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

        caller_file_path = str(Path(file_data["path"]).resolve())
        local_class_names = {c["name"] for c in file_data.get("classes", [])}
        local_imports = {
            imp.get("alias") or imp["name"].split(".")[-1]: imp["name"]
            for imp in file_data.get("imports", [])
        }

        for class_item in file_data.get("classes", []):
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
