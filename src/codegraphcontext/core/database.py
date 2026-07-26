# src/codegraphcontext/core/database.py
"""
This module provides a thread-safe singleton manager for the Neo4j database connection.
"""
import os
import re
import socket
import threading
from urllib.parse import urlparse
from typing import Optional, Tuple
from neo4j import GraphDatabase, Driver

from codegraphcontext.utils.debug_log import debug_log, info_logger, error_logger, warning_logger


class Neo4jConnectionError(Exception):
    """Raised when Neo4j cannot be reached or authenticated with actionable guidance."""

    def __init__(self, message: str, reason: Optional[str] = None, source: Optional[str] = None, suggestions: Optional[list] = None):
        super().__init__(message)
        self.reason = reason or message
        self.source = source or "unknown"
        self.suggestions = suggestions or []

    def __str__(self) -> str:
        base = f"Neo4j connection failed (source: {self.source}). Reason: {self.reason}"
        if not self.suggestions:
            return base
        suggestion_block = "\n" + "\n".join(f"  - {s}" for s in self.suggestions)
        return f"{base}\nSuggested fixes:{suggestion_block}"

class Neo4jDriverWrapper:
    """
    A simple wrapper around the Neo4j Driver to inject a database name into session() calls.
    """
    def __init__(self, driver: Driver, database: str = None):
        self._driver = driver
        self._database = database

    def session(self, **kwargs):
        """Proxy method to get a session from the underlying driver."""
        if self._database and 'database' not in kwargs:
            kwargs["database"] = self._database
        return self._driver.session(**kwargs)
    
    def close(self):
        """Proxy method to close the underlying driver."""
        self._driver.close()

