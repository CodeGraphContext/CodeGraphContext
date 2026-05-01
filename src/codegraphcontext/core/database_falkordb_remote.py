# src/codegraphcontext/core/database_falkordb_remote.py
"""
This module provides a thread-safe singleton manager for connecting to a
remote/hosted FalkorDB instance over TCP.

Unlike database_falkordb.py (which uses an embedded FalkorDB Lite via Unix sockets
and subprocesses), this module connects to an external FalkorDB server using
standard TCP connections. This is suitable for hosted FalkorDB instances
(e.g., FalkorDB Cloud) or self-hosted remote servers.

Configuration is read from environment variables:
- FALKORDB_HOST: Hostname of the FalkorDB server (required)
- FALKORDB_PORT: Port number (default: 6379)
- FALKORDB_PASSWORD: Authentication password (optional)
- FALKORDB_USERNAME: Authentication username (optional, default: None)
- FALKORDB_SSL: Enable SSL/TLS (default: false)
- FALKORDB_GRAPH_NAME: Graph name to use (default: codegraph)
"""
import os
import atexit
import threading
from typing import Optional, Tuple

from codegraphcontext.utils.debug_log import info_logger, error_logger

# Reuse the Neo4j-compatible wrapper classes from the embedded FalkorDB module
from codegraphcontext.core.database_falkordb import (
    FalkorDBDriverWrapper,
    FalkorDBSessionWrapper,
    FalkorDBResultWrapper,
)


class FalkorDBRemoteManager:
    """
    Manages a remote FalkorDB database connection as a singleton.
    Connects via TCP — no subprocess, no Unix socket.
    """
    _instance = None
    _driver = None
    _graph = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(FalkorDBRemoteManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return

        self.host = os.getenv('FALKORDB_HOST', 'localhost')
        self.port = int(os.getenv('FALKORDB_PORT', '6379'))
        self.password = os.getenv('FALKORDB_PASSWORD') or None
        self.username = os.getenv('FALKORDB_USERNAME') or None
        self.ssl = os.getenv('FALKORDB_SSL', 'false').lower() in ('true', '1', 'yes')
        self.graph_name = os.getenv('FALKORDB_GRAPH_NAME', 'codegraph')
        self._initialized = True

        atexit.register(self.shutdown)

    def get_driver(self):
        """
        Gets the remote FalkorDB connection, creating it if necessary.
        Thread-safe.

        Returns:
            A FalkorDBDriverWrapper that provides a Neo4j-like session interface.
        """
        if self._driver is None:
            with self._lock:
                if self._driver is None:
                    try:
                        from falkordb import FalkorDB

                        info_logger(
                            f"Connecting to remote FalkorDB at {self.host}:{self.port} "
                            f"(ssl={self.ssl})"
                        )

                        kwargs = {
                            'host': self.host,
                            'port': self.port,
                        }
                        if self.password:
                            kwargs['password'] = self.password
                        if self.username:
                            kwargs['username'] = self.username
                        if self.ssl:
                            kwargs['ssl'] = True

                        self._driver = FalkorDB(**kwargs)
                        self._graph = self._driver.select_graph(self.graph_name)

                        # Verify connectivity
                        self._graph.query("RETURN 1")
                        info_logger("Remote FalkorDB connection established successfully")
                        info_logger(f"Graph name: {self.graph_name}")

                    except ImportError as e:
                        error_logger(
                            "FalkorDB client is not installed. Install it with:\n"
                            "  pip install falkordb"
                        )
                        raise ValueError("FalkorDB client missing.") from e
                    except Exception as e:
                        error_logger(f"Failed to connect to remote FalkorDB: {e}")
                        raise

        return FalkorDBDriverWrapper(self._graph)

    def close_driver(self):
        """Closes the connection."""
        if self._driver is not None:
            info_logger("Closing FalkorDB Remote connection")
            self._driver = None
            self._graph = None

    def shutdown(self):
        """Clean up on exit. No subprocess to kill for remote connections."""
        self.close_driver()

    def is_connected(self) -> bool:
        """Checks if the database connection is currently active."""
        if self._graph is None:
            return False
        try:
            self._graph.query("RETURN 1")
            return True
        except Exception:
            return False

    def get_backend_type(self) -> str:
        """Returns the database backend type."""
        return 'falkordb-remote'

    @staticmethod
    def validate_config() -> Tuple[bool, Optional[str]]:
        """
        Validates remote FalkorDB configuration.

        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        host = os.getenv('FALKORDB_HOST')
        if not host:
            return False, "FALKORDB_HOST environment variable is not set."

        port_str = os.getenv('FALKORDB_PORT', '6379')
        try:
            port = int(port_str)
            if not (1 <= port <= 65535):
                return False, f"FALKORDB_PORT must be between 1 and 65535, got {port}."
        except ValueError:
            return False, f"FALKORDB_PORT must be a number, got '{port_str}'."

        return True, None

    @staticmethod
    def test_connection() -> Tuple[bool, Optional[str]]:
        """
        Tests the remote FalkorDB connection.
        """
        try:
            from falkordb import FalkorDB
        except ImportError:
            return False, (
                "FalkorDB client is not installed.\n"
                "Install it with: pip install falkordb"
            )

        host = os.getenv('FALKORDB_HOST')
        if not host:
            return False, "FALKORDB_HOST is not set."

        port = int(os.getenv('FALKORDB_PORT', '6379'))
        password = os.getenv('FALKORDB_PASSWORD') or None
        username = os.getenv('FALKORDB_USERNAME') or None
        ssl = os.getenv('FALKORDB_SSL', 'false').lower() in ('true', '1', 'yes')
        graph_name = os.getenv('FALKORDB_GRAPH_NAME', 'codegraph')

        try:
            kwargs = {'host': host, 'port': port}
            if password:
                kwargs['password'] = password
            if username:
                kwargs['username'] = username
            if ssl:
                kwargs['ssl'] = True

            db = FalkorDB(**kwargs)
            graph = db.select_graph(graph_name)
            graph.query("RETURN 1")
            return True, None
        except Exception as e:
            return False, f"Connection failed: {e}"
