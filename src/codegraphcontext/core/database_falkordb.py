# src/codegraphcontext/core/database_falkordb.py
"""
This module provides a thread-safe singleton manager for the FalkorDB Lite database connection.
FalkorDB Lite is an embedded graph database that requires no external server setup.
"""

class FalkorDBUnavailableError(RuntimeError):
    """
    Raised when FalkorDB Lite is installed but cannot actually run in this
    environment (e.g. falkordb.so not found in a PyInstaller bundle,
    or GRAPH.QUERY not available). Callers should fall back to KùzuDB.
    """
import os
import sys
import subprocess
import time
import atexit
import threading
import re
from pathlib import Path
from typing import Optional, Tuple

from codegraphcontext.utils.debug_log import debug_log, info_logger, error_logger, warning_logger

# ---------------------------------------------------------------------------
# Compatibility patch: newer redis-py releases assume every Connection exposes
# ``host`` and ``port`` attributes, but ``UnixDomainSocketConnection`` historically
# has neither. Two failure modes have been observed in the wild:
#
#   1. redis-py >= 5.x added OpenTelemetry error telemetry that reads ``conn.port``
#      inside its error handler. The missing attribute raised a secondary
#      ``AttributeError`` that masked the real connection error.
#   2. redis-py >= 6.x added a maintenance-notifications handshake
#      (``activate_maint_notifications_handling_if_enabled`` →
#      ``_enable_maintenance_notifications``) that raises ``ValueError`` on any
#      connection without a ``host`` attribute — breaking FalkorDB Lite's
#      Unix-socket connection entirely (upstream issue #1035).
#
# Patching the class at import time is cheap and fixes every call-site. The
# values themselves are inert sentinels: FalkorDB Lite never uses TCP, so no
# code path will dereference them as a real ``(host, port)`` pair.
# ---------------------------------------------------------------------------
try:
    from redis.connection import UnixDomainSocketConnection as _UDSC

    # ``port`` was never an attribute on UDSC; if it is missing, install a sentinel.
    if not hasattr(_UDSC, 'port'):
        _UDSC.port = 0  # type: ignore[attr-defined]

    # ``host`` is trickier. On redis-py >= 6 ``UDSC`` inherits an *abstract*
    # ``host`` property (from ``MaintNotificationsAbstractConnection``) whose
    # default body just returns ``None``. The maintenance-notifications
    # handshake then does ``getattr(self, "host", None)``; because the property
    # *exists* on the class, ``getattr`` returns ``None`` instead of falling
    # through to its default — and the handshake raises ValueError.
    #
    # ``hasattr(_UDSC, 'host')`` is therefore the wrong check: we must inspect
    # an instance. We probe a bare instance (``object.__new__`` skips
    # ``__init__``, so we don't need a path) and override the class attribute
    # with an inert string whenever the inherited property would yield ``None``.
    try:
        _probe = object.__new__(_UDSC)
        if getattr(_probe, 'host', None) is None:
            _UDSC.host = 'localhost'  # type: ignore[attr-defined]
        del _probe
    except Exception:
        # Probing failed for an unrelated reason; do the safe thing and
        # install the sentinel anyway. Worst case we shadow a working property
        # with a constant, which is still preferable to a crash.
        _UDSC.host = 'localhost'  # type: ignore[attr-defined]
except Exception:
    pass  # redis not installed or class structure changed — safe to ignore

