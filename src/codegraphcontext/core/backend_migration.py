"""Explicit graph migration through a retained, backend-neutral .cgc bundle.

Each backend runs in its own interpreter. In particular, Kuzu and Ladybug
must never load their native extensions into the same process.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


_EMBEDDED_BACKENDS = {"kuzudb", "ladybugdb", "falkordb"}


class MigrationError(RuntimeError):
    """Migration stopped; the source graph has not been deleted."""


@dataclass(frozen=True)
class DatabaseLocation:
    backend: str
    path: Path | None = None

    def normalized(self) -> DatabaseLocation:
        if self.backend in _EMBEDDED_BACKENDS and self.path is None:
            raise MigrationError(f"An explicit database path is required for {self.backend}.")
        if self.backend not in _EMBEDDED_BACKENDS and self.path is not None:
            raise MigrationError(f"{self.backend} uses connection settings, not an embedded database path.")
        return DatabaseLocation(self.backend, self.path.expanduser().resolve() if self.path else None)


def _overlap(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def _run_stage(stage: str, location: DatabaseLocation, bundle_path: Path, python: str) -> None:
    env = os.environ.copy()
    # Factory selection must be explicit, independent of the invoking context.
    env["CGC_RUNTIME_DB_TYPE"] = location.backend
    env.pop("CGC_RUNTIME_DB_PATH", None)
    command = [
        python, "-m", "codegraphcontext.core.backend_migration", stage,
        location.backend, str(bundle_path), str(location.path) if location.path else "",
    ]
    try:
        result = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise MigrationError(f"Could not start {stage} interpreter {python!r}: {exc}") from exc
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or f"process exited {result.returncode}"
        raise MigrationError(f"{stage.capitalize()} failed for {location.backend}: {detail}")


def migrate_graph(
    source: DatabaseLocation,
    target: DatabaseLocation,
    bundle_path: Path,
    *,
    source_python: str | None = None,
) -> str:
    """Copy the whole indexed graph into an empty target, retaining the export.

    No default database, context, or source discovery is changed. A failed
    import can leave a partial target; the exported bundle remains available.
    Callers must stop writers to both databases for the duration of migration.
    """
    source, target = source.normalized(), target.normalized()
    bundle_path = bundle_path.expanduser().resolve()
    if bundle_path.suffix != ".cgc":
        raise MigrationError("The migration bundle must have a .cgc extension.")
    if source.path is not None and not source.path.exists():
        raise MigrationError(f"Source database does not exist: {source.path}")
    if source.path and target.path and _overlap(source.path, target.path):
        raise MigrationError("Source and target database paths must be separate and must not overlap.")
    for location in (source, target):
        if location.path and _overlap(bundle_path, location.path):
            raise MigrationError("The bundle must be stored outside both database paths.")

    # Reserve the output without overwriting a previous export or backup.
    try:
        with bundle_path.open("xb"):
            pass
    except OSError as exc:
        raise MigrationError(f"Cannot create migration bundle {bundle_path}: {exc}") from exc
    try:
        _run_stage("export", source, bundle_path, source_python or sys.executable)
    except BaseException:
        bundle_path.unlink(missing_ok=True)
        raise

    try:
        _run_stage("import", target, bundle_path, sys.executable)
    except MigrationError as exc:
        raise MigrationError(
            f"{exc}\nExport retained at {bundle_path}. The target may contain a partial import; "
            "inspect it before retrying with a fresh, empty target."
        ) from exc
    return f"Migrated {source.backend} to {target.backend}. Export retained at {bundle_path}."


def _run_worker(stage: str, backend: str, bundle_path: Path, db_path: str) -> None:
    from codegraphcontext.core import get_database_manager
    from codegraphcontext.core.cgc_bundle import CGCBundle

    manager = get_database_manager(db_path=db_path or None)
    try:
        actual_backend = manager.get_backend_type()
        if actual_backend != backend:
            raise MigrationError(f"Requested {backend}, but the factory selected {actual_backend}; refusing fallback.")
        bundle = CGCBundle(manager)
        if stage == "export":
            success, message = bundle.export_to_bundle(bundle_path, include_stats=False)
        elif stage == "import":
            # An absent/unreadable count is not evidence of an empty target.
            with manager.get_driver().session() as session:
                record = session.run("MATCH (n) RETURN count(n) AS count").single()
                if record is None or record["count"] != 0:
                    raise MigrationError("Target database is not confirmed empty; refusing to import.")
            success, message = bundle.import_from_bundle(bundle_path, clear_existing=False)
        else:
            raise MigrationError(f"Unknown migration stage: {stage}")
        if not success:
            raise MigrationError(message)
    finally:
        manager.close_driver()


if __name__ == "__main__":
    try:
        stage, backend, bundle_file, db_path = sys.argv[1:]
        _run_worker(stage, backend, Path(bundle_file), db_path)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
