# src/codegraphcontext/core/database.py
"""
This module provides a thread-safe singleton manager for the Neo4j database connection.
"""
import os
import re
import threading
from typing import Optional, Tuple
from neo4j import GraphDatabase, Driver

from codegraphcontext.utils.debug_log import debug_log, info_logger, error_logger, warning_logger

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
        self._initialized = True

    def get_driver(self) -> Driver:
        """
        Gets the Neo4j driver instance, creating it if it doesn't exist.
        This method is thread-safe.

        Raises:
            ValueError: If Neo4j credentials are not set in environment variables.

        Returns:
            The active Neo4j Driver instance.
        """
        if self._driver is None:
            with self._lock:
                if self._driver is None:
                    # Ensure all necessary credentials are provided.
                    if not all([self.neo4j_uri, self.neo4j_username, self.neo4j_password]):
                        raise ValueError(
                            "Neo4j credentials must be set via environment variables:\n"
                            "- NEO4J_URI\n"
                            "- NEO4J_USERNAME\n"
                            "- NEO4J_PASSWORD"
                        )
                    
                    #validating the config before creating the driver/attempting connection
                    is_valid, validation_error = self.validate_config(
                    self.neo4j_uri, 
                    self.neo4j_username, 
                    self.neo4j_password
                    )
                    
                    if not is_valid:
                        error_logger(f"Configuration validation failed: {validation_error}")
                        raise ValueError(validation_error)

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
                        error_logger(f"Failed to connect to Neo4j: {e}")
                        if self._driver:
                            self._driver.close()
                        self._driver = None
                        raise
        return self._driver

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
            with self._driver.session() as session:
                session.run("RETURN 1").consume()
            return True
        except Exception:
            return False
    
    def get_backend_type(self) -> str:
        """Returns the database backend type."""
        return 'neo4j'


    @staticmethod
    def validate_config(uri: str, username: str, password: str) -> Tuple[bool, Optional[str]]:
        """
        Validates Neo4j configuration parameters.
        
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        # Validate URI format
        uri_pattern = r'^(neo4j|neo4j\+s|neo4j\+ssc|bolt|bolt\+s|bolt\+ssc)://[^:]+:\d+$'
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
    def test_connection(uri: str, username: str, password: str) -> Tuple[bool, Optional[str]]:
        """
        Tests the Neo4j database connection.
        
        Returns:
            Tuple[bool, Optional[str]]: (is_connected, error_message)
        """
        try:
            from neo4j import GraphDatabase
            import socket
            
            # First, test if the host is reachable
            try:
                # Extract host and port from URI
                host_port = uri.split('://')[1]
                host = host_port.split(':')[0]
                port = int(host_port.split(':')[1])
                
                # Test socket connection
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((host, port))
                sock.close()
                
                if result != 0:
                    return False, (
                        f"Cannot reach Neo4j server at {host}:{port}\n"
                        "Troubleshooting:\n"
                        "  • Is Neo4j running? Check with: docker ps (for Docker)\n"
                        "  • Is the port correct? Default is 7687\n"
                        "  • Is there a firewall blocking the connection?\n"
                        f"  • Try: docker compose up -d (if using Docker)"
                    )
            except Exception as e:
                return False, f"Error parsing URI or checking connectivity: {str(e)}"
            
            # Now test Neo4j authentication
            driver = GraphDatabase.driver(uri, auth=(username, password))
            
            with driver.session() as session:
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
            elif "serviceunAvailable" in error_msg or "failed to establish connection" in error_msg:
                return False, (
                    "Neo4j service is not available\n"
                    "Troubleshooting:\n"
                    "  • Is Neo4j running? Check: docker ps\n"
                    "  • Start Neo4j: docker compose up -d\n"
                    "  • Check logs: docker compose logs neo4j\n"
                    "  • Wait 30-60 seconds after starting for Neo4j to initialize"
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
