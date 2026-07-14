# src/codegraphcontext/core/__init__.py
"""
Core database management module.

Supports Neo4j, FalkorDB Lite, remote FalkorDB, LadybugDB, and Nornic backends.

Explicit backend selection (see ``get_database_manager``):
- ``CGC_RUNTIME_DB_TYPE``: per-invocation override.
- ``DEFAULT_DATABASE``: configured default.

When neither is set, implicit selection:
- Remote FalkorDB if ``FALKORDB_HOST`` is set.
- Else Unix: FalkorDB Lite when usable, LadybugDB, then Neo4j/Nornic.
- Else Windows: LadybugDB, then Neo4j/Nornic.
"""
from __future__ import annotations

import importlib.util
import os
import platform
from pathlib import Path
from typing import Optional

# Retained for compatibility with callers that inspect this module attribute.
# FalkorDB startup failures are now tracked by FalkorDBManager per database
# configuration, rather than disabling the backend for the whole process.
_FALKORDB_DISABLED = False


def _fallback_db_path_for(
    db_path: Optional[str],
    target_backend: str,
) -> Optional[str]:
    """
    Adjust a FalkorDB-specific db_path when falling back to another backend.

    Default DB paths embed the backend name as the last path segment. Reusing
    the FalkorDB directory for another embedded backend would mix storage
    formats, so swap the trailing segment for the target backend name.
    """
    if not db_path:
        return db_path

    path = Path(db_path)
    if path.name.lower() in ("falkordb", "falkordb.db"):
        from codegraphcontext.utils.debug_log import warning_logger

        new_path = str(path.parent / target_backend)
        warning_logger(
            f"FalkorDB fallback: db_path '{db_path}' points at FalkorDB "
            f"data; using '{new_path}' for '{target_backend}' instead."
        )
        return new_path

    return db_path


def _try_fallback_backends(db_path: Optional[str], candidates, *, reason: str):
    """
    Return the first available backend from ``candidates``, naming it in the log.

    Every fallback path funnels through here so the backend a user actually ends
    up on is always recorded. A silent switch is effectively undebuggable: the
    only trace left is that the *requested* backend was requested, so an
    interpreter where FalkorDB Lite cannot load looks identical to one where it
    loaded fine, and queries run against a different (often empty) database.

    Returns ``None`` when no candidate is available, so callers keep control of
    the error they raise.
    """
    from codegraphcontext.utils.debug_log import warning_logger

    for name in candidates:
        if name == 'ladybugdb' and _is_ladybugdb_available():
            from .database_ladybug import LadybugDBManager
            path = _fallback_db_path_for(db_path, 'ladybugdb')
            warning_logger(
                f"Database backend fallback: {reason} "
                f"Now using LadybugDB at {path or 'default path'}."
            )
            return LadybugDBManager(db_path=path)
        if name == 'neo4j' and _is_neo4j_configured():
            from .database import DatabaseManager
            warning_logger(f"Database backend fallback: {reason} Now using Neo4j Server.")
            return DatabaseManager()
        if name == 'nornic' and _is_nornic_configured():
            from .database_nornic import NornicDBManager
            warning_logger(f"Database backend fallback: {reason} Now using Nornic DB.")
            return NornicDBManager()
    return None


def mark_falkordb_unavailable() -> None:
    """Compatibility hook; startup failures are scoped by FalkorDBManager."""


def is_falkordb_usable() -> bool:
    """True when FalkorDB Lite is available on this system."""
    return _is_falkordb_available()


def _is_ladybugdb_available() -> bool:
    """Check if LadybugDB is installed."""
    try:
        return importlib.util.find_spec("ladybug") is not None
    except ImportError:
        return False


def _is_falkordb_available() -> bool:
    """Check if FalkorDB Lite is installed (Unix only)."""
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
    """Check if a remote FalkorDB host is configured."""
    return bool(os.getenv("FALKORDB_HOST"))


def _is_neo4j_configured() -> bool:
    """Check if Neo4j is configured with credentials."""
    return all(
        [
            os.getenv("NEO4J_URI"),
            os.getenv("NEO4J_USERNAME"),
            os.getenv("NEO4J_PASSWORD"),
        ]
    )


def _is_nornic_configured() -> bool:
    """Check if Nornic is configured with credentials."""
    return all(
        [
            os.getenv("NORNIC_URI"),
            os.getenv("NORNIC_USERNAME"),
            os.getenv("NORNIC_PASSWORD"),
        ]
    )


def _fallback_to_available_backend(db_path: Optional[str], reason: str):
    """Resolve the next supported backend after FalkorDB Lite cannot run."""
    from codegraphcontext.utils.debug_log import info_logger

    info_logger(reason)
    if _is_ladybugdb_available():
        from .database_ladybug import LadybugDBManager

        ladybug_path = _fallback_db_path_for(db_path, "ladybugdb")
        mgr = LadybugDBManager(db_path=ladybug_path)
        _maybe_migrate_legacy_kuzudb(mgr, ladybug_path)
        return mgr
    if _is_neo4j_configured():
        from .database import DatabaseManager

        info_logger("Using Neo4j Server (fallback)")
        mgr = DatabaseManager()
        _maybe_migrate_legacy_kuzudb(mgr, db_path)
        return mgr
    if _is_nornic_configured():
        from .database_nornic import NornicDBManager

        mgr = NornicDBManager()
        _maybe_migrate_legacy_kuzudb(mgr, db_path)
        return mgr
    return None


