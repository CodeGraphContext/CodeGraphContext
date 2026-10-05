"""Database backend selection and legacy-store migration.

LadybugDB is the maintained Kuzu-dialect embedded backend. KuzuDB remains
available only when explicitly selected and separately installed so existing
deployments retain a migration window; it is never chosen implicitly.
"""

from __future__ import annotations

import importlib.util
import os
import platform
import threading
from pathlib import Path
from typing import Optional

# Retained for compatibility with callers that inspect this module attribute.
# FalkorDB startup failures are scoped by FalkorDBManager configuration.
_FALKORDB_DISABLED = False

# Probe a target once per process so factory calls do not repeatedly inspect
# disk or retry a one-way migration.
_KUZU_MIGRATION_PROBED_PATHS: set[str] = set()
_KUZU_MIGRATION_PROBE_LOCK = threading.Lock()


def _fallback_db_path_for(db_path: Optional[str], target_backend: str) -> Optional[str]:
    """Move conventional embedded paths to a directory owned by the target."""
    if not db_path:
        return db_path

    path = Path(db_path)
    source_names = {"falkordb", "falkordb.db", "kuzudb", "kuzudb.db"}
    if path.name.lower() not in source_names:
        return db_path

    target_path = str(path.parent / target_backend)
    if target_path != db_path:
        from codegraphcontext.utils.debug_log import warning_logger

        warning_logger(
            f"Database backend replacement: '{db_path}' contains data for a different engine; "
            f"using '{target_path}' for '{target_backend}' instead."
        )
    return target_path


def _legacy_kuzu_replacement_path(db_path: Optional[str]) -> Optional[str]:
    """Return a Ladybug path that can never overwrite an explicit Kuzu path."""
    if not db_path:
        return db_path
    conventional = _fallback_db_path_for(db_path, "ladybugdb")
    if conventional != db_path:
        return conventional
    path = Path(db_path)
    return str(path.with_name(f"{path.name}.ladybugdb"))


def _migration_probe_key(target_manager, target_db_path: Optional[str]) -> str:
    backend_getter = getattr(target_manager, "get_backend_type", None)
    backend = backend_getter() if callable(backend_getter) else type(target_manager).__name__
    if target_db_path:
        try:
            return f"{backend}:{Path(target_db_path).expanduser().resolve(strict=False)}"
        except (OSError, RuntimeError, ValueError):
            return f"{backend}:{target_db_path}"
    return f"{backend}:default"


def _maybe_migrate_legacy_kuzudb(
    target_manager,
    db_path: Optional[str],
    *,
    source_db_path: Optional[str] = None,
) -> None:
    """Probe and migrate once for each resolved target backend/path."""
    backend_getter = getattr(target_manager, "get_backend_type", None)
    if not callable(backend_getter) or backend_getter() == "kuzudb":
        return

    target_db_path = db_path or getattr(target_manager, "db_path", None)
    probe_key = _migration_probe_key(target_manager, target_db_path)
    from codegraphcontext.core.legacy_kuzu_migration import migrate_legacy_kuzudb_to_manager
    from codegraphcontext.utils.debug_log import debug_log, info_logger, warning_logger

    # Keep the lock for the complete probe/import. A second factory call for
    # the same target must not receive a writable manager while the first one
    # is still importing the legacy graph.
    with _KUZU_MIGRATION_PROBE_LOCK:
        if probe_key in _KUZU_MIGRATION_PROBED_PATHS:
            return
        _KUZU_MIGRATION_PROBED_PATHS.add(probe_key)

        success, message = migrate_legacy_kuzudb_to_manager(
            target_manager,
            target_db_path=target_db_path,
            source_db_path=source_db_path,
        )
        if success:
            info_logger(message)
        elif message.startswith("No legacy KuzuDB store found"):
            debug_log(message)
        else:
            warning_logger(message)


def _ready_manager(
    manager,
    db_path: Optional[str],
    *,
    source_db_path: Optional[str] = None,
):
    _maybe_migrate_legacy_kuzudb(manager, db_path, source_db_path=source_db_path)
    return manager