class FalkorDBManager:
    """
    Manages the FalkorDB Lite database connection as a singleton.
    Uses a subprocess to isolate the embedded database from the main process environment.
    """
    _instance = None
    _process = None
    _driver = None
    _graph = None
    _lock = threading.Lock()
    _startup_failed = False
    _STARTUP_TIMEOUT_SEC = 5

    def __new__(cls, *args, **kwargs):
        """Standard singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(FalkorDBManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, db_path: Optional[str] = None, socket_path: Optional[str] = None):
        """
        Initializes the manager with default database path or explicit overrides.
        The `_initialized` flag prevents re-initialization on subsequent calls.
        """
        # Configuration priority:
        # 1. Environment variable (highest priority)
        # 2. Config manager (supports project-local .env)
        # 3. Default path (lowest priority)
        
        # Try to load from config manager
        try:
            from codegraphcontext.cli.config_manager import get_config_value
            config_db_path = get_config_value('FALKORDB_PATH')
            config_socket_path = get_config_value('FALKORDB_SOCKET_PATH')
        except Exception:
            # Config manager not available or error loading
            config_db_path = None
            config_socket_path = None
        
        # Database path with fallback chain (Explicit > Env > Config/Default)
        new_db_path = db_path or os.getenv(
            'FALKORDB_PATH',
            config_db_path or str(Path.home() / '.codegraphcontext' / 'global' / 'falkordb.db')
        )
        new_db_path = os.path.abspath(new_db_path)

        if hasattr(self, '_initialized') and getattr(self, 'db_path', None) == new_db_path:
            return

        if hasattr(self, '_initialized') and getattr(self, 'db_path', None) != new_db_path:
            self.shutdown()
            self._driver = None
            self._graph = None

        self._initialized = False
        self.db_path = new_db_path
        
        # Socket path with fallback chain
        if socket_path:
            self.socket_path = socket_path
        elif db_path:
            # If a custom DB path was given but no socket path, infer socket path automatically
            # near the custom database rather than putting it in the global directory.
            db_dir = Path(db_path).parent
            self.socket_path = str(db_dir / 'falkordb.sock')
        else:
            self.socket_path = os.getenv(
                'FALKORDB_SOCKET_PATH',
                config_socket_path or str(Path.home() / '.codegraphcontext' / 'global' / 'falkordb.sock')
            )
        self.socket_path = os.path.abspath(self.socket_path)
        
        self.graph_name = os.getenv('FALKORDB_GRAPH_NAME', 'codegraph')
        self._initialized = True

        if not getattr(self, "_atexit_registered", False):
            atexit.register(self.shutdown)
            self._atexit_registered = True

    def get_driver(self):
        """
        Gets the FalkorDB connection, starting the subprocess if necessary.
        This method is thread-safe.

        Returns:
            A FalkorDB graph instance that mimics Neo4j driver interface.
        """
        import platform

        if FalkorDBManager._startup_failed:
            raise FalkorDBUnavailableError(
                "FalkorDB Lite previously failed to start in this process."
            )
        
        if platform.system() == "Windows":
            raise RuntimeError(
                "CodeGraphContext uses redislite/FalkorDB, which does not support Windows.\n"
                "Please run the project using WSL or Docker."
            )
        
        if self._driver is None:
            if sys.version_info < (3, 12):
                raise ValueError("FalkorDB Lite is not supported on Python < 3.12.")

            with self._lock:
                if self._driver is None:
                    # CRITICAL FIX: Prevent ~/.local/bin/falkordb.so from shadowing falkordb package
                    # When running via 'cgc' script installed in ~/.local/bin, sys.path[0] is that dir.
                    if sys.path and sys.path[0]:
                        potential_shadow = os.path.join(sys.path[0], 'falkordb.so')
                        if os.path.exists(potential_shadow):
                            info_logger("Detected 'falkordb.so' in sys.path[0]. Removing path to prevent import shadowing.")
                            sys.path.pop(0)

                    try:
                        self._ensure_server_running()
                        
                        # Use Official FalkorDB Client to connect to the socket
                        from falkordb import FalkorDB
                        
                        info_logger(f"Connecting to FalkorDB Lite at {self.socket_path}")
                        try:
                            self._driver = FalkorDB(unix_socket_path=self.socket_path)
                            self._graph = self._driver.select_graph(self.graph_name)
                        except ValueError as ve:
                            # redis-py >= 6 raises ValueError on Unix-socket connections that
                            # lack a 'host' attribute (see upstream issue #1035). Even with the
                            # import-time shim above, newer redis-py revisions may shift the
                            # check. Convert to FalkorDBUnavailableError so the caller can fall
                            # back to KùzuDB instead of crashing the whole MCP server.
                            raise FalkorDBUnavailableError(
                                f"FalkorDB Lite client refused the Unix-socket connection: {ve}. "
                                "This typically indicates a redis-py / falkordblite version mismatch."
                            ) from ve
                        
                        # Test the connection
                        try:
                            # Graph creation is lazy in some clients, force a query
                            self._graph.query("RETURN 1")
                            info_logger(f"FalkorDB Lite connection established successfully")
                            info_logger(f"Graph name: {self.graph_name}")
                        except Exception as e:
                            # A wrapper that cannot run RETURN 1 is unusable; raise the
                            # typed error so the caller's fallback logic engages instead
                            # of returning a broken manager.
                            self._driver = None
                            self._graph = None
                            raise FalkorDBUnavailableError(
                                f"FalkorDB Lite connected but failed the initial health check: {e}"
                            ) from e
                            
                    except ImportError as e:
                        error_logger(
                            "FalkorDB client is not installed. Install it with:\n"
                            "  pip install falkordblite"
                        )
                        raise ValueError("FalkorDB client missing.") from e
                    except FalkorDBUnavailableError:
                        FalkorDBManager._startup_failed = True
                        raise
                    except Exception as e:
                        FalkorDBManager._startup_failed = True
                        error_logger(f"Failed to initialize FalkorDB: {e}")
                        raise

        # Return a wrapper that provides Neo4j-like session interface
        return FalkorDBDriverWrapper(self._graph)

    def _ensure_server_running(self):
        """Starts the FalkorDB worker subprocess if not reachable."""
        import platform
        
        if platform.system() == "Windows":
            raise RuntimeError(
                "CodeGraphContext uses redislite/FalkorDB, which does not support Windows.\n"
                "Please run the project using WSL or Docker."
            )
        
        # 1. Try to connect first (maybe running from previous session or other process)
        if os.path.exists(self.socket_path):
            try:
                from falkordb import FalkorDB
                d = FalkorDB(unix_socket_path=self.socket_path)
                # Test not just connectivity (PING), but functionality (GRAPH.QUERY)
                # This ensures we don't connect to a "stale" process that doesn't have the module loaded
                test_graph = d.select_graph('__cgc_health_check')
                test_graph.query("RETURN 1")
                info_logger("Connected to existing (functional) FalkorDB Lite process.")
                return
            except ValueError as ve:
                # redis-py >= 6 maintenance-notifications handshake (issue #1035) — this
                # backend cannot work in the current environment regardless of socket state.
                raise FalkorDBUnavailableError(
                    f"FalkorDB Lite client refused the Unix-socket connection: {ve}. "
                    "This typically indicates a redis-py / falkordblite version mismatch."
                ) from ve
            except Exception as e:
                # Stale socket, unresponsive, or "brainless" (unknown command GRAPH.QUERY)
                info_logger(f"Existing FalkorDB process at {self.socket_path} is stale or non-functional: {e}")
                info_logger("Cleaning up and attempting fresh start...")
                try:
                    os.remove(self.socket_path)
                except OSError:
                    pass

        # 2. Start Subprocess
        env = os.environ.copy()
        env['FALKORDB_PATH'] = self.db_path
        env['FALKORDB_SOCKET_PATH'] = self.socket_path
        
        # Determine python executable
        python_exe = sys.executable
        
        # We assume codegraphcontext is installed or in python path
        if getattr(sys, 'frozen', False):
            # In frozen mode, the executable is the bundle itself.
            # We tell the bundle to run the worker instead of the app via environment variable.
            env['CGC_RUN_FALKOR_WORKER'] = 'true'
            cmd = [python_exe]
        else:
            # If not frozen, sys.executable should be python.
            # But on some platforms (like PIP installs), it might be the 'cgc' entry point script.
            # We check if it looks like python, otherwise search the PATH.
            import shutil
            exe_name = os.path.basename(python_exe).lower()
            if not any(x in exe_name for x in ['python', 'py.exe', 'pypy']):
                python_exe = shutil.which('python3') or shutil.which('python') or sys.executable
            
            cmd = [python_exe, '-m', 'codegraphcontext.core.falkor_worker']
        
        info_logger("Starting FalkorDB Lite worker subprocess...")
        self._process = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Drain stdout/stderr continuously so a long-running chatty worker cannot
        # fill the OS pipe buffers and block the server. The (bounded) captured
        # output is still available for the startup failure report below.
        self._stdout_lines = []
        self._stderr_lines = []

        def _drain(stream, buf, limit=200):
            try:
                for line in iter(stream.readline, b''):
                    buf.append(line)
                    if len(buf) > limit:
                        del buf[:len(buf) - limit]
            except Exception:
                pass
            finally:
                try:
                    stream.close()
                except Exception:
                    pass

        self._drain_threads = [
            threading.Thread(target=_drain, args=(self._process.stdout, self._stdout_lines), daemon=True),
            threading.Thread(target=_drain, args=(self._process.stderr, self._stderr_lines), daemon=True),
        ]
        for t in self._drain_threads:
            t.start()
        
        # 3. Wait for Readiness. The Unix socket can appear before Redis has
        # loaded the FalkorDB module, so validate GRAPH.QUERY instead of
        # treating socket creation alone as ready.
        start_time = time.time()
        timeout = self._STARTUP_TIMEOUT_SEC
        last_error = None
        
        while time.time() - start_time < timeout:
            if os.path.exists(self.socket_path):
                try:
                    from falkordb import FalkorDB
                    d = FalkorDB(unix_socket_path=self.socket_path)
                    test_graph = d.select_graph('__cgc_health_check')
                    test_graph.query("RETURN 1")
                    return
                except ValueError as ve:
                    # redis-py version mismatch — no point retrying, the handshake
                    # will keep failing the same way until the user fixes deps.
                    raise FalkorDBUnavailableError(
                        f"FalkorDB Lite client refused the Unix-socket connection: {ve}. "
                        "This typically indicates a redis-py / falkordblite version mismatch."
                    ) from ve
                except Exception as e:
                    last_error = e
            
            # Check if process died
            if self._process.poll() is not None:
                # The drain threads own the pipes (communicate() would race with
                # them); give them a moment to flush the remaining output.
                for t in self._drain_threads:
                    t.join(timeout=1)
                out = b''.join(self._stdout_lines)
                err = b''.join(self._stderr_lines)
                returncode = self._process.returncode

                # Exit 0 means the worker detected an already-running FalkorDB instance.
                if returncode == 0 and os.path.exists(self.socket_path):
                    try:
                        from falkordb import FalkorDB
                        d = FalkorDB(unix_socket_path=self.socket_path)
                        test_graph = d.select_graph('__cgc_health_check')
                        test_graph.query("RETURN 1")
                        return
                    except Exception as e:
                        last_error = e

                # Any other exit code during startup means this backend is toast.
                # Raise FalkorDBUnavailableError to trigger the automatic KùzuDB fallback.
                raise FalkorDBUnavailableError(
                    f"FalkorDB Lite worker failed to start (Exit Code {returncode}).\n"
                    f"STDOUT: {out.decode().strip()}\n"
                    f"STDERR: {err.decode().strip()}"
                )
            
            time.sleep(0.5)
            
        # Timeout is also a "backend not usable here" signal — raise the typed
        # exception so the documented KùzuDB fallback fires instead of crashing.
        raise FalkorDBUnavailableError(
            f"Timed out waiting for FalkorDB Lite to start. Last error: {last_error}"
        )

    def close_driver(self, *, teardown: bool = False):
        """Closes the connection. Pass teardown=True to stop the worker subprocess."""
        if self._driver is not None:
            info_logger("Closing FalkorDB Lite connection")
            self._driver = None
            self._graph = None
        if teardown:
            self.shutdown()

    def shutdown(self):
        """Kills the subprocess on exit."""
        if self._process:
            if self._process.poll() is None:
                info_logger("Stopping FalkorDB subprocess...")
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
    
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
        return 'falkordb'


    @staticmethod
    def validate_config(db_path: str = None) -> Tuple[bool, Optional[str]]:
        """
        Validates FalkorDB configuration parameters.
        
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        if db_path:
            db_dir = Path(db_path).parent
            if not os.access(db_dir, os.W_OK) and db_dir.exists():
                return False, (
                    f"Cannot write to directory: {db_dir}\n"
                    "Please ensure you have write permissions."
                )
        return True, None

    @staticmethod
    def test_connection(db_path: str = None) -> Tuple[bool, Optional[str]]:
        """
        Tests the FalkorDB Lite connection availability.
        """
        try:
            if sys.version_info < (3, 12):
                return False, "FalkorDB Lite is not supported on Python < 3.12. Please upgrade or use Neo4j."

            import falkordb
            return True, None
        except ImportError:
            return False, (
                "FalkorDB client is not installed.\n"
                "Install it with: pip install falkordblite"
            )


