# src/codegraphcontext/cli/snapshot_commands.py
"""`cgc snapshot save|list` and `cgc diff` (#1312).

This module owns the operational half of the feature: where snapshots live,
which one `--against` resolves to, and what each command prints. The Typer
surface (option parsing, service init, stream rebinding, exit codes) stays in
``cli/main.py``, and all document/diff/render logic stays in
``core/graph_snapshot.py``.

Stream contract (#1725): the *product* of every command here is written with
plain ``print()`` so it lands on stdout — `cgc diff --json > changes.json` must
yield a parseable file. Diagnostics are raised as exceptions and rendered on
the stderr console by the caller.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from ..core.graph_snapshot import (
    Snapshot,
    SnapshotError,
    build_snapshot,
    diff_snapshots,
    dump_json,
    list_snapshots,
    load_snapshot,
    render_diff_text,
    render_snapshot_list_text,
    save_result_document,
    snapshot_list_document,
)
from ..core.graph_snapshot import save_snapshot as persist_snapshot
from . import config_manager

#: Snapshots live beside the rest of the per-user configuration (#1312).
SNAPSHOT_DIR_NAME = "snapshots"


def snapshot_directory() -> Path:
    return Path(config_manager.CONFIG_DIR) / SNAPSHOT_DIR_NAME


def snapshot_file(name: str) -> Path:
    return snapshot_directory() / f"{name}.json"


def context_info(ctx: Any) -> Dict[str, Any]:
    """The slice of a resolved context worth stamping into a snapshot.

    ``db_path`` is left out on purpose: it is machine-specific, and a snapshot
    shared between two checkouts should still diff cleanly.
    """
    return {
        "mode": str(getattr(ctx, "mode", "") or ""),
        "name": str(getattr(ctx, "context_name", "") or ""),
        "database": str(getattr(ctx, "database", "") or ""),
    }


def run_snapshot_save(
    db_manager: Any,
    *,
    name: str,
    force: bool,
    ctx: Any,
    as_json: bool = False,
) -> Snapshot:
    """Serialise the live index and write it to the snapshot directory."""
    snapshot = build_snapshot(db_manager, name=name, context=context_info(ctx))
    path = persist_snapshot(snapshot, snapshot_file(snapshot.name), force=force)
    if as_json:
        print(dump_json(save_result_document(snapshot, path)))
    else:
        counts = snapshot.counts
        print(
            f'Saved snapshot "{snapshot.name}" '
            f"({counts['nodes']} nodes, {counts['edges']} edges) to {path}"
        )
    return snapshot


def run_snapshot_list(as_json: bool = False) -> None:
    """List saved snapshots; never touches the database."""
    entries = list_snapshots(snapshot_directory())
    if as_json:
        print(dump_json(snapshot_list_document(entries)))
    else:
        print("\n".join(render_snapshot_list_text(entries)))


def load_base_snapshot(against: Optional[str]) -> Snapshot:
    """Resolve ``--against`` to a snapshot: an explicit name, else the newest."""
    directory = snapshot_directory()
    if against:
        path = snapshot_file(against)
        if not path.is_file():
            available = [entry.name for entry in list_snapshots(directory) if entry.snapshot]
            hint = f" Available: {', '.join(available)}" if available else " No snapshots saved yet."
            raise SnapshotError(f"Snapshot {against!r} not found in {directory}.{hint}")
        return load_snapshot(path)

    entries = [entry for entry in list_snapshots(directory) if entry.snapshot]
    if not entries:
        raise SnapshotError(
            f"No snapshots saved in {directory}. Run `cgc snapshot save --name <name>` first."
        )
    return entries[0].snapshot


def run_diff(
    db_manager: Any,
    *,
    base: Snapshot,
    ctx: Any,
    as_json: bool = False,
    limit: Optional[int] = None,
) -> bool:
    """Diff the live index against *base*. Returns True when anything changed.

    *base* is resolved by the caller first so a bad ``--against`` fails before
    a database connection is opened.
    """
    current = build_snapshot(db_manager, name="current", context=context_info(ctx))
    diff = diff_snapshots(base, current)
    if as_json:
        print(dump_json(diff))
    else:
        print("\n".join(render_diff_text(diff, limit)))
    return diff["summary"]["total"] > 0