def _try_fallback_backends(
    db_path: Optional[str],
    candidates,
    *,
    reason: str,
    legacy_kuzu_source: Optional[str] = None,
):
    """Return the first maintained fallback backend and name it in the log."""
    from codegraphcontext.utils.debug_log import warning_logger

    for name in candidates:
        if name == "ladybugdb" and _is_ladybugdb_available():
            from .database_ladybug import LadybugDBManager

            path = (
                _legacy_kuzu_replacement_path(db_path)
                if legacy_kuzu_source is not None
                else _fallback_db_path_for(db_path, "ladybugdb")
            )
            warning_logger(
                f"Database backend fallback: {reason} Now using LadybugDB at {path or 'default path'}."
            )
            manager = LadybugDBManager(db_path=path)
            return _ready_manager(manager, path, source_db_path=legacy_kuzu_source)
        if name == "neo4j" and _is_neo4j_configured():
            from .database import DatabaseManager

            warning_logger(f"Database backend fallback: {reason} Now using Neo4j Server.")
            return _ready_manager(DatabaseManager(), db_path, source_db_path=legacy_kuzu_source)
        if name == "nornic" and _is_nornic_configured():
            from .database_nornic import NornicDBManager

            warning_logger(f"Database backend fallback: {reason} Now using Nornic DB.")
            return _ready_manager(NornicDBManager(), db_path, source_db_path=legacy_kuzu_source)
    return None


def mark_falkordb_unavailable() -> None:
    """Compatibility hook; startup failures are scoped by FalkorDBManager."""


def is_falkordb_usable() -> bool:
    """Return whether FalkorDB Lite is available on this system."""
    return _is_falkordb_available()


def _is_kuzudb_available() -> bool:
    """Return whether the separately installed legacy Kuzu driver exists."""
    try:
        return importlib.util.find_spec("kuzu") is not None
    except (ImportError, ValueError):
        return False


def _is_ladybugdb_available() -> bool:
    """Return whether LadybugDB is installed."""
    try:
        return importlib.util.find_spec("ladybug") is not None
    except (ImportError, ValueError):
        return False


def _is_falkordb_available() -> bool:
    """Return whether FalkorDB Lite is installed and supported."""
    if platform.system() == "Windows":
        return False

    import sys

    if sys.version_info < (3, 12):
        return False
    try:
        import redislite

        return hasattr(redislite, "falkordb_client")
    except ImportError:
        return False


def _is_falkordb_remote_configured() -> bool:
    return bool(os.getenv("FALKORDB_HOST"))