class FalkorDBDriverWrapper:
    """
    Wrapper class to provide Neo4j driver-like interface for FalkorDB Lite.
    This allows existing code to work with minimal changes.
    """
    
    def __init__(self, graph):
        self.graph = graph
    
    def session(self, **kwargs):
        """Returns a session-like object for FalkorDB."""
        return FalkorDBSessionWrapper(self.graph)
    
    def close(self):
        """FalkorDB Lite doesn't need explicit close for sessions."""
        pass


class FalkorDBSessionWrapper:
    """
    Wrapper class to provide Neo4j session-like interface for FalkorDB Lite.
    """
    
    def __init__(self, graph):
        self.graph = graph
    
    def run(self, query, **parameters):
        """
        Execute a Cypher query on FalkorDB.
        """
        constraint_command = self._translate_constraint_command(query)
        if constraint_command is not None:
            try:
                self.graph.execute_command(*constraint_command)
                return FalkorDBResultWrapper(None)
            except Exception as e:
                error_msg = str(e).lower()
                if "already exists" in error_msg or "already created" in error_msg:
                    return FalkorDBResultWrapper(None)
                error_logger(f"FalkorDB constraint failed: {constraint_command!r} Error: {e}")
                raise

        # Translate Neo4j schema queries to FalkorDB syntax
        query = self._translate_schema_query(query)
        
        try:
            result = self.graph.query(query, parameters)
            return FalkorDBResultWrapper(result)
        except Exception as e:
            # Ignore errors about existing constraints/indexes
            error_msg = str(e).lower()
            if "already exists" in error_msg or "already created" in error_msg or "already indexed" in error_msg:
                return FalkorDBResultWrapper(None)
                
            error_logger(f"FalkorDB query failed: {query[:100]}... Error: {e}")
            raise

    def _translate_constraint_command(self, query: str):
        """
        Translate Neo4j-style CREATE CONSTRAINT queries to GRAPH.CONSTRAINT CREATE.
        FalkorDB 4.16.x expects this command path instead of GRAPH.QUERY.
        """
        q_upper = query.upper()
        if "CREATE CONSTRAINT" not in q_upper:
            return None

        normalized = re.sub(r"\s+IF NOT EXISTS", "", query, flags=re.IGNORECASE)
        normalized = re.sub(r"\s+", " ", normalized).strip()

        entity_match = re.search(r"FOR\s*\((\w+):([^)]+)\)", normalized, flags=re.IGNORECASE)
        if not entity_match:
            return None
        entity_type = "NODE"
        label = entity_match.group(2).strip()

        composite_match = re.search(
            r"REQUIRE\s*\(([^)]+)\)\s*IS\s+UNIQUE",
            normalized,
            flags=re.IGNORECASE,
        )
        single_match = re.search(
            r"REQUIRE\s+\w+\.([A-Za-z_][A-Za-z0-9_]*)\s+IS\s+UNIQUE",
            normalized,
            flags=re.IGNORECASE,
        )

        if composite_match:
            props = [part.split(".")[-1].strip() for part in composite_match.group(1).split(",") if part.strip()]
            constraint_type = "UNIQUE"
        elif single_match:
            props = [single_match.group(1).strip()]
            constraint_type = "UNIQUE"
        else:
            return None

        return [
            "GRAPH.CONSTRAINT",
            "CREATE",
            self.graph.name,
            constraint_type,
            entity_type,
            label,
            "PROPERTIES",
            len(props),
            *props,
        ]

    def _translate_schema_query(self, query: str) -> str:
        """Translate Neo4j schema queries to FalkorDB/RedisGraph syntax."""
        q_upper = query.upper()
        
        # Handle Fulltext Indexes (Not supported in same syntax, skip for now)
        if "CREATE FULLTEXT INDEX" in q_upper:
            return "RETURN 1"
            
        # Handle Constraints through GRAPH.CONSTRAINT in run()
        if "CREATE CONSTRAINT" in q_upper:
            return "RETURN 1"
            
        # Handle Regular Indexes
        elif "CREATE INDEX" in q_upper:
            # Remove "IF NOT EXISTS"
            query = re.sub(r'\s+IF NOT EXISTS', '', query, flags=re.IGNORECASE)
            # Remove Index Name: CREATE INDEX name FOR -> CREATE INDEX FOR
            query = re.sub(r'CREATE INDEX\s+\w+\s+FOR', 'CREATE INDEX FOR', query, flags=re.IGNORECASE)
            
        return query
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class FalkorDBRecord(dict):
    """
    Dict wrapper that provides a .data() method and integer/key index access
    for compatibility with Neo4j and Kuzu records.
    """
    def data(self):
        return self

    def __getitem__(self, key):
        if isinstance(key, int):
            keys = list(self.keys())
            if 0 <= key < len(keys):
                return super().__getitem__(keys[key])
            raise IndexError(f"Index {key} out of range")
        return super().__getitem__(key)

