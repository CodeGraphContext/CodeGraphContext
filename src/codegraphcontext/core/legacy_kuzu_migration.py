"""
Legacy KuzuDB migration helpers.

KuzuDB is archived upstream, so CGC no longer treats it as a runtime backend.
It cannot be installed reliably on Python 3.14+: pip falls back to
pyproject/setuptools and fails with "Failed building wheel for kuzu".
This module exists only to rescue data from installations that still have a
legacy KuzuDB store on disk.

These utilities detect a pre-existing KuzuDB store, export it to a temporary
bundle, and import that bundle into the backend currently selected by the user.
"""
import json
import os
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from codegraphcontext.utils.debug_log import debug_log, error_logger


def _get_config_value(key: str) -> Optional[str]:
    try:
        from codegraphcontext.cli.config_manager import get_config_value
        return get_config_value(key)
    except Exception:
        return None


def _result_rows(result):
    if result is None:
        return
    if hasattr(result, "__iter__"):
        try:
            for row in result:
                yield row
            return
        except TypeError:
            pass
    if hasattr(result, "has_next") and hasattr(result, "get_next"):
        while result.has_next():
            yield result.get_next()


def _row_value(row, index: int, key: Optional[str] = None):
    if key and isinstance(row, dict):
        return row.get(key)
    if hasattr(row, "get") and key:
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


def _node_properties(node) -> Dict[str, Any]:
    try:
        props = dict(node)
        if props:
            return props
    except Exception:
        pass
    if hasattr(node, "_properties"):
        try:
            return dict(node._properties)
        except Exception:
            pass
    if hasattr(node, "properties"):
        try:
            return dict(node.properties)
        except Exception:
            pass
    return {}


def _rel_properties(rel) -> Dict[str, Any]:
    try:
        props = dict(rel)
        if props:
            return props
    except Exception:
        pass
    if hasattr(rel, "_properties"):
        try:
            return dict(rel._properties)
        except Exception:
            pass
    if hasattr(rel, "properties"):
        try:
            return dict(rel.properties)
        except Exception:
            pass
    return {}


def find_legacy_kuzudb_source(
    target_db_path: Optional[str] = None,
) -> Optional[Path]:
    """Return the most likely legacy KuzuDB path, if one exists."""
    candidates: List[Path] = []

    def _add_candidate(raw_path: Optional[str]) -> None:
        if not raw_path:
            return
        try:
            candidate = Path(raw_path).expanduser()
        except Exception:
            return
        if candidate not in candidates:
            candidates.append(candidate)

    _add_candidate(os.getenv("KUZUDB_PATH"))
    _add_candidate(_get_config_value("KUZUDB_PATH"))

    target_path = Path(target_db_path).expanduser() if target_db_path else None
    if target_path is not None:
        _add_candidate(target_path.parent / "kuzudb")

    _add_candidate(
        Path.home() / ".codegraphcontext" / "global" / "db" / "kuzudb"
    )

    for candidate in candidates:
        try:
            if (
                target_path is not None
                and candidate.resolve() == target_path.resolve()
            ):
                continue
        except Exception:
            pass

        try:
            if candidate.exists() and (
                candidate.is_file() or any(candidate.iterdir())
            ):
                return candidate
        except Exception:
            continue

    return None


def _has_graph_data(target_manager) -> bool:
    try:
        with target_manager.get_driver().session() as session:
            result = session.run("MATCH (n) RETURN count(n) AS count")
            record = result.single()
            if not record:
                return False
            count = record["count"]
            try:
                return int(count) > 0
            except (TypeError, ValueError):
                return bool(count)
    except Exception as e:
        debug_log(
            "Legacy Kuzu migration preflight could not inspect graph size: "
            f"{e}"
        )
        return False