def get_database_manager(
    db_path: Optional[str] = None,
):
    """
    Factory function to get the configured database manager.

    Selection logic:
    1. Runtime override: ``CGC_RUNTIME_DB_TYPE``.
    2. Configured default: ``DEFAULT_DATABASE``.
    3. Implicit fallback based on available local/remote backends.
    """
    from codegraphcontext.utils.debug_log import info_logger

    db_type = os.getenv("CGC_RUNTIME_DB_TYPE") or os.getenv("DEFAULT_DATABASE")

    if db_type:
        db_type = db_type.lower()
        if db_type == "falkordb":
            if not is_falkordb_usable():
                message = (
                    "FalkorDB Lite disabled after earlier failure."
                    if _FALKORDB_DISABLED
                    else "FalkorDB Lite is not supported or not installed."
                )
                raise ValueError(
                    f"Database set to 'falkordb' but {message}\n"
                    "Explicit FalkorDB selection is strict and will not "
                    "fall back to LadybugDB. Fix FalkorDB Lite or choose "
                    "another backend explicitly."
                )

            from .database_falkordb import (
                FalkorDBManager,
                FalkorDBUnavailableError,
            )

            try:
                mgr = FalkorDBManager(db_path=db_path)
                mgr.get_driver()
                info_logger(
                    "Using FalkorDB Lite (explicit) at "
                    f"{db_path or 'default path'}"
                )

                # Migration runs after backend resolution so a configured
                # FalkorDB target stays the target. Users who never chose a DB
                # still land on the normal implicit default before any data
                # moves.
                _maybe_migrate_legacy_kuzudb(mgr, db_path)
                return mgr
            except FalkorDBUnavailableError as falkor_err:
                mark_falkordb_unavailable()
                raise ValueError(
                    "Database set to 'falkordb' but FalkorDB Lite is not "
                    f"functional: {falkor_err}.\n"
                    "Explicit FalkorDB selection is strict and will not "
                    "fall back to LadybugDB. Fix FalkorDB Lite or choose "
                    "another backend explicitly."
                ) from falkor_err

        if db_type == "falkordb-remote":
            if not _is_falkordb_remote_configured():
                raise ValueError(
                    "Database set to 'falkordb-remote' but FALKORDB_HOST is "
                    "not set.\nSet FALKORDB_HOST to your remote FalkorDB host."
                )
            from .database_falkordb_remote import FalkorDBRemoteManager

            info_logger("Using remote FalkorDB (explicit)")
            mgr = FalkorDBRemoteManager()

            # Keep Kuzu migration tied to the selected backend, not to a
            # replacement engine. That preserves explicit remote deployments.
            _maybe_migrate_legacy_kuzudb(mgr, db_path)
            return mgr

        if db_type == "neo4j":
            if not _is_neo4j_configured():
                raise ValueError(
                    "Database set to 'neo4j' but it is not configured.\n"
                    "Run 'cgc neo4j setup' to configure Neo4j."
                )
            from .database import DatabaseManager

            info_logger("Using Neo4j Server (explicit)")
            mgr = DatabaseManager()

            # Server-backed targets are valid migration destinations too. The
            # bundle importer handles the write shape for each backend.
            _maybe_migrate_legacy_kuzudb(mgr, db_path)
            return mgr

        if db_type == "nornic":
            if not _is_nornic_configured():
                raise ValueError(
                    "Database set to 'nornic' but it is not configured."
                )
            from .database_nornic import NornicDBManager

            info_logger("Using Nornic DB (explicit)")
            mgr = NornicDBManager()

            # Server-backed targets are valid migration destinations too. The
            # bundle importer handles the write shape for each backend.
            _maybe_migrate_legacy_kuzudb(mgr, db_path)
            return mgr

        if db_type == "ladybugdb":
            if not _is_ladybugdb_available():
                raise ValueError(
                    "Database set to 'ladybugdb' but LadybugDB is not "
                    "installed.\nRun 'pip install ladybug'"
                )
            from .database_ladybug import LadybugDBManager

            info_logger(
                f"Using LadybugDB (explicit) at {db_path or 'default path'}"
            )
            mgr = LadybugDBManager(db_path=db_path)

            # Ladybug is one possible destination, not a hard-coded migration
            # target. The factory decides first, then migration follows.
            _maybe_migrate_legacy_kuzudb(mgr, db_path)
            return mgr

        raise ValueError(
            f"Unknown database type: '{db_type}'. Use 'ladybugdb', "
            "'falkordb', 'falkordb-remote', 'neo4j', or 'nornic'."
        )

    if _is_falkordb_remote_configured():
        from .database_falkordb_remote import FalkorDBRemoteManager

        info_logger("Using remote FalkorDB (auto-detected via FALKORDB_HOST)")
        mgr = FalkorDBRemoteManager()

        # FALKORDB_HOST is an explicit infra signal even without
        # DEFAULT_DATABASE, so migration follows the remote backend.
        _maybe_migrate_legacy_kuzudb(mgr, db_path)
        return mgr

    if is_falkordb_usable():
        from .database_falkordb import (
            FalkorDBManager,
            FalkorDBUnavailableError,
        )

        try:
            mgr = FalkorDBManager(db_path=db_path)
            mgr.get_driver()
            info_logger(
                f"Using FalkorDB Lite (default) at "
                f"{db_path or 'default path'}"
            )

            # FalkorDB Lite is the Unix default when available, so legacy data
            # should land here unless config says otherwise.
            _maybe_migrate_legacy_kuzudb(mgr, db_path)
            return mgr
        except FalkorDBUnavailableError as falkor_err:
            mark_falkordb_unavailable()
            info_logger(
                "FalkorDB Lite not functional in this environment "
                f"({falkor_err}). Falling back to LadybugDB."
            )

            # fall through to LadybugDB below

    if _is_ladybugdb_available():
        from .database_ladybug import LadybugDBManager

        ladybug_path = _fallback_db_path_for(db_path, "ladybugdb")
        info_logger(
            f"Using LadybugDB (default) at {ladybug_path or 'default path'}"
        )
        mgr = LadybugDBManager(db_path=ladybug_path)

        # Ladybug receives migration only when it is the resolved default or
        # explicit selection.
        _maybe_migrate_legacy_kuzudb(mgr, ladybug_path)
        return mgr

    if _is_neo4j_configured():
        from .database import DatabaseManager

        info_logger("Using Neo4j Server (auto-detected)")
        mgr = DatabaseManager()

        # Neo4j can be the implicit fallback when credentials exist, so it must
        # participate in migration rather than forcing a local embedded target.
        _maybe_migrate_legacy_kuzudb(mgr, db_path)
        return mgr

    if _is_nornic_configured():
        from .database_nornic import NornicDBManager

        info_logger("Using Nornic DB (auto-detected)")
        mgr = NornicDBManager()

        # Nornic follows the same server-backed import path as Neo4j.
        _maybe_migrate_legacy_kuzudb(mgr, db_path)
        return mgr

    error_msg = "No database backend available.\n"
    error_msg += (
        "Recommended: Install LadybugDB for zero-config ('pip install "
        "ladybug')\n"
    )

    if platform.system() != "Windows":
        error_msg += (
            "Alternative: Install FalkorDB Lite ('pip install falkordblite')\n"
        )

    error_msg += "Alternative: Run 'cgc neo4j setup' to configure Neo4j."

    raise ValueError(error_msg)


