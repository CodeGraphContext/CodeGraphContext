"""One-way migration helpers for databases created by the archived KuzuDB.

Kuzu remains available as an explicit legacy backend, but it is no longer part
of CGC's normal runtime dependency or implicit backend selection.  Migration
opens the old store in a subprocess, writes a backend-neutral ``.cgc`` bundle,
and imports that bundle through the already-selected target manager.  Keeping
the native Kuzu and Ladybug modules in separate processes avoids their pybind
type-registration collision.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple


class LegacyKuzuExportError(RuntimeError):
    """Raised when the isolated Kuzu export process cannot create a bundle."""


class LegacyKuzuUnavailableError(LegacyKuzuExportError):
    """Raised when the export interpreter cannot import the Kuzu driver."""


_EXPORT_RESULT_PREFIX = "CGC_KUZU_EXPORT_RESULT:"


def _debug_log(message: str) -> None:
    from codegraphcontext.utils.debug_log import debug_log

    debug_log(message)


def _error_log(message: str) -> None:
    from codegraphcontext.utils.debug_log import error_logger

    error_logger(message)


def _get_config_value(key: str) -> Optional[str]:
    try:
        from codegraphcontext.cli.config_manager import get_config_value

        return get_config_value(key)
    except Exception:
        return None


def _result_rows(result: Any) -> Iterator[Any]:
    if result is None:
        return

    if hasattr(result, "__iter__"):
        try:
            yield from result
            return
        except TypeError:
            pass

    if hasattr(result, "has_next") and hasattr(result, "get_next"):
        while result.has_next():
            yield result.get_next()


def _row_value(row: Any, index: int, key: Optional[str] = None) -> Any:
    if key and isinstance(row, dict):
        return row.get(key)
    if key and hasattr(row, "get"):
        try:
            return row.get(key)
        except Exception:
            pass
    try:
        return row[index]
    except Exception:
        pass
    if key:
        try:
            return row[key]
        except Exception:
            pass
    return None


def _properties(value: Any) -> Dict[str, Any]:
    try:
        properties = dict(value)
        if properties:
            return properties
    except Exception:
        pass

    for attribute in ("_properties", "properties"):
        if hasattr(value, attribute):
            try:
                return dict(getattr(value, attribute))
            except Exception:
                pass
    return {}


def _pop_metadata(properties: Dict[str, Any], key: str) -> Any:
    """Pop a Kuzu/Ladybug internal field regardless of key casing."""
    if key in properties:
        return properties.pop(key)
    return properties.pop(key.upper(), None)


def find_legacy_kuzudb_source(
    target_db_path: Optional[str] = None,
    explicit_source_path: Optional[str] = None,
) -> Optional[Path]:
    """Return the first non-empty legacy Kuzu path, ordered by specificity."""
    candidates: List[Path] = []

    def add_candidate(raw_path: Any) -> None:
        if not raw_path:
            return
        try:
            candidate = Path(raw_path).expanduser()
        except (TypeError, ValueError):
            return
        if candidate not in candidates:
            candidates.append(candidate)

    target_path = Path(target_db_path).expanduser() if target_db_path else None
    default_global_source = Path.home() / ".codegraphcontext" / "global" / "db" / "kuzudb"

    add_candidate(explicit_source_path)
    add_candidate(os.getenv("KUZUDB_PATH"))

    configured_source = _get_config_value("KUZUDB_PATH")
    if configured_source:
        try:
            configured_is_default = (
                Path(configured_source).expanduser().resolve(strict=False)
                == default_global_source.resolve(strict=False)
            )
        except (OSError, RuntimeError, ValueError):
            configured_is_default = False
        # ``get_config_value`` returns the global HOME path even when the user
        # never configured it. Do not let an arbitrary resolved context or a
        # mocked factory call reach into that unrelated store. A custom config
        # value remains an explicit source; a global Ladybug target discovers
        # the default store as its sibling below.
        if target_path is None or not configured_is_default:
            add_candidate(configured_source)

    if target_path is not None:
        add_candidate(target_path.parent / "kuzudb")

    # A resolved embedded target already gives us the correct context root via
    # its sibling directory. Only use the process home as a last resort for
    # pathless targets (e.g. a remote backend), which keeps arbitrary factory
    # calls and mocks from reaching into a developer's real global store.
    if target_path is None:
        add_candidate(default_global_source)

    for candidate in candidates:
        try:
            if target_path is not None and candidate.resolve() == target_path.resolve():
                continue
            if candidate.exists() and (candidate.is_file() or any(candidate.iterdir())):
                return candidate
        except (OSError, RuntimeError):
            continue

    return None


def _has_graph_data(target_manager: Any) -> bool:
    """Return whether the target is populated; fail closed when uncertain."""
    try:
        with target_manager.get_driver().session() as session:
            record = session.run("MATCH (n) RETURN count(n) AS count").single()
            if not record:
                return False
            count = record["count"]
            try:
                return int(count) > 0
            except (TypeError, ValueError):
                return bool(count)
    except Exception as exc:
        # Importing after an inconclusive check could merge state into an
        # occupied target.  A migration can be retried after fixing the target.
        _debug_log(f"Legacy Kuzu migration could not verify an empty target: {exc}")
        return True


def migrate_legacy_kuzudb_to_manager(
    target_manager: Any,
    target_db_path: Optional[str] = None,
    source_db_path: Optional[str] = None,
) -> Tuple[bool, str]:
    """Migrate a legacy Kuzu store into an already-selected backend manager."""
    source_path = find_legacy_kuzudb_source(
        target_db_path=target_db_path,
        explicit_source_path=source_db_path,
    )
    if not source_path:
        return False, "No legacy KuzuDB store found; skipping migration."

    if _has_graph_data(target_manager):
        return (
            False,
            "Target database is not confirmed empty; skipping legacy KuzuDB migration.",
        )

    try:
        from codegraphcontext.core.cgc_bundle import CGCBundle
    except Exception as exc:
        return False, f"Could not load bundle importer for KuzuDB migration: {exc}"

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle_path = Path(temp_dir) / "legacy-kuzudb.cgc"
            node_count, edge_count = _export_legacy_kuzu_bundle_in_subprocess(
                source_path,
                bundle_path,
            )
            success, message = CGCBundle(target_manager).import_from_bundle(
                bundle_path,
                clear_existing=False,
            )
            if not success:
                return False, message

            backend = getattr(target_manager, "get_backend_type", lambda: "selected backend")()
            return True, (
                f"Migrated legacy KuzuDB data from {source_path} into {backend}. "
                f"Nodes: {node_count:,} | Edges: {edge_count:,}"
            )
    except LegacyKuzuUnavailableError:
        return False, (
            f"Legacy KuzuDB data was found at {source_path}, but the 'kuzu' package is not installed in the "
            "migration interpreter. KuzuDB is archived upstream; install it only in a compatible temporary "
            "environment and set CGC_KUZU_MIGRATION_PYTHON to that interpreter, or use the documented Docker "
            "migration. Python 3.14 may fall back to a native build and report 'Failed building wheel for kuzu'."
        )
    except Exception as exc:
        _error_log(f"Legacy KuzuDB migration failed: {exc}")
        return False, f"Failed to migrate legacy KuzuDB data from {source_path}: {exc}"


def _export_legacy_kuzu_bundle_in_subprocess(
    source_path: Path,
    bundle_path: Path,
) -> Tuple[int, int]:
    """Export Kuzu data without importing Kuzu in the target process."""
    migration_python = os.getenv("CGC_KUZU_MIGRATION_PYTHON") or sys.executable
    command = [
        migration_python,
        str(Path(__file__).resolve()),
        "export",
        str(source_path),
        str(bundle_path),
    ]

    try:
        completed = subprocess.run(command, capture_output=True, check=False, text=True)
    except OSError as exc:
        raise LegacyKuzuExportError(
            f"Could not start Kuzu migration interpreter '{migration_python}': {exc}"
        ) from exc

    detail = completed.stderr.strip() or completed.stdout.strip()
    if completed.returncode == 2:
        raise LegacyKuzuUnavailableError(detail or "Kuzu driver is unavailable")
    if completed.returncode != 0:
        raise LegacyKuzuExportError(detail or f"Kuzu export process exited with status {completed.returncode}")

    result_line = next(
        (
            line.removeprefix(_EXPORT_RESULT_PREFIX)
            for line in reversed(completed.stdout.splitlines())
            if line.startswith(_EXPORT_RESULT_PREFIX)
        ),
        None,
    )
    try:
        result = json.loads(result_line)
        return int(result["node_count"]), int(result["edge_count"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise LegacyKuzuExportError("Kuzu export process did not return valid migration statistics") from exc


def _write_migration_bundle(
    bundle_dir: Path,
    bundle_path: Path,
    source_path: Path,
    node_count: int,
    edge_count: int,
) -> None:
    metadata = {
        "cgc_version": "legacy-kuzu-migration",
        "format_version": "1.0.0",
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repo": f"legacy-kuzudb:{source_path}",
        "name": "legacy-kuzudb.cgc",
        "graph_metrics": {"total_nodes": node_count, "total_edges": edge_count},
    }
    schema = {
        "node_labels": [],
        "relationship_types": [],
        "constraints": [],
        "indexes": [],
    }

    with open(bundle_dir / "metadata.json", "w", encoding="utf-8") as metadata_file:
        json.dump(metadata, metadata_file, indent=2)
    with open(bundle_dir / "schema.json", "w", encoding="utf-8") as schema_file:
        json.dump(schema, schema_file, indent=2)

    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as bundle_file:
        for filename in ("metadata.json", "schema.json", "nodes.jsonl", "edges.jsonl"):
            bundle_file.write(bundle_dir / filename, arcname=filename)


def _export_legacy_kuzu_bundle(
    source_path: Path,
    bundle_dir: Path,
    kuzu_module: Any,
) -> Tuple[int, int]:
    """Export a Kuzu store into the JSONL shape consumed by ``CGCBundle``."""
    database = kuzu_module.Database(str(source_path))
    connection = kuzu_module.Connection(database)
    node_count = 0
    edge_count = 0

    with open(bundle_dir / "nodes.jsonl", "w", encoding="utf-8") as nodes_file:
        result = connection.execute("MATCH (n) RETURN n, labels(n) AS labels")
        for row in _result_rows(result):
            node = _row_value(row, 0, "n")
            labels = _row_value(row, 1, "labels") or []
            if isinstance(labels, str):
                labels = [labels]
            elif not isinstance(labels, list):
                labels = list(labels)

            node_properties = _properties(node)
            node_id = _pop_metadata(node_properties, "_id")
            _pop_metadata(node_properties, "_label")
            node_properties = {key: value for key, value in node_properties.items() if value is not None}
            node_properties["_labels"] = labels
            if node_id is None:
                node_id = getattr(node, "element_id", getattr(node, "id", None))
            if node_id is not None:
                node_properties["_id"] = node_id

            nodes_file.write(json.dumps(node_properties, default=str) + "\n")
            node_count += 1

    with open(bundle_dir / "edges.jsonl", "w", encoding="utf-8") as edges_file:
        # Kuzu 0.11.3 does not expose Cypher's ``type()`` function. Its Python
        # relationship value already carries the table name in ``_label``, so
        # read that metadata instead of issuing a query the archived runtime
        # cannot execute.
        result = connection.execute("MATCH (n)-[r]->(m) RETURN n, r, m")
        for row in _result_rows(result):
            source = _row_value(row, 0, "n")
            relationship = _row_value(row, 1, "r")
            target = _row_value(row, 2, "m")

            relationship_properties = _properties(relationship)
            from_id = _pop_metadata(relationship_properties, "_src")
            to_id = _pop_metadata(relationship_properties, "_dst")
            relationship_type = _pop_metadata(relationship_properties, "_label")
            _pop_metadata(relationship_properties, "_id")
            relationship_properties = {
                key: value for key, value in relationship_properties.items() if value is not None
            }

            if from_id is None:
                from_id = getattr(source, "element_id", getattr(source, "id", None))
            if to_id is None:
                to_id = getattr(target, "element_id", getattr(target, "id", None))
            if from_id is None or to_id is None:
                raise LegacyKuzuExportError("Kuzu export could not determine a relationship endpoint")
            if not relationship_type:
                raise LegacyKuzuExportError("Kuzu export could not determine a relationship type")

            edge = {
                "from": from_id,
                "to": to_id,
                "type": relationship_type,
                "properties": relationship_properties,
            }
            edges_file.write(json.dumps(edge, default=str) + "\n")
            edge_count += 1

    return node_count, edge_count


def _legacy_kuzu_export_main(argv: Optional[List[str]] = None) -> int:
    """Entry point used only by the isolated Kuzu export subprocess."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 3 or arguments[0] != "export":
        print("Usage: legacy_kuzu_migration.py export SOURCE_PATH BUNDLE_PATH", file=sys.stderr)
        return 1

    source_path = Path(arguments[1])
    bundle_path = Path(arguments[2])
    try:
        import kuzu
    except ImportError as exc:
        print(f"The 'kuzu' package is not installed: {exc}", file=sys.stderr)
        return 2

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle_dir = Path(temp_dir) / "bundle"
            bundle_dir.mkdir(parents=True, exist_ok=True)
            node_count, edge_count = _export_legacy_kuzu_bundle(source_path, bundle_dir, kuzu)
            bundle_path.parent.mkdir(parents=True, exist_ok=True)
            _write_migration_bundle(bundle_dir, bundle_path, source_path, node_count, edge_count)
    except Exception as exc:
        print(f"Legacy Kuzu export failed: {exc}", file=sys.stderr)
        return 1

    print(_EXPORT_RESULT_PREFIX + json.dumps({"node_count": node_count, "edge_count": edge_count}))
    return 0


if __name__ == "__main__":
    raise SystemExit(_legacy_kuzu_export_main())
