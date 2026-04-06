# src/codegraphcontext/core/__init__.py
"""
Core database management module.

Supports Neo4j, FalkorDB Lite, remote FalkorDB, and KùzuDB backends.
Use DATABASE_TYPE environment variable to switch:
- DATABASE_TYPE=kuzudb - Uses embedded KùzuDB (Recommended for cross-platform zero-config)
- DATABASE_TYPE=falkordb - Uses embedded FalkorDB Lite (Unix-only)
- DATABASE_TYPE=falkordb-remote - Uses a remote/hosted FalkorDB server over TCP
- DATABASE_TYPE=neo4j - Uses Neo4j server
- If not set, auto-detects based on what's available

 Priority (no DATABASE_TYPE set):
  1. FalkorDB Lite  (Unix + Python 3.12+ + falkordblite installed)
  2. KùzuDB         (cross-platform fallback)
  3. Remote FalkorDB (if FALKORDB_HOST is set)
  4. Neo4j           (if credentials are configured)
"""
import os
import platform
from typing import Union, Optional
import importlib.util

def _is_kuzudb_available() -> bool:
    """Check if KùzuDB is installed."""
    try:
        return importlib.util.find_spec("kuzu") is not None
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
        return hasattr(redislite, 'falkordb_client')
    except ImportError:
        return False

def _is_falkordb_remote_configured() -> bool:
    """Check if a remote FalkorDB host is configured."""
    return bool(os.getenv('FALKORDB_HOST'))

def _is_neo4j_configured() -> bool:
    """Check if Neo4j is configured with credentials."""
    return all([
        os.getenv('NEO4J_URI'),
        os.getenv('NEO4J_USERNAME'),
        os.getenv('NEO4J_PASSWORD')
    ])

def get_database_manager(db_path: Optional[str] = None) -> Union['DatabaseManager', 'FalkorDBManager', 'FalkorDBRemoteManager', 'KuzuDBManager']:
    """
    Factory function to get the appropriate database manager based on configuration.

    Selection logic:
    1. Runtime Override: 'CGC_RUNTIME_DB_TYPE' (set via --database flag)
    2. Configured Default: 'DEFAULT_DATABASE' (set via 'cgc default database')
    3. Legacy Env Var: 'DATABASE_TYPE'
    4. Implicit Default: KùzuDB (Best cross-platform zero-config)
    5. Auto-detect: Remote FalkorDB (if FALKORDB_HOST is set)
    6. Fallback Default: FalkorDB Lite (if Unix and available)
    7. Fallback: Neo4j (if configured)
    """
    from codegraphcontext.utils.debug_log import info_logger

    # 1. Runtime Override (CLI flag) or Config/Env
    db_type = os.getenv('CGC_RUNTIME_DB_TYPE')
    if not db_type:
        db_type = os.getenv('DEFAULT_DATABASE')
    if not db_type:
        db_type = os.getenv('DATABASE_TYPE')

    if db_type:
        db_type = db_type.lower()
        if db_type == 'kuzudb':
            if not _is_kuzudb_available():
                raise ValueError("Database set to 'kuzudb' but Kùzu is not installed.\nRun 'pip install kuzu'")
            from .database_kuzu import KuzuDBManager
            info_logger(f"Using KùzuDB (explicit) at {db_path or 'default path'}")
            return KuzuDBManager(db_path=db_path)

        elif db_type == 'falkordb':
            if not _is_falkordb_available():
                info_logger("FalkorDB Lite is not supported or not installed. Falling back to KùzuDB.")
                if _is_kuzudb_available():
                    from .database_kuzu import KuzuDBManager
                    return KuzuDBManager()
                raise ValueError("Database set to 'falkordb' but FalkorDB Lite is not installed or not supported on this OS.\nRun 'pip install falkordblite'")
            
            from .database_falkordb import FalkorDBManager, FalkorDBUnavailableError
            try:
                mgr = FalkorDBManager(db_path=db_path)
                info_logger(f"Using FalkorDB Lite (explicit) at {db_path or 'default path'}")
                return mgr
            except FalkorDBUnavailableError as falkor_err:
                info_logger(f"FalkorDB Lite not functional ({falkor_err}). Falling back to KùzuDB.")
                if _is_kuzudb_available():
                    from .database_kuzu import KuzuDBManager
                    return KuzuDBManager(db_path=db_path)
                raise

        elif db_type == 'falkordb-remote':
            if not _is_falkordb_remote_configured():
                raise ValueError(
                    "Database set to 'falkordb-remote' but FALKORDB_HOST is not set.\n"
                    "Set the FALKORDB_HOST environment variable to your remote FalkorDB host."
                )
            from .database_falkordb_remote import FalkorDBRemoteManager
            info_logger("Using remote FalkorDB (explicit)")
            return FalkorDBRemoteManager()

        elif db_type == 'neo4j':
            if not _is_neo4j_configured():
                raise ValueError("Database set to 'neo4j' but it is not configured.\nRun 'cgc neo4j setup' to configure Neo4j.")
            from .database import DatabaseManager
            info_logger("Using Neo4j Server (explicit)")
            return DatabaseManager()
        else:
            raise ValueError(f"Unknown database type: '{db_type}'. Use 'kuzudb', 'falkordb', 'falkordb-remote', or 'neo4j'.")

    # 4. Auto-detect: Remote FalkorDB (if FALKORDB_HOST is set)
    # This takes priority over zero-config local backends because it's an explicit signal
    if _is_falkordb_remote_configured():
        from .database_falkordb_remote import FalkorDBRemoteManager
        info_logger("Using remote FalkorDB (auto-detected via FALKORDB_HOST)")
        return FalkorDBRemoteManager()

    # 5. Implicit Default -> FalkorDB Lite (Unix Zero Config)
    if _is_falkordb_available():
        from .database_falkordb import FalkorDBManager, FalkorDBUnavailableError
        try:
            mgr = FalkorDBManager(db_path=db_path)
            info_logger(f"Using FalkorDB Lite (default) at {db_path or 'default path'}")
            return mgr
        except FalkorDBUnavailableError as falkor_err:
            info_logger(
                f"FalkorDB Lite not functional in this environment ({falkor_err}). "
                "Falling back to KùzuDB."
            )
            # fall through to KùzuDB below

    # 6. Implicit Default -> KùzuDB (Best Zero Config)
    if _is_kuzudb_available():
        from .database_kuzu import KuzuDBManager
        info_logger(f"Using KùzuDB (default) at {db_path or 'default path'}")
        return KuzuDBManager(db_path=db_path)

    # 7. Fallback if configured
    if _is_neo4j_configured():
        from .database import DatabaseManager
        info_logger("Using Neo4j Server (auto-detected)")
        return DatabaseManager()

    error_msg = "No database backend available.\n"
    error_msg += "Recommended: Install KùzuDB for zero-config ('pip install kuzu')\n"

    if platform.system() != "Windows":
        error_msg += "Alternative: Install FalkorDB Lite ('pip install falkordblite')\n"

    error_msg += "Alternative: Run 'cgc neo4j setup' to configure Neo4j."

    raise ValueError(error_msg)

# For backward compatibility, export managers
from .database import DatabaseManager
from .database_falkordb import FalkorDBManager
from .database_falkordb_remote import FalkorDBRemoteManager
from .database_kuzu import KuzuDBManager

__all__ = ['DatabaseManager', 'FalkorDBManager', 'FalkorDBRemoteManager', 'KuzuDBManager', 'get_database_manager']