def _maybe_migrate_legacy_kuzudb(
    target_manager,
    db_path: Optional[str],
) -> None:
    """Migrate an archived KuzuDB legacy store into the selected backend."""
    try:
        from .legacy_kuzu_migration import migrate_legacy_kuzudb_to_manager
    except Exception as e:
        from codegraphcontext.utils.debug_log import warning_logger

        warning_logger(
            "Legacy KuzuDB migration helper could not be loaded: "
            f"{e}"
        )
        return

    # KuzuDB is archived upstream and fails to install on Python 3.14+ (pip
    # falls back to pyproject/setuptools and cannot build the wheel), so this
    # is intentionally migration-only: keep the user's selected replacement
    # backend and only look for old data.
    # Context resolution may pass db_path explicitly. Auto-detected defaults do
    # not, so fall back to the manager's resolved path to find a sibling
    # legacy `kuzudb` directory.
    target_path = db_path or getattr(target_manager, "db_path", None)
    success, message = migrate_legacy_kuzudb_to_manager(
        target_manager,
        target_db_path=target_path,
    )
    if message and not success:
        from codegraphcontext.utils.debug_log import (
            warning_logger as _warning_logger,
        )

        # Missing legacy data and non-empty targets are normal startup states.
        # Warn only when a user has old Kuzu data and action is needed.
        if (
            "No legacy KuzuDB store found" not in message
            and "Target database already contains data" not in message
        ):
            _warning_logger(message)
    elif success:
        from codegraphcontext.utils.debug_log import (
            info_logger as _info_logger,
        )

        _info_logger(message)


# Lazy backward-compatible exports avoid importing optional drivers at import
# time. Accessing a manager still imports the concrete module when needed.
_LAZY_IMPORTS = {
    "DatabaseManager": ".database",
    "FalkorDBManager": ".database_falkordb",
    "FalkorDBRemoteManager": ".database_falkordb_remote",
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
    "LadybugDBManager",
    "NornicDBManager",
    "get_database_manager",
    "is_falkordb_usable",
    "mark_falkordb_unavailable",
]
