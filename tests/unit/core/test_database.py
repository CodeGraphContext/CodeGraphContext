
import os
import pytest
from unittest.mock import MagicMock, patch
from codegraphcontext.core.database import DatabaseManager

class TestDatabaseManager:
    """
    Unit tests for the DatabaseManager class.
    Mocks the actual Neo4j driver to test logic without a real DB.
    """

    @pytest.fixture
    def mock_driver(self):
        with patch('neo4j.GraphDatabase.driver') as mock_driver_cls:
            mock_instance = MagicMock()
            mock_driver_cls.return_value = mock_instance
            yield mock_instance

    def test_initialization(self, mock_driver):
        """Test that DatabaseManager initializes with correct config from env."""
        with patch.dict(os.environ, {"NEO4J_URI": "bolt://localhost:7687", "NEO4J_USERNAME": "neo4j", "NEO4J_PASSWORD": "password"}):
            # Reset properties if singleton already exists (hacky for singleton testing)
            if DatabaseManager._instance:
                DatabaseManager._instance = None
                
            db_manager = DatabaseManager()
            assert db_manager.neo4j_uri == "bolt://localhost:7687"
            assert db_manager.neo4j_username == "neo4j"
    
    def test_verify_connection_success(self, mock_driver):
        """Test verify_connectivity returns True on success."""
        with patch.dict(os.environ, {"NEO4J_URI": "bolt://localhost:7687", "NEO4J_USERNAME": "u", "NEO4J_PASSWORD": "p"}):
             # Force re-init
            if DatabaseManager._instance:
                DatabaseManager._instance._initialized = False # Force re-read env
                
            db_manager = DatabaseManager()
            # Mock the driver creation which happens in get_driver or explicit assignment
            db_manager._driver = mock_driver
            
            # verify_connection in code calls self._driver.session()...
            # Logic: with self._driver.session() as session: session.run("RETURN 1").consume()
            
            session_mock = MagicMock()
            mock_driver.session.return_value.__enter__.return_value = session_mock
            
            assert db_manager.is_connected() is True

    def test_verify_connection_failure(self, mock_driver):
        """Test verify_connectivity returns False on exception."""
        with patch.dict(os.environ, {"NEO4J_URI": "bolt://localhost:7687", "NEO4J_USERNAME": "u", "NEO4J_PASSWORD": "p"}):
            db_manager = DatabaseManager()
            db_manager._driver = mock_driver
            
            mock_driver.session.side_effect = Exception("Connection refused")
            
            assert db_manager.is_connected() is False