class DatabaseManager:
    """
    Manages the Neo4j database driver as a singleton to ensure only one
    connection pool is created and shared across the application.
    
    This pattern is crucial for performance and resource management in a
    multi-threaded or asynchronous application.
    """
    _instance = None
    _driver: Optional[Driver] = None
    _lock = threading.Lock() # Lock to ensure thread-safe initialization. 

    def __new__(cls):
        """Standard singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                # Double-check locking to prevent race conditions.
                if cls._instance is None:
                    cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """
        Initializes the manager by reading credentials from environment variables.
        The `_initialized` flag prevents re-initialization on subsequent calls.
        """
        if hasattr(self, '_initialized'):
            return

        self.neo4j_uri = os.getenv('NEO4J_URI')
        self.neo4j_username = os.getenv('NEO4J_USERNAME', 'neo4j')
        self.neo4j_password = os.getenv('NEO4J_PASSWORD')
        self.neo4j_database = os.getenv('NEO4J_DATABASE') # Optional, if not set, will use default database configured in Neo4j
        self._initialized = True

    def get_driver(self) -> Driver:
        """
        Gets the Neo4j driver instance, creating it if it doesn't exist.
        This method is thread-safe.

        Raises:
            ValueError: If Neo4j credentials are not set in environment variables.

        Returns:
            The a wrapper for Neo4j Driver instance.
        """
        if self._driver is None:
            with self._lock:
                if self._driver is None:
                    # Ensure all necessary credentials are provided.
                    missing = self.get_missing_credentials(
                        self.neo4j_uri,
                        self.neo4j_username,
                        self.neo4j_password,
                    )
                    if missing:
                        raise ValueError(self.build_missing_credentials_message(missing))
                    
                    #validating the config before creating the driver/attempting connection
                    is_valid, validation_error = self.validate_config(
                    self.neo4j_uri, 
                    self.neo4j_username, 
                    self.neo4j_password
                    )
                    
                    if not is_valid:
                        error_logger(f"Configuration validation failed: {validation_error}")
                        raise ValueError(validation_error)

                    # Fast fail on unreachable host/port before creating a full Neo4j driver.
                    is_reachable, reachability_error = self.check_port_reachable(self.neo4j_uri)
                    if not is_reachable:
                        source = self.get_db_selection_source()
                        raise Neo4jConnectionError(
                            "Neo4j service is not reachable",
                            reason=reachability_error,
                            source=source,
                            suggestions=self.get_neo4j_suggestions(),
                        )

                    info_logger(f"Creating Neo4j driver connection to {self.neo4j_uri}")
                    self._driver = GraphDatabase.driver(
                        self.neo4j_uri,
                        auth=(self.neo4j_username, self.neo4j_password)
                    )
                    # Test the connection immediately to fail fast if credentials are wrong.
                    try:
                        with self._driver.session() as session:
                            session.run("RETURN 1").consume()
                        info_logger("Neo4j connection established successfully")
                    except Exception as e:
                        # Use detailed error messages from test_connection
                        _, detailed_error = self.test_connection(
                            self.neo4j_uri,
                            self.neo4j_username,
                            self.neo4j_password
                        )
                        source = self.get_db_selection_source()
                        reason = detailed_error or "Unable to establish a Neo4j session"
                        error_logger(f"Neo4j connection failed (source: {source}). Reason: {reason}")
                        if self._driver:
                            self._driver.close()
                        self._driver = None
                        raise Neo4jConnectionError(
                            "Neo4j session initialization failed",
                            reason=reason,
                            source=source,
                            suggestions=self.get_neo4j_suggestions(),
                        ) from e
        return Neo4jDriverWrapper(self._driver, database=self.neo4j_database)

    def close_driver(self):
        """Closes the Neo4j driver connection if it exists."""
        if self._driver is not None:
            with self._lock:
                if self._driver is not None:
                    info_logger("Closing Neo4j driver")
                    self._driver.close()
                    self._driver = None

    def is_connected(self) -> bool:
        """Checks if the database connection is currently active."""
        if self._driver is None:
            return False
        try:
            session_kwargs = {}
            if self.neo4j_database:
                session_kwargs['database'] = self.neo4j_database
            with self._driver.session(**session_kwargs) as session:
                session.run("RETURN 1").consume()
            return True
        except Exception:
            return False
    
    def get_backend_type(self) -> str:
        """Returns the database backend type."""
        return 'neo4j'

    @staticmethod
    def get_db_selection_source() -> str:
        """Best-effort source for why neo4j is selected (environment, .env, mcp.json, etc.)."""
        return os.getenv("CGC_DB_SELECTION_SOURCE", "unknown")

    @staticmethod
    def get_missing_credentials(uri: Optional[str], username: Optional[str], password: Optional[str]) -> list:
        missing = []
        if not uri:
            missing.append("NEO4J_URI")
        if not username:
            missing.append("NEO4J_USERNAME")
        if not password:
            missing.append("NEO4J_PASSWORD")
        return missing

    @staticmethod
    def build_missing_credentials_message(missing_keys: list) -> str:
        missing_block = ", ".join(missing_keys)
        return (
            f"Neo4j credentials not configured: {missing_block}.\n"
            "Run:\n"
            "  cgc config set NEO4J_URI bolt://localhost:7687\n"
            "  cgc config set NEO4J_USERNAME neo4j\n"
            "  cgc config set NEO4J_PASSWORD <your-password>"
        )

    @staticmethod
    def get_neo4j_suggestions() -> list:
        return [
            "Start Neo4j Desktop and ensure your database is running.",
            "Or run Docker: docker run -d -p 7687:7687 -p 7474:7474 neo4j",
            "Verify NEO4J_URI, NEO4J_USERNAME, and NEO4J_PASSWORD.",
        ]

    @staticmethod
    def extract_host_port(uri: str) -> Tuple[Optional[str], int]:
        """Extract host and port from Neo4j URI, defaulting port to 7687."""
        parsed = urlparse(uri)
        host = parsed.hostname
        port = parsed.port or 7687
        return host, port

    @staticmethod
    def check_port_reachable(uri: str, timeout_seconds: float = 2.0) -> Tuple[bool, Optional[str]]:
        """Lightweight TCP preflight check for Neo4j endpoint reachability."""
        try:
            host, port = DatabaseManager.extract_host_port(uri)
            if not host:
                return False, "Invalid Neo4j URI: missing hostname"

            with socket.create_connection((host, port), timeout=timeout_seconds):
                return True, None
        except OSError:
            host, port = DatabaseManager.extract_host_port(uri)
            return False, (
                f"Neo4j is not running on {host}:{port}. "
                "Please start Neo4j Desktop or run Docker: "
                "docker run -d -p 7687:7687 -p 7474:7474 neo4j"
            )
        except Exception as e:
            return False, f"Neo4j endpoint validation failed: {e}"


    @staticmethod
    def validate_config(uri: str, username: str, password: str) -> Tuple[bool, Optional[str]]:
        """
        Validates Neo4j configuration parameters.
        
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        # Validate URI format
        # Modified regex to make port optional "(:\\d+)?"
        uri_pattern = r'^(neo4j|neo4j\+s|neo4j\+ssc|bolt|bolt\+s|bolt\+ssc)://[^:]+(:\d+)?$'
        if not re.match(uri_pattern, uri):
            return False, (
                "Invalid Neo4j URI format.\n"
                "Expected format: neo4j://host:port or bolt://host:port\n"
                "Example: neo4j://localhost:7687\n"
                "Common mistake: Missing 'neo4j://' or 'bolt://' prefix"
            )
        
        # Validate username
        if not username or len(username.strip()) == 0:
            return False, (
                "Username cannot be empty.\n"
                "Default Neo4j username is 'neo4j'"
            )
        
        # Validate password
        if not password or len(password.strip()) == 0:
            return False, (
                "Password cannot be empty.\n"
                "Tip: If you just set up Neo4j, use the password you configured during setup"
            )
        
        return True, None

    @staticmethod
    def test_connection(uri: str, username: str, password: str, database: str=None) -> Tuple[bool, Optional[str]]:
        """
        Tests the Neo4j database connection.
        
        Returns:
            Tuple[bool, Optional[str]]: (is_connected, error_message)
        """
        try:
            from neo4j import GraphDatabase
            # First, test if the host is reachable
            is_reachable, reachability_error = DatabaseManager.check_port_reachable(uri)
            if not is_reachable:
                return False, reachability_error
            
            # Now test Neo4j authentication
            driver = GraphDatabase.driver(uri, auth=(username, password))
            
            session_kwargs = {}
            if database:
                session_kwargs['database'] = database # Pass database to session if provided
            with driver.session(**session_kwargs) as session:
                result = session.run("RETURN 'Connection successful' as status")
                result.single()
            
            driver.close()
            return True, None
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # Provide specific error messages for common issues
            if "authentication" in error_msg or "unauthorized" in error_msg:
                return False, (
                    "Authentication failed - Invalid username or password\n"
                    "Troubleshooting:\n"
                    "  • Default username is 'neo4j'\n"
                    "  • Did you change the password during initial setup?\n"
                    "  • If you forgot the password, you may need to reset Neo4j:\n"
                    "    - Stop: docker compose down\n"
                    "    - Remove data: docker volume rm <volume_name>\n"
                    "    - Restart: docker compose up -d"
                )
            elif "serviceunavailable" in error_msg or "failed to establish connection" in error_msg or "couldn't connect to" in error_msg:
                return False, (
                    "Neo4j service is not reachable on the configured host/port.\n"
                    "Troubleshooting:\n"
                    "  • Start Neo4j Desktop or ensure your instance is running\n"
                    "  • Run Docker: docker run -d -p 7687:7687 -p 7474:7474 neo4j\n"
                    "  • Check that NEO4J_URI points to the correct host and port"
                )
            elif "unable to retrieve routing information" in error_msg:
                return False, (
                    "Cannot connect to Neo4j routing\n"
                    "Troubleshooting:\n"
                    "  • Try using 'bolt://' instead of 'neo4j://' in the URI\n"
                    "  • Example: bolt://localhost:7687"
                )
            else:
                return False, f"Connection failed: {str(e)}"
