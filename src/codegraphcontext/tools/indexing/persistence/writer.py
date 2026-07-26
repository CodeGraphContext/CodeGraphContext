# src/codegraphcontext/tools/indexing/persistence/writer.py
"""All graph DB writes for indexing (single persistence entry point)."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from ....utils.debug_log import info_logger, warning_logger
from ....utils.git_utils import get_repo_commit_hash
from ..sanitize import sanitize_props
from ..schema_contract import NODE_LABELS
from .utils import get_backend_type, execute_write_operation, execute_read_operation


def sort_import_rows_for_metadata(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Put the most descriptive import first when several rows share a module name."""

    def metadata_priority(row: Dict[str, Any]) -> Tuple[str, int, str, int]:
        name = str(row.get("name") or "")
        full_name = str(row.get("full_import_name") or "")
        stripped = full_name.strip()

        if stripped == "use super::*;":
            priority = 0
        elif stripped.startswith("pub use ") and not stripped.rstrip(";").endswith("::*"):
            priority = 1
        elif "{" in stripped and "}" in stripped:
            priority = 2
        elif stripped.startswith("pub use "):
            priority = 3
        else:
            priority = 4

        return (name, priority, full_name, int(row.get("line_number") or 0))

    return sorted(rows, key=metadata_priority)


def _normalize_path(p) -> str:
    """Normalize a path to use forward slashes for cross-platform DB consistency.

    On Windows, Path.resolve() returns backslashes which breaks STARTS WITH
    queries in the graph DB. Always store and query with forward slashes.
    See: https://github.com/CodeGraphContext/CodeGraphContext/issues/1080
    """
    return Path(p).resolve().as_posix()


def _normalize_prefix(p) -> str:
    """Return a normalized path prefix ending with '/' for STARTS WITH queries."""
    return _normalize_path(p) + "/"


def _cypher_label(label: str, backend: str) -> str:
    """Format a node label for Cypher; Kùzu reserves some identifiers and needs backticks."""
    if backend in ("kuzudb", "ladybugdb") and label in ("Union", "Macro", "Property"):
        return f"`{label}`"
    return label


def _called_context_clause(called_label: str) -> str:
    """Match CALLS targets that store scope in context, class_context, or module_context."""
    if called_label in ("Function", "Variable"):
        return (
            'AND (row.called_context = "" OR row.called_context IS NULL '
            "OR called.context = row.called_context "
            "OR called.class_context = row.called_context "
            "OR called.module_context = row.called_context)"
        )
    return ""


def _is_binder_exception(e: Exception) -> bool:
    err_str = str(e).lower()
    return "binder" in err_str or "cannot find a valid label" in err_str



