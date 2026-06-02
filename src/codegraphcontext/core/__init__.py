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
import importlib.util
import os
import platform
from pathlib import Path
from typing import Optional, Union

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

        return LadybugDBManager(
            db_path=_fallback_db_path_for(db_path, "ladybugdb")
        )
    if _is_neo4j_configured():
        from .database import DatabaseManager

        info_logger("Using Neo4j Server (fallback)")
        return DatabaseManager()
    if _is_nornic_configured():
        from .database_nornic import NornicDBManager

        return NornicDBManager()
    return None


def get_database_manager(
    db_path: Optional[str] = None,
) -> Union[
    "DatabaseManager",
    "FalkorDBManager",
    "FalkorDBRemoteManager",
    "NornicDBManager",
    "LadybugDBManager",
]:
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
                mgr = _try_fallback_backends(
                    db_path,
                    ('ladybugdb', 'neo4j', 'nornic'),
                    reason="FalkorDB Lite is not supported or not installed here.",
                )
                if mgr is not None:
                    return mgr
                raise ValueError(
                    "Database set to 'falkordb' but FalkorDB Lite is not "
                    "installed or not supported on this OS.\n"
                    "Install 'falkordblite' or configure 'ladybugdb', "
                    "'neo4j', or 'nornic'."
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
                return mgr
            except FalkorDBUnavailableError as falkor_err:
                mark_falkordb_unavailable()
                mgr = _try_fallback_backends(
                    db_path,
                    ('ladybugdb', 'neo4j', 'nornic'),
                    reason=f"FalkorDB Lite was requested but is not functional ({falkor_err}).",
                )
                if mgr is not None:
                    return mgr
                raise

        if db_type == "falkordb-remote":
            if not _is_falkordb_remote_configured():
                raise ValueError(
                    "Database set to 'falkordb-remote' but FALKORDB_HOST is "
                    "not set.\nSet FALKORDB_HOST to your remote FalkorDB host."
                )
            from .database_falkordb_remote import FalkorDBRemoteManager

            info_logger("Using remote FalkorDB (explicit)")
            return FalkorDBRemoteManager()

        if db_type == "neo4j":
            if not _is_neo4j_configured():
                raise ValueError(
                    "Database set to 'neo4j' but it is not configured.\n"
                    "Run 'cgc neo4j setup' to configure Neo4j."
                )
            from .database import DatabaseManager

            info_logger("Using Neo4j Server (explicit)")
            return DatabaseManager()

        if db_type == "nornic":
            if not _is_nornic_configured():
                raise ValueError(
                    "Database set to 'nornic' but it is not configured."
                )
            from .database_nornic import NornicDBManager

            info_logger("Using Nornic DB (explicit)")
            return NornicDBManager()

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
            return LadybugDBManager(db_path=db_path)

        raise ValueError(
            f"Unknown database type: '{db_type}'. Use 'ladybugdb', "
            "'falkordb', 'falkordb-remote', 'neo4j', or 'nornic'."
        )

    if _is_falkordb_remote_configured():
        from .database_falkordb_remote import FalkorDBRemoteManager

        info_logger("Using remote FalkorDB (auto-detected via FALKORDB_HOST)")
        return FalkorDBRemoteManager()

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
            return mgr
        except FalkorDBUnavailableError as falkor_err:
            mark_falkordb_unavailable()
            info_logger(
                "FalkorDB Lite not functional in this environment "
                f"({falkor_err}). Falling back to LadybugDB."
            )

    if _is_ladybugdb_available():
        from .database_ladybug import LadybugDBManager

        ladybug_path = _fallback_db_path_for(db_path, "ladybugdb")
        info_logger(
            f"Using LadybugDB (default) at {ladybug_path or 'default path'}"
        )
        return LadybugDBManager(db_path=ladybug_path)

    if _is_neo4j_configured():
        from .database import DatabaseManager

        info_logger("Using Neo4j Server (auto-detected)")
        return DatabaseManager()

    if _is_nornic_configured():
        from .database_nornic import NornicDBManager

        info_logger("Using Nornic DB (auto-detected)")
        return NornicDBManager()

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