class FalkorDBResultWrapper:
    """
    Wrapper class to provide Neo4j result-like interface for FalkorDB results.
    """
    
    def __init__(self, result):
        self.result = result
        self._consumed = False
    
    def consume(self):
        """Mark result as consumed (for compatibility)."""
        self._consumed = True
        return self
    
    def single(self):
        """Return single result record as a FalkorDBRecord."""
        data = self.data()
        return data[0] if data else None
    
    def data(self):
        """Return all results as list of FalkorDBRecord objects."""
        if not hasattr(self.result, 'result_set'):
            return []
        
        # Convert result_set to list of dicts (wrapped in FalkorDBRecord)
        results = []
        if hasattr(self.result, 'header') and self.result.header:
            headers = self.result.header
            for row in self.result.result_set:
                row_dict = FalkorDBRecord()
                for i, header in enumerate(headers):
                    if i < len(row):
                        # FalkorDB headers are [column_type, column_name] pairs
                        # Extract the column name (index 1) and decode if bytes
                        if isinstance(header, (list, tuple)) and len(header) > 1:
                            header_name = header[1]
                            if isinstance(header_name, bytes):
                                header_name = header_name.decode('utf-8')
                        else:
                            header_name = str(header)
                        row_dict[header_name] = row[i]
                results.append(row_dict)
        elif hasattr(self.result, 'result_set'):
            # Fallback if no header
            for row in self.result.result_set:
                if isinstance(row, (list, tuple)) and len(row) == 1:
                    results.append(FalkorDBRecord({'value': row[0]}))
                else:
                    results.append(FalkorDBRecord({'value': row}))
        
        return results
    
    def __iter__(self):
        """Iterate over results as FalkorDBRecord objects."""
        return iter(self.data())
