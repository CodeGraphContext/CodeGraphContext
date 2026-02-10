# src/codegraphcontext/core/database_falkordb.py
"""
This module provides a thread-safe singleton manager for the FalkorDB Lite database connection.
FalkorDB Lite is an embedded graph database that requires no external server setup.
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

    def __new__(cls):
        """Standard singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(FalkorDBManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """
        Initializes the manager with default database path.
        The `_initialized` flag prevents re-initialization on subsequent calls.
        """
        if hasattr(self, '_initialized'):
            return

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
        
        # Database path with fallback chain
        self.db_path = os.getenv(
            'FALKORDB_PATH',
            config_db_path or str(Path.home() / '.codegraphcontext' / 'falkordb.db')
        )
        
        # Socket path with fallback chain
        self.socket_path = os.getenv(
            'FALKORDB_SOCKET_PATH',
            config_socket_path or str(Path.home() / '.codegraphcontext' / 'falkordb.sock')
        )
        
        self.graph_name = os.getenv('FALKORDB_GRAPH_NAME', 'codegraph')
        self._initialized = True
        
        # Register cleanup on exit
        atexit.register(self.shutdown)

    def get_driver(self):
        """
        Gets the FalkorDB connection, starting the subprocess if necessary.
        This method is thread-safe.

        Returns:
            A FalkorDB graph instance that mimics Neo4j driver interface.
        """
        import platform
        
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
                        self._driver = FalkorDB(unix_socket_path=self.socket_path)
                        self._graph = self._driver.select_graph(self.graph_name)
                        
                        # Test the connection
                        try:
                            # Graph creation is lazy in some clients, force a query
                            self._graph.query("RETURN 1")
                            info_logger(f"FalkorDB Lite connection established successfully")
                            info_logger(f"Graph name: {self.graph_name}")
                        except Exception as e:
                            info_logger(f"Initial ping check: {e}")
                            
                    except ImportError as e:
                        error_logger(
                            "FalkorDB client is not installed. Install it with:\n"
                            "  pip install falkordblite"
                        )
                        raise ValueError("FalkorDB client missing.") from e
                    except Exception as e:
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
                try:
                    d.execute_command("PING")
                except AttributeError:
                    pass
                info_logger("Connected to existing FalkorDB Lite process.")
                return
            except Exception:
                # Stale socket or unresponsive
                info_logger("Found stale socket, cleaning up...")
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
        cmd = [python_exe, '-m', 'codegraphcontext.core.falkor_worker']
        
        info_logger("Starting FalkorDB Lite worker subprocess...")
        self._process = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # 3. Wait for Readiness
        start_time = time.time()
        timeout = 20 # seconds
        
        while time.time() - start_time < timeout:
            if os.path.exists(self.socket_path):
                # Socket created!
                # Give it a tiny sleep to ensure listening
                time.sleep(0.2)
                return
            
            # Check if process died
            if self._process.poll() is not None:
                out, err = self._process.communicate()
                raise RuntimeError(f"FalkorDB worker failed to start (Exit Code {self._process.returncode}):\nSTDOUT: {out.decode()}\nSTDERR: {err.decode()}")
            
            time.sleep(0.5)
            
        raise RuntimeError("Timed out waiting for FalkorDB Lite to start.")

    def close_driver(self):
        """Closes the connection."""
        self._driver = None
        self._graph = None

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
    
    def session(self):
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
        # Translate Neo4j schema queries to FalkorDB syntax
        query = self._translate_schema_query(query)
        
        try:
            result = self.graph.query(query, parameters)
            return FalkorDBResultWrapper(result)
        except Exception as e:
            # Ignore errors about existing constraints/indexes
            error_msg = str(e).lower()
            if "already exists" in error_msg or "already created" in error_msg:
                return FalkorDBResultWrapper(None)
                
            error_logger(f"FalkorDB query failed: {query[:100]}... Error: {e}")
            raise

    def _translate_schema_query(self, query: str) -> str:
        """Translate Neo4j schema queries to FalkorDB/RedisGraph syntax."""
        q_upper = query.upper()
        
        # Handle Fulltext Indexes (Not supported in same syntax, skip for now)
        if "CREATE FULLTEXT INDEX" in q_upper:
            return "RETURN 1"
            
        # Handle Constraints
        if "CREATE CONSTRAINT" in q_upper:
            # Remove "IF NOT EXISTS"
            query = re.sub(r'\s+IF NOT EXISTS', '', query, flags=re.IGNORECASE)
            
            # Handle composite keys: (n.p1, n.p2) -> downgrade to INDEX
            if "," in query:
                match_node = re.search(r'FOR\s+(\([^)]+\))', query, flags=re.IGNORECASE)
                match_props = re.search(r'REQUIRE\s+(\([^)]+\))\s+IS UNIQUE', query, flags=re.IGNORECASE)
                
                if match_node and match_props:
                    return f"CREATE INDEX FOR {match_node.group(1)} ON {match_props.group(1)}"

            # Handle simple uniqueness: CREATE CONSTRAINT name FOR (n:Label) REQUIRE n.prop IS UNIQUE
            # TO: CREATE CONSTRAINT ON (n:Label) ASSERT n.prop IS UNIQUE
            
            # Remove constraint name
            query = re.sub(r'CREATE CONSTRAINT\s+\w+\s+', 'CREATE CONSTRAINT ', query, flags=re.IGNORECASE)
            query = re.sub(r'\s+FOR\s+', ' ON ', query, flags=re.IGNORECASE)
            query = re.sub(r'\s+REQUIRE\s+', ' ASSERT ', query, flags=re.IGNORECASE)
            
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
    Dict wrapper that provides a .data() method for compatibility with Neo4j records.
    """
    def data(self):
        return self

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