class GraphWriter:
    """Persists repository/file/symbol nodes and relationships via the Neo4j-like driver API."""

    def __init__(self, driver: Any, db_manager: Any = None):
        self.driver = driver
        self._db_manager = db_manager
        if db_manager is None:
            warning_logger(
                "[GraphWriter] db_manager not provided; "
                "backend detection will default to 'neo4j'"
            )

    def _get_all_node_labels(self) -> list[str]:
        """Discover all node labels in the database, backend-aware.

        Neo4j / Nornic use ``CALL db.labels()``.
        KuzuDB / LadybugDB use ``MATCH (n) RETURN DISTINCT label(n)``
        (``SHOW TABLES`` is not supported in KuzuDB Python bindings ≤ 0.11).
        FalkorDB uses ``CALL db.labels()`` without YIELD.
        All backends fall back to :data:`schema_contract.NODE_LABELS`
        plus supplementary labels on failure.
        """
        # Prefer db_manager.get_backend_type(); fall back to driver, then neo4j
        backend = get_backend_type(self.driver, self._db_manager)

        if backend in ("kuzudb", "ladybugdb"):
            # NOTE: Full node scan required because SHOW TABLES is unavailable
            # in KuzuDB ≤ 0.11. Acceptable for delete_repository (low-frequency).
            try:
                backend = get_backend_type(self.driver, self._db_manager)
                def _work(session):
                    result = session.run(
                        "MATCH (n) RETURN DISTINCT label(n) AS lbl"
                    )
                    labels = sorted(
                        {record[0] for record in result if record[0] is not None}
                    )
                    if labels:
                        return labels
                return execute_read_operation(self.driver, backend, _work)
            except Exception as e:
                info_logger(
                    f"[DELETE] label discovery failed for {backend} "
                    f"({e}), using fallback list"
                )

        elif backend in ("neo4j", "nornic"):
            try:
                backend = get_backend_type(self.driver, self._db_manager)
                def _work(session):
                    label_records = session.run(
                        "CALL db.labels() YIELD label RETURN label"
                    )
                    return sorted({record["label"] for record in label_records})
                return execute_read_operation(self.driver, backend, _work)
            except Exception as e:
                info_logger(
                    f"[DELETE] CALL db.labels() failed for {backend} "
                    f"({e}), using fallback list"
                )

        elif backend in ("falkordb", "falkordb-remote"):
            try:
                backend = get_backend_type(self.driver, self._db_manager)
                def _work(session):
                    label_records = session.run("CALL db.labels()")
                    return sorted({record["label"] for record in label_records})
                return execute_read_operation(self.driver, backend, _work)
            except Exception as e:
                info_logger(
                    f"[DELETE] CALL db.labels() failed for {backend} "
                    f"({e}), using fallback list"
                )

        # Fallback: canonical NODE_LABELS from schema_contract + supplementary
        # labels that may exist in the graph from dynamic indexing paths.
        return sorted(NODE_LABELS | {
            "ExternalClass", "ExternalFunction",
            "EnumValue", "Namespace", "TypeAlias", "Decorator",
            "Method", "Endpoint", "OrmMapping", "Query",
            "SpringDataRepository", "Mixin", "Extension", "Object",
        })

    def add_repository_to_graph(self, repo_path: Path, is_dependency: bool = False) -> None:
        repo_name = repo_path.name
        # Use _normalize_path so the stored path always uses forward slashes,
        # making STARTS WITH queries work on Windows too.
        repo_path_str = _normalize_path(repo_path)

        commit_hash = get_repo_commit_hash(repo_path.resolve())
        indexed_at = datetime.now(timezone.utc).isoformat()

        backend = get_backend_type(self.driver, self._db_manager)
        def _work(session):
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
            if commit_hash:
                session.run(
                    """
                    MATCH (r:Repository {path: $path})
                    SET r.commit_hash = $commit_hash
                    """,
                    path=repo_path_str,
                    commit_hash=commit_hash,
                )

        execute_write_operation(self.driver, backend, _work)
    def add_file_to_graph(
        self,
        file_data: Dict[str, Any],
        repo_name: str,
        imports_map: dict,
        repo_path_str: Optional[str] = None,
    ) -> None:
        # Normalize: always store with forward slashes
        file_path_str = _normalize_path(file_data["path"])
        file_name = Path(file_path_str).name
        is_dependency = file_data.get("is_dependency", False)
        lang = file_data.get("lang")

        backend = get_backend_type(self.driver, self._db_manager)
        def _work(session):
            if repo_path_str:
                resolved_repo_str = _normalize_path(repo_path_str)
            else:
                repo_result = session.run(
                    "MATCH (r:Repository {path: $repo_path}) RETURN r.path as path",
                    repo_path=_normalize_path(file_data["repo_path"]),
                ).single()
                resolved_repo_str = (
                    repo_result["path"] if repo_result else _normalize_path(file_data["repo_path"])
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
                # Normalize directory paths too
                current_path_str = _normalize_path(Path(parent_path) / part)
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
                (file_data.get("enum_members", []), "EnumMember"),
            ]

            params_batch: List[Dict[str, Any]] = []
            class_fn_batch: List[Dict[str, Any]] = []
            enum_member_batch: List[Dict[str, Any]] = []
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
                    if label == "EnumMember":
                        enum_member_batch.append(
                            {
                                "class_name": item.get("enum_name"),
                                "class_line": item.get("enum_line_number", -1),
                                "member_name": item["name"],
                            }
                        )
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
                            outer_ctx = item.get("context")
                            outer_name = (
                                outer_ctx[0]
                                if isinstance(outer_ctx, (tuple, list)) and outer_ctx
                                else outer_ctx
                            )
                            nested_fn_batch.append(
                                {
                                    "outer": outer_name,
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
                    SET p.name = row.arg_name, p.path = $file_path, p.function_line_number = row.line_number
                    MERGE (fn)-[:HAS_PARAMETER]->(p)
                """,
                    batch=unique_params,
                    file_path=file_path_str,
                )

            if enum_member_batch:
                for label in ("Class", "Enum"):
                    try:
                        session.run(
                            f"""
                            UNWIND $batch AS row
                            MATCH (c:{label} {{name: row.class_name, path: $file_path}})
                            MATCH (m:EnumMember {{name: row.member_name, path: $file_path}})
                            WHERE row.class_line < 0 OR c.line_number = row.class_line
                            MERGE (c)-[:CONTAINS]->(m)
                            """,
                            batch=enum_member_batch,
                            file_path=file_path_str,
                        )
                    except Exception as e:
                        if _is_binder_exception(e):
                            continue
                        raise e

            if class_fn_batch:
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
                    module_name = (
                        imp.get("name")
                        or imp.get("source")
                        or imp.get("full_import_name")
                    )
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
                    MERGE (f)-[r:IMPORTS {line_number: row.line_number}]->(m)
                    SET r.imported_name = row.imported_name,
                        r.alias = row.alias
                """,
                    batch=js_imports,
                    file_path=file_path_str,
                )

            if other_imports:
                other_imports = sort_import_rows_for_metadata(other_imports)
                session.run(
                    """
                    UNWIND $batch AS row
                    MATCH (f:File {path: $file_path})
                    MERGE (m:Module {name: row.name})
                    SET m.lang = coalesce(m.lang, row.lang),
                        m.full_import_name = coalesce(m.full_import_name, row.full_import_name)
                    MERGE (f)-[r:IMPORTS {line_number: row.line_number}]->(m)
                    SET r.alias = coalesce(row.alias, ""),
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

        execute_write_operation(self.driver, backend, _work)
    def add_minimal_file_node(
        self, file_path: Path, repo_path: Path, is_dependency: bool = False
    ) -> None:
        # Normalize both paths for cross-platform consistency
        file_path_str = _normalize_path(file_path)
        file_name = file_path.name
        repo_name = repo_path.name
        repo_path_str = _normalize_path(repo_path)

        backend = get_backend_type(self.driver, self._db_manager)
        def _work(session):
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
                # Normalize directory node paths too
                current_path_str = _normalize_path(Path(parent_path) / part)

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

        execute_write_operation(self.driver, backend, _work)
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
        fn_to_param: List[Dict] = None,
        fn_to_file: List[Dict] = None,
    ) -> None:
        batch_size = 1000

        backend = get_backend_type(self.driver, self._db_manager)
        calls_keyword = "CREATE" if backend in ("neo4j", "nornic") else "MERGE"
        # Neo4j-only fast/slow MATCH split (PR #1192 perf). Embedded backends keep the
        # unified name+path MATCH + line WHERE filter for parity with FalkorDB/Neo4j.
        use_fast_slow_split = backend in ("neo4j", "nornic")
        info_logger(
            f"[CALLS] backend={backend}, using {calls_keyword} for CALLS edges"
            + (", fast/slow MATCH split" if use_fast_slow_split else ", unified MATCH")
        )

        fn_to_fn = fn_to_fn or []
        fn_to_class = fn_to_class or []
        fn_to_interface = fn_to_interface or []
        fn_to_object = fn_to_object or []
        file_to_fn = file_to_fn or []
        file_to_class = file_to_class or []
        file_to_interface = file_to_interface or []
        file_to_object = file_to_object or []
        fn_to_param = fn_to_param or []
        fn_to_file = fn_to_file or []

        queries = [
            (fn_to_fn, "Function", "Function"),
            (fn_to_class, "Function", "Class"),
            (fn_to_interface, "Function", "Interface"),
            (fn_to_object, "Function", "Object"),
            (fn_to_param, "Function", "Parameter"),
            (fn_to_file, "Function", "File"),
            (file_to_fn, "File", "Function"),
            (file_to_class, "File", "Class"),
            (file_to_interface, "File", "Interface"),
            (file_to_object, "File", "Object"),
        ]
        def _work(session):
            for batch_data, caller_label, called_label in queries:
                if not batch_data:
                    continue

                sanitized_batch = []
                for row in batch_data:
                    if not isinstance(row, dict) or not row.get("caller_file_path") or not row.get("called_name"):
                        continue

                    if row.get("called_line_number") is False or row.get("called_context") is False:
                        continue

                    row = dict(row)
                    if "confidence" not in row or row["confidence"] is None:
                        row["confidence"] = 0.0
                    if "resolution_tier" not in row or row["resolution_tier"] is None:
                        row["resolution_tier"] = -1
                    if "confidence_label" not in row or row["confidence_label"] is None:
                        row["confidence_label"] = "EXTRACTED"

                    val = row.get("called_line_number")
                    if "called_line_number" not in row or not isinstance(val, int):
                        try:
                            row["called_line_number"] = int(val or 0)
                        except (ValueError, TypeError):
                            row["called_line_number"] = 0

                    if "called_context" not in row or row["called_context"] is None:
                        row["called_context"] = ""
                    if "line_number" not in row or row["line_number"] is None:
                        row["line_number"] = 0

                    import json as _json
                    raw_args = row.get("args") or []
                    if isinstance(raw_args, list):
                        row["args_key"] = _json.dumps(raw_args, sort_keys=False)
                    else:
                        row["args_key"] = str(raw_args)

                    sanitized_batch.append(row)

                if not sanitized_batch:
                    continue

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

                called_context_clause = _called_context_clause(called_label)

                caller_match = (
                    f"MATCH (caller:File {{path: row.caller_file_path}})"
                    if caller_label == "File"
                    else f"MATCH (caller:`{caller_label}` {{name: row.caller_name, path: row.caller_file_path, line_number: row.caller_line_number}})"
                )
                set_clause = """
                        SET call.args = row.args
                        SET call.confidence = row.confidence
                        SET call.resolution_tier = row.resolution_tier
                        SET call.confidence_label = row.confidence_label"""
                create_clause = f"{calls_keyword} (caller)-[call:CALLS {{line_number: row.line_number, full_call_name: row.full_call_name, args_key: row.args_key}}]->(called)"

                def _run_call_batch(q: str, sub_batch: List[Dict[str, Any]]) -> None:
                    if not sub_batch:
                        return
                    captured_q, captured_b = q, sub_batch

                    def _batch_work(tx, _q=captured_q, _b=captured_b):
                        tx.run(_q, batch=_b)

                    try:
                        if hasattr(session, "execute_write"):
                            session.execute_write(_batch_work)
                        elif hasattr(session, "write_transaction"):
                            session.write_transaction(_batch_work)
                        else:
                            session.run(q, batch=sub_batch)
                    except Exception as e:
                        if _is_binder_exception(e):
                            return
                        raise e

                t0 = time.time()
                total = len(sanitized_batch)

                if use_fast_slow_split:
                    if called_label == "Parameter":
                        q_with_line = f"""
                            UNWIND $batch AS row
                            {caller_match}
                            MATCH (called:Parameter {{name: row.called_name, path: row.called_file_path, function_line_number: row.called_line_number}})
                            {create_clause}{set_clause}
                        """
                        q_without_line = q_with_line
                    elif called_label == "File":
                        q_with_line = f"""
                            UNWIND $batch AS row
                            {caller_match}
                            MATCH (called:File {{path: row.called_file_path}})
                            {create_clause}{set_clause}
                        """
                        q_without_line = q_with_line
                    else:
                        q_with_line = f"""
                            UNWIND $batch AS row
                            {caller_match}
                            MATCH (called:`{called_label}` {{name: row.called_name, path: row.called_file_path, line_number: row.called_line_number}})
                            {"WHERE " + called_context_clause.lstrip("AND ") if called_context_clause else ""}
                            {create_clause}{set_clause}
                        """
                        q_without_line = f"""
                            UNWIND $batch AS row
                            {caller_match}
                            MATCH (called:`{called_label}` {{name: row.called_name, path: row.called_file_path}})
                            {"WHERE " + called_context_clause.lstrip("AND ") if called_context_clause else ""}
                            {create_clause}{set_clause}
                        """

                    fast_total = sum(1 for r in sanitized_batch if r.get("called_line_number", 0) > 0)
                    slow_total = total - fast_total
                    info_logger(
                        f"[CALLS] {caller_label}-to-{called_label}: {total} edges — "
                        f"fast path (line known): {fast_total} ({100*fast_total//total if total else 0}%), "
                        f"slow path: {slow_total} ({100*slow_total//total if total else 0}%)"
                    )
                    for i in range(0, total, batch_size):
                        batch = sanitized_batch[i : i + batch_size]
                        batch_with_line = [r for r in batch if r.get("called_line_number", 0) > 0]
                        batch_without_line = [r for r in batch if r.get("called_line_number", 0) <= 0]
                        for q, sub_batch in ((q_with_line, batch_with_line), (q_without_line, batch_without_line)):
                            _run_call_batch(q, sub_batch)
                        written_so_far = min(i + batch_size, total)
                        info_logger(
                            f"[CALLS] {caller_label}-to-{called_label}: "
                            f"{written_so_far}/{total} edges written ({time.time()-t0:.1f}s elapsed)"
                        )
                else:
                    line_where = (
                        "WHERE (row.called_line_number <= 0 OR called.line_number = row.called_line_number)"
                    )
                    if called_context_clause:
                        line_where += f" {called_context_clause}"

                    if called_label == "Parameter":
                        q_unified = f"""
                            UNWIND $batch AS row
                            {caller_match}
                            MATCH (called:Parameter {{name: row.called_name, path: row.called_file_path, function_line_number: row.called_line_number}})
                            {create_clause}{set_clause}
                        """
                    elif called_label == "File":
                        q_unified = f"""
                            UNWIND $batch AS row
                            {caller_match}
                            MATCH (called:File {{path: row.called_file_path}})
                            {create_clause}{set_clause}
                        """
                    else:
                        q_unified = f"""
                            UNWIND $batch AS row
                            {caller_match}
                            MATCH (called:`{called_label}` {{name: row.called_name, path: row.called_file_path}})
                            {line_where}
                            {create_clause}{set_clause}
                        """

                    for i in range(0, total, batch_size):
                        _run_call_batch(q_unified, sanitized_batch[i : i + batch_size])
                        written_so_far = min(i + batch_size, total)
                        info_logger(
                            f"[CALLS] {caller_label}-to-{called_label}: "
                            f"{written_so_far}/{total} edges written ({time.time()-t0:.1f}s elapsed)"
                        )

                info_logger(f"[CALLS] {caller_label}-to-{called_label}: {total} edges written in {time.time()-t0:.1f}s")

        with self.driver.session() as session:
            _work(session)
        info_logger("[CALLS] All relationships processed.")

    def _create_csharp_inheritance_and_interfaces(
        self, session: Any, file_data: Dict[str, Any], imports_map: dict
    ) -> None:
        if file_data.get("lang") != "c_sharp":
            return

        caller_file_path = _normalize_path(file_data["path"])

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

                    for iface in file_data.get("interfaces", []):
                        if iface["name"] == base_name:
                            is_interface = True
                            break

                    if base_name in imports_map:
                        possible_paths = imports_map[base_name]
                        if len(possible_paths) > 0:
                            pass

                    base_index = type_item["bases"].index(base_str)

                    if is_interface or (base_index > 0 and type_label == "Class"):
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
        backend = get_backend_type(self.driver, self._db_manager)
        def _work(session):
            internal_batch = [r for r in inheritance_batch if r.get("resolved_parent_file_path") != "__external__"]
            external_batch = [r for r in inheritance_batch if r.get("resolved_parent_file_path") == "__external__"]

            labels = ("Class", "Trait", "Interface", "Struct", "Enum", "Union", "Record", "Mixin", "Extension", "Module", "Object", "Variable")
            for child_label in labels:
                child_cypher = _cypher_label(child_label, backend)
                for parent_label in labels:
                    parent_cypher = _cypher_label(parent_label, backend)
                    try:
                        session.run(
                            f"""
                            UNWIND $batch AS row
                            MATCH (child:{child_cypher} {{name: row.child_name, path: row.path}})
                            MATCH (parent:{parent_cypher} {{name: row.parent_name, path: row.resolved_parent_file_path}})
                            MERGE (child)-[r:INHERITS]->(parent)
                            SET r.confidence_label = coalesce(row.confidence_label, 'EXTRACTED')
                        """,
                            batch=internal_batch,
                        )
                    except Exception as e:
                        if _is_binder_exception(e):
                            continue
                        raise e

            for child_label in labels:
                child_cypher = _cypher_label(child_label, backend)
                try:
                    session.run(
                        f"""
                        UNWIND $batch AS row
                        MATCH (child:{child_cypher} {{name: row.child_name, path: row.path}})
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

        execute_write_operation(self.driver, backend, _work)
        info_logger(f"[INHERITS] Complete: {len(inheritance_batch)} inheritance links processed.")

    def write_implements_links(self, implements_batch: List[Dict[str, Any]]) -> None:
        if not implements_batch:
            return

        backend = get_backend_type(self.driver, self._db_manager)

        def _work(session):
            for row in implements_batch:
                child_label = _cypher_label(row.get("child_label", "Struct"), backend)
                parent_label = _cypher_label(row.get("parent_label", "Interface"), backend)
                try:
                    session.run(
                        f"""
                        MATCH (child:{child_label} {{name: $child_name, path: $path}})
                        MATCH (parent:{parent_label} {{name: $parent_name, path: $resolved_parent_file_path}})
                        MERGE (child)-[r:IMPLEMENTS]->(parent)
                        SET r.confidence_label = coalesce($confidence_label, 'INFERRED')
                        """,
                        child_name=row["child_name"],
                        path=row["path"],
                        parent_name=row["parent_name"],
                        resolved_parent_file_path=row["resolved_parent_file_path"],
                        confidence_label=row.get("confidence_label", "INFERRED"),
                    )
                except Exception as e:
                    if _is_binder_exception(e):
                        continue
                    raise e

        execute_write_operation(self.driver, backend, _work)
        info_logger(f"[IMPLEMENTS] Complete: {len(implements_batch)} implementation links processed.")

    def write_partial_of_links(self, partial_of_batch: List[Dict[str, Any]]) -> None:
        if not partial_of_batch:
            return

        backend = get_backend_type(self.driver, self._db_manager)

        def _work(session):
            for row in partial_of_batch:
                child_label = _cypher_label(row.get("child_label", "Class"), backend)
                parent_label = _cypher_label(row.get("parent_label", "Class"), backend)
                try:
                    session.run(
                        f"""
                        MATCH (child:{child_label} {{name: $child_name, path: $path}})
                        MATCH (parent:{parent_label} {{name: $parent_name, path: $resolved_parent_file_path}})
                        MERGE (child)-[r:PARTIAL_OF]->(parent)
                        SET r.confidence_label = coalesce($confidence_label, 'INFERRED')
                        """,
                        child_name=row["child_name"],
                        path=row["path"],
                        parent_name=row["parent_name"],
                        resolved_parent_file_path=row["resolved_parent_file_path"],
                        confidence_label=row.get("confidence_label", "INFERRED"),
                    )
                except Exception as e:
                    if _is_binder_exception(e):
                        continue
                    raise e

        execute_write_operation(self.driver, backend, _work)
        info_logger(f"[PARTIAL_OF] Complete: {len(partial_of_batch)} partial class links processed.")

    def write_part_of_links(self, part_of_batch: List[Dict[str, Any]]) -> None:
        if not part_of_batch:
            return

        backend = get_backend_type(self.driver, self._db_manager)

        def _work(session):
            for row in part_of_batch:
                try:
                    session.run(
                        """
                        MATCH (child:File {path: $child_path})
                        MATCH (parent:File {path: $parent_path})
                        MERGE (child)-[r:PART_OF]->(parent)
                        """,
                        child_path=row["child_path"],
                        parent_path=row["parent_path"],
                    )
                except Exception as e:
                    if _is_binder_exception(e):
                        continue
                    raise e

        execute_write_operation(self.driver, backend, _work)
        info_logger(f"[PART_OF] Complete: {len(part_of_batch)} library part links processed.")

    def write_decorated_by_links(self, decorated_by_batch: List[Dict[str, Any]]) -> None:
        if not decorated_by_batch:
            return

        backend = get_backend_type(self.driver, self._db_manager)

        def _work(session):
            for row in decorated_by_batch:
                try:
                    session.run(
                        """
                        MATCH (decorated:Function {
                            name: $decorated_name,
                            path: $decorated_path,
                            line_number: $decorated_line
                        })
                        WHERE $decorated_context = "" OR decorated.context = $decorated_context
                        MATCH (decorator:Function {
                            name: $decorator_name,
                            path: $decorator_path
                        })
                        MERGE (decorated)-[r:DECORATED_BY]->(decorator)
                        SET r.line_number = $line_number
                        """,
                        decorated_name=row["decorated_name"],
                        decorated_path=row["decorated_path"],
                        decorated_line=row["decorated_line"],
                        decorated_context=row.get("decorated_context", ""),
                        decorator_name=row["decorator_name"],
                        decorator_path=row["decorator_path"],
                        line_number=row.get("line_number", row["decorated_line"]),
                    )
                except Exception as e:
                    if _is_binder_exception(e):
                        continue
                    raise e

        execute_write_operation(self.driver, backend, _work)
        info_logger(f"[DECORATED_BY] Complete: {len(decorated_by_batch)} decorator links processed.")

    def write_metaclass_links(self, metaclass_batch: List[Dict[str, Any]]) -> None:
        if not metaclass_batch:
            return

        backend = get_backend_type(self.driver, self._db_manager)

        def _work(session):
            for row in metaclass_batch:
                try:
                    session.run(
                        """
                        MATCH (child:Class {name: $child_name, path: $path})
                        MATCH (parent:Class {name: $parent_name, path: $resolved_parent_file_path})
                        MERGE (child)-[r:METACLASS]->(parent)
                        SET r.line_number = $line_number
                        SET r.confidence_label = coalesce($confidence_label, 'EXTRACTED')
                        """,
                        child_name=row["child_name"],
                        path=row["path"],
                        parent_name=row["parent_name"],
                        resolved_parent_file_path=row["resolved_parent_file_path"],
                        line_number=row.get("line_number", 0),
                        confidence_label=row.get("confidence_label", "EXTRACTED"),
                    )
                except Exception as e:
                    if _is_binder_exception(e):
                        continue
                    raise e

        execute_write_operation(self.driver, backend, _work)
        info_logger(f"[METACLASS] Complete: {len(metaclass_batch)} metaclass links processed.")

    def write_companion_of_links(self, companion_batch: List[Dict[str, Any]]) -> None:
        if not companion_batch:
            return

        backend = get_backend_type(self.driver, self._db_manager)

        def _work(session):
            for row in companion_batch:
                try:
                    session.run(
                        """
                        MATCH (companion:Object {
                            name: $companion_name,
                            path: $companion_path,
                            line_number: $companion_line
                        })
                        MATCH (owner:Class {
                            name: $owner_name,
                            path: $owner_path,
                            line_number: $owner_line
                        })
                        MERGE (companion)-[r:COMPANION_OF]->(owner)
                        """,
                        companion_name=row["companion_name"],
                        companion_path=row["companion_path"],
                        companion_line=row["companion_line"],
                        owner_name=row["owner_name"],
                        owner_path=row["owner_path"],
                        owner_line=row["owner_line"],
                    )
                except Exception as e:
                    if _is_binder_exception(e):
                        continue
                    raise e

        execute_write_operation(self.driver, backend, _work)
        info_logger(f"[COMPANION_OF] Complete: {len(companion_batch)} companion links processed.")

    def write_embeds_links(self, embeds_batch: List[Dict[str, Any]]) -> None:
        if not embeds_batch:
            return

        backend = get_backend_type(self.driver, self._db_manager)

        def _work(session):
            for row in embeds_batch:
                try:
                    session.run(
                        """
                        MATCH (child:Struct {name: $child_name, path: $path})
                        MATCH (parent:Struct {name: $parent_name, path: $resolved_parent_file_path})
                        MERGE (child)-[r:EMBEDS]->(parent)
                        SET r.line_number = $line_number
                        """,
                        child_name=row["child_name"],
                        path=row["path"],
                        parent_name=row["parent_name"],
                        resolved_parent_file_path=row["resolved_parent_file_path"],
                        line_number=row.get("line_number", 0),
                    )
                except Exception as e:
                    if _is_binder_exception(e):
                        continue
                    raise e

        execute_write_operation(self.driver, backend, _work)
        info_logger(f"[EMBEDS] Complete: {len(embeds_batch)} embed links processed.")

    def write_scip_call_edges(
        self, files_data: Dict[str, Any], name_from_symbol: Callable[[str], str]
    ) -> None:
        backend = get_backend_type(self.driver, self._db_manager)
        def _work(session):
            for file_data in files_data.values():
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

        execute_write_operation(self.driver, backend, _work)
    def delete_file_from_graph(self, path: str) -> None:
        file_path_str = _normalize_path(path)
        backend = get_backend_type(self.driver, self._db_manager)
        def _work(session):
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
                OPTIONAL MATCH (element)-[:HAS_PARAMETER]->(p:Parameter)
                DETACH DELETE f, element, p
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

        execute_write_operation(self.driver, backend, _work)
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
        # Normalize the incoming repo path so STARTS WITH matches stored paths
        repo_path_str = _normalize_path(repo_path_str)

        _cpp_exts = ('.cpp', '.cc', '.cxx', '.c++', '.C')
        ext_conditions = ' OR '.join(f'fn.path ENDS WITH "{ext}"' for ext in _cpp_exts)

        container_labels = ("Class", "Struct", "Module")
        backend = get_backend_type(self.driver, self._db_manager)
        def _work(session):
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
                    warning_logger(f"Failed to link C++ methods for label {clab}: {e}")

        execute_write_operation(self.driver, backend, _work)
    def write_spring_inject_links(self, inject_batch: List[Dict[str, Any]]) -> None:
        """Create INJECTS edges: injector Class -> injected Class (via @Autowired / @Inject)."""
        if not inject_batch:
            return
        info_logger(f"[SPRING] Writing {len(inject_batch)} INJECTS edges...")
        batch_size = 500
        backend = get_backend_type(self.driver, self._db_manager)
        def _work(session):
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
        execute_write_operation(self.driver, backend, _work)
        info_logger("[SPRING] INJECTS edges written.")

    def write_spring_endpoint_properties(self, endpoint_batch: List[Dict[str, Any]]) -> None:
        """Set http_method / http_path / transactional properties on Function nodes."""
        if not endpoint_batch:
            return
        info_logger(f"[SPRING] Updating {len(endpoint_batch)} endpoint function properties...")
        batch_size = 500
        backend = get_backend_type(self.driver, self._db_manager)
        def _work(session):
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
        execute_write_operation(self.driver, backend, _work)
        info_logger("[SPRING] Endpoint properties updated.")

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

        # Normalize repo path for consistent STARTS WITH matching
        repo_path_str = _normalize_path(repo_path_str)

        info_logger(f"[MAVEN] Writing {len(modules)} modules, "
                    f"{len(inter_module_deps)} inter-module deps, "
                    f"{len(external_libs)} external libs...")

        batch_size = 200
        backend = get_backend_type(self.driver, self._db_manager)
        def _work(session):
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

        execute_write_operation(self.driver, backend, _work)
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

        # Normalize repo path for consistent STARTS WITH matching
        repo_path_str = _normalize_path(repo_path_str)

        info_logger(f"[GRADLE] Writing {len(modules)} modules, "
                    f"{len(inter_module_deps)} inter-module deps, "
                    f"{len(external_libs)} external libs...")

        batch_size = 200
        backend = get_backend_type(self.driver, self._db_manager)
        def _work(session):
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

        execute_write_operation(self.driver, backend, _work)
        info_logger("[GRADLE] Build graph written.")

    def write_datasource_graph(self, ingested: Dict[str, Any]) -> None:
        """Write Datasource / DbTable / DbColumn / RedisKeyPattern nodes and edges."""
        ds = ingested.get("datasource", {})
        if not ds:
            return
        ds_name = ds["name"]
        ds_kind = ds.get("kind", "unknown")

        backend = get_backend_type(self.driver, self._db_manager)
        def _work(session):
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

            tables = ingested.get("tables", [])
            batch_size = 500

            for i in range(0, len(tables), batch_size):
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

            columns = ingested.get("columns", [])
            for i in range(0, len(columns), batch_size):
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

            key_patterns = ingested.get("key_patterns", [])
            for i in range(0, len(key_patterns), batch_size):
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
            
            return len(tables), len(columns), len(key_patterns)

        tables_len, columns_len, key_patterns_len = execute_write_operation(self.driver, backend, _work)
        
        info_logger(f"[DATASOURCE] Written Datasource node: {ds_name} ({ds_kind})")
        if tables_len:
            info_logger(f"[DATASOURCE] Written {tables_len} DbTable nodes for {ds_name}")
        if columns_len:
            info_logger(f"[DATASOURCE] Written {columns_len} DbColumn nodes for {ds_name}")
        if key_patterns_len:
            info_logger(f"[DATASOURCE] Written {key_patterns_len} RedisKeyPattern nodes for {ds_name}")

    def write_orm_mappings(self, orm_batch: List[Dict[str, Any]]) -> None:
        """Write MAPS_TO edges from Class → DbTable (JPA, Cassandra, Redis)."""
        class_table = [r for r in orm_batch if r.get("kind") == "class_table"]
        if not class_table:
            return

        batch_size = 500
        backend = get_backend_type(self.driver, self._db_manager)
        def _work(session):
            for i in range(0, len(class_table), batch_size):
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
        execute_write_operation(self.driver, backend, _work)
        info_logger(f"[ORM] Written {len(class_table)} MAPS_TO edges")

    def write_query_links(self, query_batch: List[Dict[str, Any]]) -> None:
        """Write READS / WRITES edges from Function → DbTable."""
        method_queries = [r for r in query_batch if r.get("kind") == "method_query" and r.get("db_tables")]
        if not method_queries:
            return

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
        backend = get_backend_type(self.driver, self._db_manager)
        def _work(session):
            for op in ("READS", "WRITES"):
                op_edges = [e for e in edges if e["operation"] == op]
                for i in range(0, len(op_edges), batch_size):
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
        execute_write_operation(self.driver, backend, _work)
        info_logger(f"[ORM] Written {len(edges)} READS/WRITES query edges")

    def write_mybatis_links(self, mybatis_batch: List[Dict[str, Any]]) -> None:
        """Write READS / WRITES edges from Function → DbTable for MyBatis XML mappers."""
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
        backend = get_backend_type(self.driver, self._db_manager)
        def _work(session):
            local_written = 0
            for op in ("READS", "WRITES"):
                op_edges = [e for e in edges if e["operation"] == op]
                if not op_edges:
                    continue
                for i in range(0, len(op_edges), batch_size):
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
                    local_written += len(op_edges[i : i + batch_size])
            return local_written
        written = execute_write_operation(self.driver, backend, _work)
        info_logger(f"[MYBATIS] Written {written} READS/WRITES MyBatis edges")

    def write_spring_data_repo_links(self, orm_batch: List[Dict[str, Any]]) -> None:
        """Write READS/WRITES edges for Spring Data repository derived-query methods."""
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
        backend = get_backend_type(self.driver, self._db_manager)
        def _work(session):
            local_written = 0
            for op in ("READS", "WRITES"):
                op_edges = [e for e in edges if e["operation"] == op]
                if not op_edges:
                    continue
                for i in range(0, len(op_edges), batch_size):
                    session.run(
                        f"""
                        UNWIND $batch AS q
                        MATCH (fn:Function {{name: q.method_name, path: q.method_path}})
                        MATCH (entity:Class {{name: q.entity_class}})-[:MAPS_TO]->(tbl:DbTable)
                        MERGE (fn)-[:{op} {{line_number: q.line_number, source: 'spring_data'}}]->(tbl)
                        """,
                        batch=op_edges[i : i + batch_size],
                    )
                    local_written += len(op_edges[i : i + batch_size])
            return local_written
        written = execute_write_operation(self.driver, backend, _work)
        info_logger(f"[SPRING_DATA] Written {written} READS/WRITES derived-query edges")

    def delete_repository_from_graph(self, repo_path: str) -> bool:
        # Normalize to forward slashes — paths are always stored normalized.
        # The old .replace("\\", "/") band-aid is replaced by _normalize_path
        # which uses Path.resolve().as_posix() for consistent cross-platform output.
        # See: https://github.com/CodeGraphContext/CodeGraphContext/issues/1080
        repo_path_str = _normalize_path(repo_path)
        path_prefix = _normalize_prefix(repo_path)

        backend = get_backend_type(self.driver, self._db_manager)

        def _existence_check(session):
            result = session.run(
                "MATCH (r:Repository {path: $path}) RETURN count(r) as cnt",
                path=repo_path_str,
            ).single()
            return bool(result and result["cnt"] > 0)

        found = execute_write_operation(self.driver, backend, _existence_check)

        # Backward-compat: old CGC versions stored Windows paths with backslashes.
        if not found:
            native = str(Path(repo_path).resolve())
            if native != repo_path_str:

                def _legacy_check(session):
                    result = session.run(
                        "MATCH (r:Repository {path: $path}) RETURN count(r) as cnt",
                        path=native,
                    ).single()
                    return bool(result and result["cnt"] > 0)

                if execute_write_operation(self.driver, backend, _legacy_check):
                    found = True
                    info_logger(f"[DELETE] Found legacy backslash repo entry: {native}")
                    repo_path_str = native
                    path_prefix = native + os.sep

        if not found:
            warning_logger(f"Attempted to delete non-existent repository: {repo_path}")
            return False

        for rel_type in ("CALLS", "INHERITS", "IMPORTS", "INCLUDES"):
            while True:
                backend = get_backend_type(self.driver, self._db_manager)
                def _work(session):
                    result = session.run(
                        f"MATCH (a)-[r:{rel_type}]->(b) "
                        "WHERE a.path STARTS WITH $prefix OR a.path = $path "
                        "OR b.path STARTS WITH $prefix OR b.path = $path "
                        "WITH r LIMIT 5000 DELETE r RETURN count(r) AS deleted",
                        prefix=path_prefix,
                        path=repo_path_str,
                    ).single()
                    return result["deleted"] if result else 0
                deleted = execute_write_operation(self.driver, backend, _work)
                if deleted == 0:
                    break
                info_logger(f"[DELETE] Removed {deleted} {rel_type} rels for {repo_path_str}")

        while True:
            backend = get_backend_type(self.driver, self._db_manager)
            def _work(session):
                result = session.run(
                    "MATCH (a)-[r:CONTAINS]->(b) "
                    "WHERE a.path STARTS WITH $prefix OR a.path = $path "
                    "WITH r LIMIT 10000 DELETE r RETURN count(r) AS deleted",
                    prefix=path_prefix,
                    path=repo_path_str,
                ).single()
                return result["deleted"] if result else 0
            deleted = execute_write_operation(self.driver, backend, _work)
            if deleted == 0:
                break
            info_logger(f"[DELETE] Removed {deleted} CONTAINS rels for {repo_path_str}")

        all_labels = self._get_all_node_labels()

        for label in all_labels:
            while True:
                backend = get_backend_type(self.driver, self._db_manager)
                def _work(session):
                    result = session.run(
                        f"MATCH (n:{label}) WHERE n.path STARTS WITH $prefix OR n.path = $path "
                        "WITH n LIMIT 10000 DETACH DELETE n RETURN count(n) AS deleted",
                        prefix=path_prefix,
                        path=repo_path_str,
                    ).single()
                    return result["deleted"] if result else 0
                deleted = execute_write_operation(self.driver, backend, _work)
                if deleted == 0:
                    break
                info_logger(f"[DELETE] Removed {deleted} {label} nodes for {repo_path_str}")

        self._purge_dangling_pathless_nodes()

        backend = get_backend_type(self.driver, self._db_manager)

        def _delete_repo_node(session):
            session.run("""
MATCH (r:Repository {path: $path})
OPTIONAL MATCH (r)-[:CONTAINS*]->(n)
DETACH DELETE r, n
""", path=repo_path_str)
        execute_write_operation(self.driver, backend, _delete_repo_node)
        info_logger(f"Deleted repository and its contents from graph: {repo_path_str}")
        return True

    def _purge_dangling_pathless_nodes(self) -> None:
        """Remove shared pathless nodes (e.g. imported Module headers) left without references."""
        dangling_queries = [
            (
                "MATCH (m:Module) WHERE NOT ()-[:IMPORTS|INCLUDES]->(m) "
                "WITH m LIMIT 5000 DETACH DELETE m RETURN count(m) AS deleted"
            ),
            (
                "MATCH (n:ExternalClass) WHERE NOT ()-[]->(n) "
                "WITH n LIMIT 5000 DETACH DELETE n RETURN count(n) AS deleted"
            ),
            (
                "MATCH (n:ExternalFunction) WHERE NOT ()-[]->(n) "
                "WITH n LIMIT 5000 DETACH DELETE n RETURN count(n) AS deleted"
            ),
            (
                "MATCH (p:Parameter) WHERE NOT ()-[:HAS_PARAMETER]->(p) "
                "WITH p LIMIT 5000 DETACH DELETE p RETURN count(p) AS deleted"
            ),
        ]
        for query in dangling_queries:
            try:
                while True:
                    with self.driver.session() as session:
                        result = session.run(query).single()
                        deleted = result["deleted"] if result else 0
                    if deleted == 0:
                        break
                    info_logger(f"[DELETE] Purged {deleted} dangling pathless nodes")
            except Exception as e:
                if _is_binder_exception(e):
                    continue
                raise

    def get_caller_file_paths(self, file_path_str: str) -> set:
        backend = get_backend_type(self.driver, self._db_manager)
        def _work(session):
            result = session.run(
                "MATCH (caller)-[:CALLS]->(callee) "
                "WHERE callee.path = $path "
                "RETURN DISTINCT coalesce(caller.path, '') AS p",
                path=file_path_str,
            )
            return {r["p"] for r in result if r["p"] and r["p"] != file_path_str}

        return execute_read_operation(self.driver, backend, _work)

    def get_repo_file_paths(self, repo_path: Path) -> set:
        """Return every indexed File path below a repository root."""
        prefix = _normalize_prefix(repo_path)
        backend = get_backend_type(self.driver, self._db_manager)

        def _work(session):
            result = session.run(
                "MATCH (f:File) WHERE f.path STARTS WITH $prefix RETURN f.path AS p",
                prefix=prefix,
            )
            return {record["p"] for record in result if record["p"]}

        return execute_read_operation(self.driver, backend, _work)

    def get_inheritance_neighbor_paths(self, file_path_str: str) -> set:
        backend = get_backend_type(self.driver, self._db_manager)
        def _work(session):
            result = session.run(
                "MATCH (a)-[:INHERITS]->(b) "
                "WHERE a.path = $path OR b.path = $path "
                "RETURN DISTINCT CASE WHEN a.path = $path THEN b.path ELSE a.path END AS p",
                path=file_path_str,
            )
            return {r["p"] for r in result if r["p"] and r["p"] != file_path_str}

        return execute_read_operation(self.driver, backend, _work)
    def delete_outgoing_calls_from_files(self, file_paths: List[str]) -> None:
        backend = get_backend_type(self.driver, self._db_manager)
        def _work(session):
            result = session.run(
                "MATCH (a)-[r:CALLS]->(b) WHERE a.path IN $paths DELETE r RETURN count(r) AS cnt",
                paths=file_paths,
            ).single()
            return result["cnt"] if result else 0
        cnt = execute_write_operation(self.driver, backend, _work)
        info_logger(f"[RELINK] Deleted {cnt} outgoing CALLS from {len(file_paths)} caller files")

    def delete_inherits_for_files(self, file_paths: List[str]) -> None:
        backend = get_backend_type(self.driver, self._db_manager)
        def _work(session):
            result = session.run(
                "MATCH (a)-[r:INHERITS]->(b) WHERE a.path IN $paths OR b.path IN $paths "
                "DELETE r RETURN count(r) AS cnt",
                paths=file_paths,
            ).single()
            return result["cnt"] if result else 0
        cnt = execute_write_operation(self.driver, backend, _work)
        info_logger(f"[RELINK] Deleted {cnt} INHERITS for {len(file_paths)} affected files")

    def get_repo_class_lookup(self, repo_path: Path) -> Dict[str, set]:
        # Use _normalize_prefix so the STARTS WITH matches forward-slash stored paths
        prefix = _normalize_prefix(repo_path)
        result_map: Dict[str, set] = {}
        backend = get_backend_type(self.driver, self._db_manager)
        def _work(session):
            local_map = {}
            result = session.run(
                "MATCH (c:Class) WHERE c.path STARTS WITH $prefix "
                "RETURN c.name AS name, c.path AS path",
                prefix=prefix,
            )
            for record in result:
                path = record["path"]
                if path not in local_map:
                    local_map[path] = set()
                local_map[path].add(record["name"])
            return local_map
        result_map.update(execute_read_operation(self.driver, backend, _work))
        return result_map

    def delete_relationship_links(self, repo_path: Path) -> None:
        # Use _normalize_prefix so the STARTS WITH matches forward-slash stored paths
        repo_path_str = _normalize_prefix(repo_path)
        backend = get_backend_type(self.driver, self._db_manager)
        def _work(session):
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
            return calls_deleted, inherits_deleted

        calls_deleted, inherits_deleted = execute_write_operation(self.driver, backend, _work)
        info_logger(
            f"[RELINK] Cleared {calls_deleted} CALLS and {inherits_deleted} INHERITS before re-linking: {repo_path}"
        )
