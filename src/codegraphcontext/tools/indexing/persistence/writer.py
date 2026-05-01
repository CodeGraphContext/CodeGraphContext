"""All graph DB writes for indexing (single persistence entry point)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import random
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from ....utils.debug_log import info_logger, warning_logger
from ..sanitize import sanitize_props
from .. import profiling


class GraphWriter:
    """Persists repository/file/symbol nodes and relationships via the Neo4j-like driver API."""

    def __init__(self, driver: Any):
        self.driver = driver

    @staticmethod
    def _chunk_items(items: List[Dict], chunk_size: int):
        for i in range(0, len(items), chunk_size):
            yield items[i : i + chunk_size]

    @staticmethod
    def _adaptive_batch_size(total_items: int, base: int, minimum: int, maximum: int) -> int:
        if total_items <= base * 4:
            return max(minimum, base)
        if total_items <= 50000:
            return min(maximum, base * 2)
        if total_items <= 200000:
            return min(maximum, base * 4)
        return maximum

    @staticmethod
    @staticmethod
    def _is_oom_error(exc: Exception) -> bool:
        return "MemoryPoolOutOfMemoryError" in str(exc)

    @staticmethod
    def _is_retryable_write_error(exc: Exception) -> bool:
        msg = str(exc)
        if "MemoryPoolOutOfMemoryError" in msg:
            return False  # OOM needs batch reduction, not same-batch retry
        return "TransientError" in msg or "DeadlockDetected" in msg

    def _run_with_deadlock_retry(
        self,
        session: Any,
        query: str,
        max_attempts: int = 6,
        **parameters: Any,
    ) -> None:
        """session.run() with exponential-backoff retry on transient Neo4j deadlocks."""
        attempt = 0
        while True:
            try:
                self._run_and_maybe_consume(session, query, **parameters)
                return
            except Exception as e:
                if not self._is_retryable_write_error(e) or attempt >= max_attempts:
                    raise
                attempt += 1
                time.sleep((0.05 * (2**attempt)) + random.uniform(0.01, 0.20))

    @staticmethod
    def _run_and_maybe_consume(session: Any, query: str, **parameters: Any) -> None:
        """
        Execute a write query and consume when the driver result supports it.

        Some unit-test fakes return lightweight result objects without `consume()`;
        production drivers expose it.
        """
        result = session.run(query, **parameters)
        consume = getattr(result, "consume", None)
        if callable(consume):
            consume()

    @staticmethod
    def _resolve_neo4j_worker_count(
        *, configured: Optional[str], default_auto: int, min_workers: int, max_workers: int
    ) -> int:
        raw = (configured or "auto").strip().lower()
        if raw == "auto":
            base = max(1, default_auto)
        else:
            try:
                base = max(1, int(raw))
            except ValueError:
                base = max(1, default_auto)
        return max(min_workers, min(max_workers, base))

    def _neo4j_rel_write_workers(self) -> int:
        """Bounded concurrent transaction workers for Neo4j relationship writes."""
        backend = (os.getenv("CGC_RUNTIME_DB_TYPE") or os.getenv("DEFAULT_DATABASE") or "").strip().lower()
        if backend != "neo4j":
            return 1
        configured = (
            os.getenv("CGC_NEO4J_REL_WRITE_WORKERS")
            or os.getenv("NEO4J_REL_WRITE_WORKERS")
            or os.getenv("PARALLEL_WORKERS")
        )
        max_cap = os.getenv("CGC_NEO4J_REL_WRITE_WORKERS_MAX") or "12"
        try:
            max_workers = max(2, int(max_cap))
        except ValueError:
            max_workers = 12
        min_workers = 1 if (configured or "").strip() == "1" else 2
        return self._resolve_neo4j_worker_count(
            configured=configured,
            default_auto=max(1, (os.cpu_count() or 4) - 2),
            min_workers=min_workers,
            max_workers=max_workers,
        )

    def _batched_unwind_write(
        self,
        session: Any,
        query: str,
        batch: List[Dict[str, Any]],
        *,
        file_path: str,
        base: int,
        minimum: int,
        maximum: int,
    ) -> None:
        if not batch:
            return
        batch_size = self._adaptive_batch_size(len(batch), base=base, minimum=minimum, maximum=maximum)
        for chunk in self._chunk_items(batch, batch_size):
            self._run_with_deadlock_retry(session, query, batch=chunk, file_path=file_path)

    @staticmethod
    def _calls_batch_size_params(label: str) -> Tuple[int, int, int]:
        # Reduced maximums vs. earlier defaults to stay within Neo4j transaction memory limits
        # under concurrent write workers (8 workers × large batches can exceed 1 GB tx pool).
        if label.startswith("file→"):
            return 700, 300, 1500
        if label.startswith("cls→"):
            return 900, 400, 2500
        return 1200, 500, 3000

    def _write_calls_group(self, label: str, calls: List[Dict], query: str, batch_size: int) -> Tuple[str, int, float]:
        profiling.set_phase("function_calls")
        t0 = time.time()
        with self.driver.session() as session:
            i = 0
            current_batch_size = batch_size
            while i < len(calls):
                batch = calls[i : i + current_batch_size]
                attempt = 0
                while True:
                    try:
                        self._run_and_maybe_consume(session, query, batch=batch)
                        i += len(batch)
                        break
                    except Exception as e:
                        if self._is_oom_error(e) and current_batch_size > 50:
                            # Transaction memory exhausted — halve batch size and retry this slice.
                            profiling.record_oom_retry()
                            current_batch_size = max(50, current_batch_size // 2)
                            batch = calls[i : i + current_batch_size]
                            attempt = 0
                        elif not self._is_retryable_write_error(e) or attempt >= 8:
                            raise
                        else:
                            profiling.record_deadlock_retry()
                            attempt += 1
                            time.sleep((0.05 * (2**attempt)) + random.uniform(0.01, 0.20))
        return label, len(calls), time.time() - t0

    def add_repository_to_graph(self, repo_path: Path, is_dependency: bool = False) -> None:
        repo_name = repo_path.name
        repo_path_str = str(repo_path.resolve())
        with self.driver.session() as session:
            session.run(
                """
                MERGE (r:Repository {path: $path})
                SET r.name = $name, r.is_dependency = $is_dependency
                """,
                path=repo_path_str,
                name=repo_name,
                is_dependency=is_dependency,
            )

    def pre_create_directory_structure(self, file_paths: List[Path], repo_path: Path) -> None:
        """Bulk-create all Directory nodes + CONTAINS edges before parallel file writes.

        Calling this before any `add_file_to_graph(..., directories_pre_created=True)` calls
        eliminates concurrent MERGE lock contention on shared parent directories, which is the
        primary source of Neo4j CPU thrashing under multiple write workers.
        """
        repo_path_str = str(repo_path.resolve())

        dir_rows: List[Dict[str, Any]] = []
        seen: set = set()

        for file_path in file_paths:
            try:
                rel = Path(str(file_path.resolve())).relative_to(repo_path_str)
            except ValueError:
                continue
            parts = list(rel.parts[:-1])
            if not parts:
                continue
            prev = repo_path_str
            is_repo_parent = True
            for part in parts:
                current = str(Path(prev) / part)
                key = (prev, current)
                if key not in seen:
                    seen.add(key)
                    dir_rows.append(
                        {
                            "parent_path": prev,
                            "dir_path": current,
                            "dir_name": part,
                            "is_repo_parent": is_repo_parent,
                        }
                    )
                prev = current
                is_repo_parent = False

        if not dir_rows:
            return

        chunk_size = self._adaptive_batch_size(len(dir_rows), base=500, minimum=200, maximum=5000)
        repo_rows = [r for r in dir_rows if r["is_repo_parent"]]
        dir_dir_rows = [r for r in dir_rows if not r["is_repo_parent"]]

        with self.driver.session() as session:
            # 1) Create all Directory nodes first (no parent MATCH needed).
            for chunk in self._chunk_items(dir_rows, chunk_size):
                self._run_and_maybe_consume(
                    session,
                    "UNWIND $batch AS row MERGE (d:Directory {path: row.dir_path}) SET d.name = row.dir_name",
                    batch=chunk,
                )
            # 2) Repository → first-level Directory CONTAINS.
            for chunk in self._chunk_items(repo_rows, chunk_size):
                self._run_and_maybe_consume(
                    session,
                    """UNWIND $batch AS row
                    MATCH (p:Repository {path: row.parent_path})
                    MATCH (d:Directory {path: row.dir_path})
                    MERGE (p)-[:CONTAINS]->(d)""",
                    batch=chunk,
                )
            # 3) Directory → Directory CONTAINS.
            for chunk in self._chunk_items(dir_dir_rows, chunk_size):
                self._run_and_maybe_consume(
                    session,
                    """UNWIND $batch AS row
                    MATCH (p:Directory {path: row.parent_path})
                    MATCH (d:Directory {path: row.dir_path})
                    MERGE (p)-[:CONTAINS]->(d)""",
                    batch=chunk,
                )

        info_logger(f"[DIRS] Pre-created {len(dir_rows)} directory path entries.")

    def pre_create_module_nodes(self, all_file_data: List[Dict[str, Any]]) -> None:
        """Bulk-create all Module nodes before parallel file writes.

        Module nodes are shared across files (every file that imports 'os' references the
        same Module node).  When 4+ workers all race to MERGE Module('os') and then
        MERGE (:File)-[:IMPORTS]->(:Module) simultaneously, Neo4j generates a lock-order
        inversion deadlock: one tx holds NODE(module) waiting for REL_GROUP, another holds
        REL_GROUP waiting for NODE.  Pre-creating the nodes so parallel writes only need
        to MATCH them eliminates this cycle entirely.
        """
        module_names: set = set()
        for file_data in all_file_data:
            lang = file_data.get("lang")
            if lang == "javascript":
                for imp in file_data.get("imports", []):
                    src = imp.get("source")
                    if src:
                        module_names.add(src)
            else:
                for imp in file_data.get("imports", []):
                    name = imp.get("name")
                    if name:
                        module_names.add(name)
            for inc in file_data.get("module_inclusions", []):
                mod = inc.get("module")
                if mod:
                    module_names.add(mod)
            for m in file_data.get("modules", []):
                n = m.get("name")
                if n:
                    module_names.add(n)

        if not module_names:
            return

        rows = [{"name": n} for n in module_names]
        chunk_size = self._adaptive_batch_size(len(rows), base=500, minimum=200, maximum=5000)
        with self.driver.session() as session:
            for chunk in self._chunk_items(rows, chunk_size):
                self._run_and_maybe_consume(
                    session,
                    "UNWIND $batch AS row MERGE (m:Module {name: row.name})",
                    batch=chunk,
                )
        info_logger(f"[MODULES] Pre-created {len(module_names)} module nodes.")

    def add_file_to_graph(
        self,
        file_data: Dict[str, Any],
        repo_name: str,
        imports_map: dict,
        repo_path_str: Optional[str] = None,
        directories_pre_created: bool = False,
    ) -> None:
        profiling.set_phase("file_writes")
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
            dir_parts = list(relative_path_to_file.parts[:-1])

            if directories_pre_created:
                # Directories already exist from pre_create_directory_structure; only
                # link the file to its immediate parent.
                if dir_parts:
                    parent_path = str(Path(resolved_repo_str).joinpath(*dir_parts))
                    parent_label = "Directory"
                else:
                    parent_path = resolved_repo_str
                    parent_label = "Repository"
                self._run_with_deadlock_retry(
                    session,
                    f"""
                    MATCH (p:{parent_label} {{path: $parent_path}})
                    MATCH (f:File {{path: $path}})
                    MERGE (p)-[:CONTAINS]->(f)
                """,
                    parent_path=parent_path,
                    path=file_path_str,
                )
            else:
                parent_path = resolved_repo_str
                parent_label = "Repository"
                if dir_parts:
                    first_dir_path = str(Path(resolved_repo_str) / dir_parts[0])
                    session.run(
                        """
                        MATCH (p:Repository {path: $repo_path})
                        MERGE (d:Directory {path: $dir_path})
                        SET d.name = $dir_name
                        MERGE (p)-[:CONTAINS]->(d)
                    """,
                        repo_path=resolved_repo_str,
                        dir_path=first_dir_path,
                        dir_name=dir_parts[0],
                    )
                    parent_path = first_dir_path
                    parent_label = "Directory"
                    if len(dir_parts) > 1:
                        directory_rows: List[Dict[str, str]] = []
                        prev_path = first_dir_path
                        for part in dir_parts[1:]:
                            current_path = str(Path(prev_path) / part)
                            directory_rows.append(
                                {
                                    "parent_path": prev_path,
                                    "current_path": current_path,
                                    "part": part,
                                }
                            )
                            prev_path = current_path
                        session.run(
                            """
                            UNWIND $rows AS row
                            MATCH (p:Directory {path: row.parent_path})
                            MERGE (d:Directory {path: row.current_path})
                            SET d.name = row.part
                            MERGE (p)-[:CONTAINS]->(d)
                        """,
                            rows=directory_rows,
                        )
                        parent_path = prev_path
                session.run(
                    f"""
                    MATCH (p:{parent_label} {{path: $parent_path}})
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
                                    b[k] = ""
                                elif isinstance(v, list):
                                    b[k] = _json.dumps(v)
                                elif not isinstance(v, str):
                                    b[k] = str(v)

                    key_order = sorted(all_keys)
                    batch[:] = [{k: b[k] for k in key_order} for b in batch]

                item_batch_size = self._adaptive_batch_size(
                    len(batch), base=500, minimum=200, maximum=5000
                )
                for batch_chunk in self._chunk_items(batch, item_batch_size):
                    session.run(
                        f"""
                        UNWIND $batch AS row
                        MATCH (f:File {{path: $file_path}})
                        MERGE (n:{label} {{name: row.name, path: $file_path, line_number: row.line_number}})
                        SET n += row
                        MERGE (f)-[:CONTAINS]->(n)
                    """,
                        batch=batch_chunk,
                        file_path=file_path_str,
                    )

            if params_batch:
                self._batched_unwind_write(
                    session,
                    """
                    UNWIND $batch AS row
                    MATCH (fn:Function {name: row.func_name, path: $file_path, line_number: row.line_number})
                    MERGE (p:Parameter {name: row.arg_name, path: $file_path, function_line_number: row.line_number})
                    MERGE (fn)-[:HAS_PARAMETER]->(p)
                """,
                    params_batch,
                    file_path=file_path_str,
                    base=400,
                    minimum=150,
                    maximum=2000,
                )

            if class_fn_batch:
                self._batched_unwind_write(
                    session,
                    """
                    UNWIND $batch AS row
                    MATCH (c:Class {name: row.class_name, path: $file_path})
                    MATCH (fn:Function {name: row.func_name, path: $file_path, line_number: row.func_line})
                    MERGE (c)-[:CONTAINS]->(fn)
                """,
                    class_fn_batch,
                    file_path=file_path_str,
                    base=1000,
                    minimum=400,
                    maximum=6000,
                )

            if nested_fn_batch:
                self._batched_unwind_write(
                    session,
                    """
                    UNWIND $batch AS row
                    MATCH (outer:Function {name: row.outer, path: $file_path})
                    MATCH (inner:Function {name: row.inner_name, path: $file_path, line_number: row.inner_line})
                    MERGE (outer)-[:CONTAINS]->(inner)
                """,
                    nested_fn_batch,
                    file_path=file_path_str,
                    base=1000,
                    minimum=400,
                    maximum=6000,
                )

            ruby_modules = file_data.get("modules", [])
            if ruby_modules:
                # Module MERGE and property set is its own transaction — no relationships
                # created here, so no REL_GROUP lock contention with concurrent workers.
                self._run_with_deadlock_retry(
                    session,
                    """
                    UNWIND $batch AS row
                    MERGE (mod:Module {name: row.name})
                    ON CREATE SET mod.lang = row.lang
                    ON MATCH  SET mod.lang = coalesce(mod.lang, row.lang)
                """,
                    batch=[{"name": m["name"], "lang": lang} for m in ruby_modules],
                )

            js_imports = []
            other_imports = []
            for imp in file_data.get("imports", []):
                if lang == "javascript":
                    module_name = imp.get("source")
                    if module_name:
                        js_imports.append(
                            {
                                "module_name": module_name,
                                "imported_name": imp.get("name", "*"),
                                "alias": imp.get("alias"),
                                "line_number": imp.get("line_number"),
                            }
                        )
                else:
                    # Keep a stable row schema for KùzuDB UNWIND struct typing.
                    other_imports.append(
                        {
                            "name": imp.get("name"),
                            "alias": imp.get("alias"),
                            "full_import_name": imp.get("full_import_name"),
                            "line_number": imp.get("line_number"),
                        }
                    )

            if js_imports:
                # Split into two autocommit transactions to prevent lock-order inversion:
                # tx-1 acquires NODE locks (MERGE module nodes, no relationship locks).
                # tx-2 acquires only REL_GROUP locks (MATCH both endpoints, MERGE rel).
                # A single combined tx holding NODE(module) + REL_GROUP(file/module)
                # simultaneously can deadlock with a concurrent worker holding the inverse.
                self._run_with_deadlock_retry(
                    session,
                    "UNWIND $batch AS row MERGE (m:Module {name: row.module_name})",
                    batch=js_imports,
                )
                self._run_with_deadlock_retry(
                    session,
                    """
                    UNWIND $batch AS row
                    MATCH (f:File {path: $file_path})
                    MATCH (m:Module {name: row.module_name})
                    MERGE (f)-[r:IMPORTS]->(m)
                    SET r.imported_name = row.imported_name,
                        r.alias = row.alias,
                        r.line_number = row.line_number
                """,
                    batch=js_imports,
                    file_path=file_path_str,
                )

            if other_imports:
                # Same split strategy: Module nodes first (NODE locks), then IMPORTS rels
                # (REL_GROUP locks only — both endpoints already exist via MATCH).
                self._run_with_deadlock_retry(
                    session,
                    """
                    UNWIND $batch AS row
                    MERGE (m:Module {name: row.name})
                    SET m.alias = coalesce(row.alias, m.alias),
                        m.full_import_name = coalesce(row.full_import_name, m.full_import_name)
                """,
                    batch=other_imports,
                )
                self._run_with_deadlock_retry(
                    session,
                    """
                    UNWIND $batch AS row
                    MATCH (f:File {path: $file_path})
                    MATCH (m:Module {name: row.name})
                    MERGE (f)-[r:IMPORTS]->(m)
                    SET r.line_number = row.line_number,
                        r.alias = row.alias
                """,
                    batch=other_imports,
                    file_path=file_path_str,
                )

            module_inclusions = file_data.get("module_inclusions", [])
            if module_inclusions:
                # Same split: create Module nodes first, then INCLUDES relationships.
                inc_batch = [
                    {"class_name": i["class"], "module_name": i["module"]} for i in module_inclusions
                ]
                self._run_with_deadlock_retry(
                    session,
                    "UNWIND $batch AS row MERGE (m:Module {name: row.module_name})",
                    batch=inc_batch,
                )
                self._run_with_deadlock_retry(
                    session,
                    """
                    UNWIND $batch AS row
                    MATCH (c:Class {name: row.class_name, path: $file_path})
                    MATCH (m:Module {name: row.module_name})
                    MERGE (c)-[:INCLUDES]->(m)
                """,
                    batch=inc_batch,
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
        fn_to_fn: List[Dict],
        fn_to_cls: List[Dict],
        cls_to_fn: List[Dict],
        cls_to_cls: List[Dict],
        file_to_fn: List[Dict],
        file_to_cls: List[Dict],
    ) -> None:
        q_fn_to_fn = """
            UNWIND $batch AS row
            MATCH (caller:Function {name: row.caller_name, path: row.caller_file_path, line_number: row.caller_line_number})
            MATCH (called:Function {name: row.called_name, path: row.called_file_path})
            MERGE (caller)-[:CALLS {line_number: row.line_number, args: row.args, full_call_name: row.full_call_name}]->(called)
        """
        q_fn_to_cls = """
            UNWIND $batch AS row
            MATCH (caller:Function {name: row.caller_name, path: row.caller_file_path, line_number: row.caller_line_number})
            MATCH (called:Class {name: row.called_name, path: row.called_file_path})
            MERGE (caller)-[:CALLS {line_number: row.line_number, args: row.args, full_call_name: row.full_call_name}]->(called)
        """
        q_cls_to_fn = """
            UNWIND $batch AS row
            MATCH (caller:Class {name: row.caller_name, path: row.caller_file_path, line_number: row.caller_line_number})
            MATCH (called:Function {name: row.called_name, path: row.called_file_path})
            MERGE (caller)-[:CALLS {line_number: row.line_number, args: row.args, full_call_name: row.full_call_name}]->(called)
        """
        q_cls_to_cls = """
            UNWIND $batch AS row
            MATCH (caller:Class {name: row.caller_name, path: row.caller_file_path, line_number: row.caller_line_number})
            MATCH (called:Class {name: row.called_name, path: row.called_file_path})
            MERGE (caller)-[:CALLS {line_number: row.line_number, args: row.args, full_call_name: row.full_call_name}]->(called)
        """
        q_file_to_fn = """
            UNWIND $batch AS row
            MATCH (caller:File {path: row.caller_file_path})
            MATCH (called:Function {name: row.called_name, path: row.called_file_path})
            MERGE (caller)-[:CALLS {line_number: row.line_number, args: row.args, full_call_name: row.full_call_name}]->(called)
        """
        q_file_to_cls = """
            UNWIND $batch AS row
            MATCH (caller:File {path: row.caller_file_path})
            MATCH (called:Class {name: row.called_name, path: row.called_file_path})
            MERGE (caller)-[:CALLS {line_number: row.line_number, args: row.args, full_call_name: row.full_call_name}]->(called)
        """
        groups: List[Tuple[str, List[Dict], str]] = [
            ("fn→fn", fn_to_fn, q_fn_to_fn),
            ("fn→cls", fn_to_cls, q_fn_to_cls),
            ("cls→fn", cls_to_fn, q_cls_to_fn),
            ("cls→cls", cls_to_cls, q_cls_to_cls),
            ("file→fn", file_to_fn, q_file_to_fn),
            ("file→cls", file_to_cls, q_file_to_cls),
        ]
        total_all = sum(len(g[1]) for g in groups)
        runnable_groups = [(label, calls, query) for (label, calls, query) in groups if calls]
        for label, calls, _query in groups:
            if not calls:
                info_logger(f"[CALLS] {label}: 0 (skipped)")

        if not runnable_groups:
            info_logger(f"[CALLS] All complete: {total_all} CALLS relationships processed.")
            return

        group_workers = min(self._neo4j_rel_write_workers(), len(runnable_groups))
        with ThreadPoolExecutor(max_workers=group_workers) as executor:
            futures = {}
            for label, calls, query in runnable_groups:
                base, minimum, maximum = self._calls_batch_size_params(label)
                batch_size = self._adaptive_batch_size(len(calls), base=base, minimum=minimum, maximum=maximum)
                future = executor.submit(self._write_calls_group, label, calls, query, batch_size)
                futures[future] = label

            for future in as_completed(futures):
                label = futures[future]
                try:
                    result_label, written_count, elapsed = future.result()
                    info_logger(f"[CALLS] {result_label} done: {written_count} in {elapsed:.1f}s")
                except Exception as e:
                    warning_logger(f"[CALLS] {label} failed: {e}")
                    raise
        info_logger(f"[CALLS] All complete: {total_all} CALLS relationships processed.")

    def _write_inheritance_batch(self, batch: List[Dict[str, Any]]) -> int:
        profiling.set_phase("inheritance")
        query = """
            UNWIND $batch AS row
            MATCH (child:Class {name: row.child_name, path: row.path})
            MATCH (parent:Class {name: row.parent_name, path: row.resolved_parent_file_path})
            MERGE (child)-[:INHERITS]->(parent)
        """
        attempt = 0
        while True:
            try:
                with self.driver.session() as session:
                    self._run_and_maybe_consume(session, query, batch=batch)
                return len(batch)
            except Exception as e:
                if not self._is_retryable_write_error(e) or attempt >= 8:
                    raise
                attempt += 1
                time.sleep((0.05 * (2**attempt)) + random.uniform(0.01, 0.20))

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
                        session.run(
                            """
                            MATCH (child {name: $child_name, path: $path})
                            WHERE child:Class OR child:Struct OR child:Record
                            MATCH (iface:Interface {name: $interface_name})
                            MERGE (child)-[:IMPLEMENTS]->(iface)
                        """,
                            child_name=type_item["name"],
                            path=caller_file_path,
                            interface_name=base_name,
                        )
                    else:
                        session.run(
                            """
                            MATCH (child {name: $child_name, path: $path})
                            WHERE child:Class OR child:Record OR child:Interface
                            MATCH (parent {name: $parent_name})
                            WHERE parent:Class OR parent:Record OR parent:Interface
                            MERGE (child)-[:INHERITS]->(parent)
                        """,
                            child_name=type_item["name"],
                            path=caller_file_path,
                            parent_name=base_name,
                        )

    def write_inheritance_links(
        self,
        inheritance_batch: List[Dict[str, Any]],
        csharp_files: List[Dict[str, Any]],
        imports_map: dict,
    ) -> None:
        info_logger(
            f"[INHERITS] Resolved {len(inheritance_batch)} inheritance links, "
            f"{len(csharp_files)} C# files. Writing to Neo4j..."
        )
        batch_size = self._adaptive_batch_size(
            len(inheritance_batch), base=500, minimum=250, maximum=8000
        )
        batches = [
            inheritance_batch[i : i + batch_size]
            for i in range(0, len(inheritance_batch), batch_size)
        ]
        workers = min(self._neo4j_rel_write_workers(), len(batches)) if batches else 1
        if batches:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(self._write_inheritance_batch, batch) for batch in batches]
                for future in as_completed(futures):
                    future.result()

        with self.driver.session() as session:
            for file_data in csharp_files:
                self._create_csharp_inheritance_and_interfaces(session, file_data, imports_map)

        info_logger(f"[INHERITS] Complete: {len(inheritance_batch)} inheritance links processed.")

    def write_scip_call_edges(
        self, files_data: Dict[str, Any], name_from_symbol: Callable[[str], str]
    ) -> None:
        with self.driver.session() as session:
            for file_data in files_data.values():
                for edge in file_data.get("function_calls_scip", []):
                    try:
                        session.run(
                            """
                            MATCH (caller:Function {name: $caller_name, path: $caller_file, line_number: $caller_line})
                            MATCH (callee:Function {name: $callee_name, path: $callee_file, line_number: $callee_line})
                            MERGE (caller)-[:CALLS {line_number: $ref_line, source: 'scip'}]->(callee)
                        """,
                            caller_name=name_from_symbol(edge["caller_symbol"]),
                            caller_file=edge["caller_file"],
                            caller_line=edge["caller_line"],
                            callee_name=edge["callee_name"],
                            callee_file=edge["callee_file"],
                            callee_line=edge["callee_line"],
                            ref_line=edge["ref_line"],
                        )
                    except Exception as e:
                        warning_logger(f"Failed to write SCIP call edge: {e}")

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

    def delete_repository_from_graph(self, repo_path: str) -> bool:
        repo_path_str = str(Path(repo_path).resolve())
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

        for label in ("Function", "Class", "File"):
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