def migrate_legacy_kuzudb_to_manager(
    target_manager,
    target_db_path: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Migrate a legacy KuzuDB store into the supplied database manager.

    The target is whatever backend the user configured or whatever default the
    application resolved when no explicit backend was set.
    """
    source_path = find_legacy_kuzudb_source(target_db_path=target_db_path)
    if not source_path:
        return False, "No legacy KuzuDB store found; skipping migration."

    if _has_graph_data(target_manager):

        # KuzuDB is archived, so migration is a one-way escape hatch rather
        # than a sync path. Refusing non-empty targets avoids silent merges.
        return (
            False,
            "Target database already contains data; skipping legacy KuzuDB "
            "migration.",
        )

    try:
        import kuzu
    except ImportError:
        return False, (
            f"Legacy KuzuDB data was found at {source_path}, but the 'kuzu' "
            "package is not installed. KuzuDB is archived upstream; install "
            "it only in an older temporary Python environment. On Python "
            "3.14+, pip falls back to the pyproject/setuptools build path "
            "and fails with 'Failed building wheel for kuzu'."
        )

    try:
        from codegraphcontext.core.cgc_bundle import CGCBundle
    except Exception as e:
        return (
            False,
            f"Could not load bundle importer for KuzuDB migration: {e}",
        )

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            bundle_dir = temp_path / "bundle"
            bundle_dir.mkdir(parents=True, exist_ok=True)
            bundle_path = temp_path / "legacy-kuzudb.cgc"

            node_count, edge_count = _export_legacy_kuzu_bundle(
                source_path,
                bundle_dir,
                kuzu,
            )
            _write_migration_bundle(
                bundle_dir,
                bundle_path,
                source_path,
                node_count,
                edge_count,
            )

            bundle = CGCBundle(target_manager)
            success, message = bundle.import_from_bundle(
                bundle_path,
                clear_existing=False,
            )
            if success:
                return True, (
                    f"Migrated legacy KuzuDB data from {source_path} into "
                    f"{target_manager.get_backend_type()}. "
                    f"Nodes: {node_count:,} | Edges: {edge_count:,}"
                )
            return False, message
    except Exception as e:
        error_logger(f"Legacy KuzuDB migration failed: {e}")
        debug_log(f"Legacy KuzuDB migration failed: {e}")
        return (
            False,
            f"Failed to migrate legacy KuzuDB data from {source_path}: {e}",
        )


def _write_migration_bundle(
    bundle_dir: Path,
    bundle_path: Path,
    source_path: Path,
    node_count: int,
    edge_count: int,
) -> None:
    metadata = {
        "cgc_version": "migration",
        "format_version": "1.0",
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repo": f"legacy-kuzudb:{source_path}",
        "name": "legacy-kuzudb.cgc",
        "graph_metrics": {
            "total_nodes": node_count,
            "total_edges": edge_count,
        },
    }
    schema = {
        "node_labels": [],
        "relationship_types": [],
        "constraints": [],
        "indexes": [],
    }

    with open(bundle_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    with open(bundle_dir / "schema.json", "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)

    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for filename in (
            "metadata.json",
            "schema.json",
            "nodes.jsonl",
            "edges.jsonl",
        ):
            zipf.write(bundle_dir / filename, arcname=filename)


def _export_legacy_kuzu_bundle(
    source_path: Path,
    bundle_dir: Path,
    kuzu_module,
) -> Tuple[int, int]:
    db = kuzu_module.Database(str(source_path))
    conn = kuzu_module.Connection(db)

    node_count = 0
    edge_count = 0

    node_query = "MATCH (n) RETURN n, labels(n) AS labels"
    edge_query = "MATCH (n)-[r]->(m) RETURN n, r, m, type(r) AS rel_type"

    with open(bundle_dir / "nodes.jsonl", "w", encoding="utf-8") as nodes_file:
        result = conn.execute(node_query)
        for row in _result_rows(result):
            node = _row_value(row, 0, "n")
            labels = _row_value(row, 1, "labels") or []
            if isinstance(labels, str):
                labels = [labels]
            elif not isinstance(labels, list):
                labels = list(labels)

            node_dict = _node_properties(node)
            node_dict.pop("_label", None)
            for key, val in list(node_dict.items()):
                if key != "_id" and val is None:
                    node_dict.pop(key)
            node_dict["_labels"] = labels
            if "_id" not in node_dict:
                if hasattr(node, "element_id"):
                    node_dict["_id"] = node.element_id
                elif hasattr(node, "id"):
                    node_dict["_id"] = str(node.id)
            nodes_file.write(json.dumps(node_dict, default=str) + "\n")
            node_count += 1

    with open(bundle_dir / "edges.jsonl", "w", encoding="utf-8") as edges_file:
        result = conn.execute(edge_query)
        for row in _result_rows(result):
            source = _row_value(row, 0, "n")
            rel = _row_value(row, 1, "r")
            target = _row_value(row, 2, "m")
            rel_type = _row_value(row, 3, "rel_type")

            rel_props = _rel_properties(rel)
            from_id = rel_props.pop("_src", None)
            to_id = rel_props.pop("_dst", None)
            rel_props.pop("_label", None)
            rel_props.pop("_id", None)
            for key, val in list(rel_props.items()):
                if val is None:
                    rel_props.pop(key)

            if from_id is None:
                if hasattr(source, "element_id"):
                    from_id = source.element_id
                elif hasattr(source, "id"):
                    from_id = str(source.id)
                else:
                    from_id = str(id(source))

            if to_id is None:
                if hasattr(target, "element_id"):
                    to_id = target.element_id
                elif hasattr(target, "id"):
                    to_id = str(target.id)
                else:
                    to_id = str(id(target))

            edge_dict = {
                "from": from_id,
                "to": to_id,
                "type": rel_type,
                "properties": rel_props,
            }
            edges_file.write(json.dumps(edge_dict, default=str) + "\n")
            edge_count += 1

    return node_count, edge_count
