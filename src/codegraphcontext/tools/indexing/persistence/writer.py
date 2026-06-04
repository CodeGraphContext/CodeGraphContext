# src/codegraphcontext/tools/indexing/persistence/writer.py
"""All graph DB writes for indexing (single persistence entry point)."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from ....utils.debug_log import info_logger, warning_logger
from ....utils.git_utils import get_repo_commit_hash
from ..sanitize import sanitize_props


def _is_binder_exception(e: Exception) -> bool:
    err_str = str(e).lower()
    return "binder" in err_str or "cannot find a valid label" in err_str



class GraphWriter:
    """Persists repository/file/symbol nodes and relationships via the Neo4j-like driver API."""

    def __init__(self, driver: Any):
        self.driver = driver

    def add_repository_to_graph(self, repo_path: Path, is_dependency: bool = False) -> None:
        repo_name = repo_path.name
        resolved = repo_path.resolve()
        repo_path_str = str(resolved)

        commit_hash = get_repo_commit_hash(resolved)
        indexed_at = datetime.now(timezone.utc).isoformat()

        with self.driver.session() as session:
            session.run(
                """
                MERGE (r:Repository {path: $path})
                SET r.name = $name,
                    r.is_dependency = $is_dependency,
                    r.indexed_at = $indexed_at
                """,
                path=repo_path_str,
                name=repo_name,
                is_dependency=is_dependency,
                indexed_at=indexed_at,
            )
            # Write commit_hash only when the repo is a git working tree so that
            # non-git directories do not get a null/empty property polluting the schema.
            if commit_hash:
                session.run(
                    """
                    MATCH (r:Repository {path: $path})
                    SET r.commit_hash = $commit_hash
                    """,
                    path=repo_path_str,
                    commit_hash=commit_hash,
                )

    def add_file_to_graph(
        self,
        file_data: Dict[str, Any],
        repo_name: str,
        imports_map: dict,
        repo_path_str: Optional[str] = None,
    ) -> None:
        file_path_str = str(Path(file_data["path"]).resolve())
        file_name = Path(file_path_str).name
        is_dependency = file_data.get("is_dependency", False)
        lang = file_data.get("lang")

        with self.driver.session() as session:
            if repo_path_str:
                resolved_repo_str = repo_path_str
            else:
                repo_result = session.run(
                    "MATCH (r:Repository {path: $repo_path}) RETURN r.path as path",
                    repo_path=str(Path(file_data["repo_path"]).resolve()),
                ).single()
                resolved_repo_str = (
                    repo_result["path"] if repo_result else str(Path(file_data["repo_path"]).resolve())
                )
                if not repo_result:
                    warning_logger(
                        f"Repository node not found for {file_data['repo_path']} during indexing of {file_name}."
                    )

            try:
                relative_path = str(Path(file_path_str).relative_to(Path(resolved_repo_str)))
            except ValueError:
                relative_path = file_name

            session.run(
                """
                MERGE (f:File {path: $path})
                SET f.name = $name, f.relative_path = $relative_path, f.is_dependency = $is_dependency
            """,
                path=file_path_str,
                name=file_name,
                relative_path=relative_path,
                is_dependency=is_dependency,
            )

            file_path_obj = Path(file_path_str)
            repo_path_obj = Path(resolved_repo_str)
            relative_path_to_file = file_path_obj.relative_to(repo_path_obj)
            parent_path = resolved_repo_str
            parent_label = "Repository"
            for part in relative_path_to_file.parts[:-1]:
                current_path_str = str(Path(parent_path) / part)
                session.run(
                    f"""
                    MATCH (p:`{parent_label}` {{path: $parent_path}})
                    MERGE (d:Directory {{path: $current_path}})
                    SET d.name = $part
                    MERGE (p)-[:CONTAINS]->(d)
                """,
                    parent_path=parent_path,
                    current_path=current_path_str,
                    part=part,
                )
                parent_path = current_path_str
                parent_label = "Directory"
            session.run(
                f"""
                MATCH (p:`{parent_label}` {{path: $parent_path}})
                MATCH (f:File {{path: $path}})
                MERGE (p)-[:CONTAINS]->(f)
            """,
                parent_path=parent_path,
                path=file_path_str,
            )

            item_mappings = [
                (file_data.get("functions", []), "Function"),
                (file_data.get("classes", []), "Class"),
                (file_data.get("traits", []), "Trait"),
                (file_data.get("variables", []), "Variable"),
                (file_data.get("interfaces", []), "Interface"),
                (file_data.get("macros", []), "Macro"),
                (file_data.get("structs", []), "Struct"),
                (file_data.get("enums", []), "Enum"),
                (file_data.get("unions", []), "Union"),
                (file_data.get("records", []), "Record"),
                (file_data.get("properties", []), "Property"),
                (file_data.get("mixins", []), "Mixin"),
                (file_data.get("extensions", []), "Extension"),
                (file_data.get("modules", []), "Module"),
                (file_data.get("objects", []), "Object"),
            ]

            params_batch: List[Dict[str, Any]] = []
            class_fn_batch: List[Dict[str, Any]] = []
            nested_fn_batch: List[Dict[str, Any]] = []

            for item_list, label in item_mappings:
                if not item_list:
                    continue
                batch: List[Dict[str, Any]] = []
                for item in item_list:
                    row = dict(item)
                    row["path"] = file_path_str
                    if label == "Function" and "cyclomatic_complexity" not in row:
                        row["cyclomatic_complexity"] = 1
                    batch.append(sanitize_props(row))
                    if label == "Function":
                        for arg_name in item.get("args", []):
                            params_batch.append(
                                {
                                    "func_name": item["name"],
                                    "line_number": item["line_number"],
                                    "arg_name": arg_name,
                                }
                            )
                        if item.get("class_context"):
                            class_fn_batch.append(
                                {
                                    "class_name": item["class_context"],
                                    "class_line": item.get("class_context_line", -1)
                                    if item.get("class_context_line") is not None
                                    else -1,
                                    "func_name": item["name"],
                                    "func_line": item["line_number"],
                                }
                            )
                        if item.get("context_type") == "function_definition":
                            nested_fn_batch.append(
                                {
                                    "outer": item["context"],
                                    "inner_name": item["name"],
                                    "inner_line": item["line_number"],
                                }
                            )

                if batch:
                    import json as _json

                    all_keys = set()
                    for b in batch:
                        all_keys.update(b.keys())

                    for k in all_keys:
                        counts: Dict[str, int] = {}
                        for b in batch:
                            v = b.get(k)
                            if v is not None:
                                tname = type(v).__name__
                                counts[tname] = counts.get(tname, 0) + 1

                        dominant = max(counts, key=counts.get) if counts else "str"

                        for b in batch:
                            v = b.get(k)
                            if dominant == "list":
                                if isinstance(v, list):
                                    b[k] = [str(x) for x in v] if v else [""]
                                elif isinstance(v, str) and v:
                                    try:
                                        p = _json.loads(v)
                                        b[k] = [str(x) for x in p] if isinstance(p, list) and p else [""]
                                    except Exception:
                                        b[k] = [v]
                                else:
                                    b[k] = [""]
                            elif dominant == "int":
                                if v is None or v == "":
                                    b[k] = 0
                                elif not isinstance(v, int):
                                    try:
                                        b[k] = int(v)
                                    except Exception:
                                        b[k] = 0
                            elif dominant == "bool":
                                b[k] = bool(v) if v is not None else False
                            else:
                                if v is None:
                                    b.pop(k, None)
                                elif isinstance(v, list):
                                    b[k] = _json.dumps(v)
                                elif not isinstance(v, str):
                                    b[k] = str(v)

                    key_order = sorted(all_keys)
                    batch[:] = [{k: b[k] for k in key_order if k in b} for b in batch]

                if label in {"Module", "DbTable", "ExternalClass"}:
                    merge_clause = f"MERGE (n:{label} {{name: row.name}})"
                    match_clause = f"MATCH (n:{label} {{name: row.name}})"
                else:
                    merge_clause = f"MERGE (n:{label} {{name: row.name, path: $file_path, line_number: row.line_number}})"
                    match_clause = f"MATCH (n:{label} {{name: row.name, path: $file_path, line_number: row.line_number}})"

                session.run(
                    f"""
                    UNWIND $batch AS row
                    {merge_clause}
                    SET n += row
                """,
                    batch=batch,
                    file_path=file_path_str,
                )
                session.run(
                    f"""
                    UNWIND $batch AS row
                    MATCH (f:File {{path: $file_path}})
                    {match_clause}
                    MERGE (f)-[:CONTAINS]->(n)
                """,
                    batch=batch,
                    file_path=file_path_str,
                )

            if params_batch:
                # Deduplicate parameter rows to ensure consistent counts across
                # all database backends.  FalkorDB in particular may create
                # duplicate Parameter nodes / HAS_PARAMETER edges when the same
                # (func_name, line_number, arg_name) tuple appears more than once.
                seen_params: set = set()
                unique_params: List[Dict[str, Any]] = []
                for p in params_batch:
                    key = (p["func_name"], p["line_number"], p["arg_name"])
                    if key not in seen_params:
                        seen_params.add(key)
                        unique_params.append(p)
                session.run(
                    """
                    UNWIND $batch AS row
                    MATCH (fn:Function {name: row.func_name, path: $file_path, line_number: row.line_number})
                    MERGE (p:Parameter {name: row.arg_name, path: $file_path, function_line_number: row.line_number})
                    MERGE (fn)-[:HAS_PARAMETER]->(p)
                """,
                    batch=unique_params,
                    file_path=file_path_str,
                )

            if class_fn_batch:
                # KuzuDB requires deterministic node labels for relationship creation.
                # We split the multi-label MATCH into individual queries.
                for label in ("Class", "Module", "Interface", "Struct", "Record", "Trait", "Object", "Mixin"):
                    try:
                        session.run(
                            f"""
                            UNWIND $batch AS row
                            MATCH (c:{label} {{name: row.class_name, path: $file_path}})
                            MATCH (fn:Function {{name: row.func_name, path: $file_path, line_number: row.func_line}})
                            WHERE row.class_line < 0 OR c.line_number = row.class_line
                            MERGE (c)-[:CONTAINS]->(fn)
                            """,
                            batch=class_fn_batch,
                            file_path=file_path_str,
                        )
                    except Exception as e:
                        if _is_binder_exception(e):
                            continue
                        raise e


            if nested_fn_batch:
                session.run(
                    """
                    UNWIND $batch AS row
                    MATCH (outer:Function {name: row.outer, path: $file_path})
                    MATCH (inner:Function {name: row.inner_name, path: $file_path, line_number: row.inner_line})
                    MERGE (outer)-[:CONTAINS]->(inner)
                """,
                    batch=nested_fn_batch,
                    file_path=file_path_str,
                )

            js_imports = []

            other_imports = []
            for imp in file_data.get("imports", []):
                if lang in {"javascript", "typescript", "tsx"}:
                    module_name = imp.get("source")
                    if module_name:
                        js_imports.append(
                            {
                                "module_name": module_name,
                                "imported_name": imp.get("name", "*"),
                                "alias": imp.get("alias") or "",
                                "line_number": imp.get("line_number") or 0,
                            }
                        )
                else:
                    module_name = imp.get("name") or imp.get("source")
                    if not module_name:
                        continue
                    full_import_name = (
                        imp.get("full_import_name")
                        or imp.get("source")
                        or module_name
                    )
                    other_imports.append(
                        {
                            "name": module_name,
                            "full_import_name": full_import_name,
                            "imported_name": imp.get("imported_name") or module_name,
                            "alias": imp.get("alias"),
                            "line_number": imp.get("line_number") or 0,
                            "lang": imp.get("lang") or lang,
                        }
                    )

            if js_imports:
                session.run(
                    """
                    UNWIND $batch AS row
                    MATCH (f:File {path: $file_path})
                    MERGE (m:Module {name: row.module_name})
                    MERGE (f)-[r:IMPORTS]->(m)
                    SET r.imported_name = row.imported_name,
                        r.alias = row.alias,
                        r.line_number = row.line_number
                """,
                    batch=js_imports,
                    file_path=file_path_str,
                )

            if other_imports:
                session.run(
                    """
                    UNWIND $batch AS row
                    MATCH (f:File {path: $file_path})
                    MERGE (m:Module {name: row.name})
                    SET m.lang = coalesce(row.lang, m.lang),
                        m.full_import_name = coalesce(row.full_import_name, m.full_import_name)
                    MERGE (f)-[r:IMPORTS]->(m)
                    SET r.line_number = row.line_number,
                        r.alias = coalesce(row.alias, ""),
                        r.imported_name = row.imported_name,
                        r.full_import_name = row.full_import_name
                """,
                    batch=other_imports,
                    file_path=file_path_str,
                )

            module_inclusions = file_data.get("module_inclusions", [])
            if module_inclusions:
                session.run(
                    """
                    UNWIND $batch AS row
                    MATCH (c:Class {name: row.class_name, path: $file_path})
                    MERGE (m:Module {name: row.module_name})
                    MERGE (c)-[:INCLUDES]->(m)
                """,
                    batch=[
                        {"class_name": i["class"], "module_name": i["module"]} for i in module_inclusions
                    ],
                    file_path=file_path_str,
                )

    def add_minimal_file_node(
        self, file_path: Path, repo_path: Path, is_dependency: bool = False
    ) -> None:
        file_path_str = str(file_path.resolve())
        file_name = file_path.name
        repo_name = repo_path.name
        repo_path_str = str(repo_path.resolve())

        with self.driver.session() as session:
            session.run(
                """
                MERGE (r:Repository {path: $repo_path})
                SET r.name = $repo_name
                """,
                repo_path=repo_path_str,
                repo_name=repo_name,
            )

            session.run(
                """
                MERGE (f:File {path: $file_path})
                SET f.name = $file_name,
                    f.is_dependency = $is_dependency
                """,
                file_path=file_path_str,
                file_name=file_name,
                is_dependency=is_dependency,
            )

            file_path_obj = Path(file_path_str)
            repo_path_obj = Path(repo_path_str)
            try:
                relative_path_to_file = file_path_obj.relative_to(repo_path_obj)
            except ValueError:
                relative_path_to_file = Path(file_path_obj.name)

            parent_path = repo_path_str
            parent_label = "Repository"

            for part in relative_path_to_file.parts[:-1]:
                current_path = Path(parent_path) / part
                current_path_str = str(current_path)

                session.run(
                    f"""
                    MATCH (p:{parent_label} {{path: $parent_path}})
                    MERGE (d:Directory {{path: $current_path}})
                    SET d.name = $part
                    MERGE (p)-[:CONTAINS]->(d)
                """,
                    parent_path=parent_path,
                    current_path=current_path_str,
                    part=part,
                )

                parent_path = current_path_str
                parent_label = "Directory"

            session.run(
                f"""
                MATCH (p:{parent_label} {{path: $parent_path}})
                MATCH (f:File {{path: $file_path}})
                MERGE (p)-[:CONTAINS]->(f)
            """,
                parent_path=parent_path,
                file_path=file_path_str,
            )

    def write_function_call_groups(
        self,
        fn_to_fn: List[Dict] = None,
        fn_to_class: List[Dict] = None,
        fn_to_interface: List[Dict] = None,
        fn_to_object: List[Dict] = None,
        file_to_fn: List[Dict] = None,
        file_to_class: List[Dict] = None,
        file_to_interface: List[Dict] = None,
        file_to_object: List[Dict] = None,
    ) -> None:
        batch_size = 1000

        # Initialize defaults to avoid TypeError on missing args or None values
        fn_to_fn = fn_to_fn or []
        fn_to_class = fn_to_class or []
        fn_to_interface = fn_to_interface or []
        fn_to_object = fn_to_object or []
        file_to_fn = file_to_fn or []
        file_to_class = file_to_class or []
        file_to_interface = file_to_interface or []
        file_to_object = file_to_object or []

        # KuzuDB requires deterministic node labels for relationship creation.
        # We use specific queries for each bucket to satisfy the binder.
        queries = [
            (fn_to_fn, "Function", "Function"),
            (fn_to_class, "Function", "Class"),
            (fn_to_interface, "Function", "Interface"),
            (fn_to_object, "Function", "Object"),
            (file_to_fn, "File", "Function"),
            (file_to_class, "File", "Class"),
            (file_to_interface, "File", "Interface"),
            (file_to_object, "File", "Object"),
        ]

        with self.driver.session() as session:
            for batch_data, caller_label, called_label in queries:
                if not batch_data:
                    continue

                # Ensure all rows have the required keys with correct types for KuzuDB
                sanitized_batch = []
                for row in batch_data:
                    if not isinstance(row, dict) or not row.get("caller_file_path") or not row.get("called_name"):
                        continue

                    # Skip rows with explicitly False filters (considered malformed in #885)
                    if row.get("called_line_number") is False or row.get("called_context") is False:
                        continue

                    row = dict(row) # Copy to avoid mutating input
                    if "confidence" not in row or row["confidence"] is None:
                        row["confidence"] = 0.0
                    if "resolution_tier" not in row or row["resolution_tier"] is None:
                        row["resolution_tier"] = -1
                    if "confidence_label" not in row or row["confidence_label"] is None:
                        row["confidence_label"] = "EXTRACTED"

                    val = row.get("called_line_number")
                    if "called_line_number" not in row or not isinstance(val, int):
                        # Force int for KuzuDB matching, handle None/0 (#885)
                        try:
                            row["called_line_number"] = int(val or 0)
                        except (ValueError, TypeError):
                            row["called_line_number"] = 0

                    if "called_context" not in row or row["called_context"] is None:
                        row["called_context"] = ""
                    if "line_number" not in row or row["line_number"] is None:
                        row["line_number"] = 0

                    # Serialize args to a deterministic string for the MERGE key.
                    # FalkorDB can't match list-typed properties in MERGE (creates
                    # duplicates), but removing args entirely caused Neo4j to
                    # merge distinct calls.  A serialized string gives universal
                    # scalar comparison across all backends.
                    import json as _json
                    raw_args = row.get("args") or []
                    if isinstance(raw_args, list):
                        row["args_key"] = _json.dumps(raw_args, sort_keys=False)
                    else:
                        row["args_key"] = str(raw_args)

                    sanitized_batch.append(row)

                if not sanitized_batch:
                    continue

                # Deduplicate CALLS batch to ensure consistent counts across
                # all backends.  FalkorDB's MERGE within an UNWIND batch does
                # not see edges created by earlier rows in the same snapshot,
                # leading to duplicate edges.  Dedup at the application level
                # guarantees identical input to every backend.
                seen_calls: set = set()
                unique_calls: List[Dict[str, Any]] = []
                for row in sanitized_batch:
                    dedup_key = (
                        row.get("caller_name", ""),
                        row.get("caller_file_path", ""),
                        row.get("caller_line_number", 0),
                        row.get("called_name", ""),
                        row.get("called_file_path", ""),
                        row.get("called_line_number", 0),
                        row.get("called_context", ""),
                        row.get("line_number", 0),
                        row.get("full_call_name", ""),
                        row.get("args_key", ""),
                    )
                    if dedup_key not in seen_calls:
                        seen_calls.add(dedup_key)
                        unique_calls.append(row)
                sanitized_batch = unique_calls

                # Define which labels have a 'context' property in the schema
                labels_with_context = {"Function", "Variable"}
                called_context_clause = ""
                if called_label in labels_with_context:
                    called_context_clause = 'AND (row.called_context = "" OR called.context = row.called_context)'

                # Choose query pattern based on whether caller is a File
                if caller_label == "File":
                    q = f"""
                        UNWIND $batch AS row
                        MATCH (caller:File {{path: row.caller_file_path}})
                        MATCH (called:{called_label} {{name: row.called_name, path: row.called_file_path}})
                        WHERE (row.called_line_number <= 0 OR called.line_number = row.called_line_number)
                          {called_context_clause}
                        MERGE (caller)-[call:CALLS {{line_number: row.line_number, full_call_name: row.full_call_name, args_key: row.args_key}}]->(called)
                        SET call.args = row.args
                        SET call.confidence = row.confidence
                        SET call.resolution_tier = row.resolution_tier
                        SET call.confidence_label = row.confidence_label
                    """
                else:
                    q = f"""
                        UNWIND $batch AS row
                        MATCH (caller:{caller_label} {{name: row.caller_name, path: row.caller_file_path, line_number: row.caller_line_number}})
                        MATCH (called:{called_label} {{name: row.called_name, path: row.called_file_path}})
                        WHERE (row.called_line_number <= 0 OR called.line_number = row.called_line_number)
                          {called_context_clause}
                        MERGE (caller)-[call:CALLS {{line_number: row.line_number, full_call_name: row.full_call_name, args_key: row.args_key}}]->(called)
                        SET call.args = row.args
                        SET call.confidence = row.confidence
                        SET call.resolution_tier = row.resolution_tier
                        SET call.confidence_label = row.confidence_label
                    """

                t0 = time.time()
                for i in range(0, len(sanitized_batch), batch_size):
                    batch = sanitized_batch[i : i + batch_size]
                    try:
                        session.run(q, batch=batch)
                    except Exception as e:
                        if _is_binder_exception(e):
                            # Skip unsupported label combinations in KuzuDB
                            continue
                        raise e
                info_logger(f"[CALLS] {caller_label}-to-{called_label}: {len(sanitized_batch)} edges written in {time.time()-t0:.1f}s")

        info_logger("[CALLS] All relationships processed.")

    def _create_csharp_inheritance_and_interfaces(
        self, session: Any, file_data: Dict[str, Any], imports_map: dict
    ) -> None:
        if file_data.get("lang") != "c_sharp":
            return

        caller_file_path = str(Path(file_data["path"]).resolve())

        for type_list_name, type_label in [
            ("classes", "Class"),
            ("structs", "Struct"),
            ("records", "Record"),
            ("interfaces", "Interface"),
        ]:
            for type_item in file_data.get(type_list_name, []):
                if not type_item.get("bases"):
                    continue

                for base_str in type_item["bases"]:
                    base_name = base_str.split("<")[0].strip()

                    is_interface = False
                    resolved_path = caller_file_path

                    for iface in file_data.get("interfaces", []):
                        if iface["name"] == base_name:
                            is_interface = True
                            break

                    if base_name in imports_map:
                        possible_paths = imports_map[base_name]
                        if len(possible_paths) > 0:
                            resolved_path = possible_paths[0]

                    base_index = type_item["bases"].index(base_str)

                    if is_interface or (base_index > 0 and type_label == "Class"):
                        # Split by label for Kuzu binder
                        for clab in ("Class", "Struct", "Record", "Mixin", "Extension"):
                            try:
                                session.run(
                                    f"""
                                    MATCH (child:`{clab}` {{name: $child_name, path: $path}})
                                    MATCH (iface:Interface {{name: $interface_name}})
                                    MERGE (child)-[:IMPLEMENTS]->(iface)
                                """,
                                    child_name=type_item["name"],
                                    path=caller_file_path,
                                    interface_name=base_name,
                                )
                            except Exception as e:
                                if _is_binder_exception(e):
                                    continue
                                raise e
                    else:
                        child_labels = ("Class", "Record", "Interface", "Mixin", "Extension")
                        parent_labels = ("Class", "Record", "Interface", "Mixin", "Extension")
                        for clab in child_labels:
                            for plab in parent_labels:
                                try:
                                    session.run(
                                        f"""
                                        MATCH (child:`{clab}` {{name: $child_name, path: $path}})
                                        MATCH (parent:`{plab}` {{name: $parent_name}})
                                        MERGE (child)-[:INHERITS]->(parent)
                                    """,
                                        child_name=type_item["name"],
                                        path=caller_file_path,
                                        parent_name=base_name,
                                    )
                                except Exception as e:
                                    if _is_binder_exception(e):
                                        continue
                                    raise e


    def write_inheritance_links(
        self,
        inheritance_batch: List[Dict[str, Any]],
        csharp_files: List[Dict[str, Any]],
        imports_map: dict,
    ) -> None:
        info_logger(
            f"[INHERITS] Resolving inheritance links across {len(inheritance_batch)} files..."
        )
        batch_size = 500
        with self.driver.session() as session:
            internal_batch = [r for r in inheritance_batch if r.get("resolved_parent_file_path") != "__external__"]
            external_batch = [r for r in inheritance_batch if r.get("resolved_parent_file_path") == "__external__"]

            # Internal inheritance (within workspace)
            # KuzuDB binder requires explicit labels on both sides of a relationship creation.
            # We iterate over labels to ensure each MERGE targets a single sub-table of the INHERITS group.
            labels = ("Class", "Trait", "Interface", "Struct", "Enum", "Union", "Record", "Mixin", "Extension", "Module", "Object")
            for child_label in labels:
                for parent_label in labels:
                    try:
                        session.run(
                            f"""
                            UNWIND $batch AS row
                            MATCH (child:`{child_label}` {{name: row.child_name, path: row.path}})
                            MATCH (parent:`{parent_label}` {{name: row.parent_name, path: row.resolved_parent_file_path}})
                            MERGE (child)-[r:INHERITS]->(parent)
                            SET r.confidence_label = coalesce(row.confidence_label, 'EXTRACTED')
                        """,
                            batch=internal_batch,
                        )
                    except Exception as e:
                        if _is_binder_exception(e):
                            continue
                        raise e

            # External inheritance (outside workspace)
            for child_label in labels:
                try:
                    session.run(
                        f"""
                        UNWIND $batch AS row
                        MATCH (child:`{child_label}` {{name: row.child_name, path: row.path}})
                        MERGE (parent:ExternalClass {{name: row.parent_name}})
                        MERGE (child)-[r:INHERITS]->(parent)
                        SET r.confidence_label = coalesce(row.confidence_label, 'INFERRED')
                        """,
                        batch=external_batch,
                    )
                except Exception as e:
                    if _is_binder_exception(e):
                        continue
                    raise e


            for file_data in csharp_files:
                self._create_csharp_inheritance_and_interfaces(session, file_data, imports_map)

        info_logger(f"[INHERITS] Complete: {len(inheritance_batch)} inheritance links processed.")

    def write_scip_call_edges(
        self, files_data: Dict[str, Any], name_from_symbol: Callable[[str], str]
    ) -> None:
        with self.driver.session() as session:
            for file_data in files_data.values():
                # ── Code-level caller → Any code-level callee ────────────────
                caller_labels = ("Function", "Variable", "Class", "Interface", "Trait", "Struct", "Record", "Union", "Mixin", "Extension")
                callee_labels = ("Function", "Class", "Interface", "Trait", "Struct", "Enum", "Record", "Union", "Mixin", "Extension")
                for edge in file_data.get("function_calls_scip", []):
                    for clab in caller_labels:
                        for calab in callee_labels:
                            try:
                                session.run(
                                    f"""
                                    MATCH (caller:`{clab}` {{name: $caller_name, path: $caller_file, line_number: $caller_line}})
                                    MATCH (callee:`{calab}` {{name: $callee_name, path: $callee_file}})
                                    MERGE (caller)-[:CALLS {{line_number: $ref_line, source: 'scip'}}]->(callee)
                                """,
                                    caller_name=name_from_symbol(edge["caller_symbol"]),
                                    caller_file=edge["caller_file"],
                                    caller_line=edge["caller_line"],
                                    callee_name=edge["callee_name"],
                                    callee_file=edge["callee_file"],
                                    ref_line=edge["ref_line"],
                                )
                            except Exception as e:
                                warning_logger(f"Failed to write SCIP call edge: {e}")

                # ── Module-level (top-level) caller → Any code-level callee ─
                for edge in file_data.get("module_level_calls_scip", []):
                    for calab in callee_labels:
                        try:
                            session.run(
                                f"""
                                MATCH (caller:File {{path: $caller_file}})
                                MATCH (callee:`{calab}` {{name: $callee_name, path: $callee_file}})
                                MERGE (caller)-[:CALLS {{line_number: $ref_line, source: 'scip'}}]->(callee)
                            """,
                                caller_file=edge["caller_file"],
                                callee_name=edge["callee_name"],
                                callee_file=edge["callee_file"],
                                ref_line=edge["ref_line"],
                            )
                        except Exception as e:
                            warning_logger(f"Failed to write SCIP module-level call edge: {e}")

    def delete_file_from_graph(self, path: str) -> None:
        file_path_str = str(Path(path).resolve())
        with self.driver.session() as session:
            parents_res = session.run(
                """
                MATCH (f:File {path: $path})<-[:CONTAINS*]-(d:Directory)
                RETURN d.path as path ORDER BY d.path DESC
            """,
                path=file_path_str,
            )
            parent_paths = [record["path"] for record in parents_res]

            session.run(
                """
                MATCH (f:File {path: $path})
                OPTIONAL MATCH (f)-[:CONTAINS]->(element)
                DETACH DELETE f, element
            """,
                path=file_path_str,
            )
            info_logger(f"Deleted file and its elements from graph: {file_path_str}")

            for p in parent_paths:
                session.run(
                    """
                    MATCH (d:Directory {path: $path})
                    WHERE NOT (d)-[:CONTAINS]->()
                    DETACH DELETE d
                """,
                    path=p,
                )

    # ── Spring semantic edges (#887) ───────────────────────────────────────────

    def write_cpp_class_function_links(self, repo_path_str: str) -> None:
        """Post-pass: create Class-[:CONTAINS]->Function edges for C++ files.

        C++ defines class methods out-of-line in .cpp files while the Class node
        lives in the corresponding .h file.  The per-file write pass cannot create
        these edges because the Class node may not exist yet when the .cpp is
        processed.  This method runs AFTER all file nodes are in the graph and
        resolves every Function that carries a class_context property.

        Scoped strictly to C++ extensions (.cpp / .cc / .cxx / .c++ / .C) so
        other languages are completely unaffected.
        """
        _cpp_exts = ('.cpp', '.cc', '.cxx', '.c++', '.C')
        ext_conditions = ' OR '.join(f'fn.path ENDS WITH "{ext}"' for ext in _cpp_exts)

        container_labels = ("Class", "Struct", "Module")
        with self.driver.session() as session:
            for clab in container_labels:
                query = f"""
                    MATCH (fn:Function)
                    WHERE fn.path STARTS WITH $repo_path
                      AND fn.class_context IS NOT NULL
                      AND ({ext_conditions})
                    MATCH (c:`{clab}`)
                    WHERE c.name = fn.class_context
                      AND c.path STARTS WITH $repo_path
                    MERGE (c)-[:CONTAINS]->(fn)
                """
                try:
                    session.run(query, repo_path=repo_path_str)
                except Exception as e:
                    debug_log(f"Failed to link C++ methods for label {clab}: {e}")

    def write_spring_inject_links(self, inject_batch: List[Dict[str, Any]]) -> None:
        """Create INJECTS edges: injector Class -> injected Class (via @Autowired / @Inject)."""
        if not inject_batch:
            return
        info_logger(f"[SPRING] Writing {len(inject_batch)} INJECTS edges...")
        batch_size = 500
        with self.driver.session() as session:
            for i in range(0, len(inject_batch), batch_size):
                batch = inject_batch[i : i + batch_size]
                session.run(
                    """
                    UNWIND $batch AS row
                    MATCH (injector:Class {name: row.injector_class, path: row.injector_path})
                    MATCH (injected:Class {name: row.injected_class})
                    MERGE (injector)-[r:INJECTS]->(injected)
                    SET r.field_name = row.field_name,
                        r.inject_line = row.inject_line,
                        r.confidence_label = 'EXTRACTED'
                    """,
                    batch=batch,
                )
        info_logger(f"[SPRING] INJECTS edges written.")

    def write_spring_endpoint_properties(self, endpoint_batch: List[Dict[str, Any]]) -> None:
        """Set http_method / http_path / transactional properties on Function nodes."""
        if not endpoint_batch:
            return
        info_logger(f"[SPRING] Updating {len(endpoint_batch)} endpoint function properties...")
        batch_size = 500
        with self.driver.session() as session:
            for i in range(0, len(endpoint_batch), batch_size):
                batch = endpoint_batch[i : i + batch_size]
                session.run(
                    """
                    UNWIND $batch AS row
                    MATCH (fn:Function {name: row.func_name, path: row.path, line_number: row.line_number})
                    SET fn.http_method = row.http_method,
                        fn.http_path = row.http_path
                    """,
                    batch=batch,
                )
        info_logger("[SPRING] Endpoint properties updated.")

    # ── Maven / Gradle build graph (#888) ─────────────────────────────────────

    def write_maven_build_graph(self, build_data: Dict[str, Any], repo_path_str: str) -> None:
        """Write MavenModule nodes, CHILD_MODULE, MODULE_DEPENDS_ON, USES_LIBRARY edges."""
        if not build_data:
            return
        modules = build_data.get("modules", [])
        external_libs = build_data.get("external_libs", [])
        inter_module_deps = build_data.get("inter_module_deps", [])
        child_relations = build_data.get("child_relations", [])

        if not modules:
            return

        info_logger(f"[MAVEN] Writing {len(modules)} modules, "
                    f"{len(inter_module_deps)} inter-module deps, "
                    f"{len(external_libs)} external libs...")

        batch_size = 200
        with self.driver.session() as session:
            # MavenModule nodes
            for i in range(0, len(modules), batch_size):
                session.run(
                    """
                    UNWIND $batch AS row
                    MERGE (m:MavenModule {group_id: row.group_id, artifact_id: row.artifact_id})
                    SET m.version = row.version,
                        m.packaging = row.packaging,
                        m.pom_path = row.pom_path,
                        m.path = row.pom_path,
                        m.repo_path = $repo_path
                    """,
                    batch=modules[i : i + batch_size],
                    repo_path=repo_path_str,
                )
            # CHILD_MODULE edges
            for i in range(0, len(child_relations), batch_size):
                session.run(
                    """
                    UNWIND $batch AS row
                    MATCH (parent:MavenModule {artifact_id: row.parent_artifact_id})
                    MATCH (child:MavenModule {artifact_id: row.child_artifact_id})
                    MERGE (parent)-[:CHILD_MODULE]->(child)
                    """,
                    batch=child_relations[i : i + batch_size],
                )
            # MODULE_DEPENDS_ON edges (inter-module)
            for i in range(0, len(inter_module_deps), batch_size):
                session.run(
                    """
                    UNWIND $batch AS row
                    MATCH (src:MavenModule {artifact_id: row.src_artifact_id})
                    MATCH (tgt:MavenModule {artifact_id: row.tgt_artifact_id})
                    MERGE (src)-[r:MODULE_DEPENDS_ON]->(tgt)
                    SET r.scope = row.scope
                    """,
                    batch=inter_module_deps[i : i + batch_size],
                )
            # ExternalLibrary nodes + USES_LIBRARY edges
            for i in range(0, len(external_libs), batch_size):
                session.run(
                    """
                    UNWIND $batch AS row
                    MERGE (lib:ExternalLibrary {group_id: row.group_id, artifact_id: row.artifact_id})
                    SET lib.version = row.version
                    WITH lib, row
                    MATCH (src:MavenModule {artifact_id: row.src_artifact_id})
                    MERGE (src)-[r:USES_LIBRARY]->(lib)
                    SET r.scope = row.scope
                    """,
                    batch=external_libs[i : i + batch_size],
                )

        info_logger("[MAVEN] Build graph written.")

    def write_gradle_build_graph(self, build_data: Dict[str, Any], repo_path_str: str) -> None:
        """Write GradleModule nodes and MODULE_DEPENDS_ON / USES_LIBRARY edges."""
        if not build_data:
            return
        modules = build_data.get("modules", [])
        inter_module_deps = build_data.get("inter_module_deps", [])
        external_libs = build_data.get("external_libs", [])

        if not modules:
            return

        info_logger(f"[GRADLE] Writing {len(modules)} modules, "
                    f"{len(inter_module_deps)} inter-module deps, "
                    f"{len(external_libs)} external libs...")

        batch_size = 200
        with self.driver.session() as session:
            for i in range(0, len(modules), batch_size):
                session.run(
                    """
                    UNWIND $batch AS row
                    MERGE (m:GradleModule {name: row.name})
                    SET m.build_file = row.build_file, m.path = row.build_file, m.repo_path = $repo_path
                    """,
                    batch=modules[i : i + batch_size],
                    repo_path=repo_path_str,
                )
            for i in range(0, len(inter_module_deps), batch_size):
                session.run(
                    """
                    UNWIND $batch AS row
                    MATCH (src:GradleModule {name: row.src_name})
                    MATCH (tgt:GradleModule {name: row.tgt_name})
                    MERGE (src)-[r:MODULE_DEPENDS_ON]->(tgt)
                    SET r.configuration = row.configuration
                    """,
                    batch=inter_module_deps[i : i + batch_size],
                )
            for i in range(0, len(external_libs), batch_size):
                session.run(
                    """
                    UNWIND $batch AS row
                    MERGE (lib:ExternalLibrary {group_id: row.group_id, artifact_id: row.artifact_id})
                    SET lib.version = row.version
                    WITH lib, row
                    MATCH (src:GradleModule {name: row.src_name})
                    MERGE (src)-[r:USES_LIBRARY]->(lib)
                    SET r.configuration = row.configuration
                    """,
                    batch=external_libs[i : i + batch_size],
                )

        info_logger("[GRADLE] Build graph written.")

    # ── Datasource architecture graph (#843 scoped) ──────────────────────────

    def write_datasource_graph(self, ingested: Dict[str, Any]) -> None:
        """Write Datasource / DbTable / DbColumn / RedisKeyPattern nodes and edges.

        Accepts the dict returned by mysql_ingester.ingest(), cassandra_ingester.ingest(),
        or redis_ingester.ingest().
        """
        ds = ingested.get("datasource", {})
        if not ds:
            return
        ds_name = ds["name"]
        ds_kind = ds.get("kind", "unknown")

        with self.driver.session() as session:
            session.run(
                """
                MERGE (d:Datasource {name: $name})
                SET d.kind = $kind, d.host = $host, d.env = $env
                """,
                name=ds_name,
                kind=ds_kind,
                host=ds.get("host", ""),
                env=ds.get("env", ""),
            )
        info_logger(f"[DATASOURCE] Written Datasource node: {ds_name} ({ds_kind})")

        # ── MySQL / Cassandra tables + columns ────────────────────────────
        tables = ingested.get("tables", [])
        batch_size = 500

        for i in range(0, len(tables), batch_size):
            with self.driver.session() as session:
                session.run(
                    """
                    UNWIND $batch AS t
                    MERGE (tbl:DbTable {fqn: t.fqn})
                    SET tbl.name = t.name,
                        tbl.datasource_name = t.datasource_name,
                        tbl.table_type = coalesce(t.table_type, ''),
                        tbl.comment = coalesce(t.comment, '')
                    WITH tbl, t
                    MATCH (d:Datasource {name: t.datasource_name})
                    MERGE (tbl)-[:STORED_IN]->(d)
                    """,
                    batch=tables[i : i + batch_size],
                )
        if tables:
            info_logger(f"[DATASOURCE] Written {len(tables)} DbTable nodes for {ds_name}")

        columns = ingested.get("columns", [])
        for i in range(0, len(columns), batch_size):
            with self.driver.session() as session:
                session.run(
                    """
                    UNWIND $batch AS c
                    MERGE (col:DbColumn {name: c.name, table_fqn: c.table_fqn})
                    SET col.type = c.type,
                        col.nullable = c.nullable,
                        col.datasource_name = c.datasource_name,
                        col.is_primary_key = coalesce(c.is_primary_key, false)
                    WITH col, c
                    MATCH (tbl:DbTable {fqn: c.table_fqn})
                    MERGE (tbl)-[:HAS_COLUMN]->(col)
                    """,
                    batch=columns[i : i + batch_size],
                )
        if columns:
            info_logger(f"[DATASOURCE] Written {len(columns)} DbColumn nodes for {ds_name}")

        # ── Redis key patterns ────────────────────────────────────────────
        key_patterns = ingested.get("key_patterns", [])
        for i in range(0, len(key_patterns), batch_size):
            with self.driver.session() as session:
                session.run(
                    """
                    UNWIND $batch AS kp
                    MERGE (k:RedisKeyPattern {pattern: kp.pattern, datasource_name: kp.datasource_name})
                    SET k.key_type = kp.key_type,
                        k.example_key = kp.example_key,
                        k.count = kp.count
                    WITH k, kp
                    MATCH (d:Datasource {name: kp.datasource_name})
                    MERGE (k)-[:STORED_IN]->(d)
                    """,
                    batch=key_patterns[i : i + batch_size],
                )
        if key_patterns:
            info_logger(f"[DATASOURCE] Written {len(key_patterns)} RedisKeyPattern nodes for {ds_name}")

    def write_orm_mappings(self, orm_batch: List[Dict[str, Any]]) -> None:
        """Write MAPS_TO edges from Class → DbTable (JPA, Cassandra, Redis) for #843.

        Each record in orm_batch must have:
            kind: "class_table"
            class_name, class_path, orm_table, datastore, line_number
        """
        class_table = [r for r in orm_batch if r.get("kind") == "class_table"]
        if not class_table:
            return

        batch_size = 500
        for i in range(0, len(class_table), batch_size):
            with self.driver.session() as session:
                session.run(
                    """
                    UNWIND $batch AS m
                    MATCH (c:Class {name: m.class_name, path: m.class_path})
                    MERGE (tbl:DbTable {name: m.orm_table})
                    ON CREATE SET tbl.fqn = m.orm_table, tbl.datasource_name = m.datastore
                    ON MATCH SET tbl.datasource_name = COALESCE(tbl.datasource_name, m.datastore)
                    MERGE (c)-[:MAPS_TO {datastore: m.datastore, line_number: m.line_number}]->(tbl)
                    """,
                    batch=class_table[i : i + batch_size],
                )
        info_logger(f"[ORM] Written {len(class_table)} MAPS_TO edges")

    def write_query_links(self, query_batch: List[Dict[str, Any]]) -> None:
        """Write READS / WRITES edges from Function → DbTable for #843.

        Each record must have:
            kind: "method_query"
            method_name, class_name, method_path, db_tables, operation, line_number
        """
        method_queries = [r for r in query_batch if r.get("kind") == "method_query" and r.get("db_tables")]
        if not method_queries:
            return

        # Flatten: one edge per (method, table)
        edges = []
        for r in method_queries:
            for tbl in r["db_tables"]:
                edges.append({
                    "method_name": r.get("method_name"),
                    "class_name": r.get("class_name"),
                    "method_path": r.get("method_path"),
                    "table_name": tbl,
                    "operation": r.get("operation", "READS"),
                    "line_number": r.get("line_number", 0),
                })

        batch_size = 500
        for op in ("READS", "WRITES"):
            op_edges = [e for e in edges if e["operation"] == op]
            for i in range(0, len(op_edges), batch_size):
                with self.driver.session() as session:
                    session.run(
                        f"""
                        UNWIND $batch AS q
                        MATCH (fn:Function {{name: q.method_name, path: q.method_path}})
                        MERGE (tbl:DbTable {{name: q.table_name}})
                        ON CREATE SET tbl.fqn = q.table_name, tbl.datasource_name = 'mysql'
                        ON MATCH SET tbl.datasource_name = COALESCE(tbl.datasource_name, 'mysql')
                        MERGE (fn)-[:{op} {{line_number: q.line_number}}]->(tbl)
                        """,
                        batch=op_edges[i : i + batch_size],
                    )
        info_logger(f"[ORM] Written {len(edges)} READS/WRITES query edges")

    def write_mybatis_links(self, mybatis_batch: List[Dict[str, Any]]) -> None:
        """Write READS / WRITES edges from Function → DbTable for MyBatis XML mappers.

        Matches Function nodes by (name, class_context) instead of path because
        the XML mapper files don't directly reference Java source paths.

        Each record must have:
            method_name, class_name, db_tables (list), operation ("READS"/"WRITES")
        """
        edges = []
        for r in mybatis_batch:
            for tbl in r.get("db_tables", []):
                edges.append({
                    "method_name": r["method_name"],
                    "class_name": r["class_name"],
                    "table_name": tbl,
                    "operation": r.get("operation", "READS"),
                })

        if not edges:
            return

        batch_size = 500
        written = 0
        for op in ("READS", "WRITES"):
            op_edges = [e for e in edges if e["operation"] == op]
            if not op_edges:
                continue
            for i in range(0, len(op_edges), batch_size):
                with self.driver.session() as session:
                    session.run(
                        f"""
                        UNWIND $batch AS q
                        MATCH (fn:Function {{name: q.method_name}})
                        WHERE fn.class_context = q.class_name
                        MERGE (tbl:DbTable {{name: q.table_name}})
                        ON CREATE SET tbl.fqn = q.table_name, tbl.datasource_name = 'mysql'
                        ON MATCH SET tbl.datasource_name = COALESCE(tbl.datasource_name, 'mysql')
                        MERGE (fn)-[:{op}]->(tbl)
                        """,
                        batch=op_edges[i : i + batch_size],
                    )
                written += len(op_edges[i : i + batch_size])
        info_logger(f"[MYBATIS] Written {written} READS/WRITES MyBatis edges")

    def write_spring_data_repo_links(self, orm_batch: List[Dict[str, Any]]) -> None:
        """Write READS/WRITES edges for Spring Data repository derived-query methods.

        Each record must have kind='spring_data_method' and:
            entity_class, method_name, method_path, operation, line_number

        Uses a two-hop lookup: Function → (entity_class Class)-[:MAPS_TO]→ DbTable
        so no table name is required at parse time.
        """
        records = [r for r in orm_batch if r.get("kind") == "spring_data_method"]
        if not records:
            return

        edges = [
            {
                "method_name": r["method_name"],
                "method_path": r["method_path"],
                "entity_class": r["entity_class"],
                "operation": r.get("operation", "READS"),
                "line_number": r.get("line_number", 0),
            }
            for r in records
        ]

        batch_size = 500
        written = 0
        for op in ("READS", "WRITES"):
            op_edges = [e for e in edges if e["operation"] == op]
            if not op_edges:
                continue
            for i in range(0, len(op_edges), batch_size):
                with self.driver.session() as session:
                    session.run(
                        f"""
                        UNWIND $batch AS q
                        MATCH (fn:Function {{name: q.method_name, path: q.method_path}})
                        MATCH (entity:Class {{name: q.entity_class}})-[:MAPS_TO]->(tbl:DbTable)
                        MERGE (fn)-[:{op} {{line_number: q.line_number, source: 'spring_data'}}]->(tbl)
                        """,
                        batch=op_edges[i : i + batch_size],
                    )
                written += len(op_edges[i : i + batch_size])
        info_logger(f"[SPRING_DATA] Written {written} READS/WRITES derived-query edges")

    def delete_repository_from_graph(self, repo_path: str) -> bool:
        repo_path_str = repo_path
        path_prefix = repo_path_str + "/"
        with self.driver.session() as session:
            result = session.run(
                "MATCH (r:Repository {path: $path}) RETURN count(r) as cnt", path=repo_path_str
            ).single()
            if not result or result["cnt"] == 0:
                warning_logger(f"Attempted to delete non-existent repository: {repo_path_str}")
                return False

        for rel_type in ("CALLS", "INHERITS", "IMPORTS"):
            while True:
                with self.driver.session() as session:
                    result = session.run(
                        f"MATCH (a)-[r:{rel_type}]->(b) "
                        "WHERE a.path STARTS WITH $prefix OR b.path STARTS WITH $prefix "
                        "WITH r LIMIT 5000 DELETE r RETURN count(r) AS deleted",
                        prefix=path_prefix,
                    ).single()
                    deleted = result["deleted"] if result else 0
                if deleted == 0:
                    break
                info_logger(f"[DELETE] Removed {deleted} {rel_type} rels for {repo_path_str}")

        while True:
            with self.driver.session() as session:
                result = session.run(
                    "MATCH (a)-[r:CONTAINS]->(b) "
                    "WHERE a.path STARTS WITH $prefix OR a.path = $path "
                    "WITH r LIMIT 10000 DELETE r RETURN count(r) AS deleted",
                    prefix=path_prefix,
                    path=repo_path_str,
                ).single()
                deleted = result["deleted"] if result else 0
            if deleted == 0:
                break
            info_logger(f"[DELETE] Removed {deleted} CONTAINS rels for {repo_path_str}")

        # Discover the labels currently in use rather than hardcoding the
        # list. Every time the indexer learned a new node type (Variable,
        # Parameter, Directory, ExternalClass, DbTable, ...) the hardcoded
        # tuple here had to be kept in lockstep, and every miss leaked
        # orphan nodes on `delete_repository`. `CALL db.labels()` returns
        # exactly the set of labels that have at least one node in the
        # current database -- per-label DETACH DELETE with the same path
        # prefix is then label-agnostic and self-maintaining.
        #
        # Labels with no node matching the path prefix are cheap: the
        # label-scoped scan returns 0 rows, the while-True loop exits
        # immediately, and we move on.
        with self.driver.session() as session:
            label_records = session.run("CALL db.labels() YIELD label RETURN label")
            all_labels = sorted({record["label"] for record in label_records})

        for label in all_labels:
            while True:
                with self.driver.session() as session:
                    result = session.run(
                        f"MATCH (n:{label}) WHERE n.path STARTS WITH $prefix "
                        "WITH n LIMIT 10000 DETACH DELETE n RETURN count(n) AS deleted",
                        prefix=path_prefix,
                    ).single()
                    deleted = result["deleted"] if result else 0
                if deleted == 0:
                    break
                info_logger(f"[DELETE] Removed {deleted} {label} nodes for {repo_path_str}")

        with self.driver.session() as session:
            session.run("MATCH (r:Repository {path: $path}) DETACH DELETE r", path=repo_path_str)

        info_logger(f"Deleted repository and its contents from graph: {repo_path_str}")
        return True

    def get_caller_file_paths(self, file_path_str: str) -> set:
        with self.driver.session() as session:
            result = session.run(
                "MATCH (caller)-[:CALLS]->(callee) "
                "WHERE callee.path = $path "
                "RETURN DISTINCT coalesce(caller.path, '') AS p",
                path=file_path_str,
            )
            return {r["p"] for r in result if r["p"] and r["p"] != file_path_str}

    def get_inheritance_neighbor_paths(self, file_path_str: str) -> set:
        with self.driver.session() as session:
            result = session.run(
                "MATCH (a)-[:INHERITS]->(b) "
                "WHERE a.path = $path OR b.path = $path "
                "RETURN DISTINCT CASE WHEN a.path = $path THEN b.path ELSE a.path END AS p",
                path=file_path_str,
            )
            return {r["p"] for r in result if r["p"] and r["p"] != file_path_str}

    def delete_outgoing_calls_from_files(self, file_paths: List[str]) -> None:
        with self.driver.session() as session:
            result = session.run(
                "MATCH (a)-[r:CALLS]->(b) WHERE a.path IN $paths DELETE r RETURN count(r) AS cnt",
                paths=file_paths,
            ).single()
            cnt = result["cnt"] if result else 0
        info_logger(f"[RELINK] Deleted {cnt} outgoing CALLS from {len(file_paths)} caller files")

    def delete_inherits_for_files(self, file_paths: List[str]) -> None:
        with self.driver.session() as session:
            result = session.run(
                "MATCH (a)-[r:INHERITS]->(b) WHERE a.path IN $paths OR b.path IN $paths "
                "DELETE r RETURN count(r) AS cnt",
                paths=file_paths,
            ).single()
            cnt = result["cnt"] if result else 0
        info_logger(f"[RELINK] Deleted {cnt} INHERITS for {len(file_paths)} affected files")

    def get_repo_class_lookup(self, repo_path: Path) -> Dict[str, set]:
        prefix = str(repo_path.resolve()) + "/"
        result_map: Dict[str, set] = {}
        with self.driver.session() as session:
            result = session.run(
                "MATCH (c:Class) WHERE c.path STARTS WITH $prefix "
                "RETURN c.name AS name, c.path AS path",
                prefix=prefix,
            )
            for record in result:
                path = record["path"]
                if path not in result_map:
                    result_map[path] = set()
                result_map[path].add(record["name"])
        return result_map

    def delete_relationship_links(self, repo_path: Path) -> None:
        repo_path_str = str(repo_path.resolve()) + "/"
        with self.driver.session() as session:
            result = session.run(
                "MATCH (a)-[r:CALLS]->(b) WHERE a.path STARTS WITH $prefix DELETE r RETURN count(r) AS cnt",
                prefix=repo_path_str,
            ).single()
            calls_deleted = result["cnt"] if result else 0

            result = session.run(
                "MATCH (a)-[r:INHERITS]->(b) WHERE a.path STARTS WITH $prefix DELETE r RETURN count(r) AS cnt",
                prefix=repo_path_str,
            ).single()
            inherits_deleted = result["cnt"] if result else 0

        info_logger(
            f"[RELINK] Cleared {calls_deleted} CALLS and {inherits_deleted} INHERITS before re-linking: {repo_path}"
        )