def _is_neo4j_configured() -> bool:
    return all(os.getenv(key) for key in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"))


def _is_nornic_configured() -> bool:
    return all(os.getenv(key) for key in ("NORNIC_URI", "NORNIC_USERNAME", "NORNIC_PASSWORD"))


def get_database_manager(db_path: Optional[str] = None):
    """Resolve the configured manager, preferring maintained runtime backends."""
    from codegraphcontext.utils.debug_log import info_logger, warning_logger

    db_type = os.getenv("CGC_RUNTIME_DB_TYPE") or os.getenv("DEFAULT_DATABASE")
    if db_type:
        db_type = db_type.lower()

        if db_type == "kuzudb":
            if _is_kuzudb_available():
                from .database_kuzu import KuzuDBManager

                warning_logger(
                    "KuzuDB is a legacy backend archived upstream. Use LadybugDB for maintained embedded "
                    "operation and migrate this store before a future CGC release removes runtime selection."
                )
                return KuzuDBManager(db_path=db_path)

            manager = _try_fallback_backends(
                db_path,
                ("ladybugdb", "neo4j", "nornic"),
                reason="database was set to legacy 'kuzudb', but Kuzu is not installed.",
                legacy_kuzu_source=db_path,
            )
            if manager is not None:
                return manager
            raise ValueError(
                "Database set to legacy 'kuzudb', but Kuzu is not installed and no maintained replacement "
                "is available. Install 'codegraphcontext[ladybug]' and migrate the legacy store."
            )

        if db_type == "falkordb":
            if not is_falkordb_usable():
                manager = _try_fallback_backends(
                    db_path,
                    ("ladybugdb", "neo4j", "nornic"),
                    reason="FalkorDB Lite is not supported or not installed here.",
                )
                if manager is not None:
                    return manager
                raise ValueError(
                    "Database set to 'falkordb', but FalkorDB Lite is not installed or supported on this OS. "
                    "Install 'falkordblite' or configure LadybugDB, Neo4j, or Nornic."
                )

            from .database_falkordb import FalkorDBManager, FalkorDBUnavailableError

            try:
                manager = FalkorDBManager(db_path=db_path)
                manager.get_driver()
                info_logger(f"Using FalkorDB Lite (explicit) at {db_path or 'default path'}")
                return _ready_manager(manager, db_path)
            except FalkorDBUnavailableError as falkor_error:
                mark_falkordb_unavailable()
                manager = _try_fallback_backends(
                    db_path,
                    ("ladybugdb", "neo4j", "nornic"),
                    reason=f"FalkorDB Lite was requested but is not functional ({falkor_error}).",
                )
                if manager is not None:
                    return manager
                raise

        if db_type == "falkordb-remote":
            if not _is_falkordb_remote_configured():
                raise ValueError(
                    "Database set to 'falkordb-remote', but FALKORDB_HOST is not set. Set FALKORDB_HOST to "
                    "the remote FalkorDB host."
                )
            from .database_falkordb_remote import FalkorDBRemoteManager

            info_logger("Using remote FalkorDB (explicit)")
            return _ready_manager(FalkorDBRemoteManager(), db_path)

        if db_type == "neo4j":
            if not _is_neo4j_configured():
                raise ValueError("Database set to 'neo4j', but it is not configured. Run 'cgc neo4j setup'.")
            from .database import DatabaseManager

            info_logger("Using Neo4j Server (explicit)")
            return _ready_manager(DatabaseManager(), db_path)

        if db_type == "nornic":
            if not _is_nornic_configured():
                raise ValueError("Database set to 'nornic', but it is not configured.")
            from .database_nornic import NornicDBManager

            info_logger("Using Nornic DB (explicit)")
            return _ready_manager(NornicDBManager(), db_path)

        if db_type == "ladybugdb":
            if not _is_ladybugdb_available():
                raise ValueError(
                    "Database set to 'ladybugdb', but LadybugDB is not installed. "
                    "Run 'pip install codegraphcontext[ladybug]'."
                )
            from .database_ladybug import LadybugDBManager

            ladybug_path = _fallback_db_path_for(db_path, "ladybugdb")
            info_logger(f"Using LadybugDB (explicit) at {ladybug_path or 'default path'}")
            return _ready_manager(LadybugDBManager(db_path=ladybug_path), ladybug_path)

        raise ValueError(
            f"Unknown database type: '{db_type}'. Use 'ladybugdb', 'falkordb', 'falkordb-remote', 'neo4j', "
            "'nornic', or legacy 'kuzudb'."
        )

    if _is_falkordb_remote_configured():
        from .database_falkordb_remote import FalkorDBRemoteManager

        info_logger("Using remote FalkorDB (auto-detected via FALKORDB_HOST)")
        return _ready_manager(FalkorDBRemoteManager(), db_path)

    if is_falkordb_usable():
        from .database_falkordb import FalkorDBManager, FalkorDBUnavailableError

        try:
            manager = FalkorDBManager(db_path=db_path)
            manager.get_driver()
            info_logger(f"Using FalkorDB Lite (default) at {db_path or 'default path'}")
            return _ready_manager(manager, db_path)
        except FalkorDBUnavailableError as falkor_error:
            mark_falkordb_unavailable()
            warning_logger(
                f"FalkorDB Lite is not functional in this environment ({falkor_error}); trying LadybugDB."
            )

    if _is_ladybugdb_available():
        from .database_ladybug import LadybugDBManager

        ladybug_path = _fallback_db_path_for(db_path, "ladybugdb")
        info_logger(f"Using LadybugDB (default) at {ladybug_path or 'default path'}")
        return _ready_manager(LadybugDBManager(db_path=ladybug_path), ladybug_path)

    if _is_neo4j_configured():
        from .database import DatabaseManager

        info_logger("Using Neo4j Server (auto-detected)")
        return _ready_manager(DatabaseManager(), db_path)

    if _is_nornic_configured():
        from .database_nornic import NornicDBManager

        info_logger("Using Nornic DB (auto-detected)")
        return _ready_manager(NornicDBManager(), db_path)

    message = "No maintained database backend is available.\n"
    message += "Recommended: install LadybugDB ('pip install codegraphcontext[ladybug]').\n"
    if platform.system() != "Windows":
        message += "Alternative: install FalkorDB Lite ('pip install codegraphcontext[falkordb-embedded]').\n"
    message += "Alternative: run 'cgc neo4j setup' to configure Neo4j."
    raise ValueError(message)


# Lazy compatibility exports keep optional drivers out of import-time startup.
_LAZY_IMPORTS = {
    "DatabaseManager": ".database",
    "FalkorDBManager": ".database_falkordb",
    "FalkorDBRemoteManager": ".database_falkordb_remote",
    "KuzuDBManager": ".database_kuzu",
    "LadybugDBManager": ".database_ladybug",
    "NornicDBManager": ".database_nornic",
}


def __getattr__(name: str):
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name], __package__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DatabaseManager",
    "FalkorDBManager",
    "FalkorDBRemoteManager",
    "KuzuDBManager",
    "LadybugDBManager",
    "NornicDBManager",
    "get_database_manager",
]
