# src/codegraphcontext/core/database_nornic.py
"""
This module provides a thread-safe singleton manager for the Nornic DB connection.
Nornic DB is compatible with Neo4j APIs and drivers.
"""
import os
import re
import threading
from typing import Optional, Tuple
from neo4j import GraphDatabase, Driver

from codegraphcontext.utils.debug_log import debug_log, info_logger, error_logger, warning_logger

class NornicDriverWrapper:
    """
    A simple wrapper around the Nornic (Neo4j) Driver to inject a database name into session() calls.
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

class NornicDBManager:
    """
    Manages the Nornic database driver as a singleton to ensure only one
    connection pool is created and shared across the application.
    """
    _instance = None
    _driver: Optional[Driver] = None
    _lock = threading.Lock()

    def __new__(cls):
        """Standard singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(NornicDBManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """
        Initializes the manager by reading credentials from environment variables.
        The `_initialized` flag prevents re-initialization on subsequent calls.
        """
        if hasattr(self, '_initialized'):
            return

        self.nornic_uri = os.getenv('NORNIC_URI')
        self.nornic_username = os.getenv('NORNIC_USERNAME', 'nornic')
        self.nornic_password = os.getenv('NORNIC_PASSWORD')
        self.nornic_database = os.getenv('NORNIC_DATABASE') 
        self._initialized = True

    def get_driver(self) -> Driver:
        """
        Gets the Nornic driver instance, creating it if it doesn't exist.
        This method is thread-safe.

        Returns:
            The a wrapper for Nornic Driver instance.
        """
        if self._driver is None:
            with self._lock:
                if self._driver is None:
                    if not all([self.nornic_uri, self.nornic_username, self.nornic_password]):
                        raise ValueError(
                            "Nornic credentials must be set via environment variables:\n"
                            "- NORNIC_URI\n"
                            "- NORNIC_USERNAME\n"
                            "- NORNIC_PASSWORD"
                        )
                    
                    is_valid, validation_error = self.validate_config(
                        self.nornic_uri, 
                        self.nornic_username, 
                        self.nornic_password
                    )
                    
                    if not is_valid:
                        error_logger(f"Nornic configuration validation failed: {validation_error}")
                        raise ValueError(validation_error)

                    info_logger(f"Creating Nornic driver connection to {self.nornic_uri}")
                    self._driver = GraphDatabase.driver(
                        self.nornic_uri,
                        auth=(self.nornic_username, self.nornic_password)
                    )
                    try:
                        with self._driver.session() as session:
                            session.run("RETURN 1").consume()
                        info_logger("Nornic connection established successfully")
                    except Exception as e:
                        _, detailed_error = self.test_connection(
                            self.nornic_uri,
                            self.nornic_username,
                            self.nornic_password
                        )
                        error_logger(f"Failed to connect to Nornic: {e}")
                        if self._driver:
                            self._driver.close()
                        self._driver = None
                        raise
        return NornicDriverWrapper(self._driver, database=self.nornic_database)

    def close_driver(self):
        """Closes the Nornic driver connection if it exists."""
        if self._driver is not None:
            with self._lock:
                if self._driver is not None:
                    info_logger("Closing Nornic driver")
                    self._driver.close()
                    self._driver = None

    def is_connected(self) -> bool:
        """Checks if the database connection is currently active."""
        if self._driver is None:
            return False
        try:
            session_kwargs = {}
            if self.nornic_database:
                session_kwargs['database'] = self.nornic_database
            with self._driver.session(**session_kwargs) as session:
                session.run("RETURN 1").consume()
            return True
        except Exception:
            return False
    
    def get_backend_type(self) -> str:
        """Returns the database backend type."""
        return 'nornic'

    @staticmethod
    def validate_config(uri: str, username: str, password: str) -> Tuple[bool, Optional[str]]:
        """
        Validates Nornic configuration parameters.
        """
        # Nornic likely uses similar URI formats to Neo4j/Bolt
        uri_pattern = r'^(nornic|nornic\+s|nornic\+ssc|bolt|bolt\+s|bolt\+ssc|neo4j|neo4j\+s|neo4j\+ssc)://[^:]+(:\d+)?$'
        if not re.match(uri_pattern, uri):
            return False, (
                "Invalid Nornic URI format.\n"
                "Expected format: nornic://host:port or bolt://host:port\n"
                "Example: nornic://localhost:7687"
            )
        
        if not username or len(username.strip()) == 0:
            return False, "Username cannot be empty."
        
        if not password or len(password.strip()) == 0:
            return False, "Password cannot be empty."
        
        return True, None

    @staticmethod
    def test_connection(uri: str, username: str, password: str, database: str=None) -> Tuple[bool, Optional[str]]:
        """
        Tests the Nornic database connection.
        """
        try:
            from neo4j import GraphDatabase
            import socket
            
            try:
                host_port = uri.split('://')[1]
                if ':' in host_port:
                    host = host_port.split(':')[0]
                    port = int(host_port.split(':')[1])
                else:
                    host = host_port
                    port = 7687 
                
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((host, port))
                sock.close()
                
                if result != 0:
                    return False, f"Cannot reach Nornic server at {host}:{port}"
            except Exception as e:
                return False, f"Error parsing URI or checking connectivity: {str(e)}"
            
            driver = GraphDatabase.driver(uri, auth=(username, password))
            
            session_kwargs = {}
            if database:
                session_kwargs['database'] = database
            with driver.session(**session_kwargs) as session:
                result = session.run("RETURN 'Connection successful' as status")
                result.single()
            
            driver.close()
            return True, None
            
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
