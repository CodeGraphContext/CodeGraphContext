
import os
import pytest
from unittest.mock import MagicMock, patch, call
from codegraphcontext.core.database import DatabaseManager, Neo4jDriverWrapper, Neo4jConnectionError

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

    def test_initialization_with_database(self, mock_driver):
        """Test that DatabaseManager reads NEO4J_DATABASE from env."""
        with patch.dict(os.environ, {
            "NEO4J_URI": "bolt://localhost:7687",
            "NEO4J_USERNAME": "neo4j",
            "NEO4J_PASSWORD": "password",
            "NEO4J_DATABASE": "mydb"
        }):
            if DatabaseManager._instance:
                DatabaseManager._instance = None
            db_manager = DatabaseManager()
            assert db_manager.neo4j_database == "mydb"

    def test_initialization_without_database(self, mock_driver):
        """Test that neo4j_database is None when NEO4J_DATABASE is not set."""
        env = {"NEO4J_URI": "bolt://localhost:7687", "NEO4J_USERNAME": "neo4j", "NEO4J_PASSWORD": "password"}
        with patch.dict(os.environ, env, clear=True):
            if DatabaseManager._instance:
                DatabaseManager._instance = None
            db_manager = DatabaseManager()
            assert db_manager.neo4j_database is None

    def test_get_driver_returns_wrapper_with_database(self, mock_driver):
        """Test get_driver() returns a Neo4jDriverWrapper with the configured database."""
        with patch.dict(os.environ, {
            "NEO4J_URI": "bolt://localhost:7687",
            "NEO4J_USERNAME": "neo4j",
            "NEO4J_PASSWORD": "password",
            "NEO4J_DATABASE": "mydb"
        }):
            if DatabaseManager._instance:
                DatabaseManager._instance = None
            db_manager = DatabaseManager()
            db_manager._driver = mock_driver

            # Mock the connection test inside get_driver
            session_mock = MagicMock()
            mock_driver.session.return_value.__enter__.return_value = session_mock

            wrapper = db_manager.get_driver()
            assert isinstance(wrapper, Neo4jDriverWrapper)
            assert wrapper._database == "mydb"

    def test_get_driver_returns_wrapper_without_database(self, mock_driver):
        """Test get_driver() returns a Neo4jDriverWrapper with None database when not configured."""
        env = {"NEO4J_URI": "bolt://localhost:7687", "NEO4J_USERNAME": "neo4j", "NEO4J_PASSWORD": "password"}
        with patch.dict(os.environ, env, clear=True):
            if DatabaseManager._instance:
                DatabaseManager._instance = None
            db_manager = DatabaseManager()
            db_manager._driver = mock_driver

            session_mock = MagicMock()
            mock_driver.session.return_value.__enter__.return_value = session_mock

            wrapper = db_manager.get_driver()
            assert isinstance(wrapper, Neo4jDriverWrapper)
            assert wrapper._database is None

    def test_is_connected_passes_database_to_session(self, mock_driver):
        """Test is_connected() includes database in session kwargs when neo4j_database is set."""
        with patch.dict(os.environ, {
            "NEO4J_URI": "bolt://localhost:7687",
            "NEO4J_USERNAME": "u",
            "NEO4J_PASSWORD": "p",
            "NEO4J_DATABASE": "mydb"
        }):
            if DatabaseManager._instance:
                DatabaseManager._instance = None
            db_manager = DatabaseManager()
            db_manager._driver = mock_driver

            session_mock = MagicMock()
            mock_driver.session.return_value.__enter__.return_value = session_mock

            db_manager.is_connected()
            mock_driver.session.assert_called_with(database="mydb")

    def test_is_connected_no_database_in_session(self, mock_driver):
        """Test is_connected() does NOT include database in session kwargs when neo4j_database is None."""
        env = {"NEO4J_URI": "bolt://localhost:7687", "NEO4J_USERNAME": "u", "NEO4J_PASSWORD": "p"}
        with patch.dict(os.environ, env, clear=True):
            if DatabaseManager._instance:
                DatabaseManager._instance = None
            db_manager = DatabaseManager()
            db_manager._driver = mock_driver

            session_mock = MagicMock()
            mock_driver.session.return_value.__enter__.return_value = session_mock

            db_manager.is_connected()
            mock_driver.session.assert_called_with()


class TestNeo4jDriverWrapper:
    """Unit tests for the Neo4jDriverWrapper class."""

    def test_session_injects_database_when_set(self):
        """Test session() adds database kwarg when wrapper has a database configured."""
        mock_driver = MagicMock()
        wrapper = Neo4jDriverWrapper(mock_driver, database="mydb")

        wrapper.session()
        mock_driver.session.assert_called_once_with(database="mydb")

    def test_session_no_database_when_none(self):
        """Test session() does NOT add database kwarg when database is None."""
        mock_driver = MagicMock()
        wrapper = Neo4jDriverWrapper(mock_driver, database=None)

        wrapper.session()
        mock_driver.session.assert_called_once_with()

    def test_session_does_not_override_existing_database(self):
        """Test session() respects caller-provided database kwarg."""
        mock_driver = MagicMock()
        wrapper = Neo4jDriverWrapper(mock_driver, database="mydb")

        wrapper.session(database="otherdb")
        mock_driver.session.assert_called_once_with(database="otherdb")

    def test_close_delegates_to_driver(self):
        """Test close() calls close() on the underlying driver."""
        mock_driver = MagicMock()
        wrapper = Neo4jDriverWrapper(mock_driver, database="mydb")

        wrapper.close()
        mock_driver.close.assert_called_once()


class TestTestConnection:
    """Unit tests for DatabaseManager.test_connection() with database parameter."""

    @patch('neo4j.GraphDatabase')
    @patch('socket.socket')
    def test_test_connection_with_database(self, mock_socket_cls, mock_gdb):
        """Test test_connection() passes database to session when provided."""
        # Mock socket connectivity check
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock
        mock_sock.connect_ex.return_value = 0

        # Mock driver and session
        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        is_connected, error = DatabaseManager.test_connection(
            "bolt://localhost:7687", "neo4j", "password", database="mydb"
        )

        assert is_connected is True
        assert error is None
        mock_driver.session.assert_called_once_with(database="mydb")

    @patch('neo4j.GraphDatabase')
    @patch('socket.socket')
    def test_test_connection_without_database(self, mock_socket_cls, mock_gdb):
        """Test test_connection() does NOT pass database to session when None."""
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock
        mock_sock.connect_ex.return_value = 0

        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        is_connected, error = DatabaseManager.test_connection(
            "bolt://localhost:7687", "neo4j", "password"
        )

        assert is_connected is True
        assert error is None
        mock_driver.session.assert_called_once_with()


class TestNeo4jPreflight:
    @patch("socket.create_connection")
    def test_check_port_reachable_success(self, mock_create_connection):
        mock_conn = MagicMock()
        mock_create_connection.return_value.__enter__.return_value = mock_conn

        ok, err = DatabaseManager.check_port_reachable("bolt://localhost:7687")

        assert ok is True
        assert err is None

    @patch("socket.create_connection", side_effect=OSError("refused"))
    def test_check_port_reachable_failure(self, _mock_create_connection):
        ok, err = DatabaseManager.check_port_reachable("bolt://localhost:7687")

        assert ok is False
        assert "Neo4j is not running on localhost:7687" in err

    def test_missing_credentials_message_contains_config_commands(self):
        message = DatabaseManager.build_missing_credentials_message(["NEO4J_PASSWORD"])

        assert "Neo4j credentials not configured" in message
        assert "cgc config set NEO4J_PASSWORD" in message

    @patch("codegraphcontext.core.database.DatabaseManager.check_port_reachable", return_value=(False, "service not reachable on port 7687"))
    def test_get_driver_fails_fast_when_port_unreachable(self, _mock_reachable):
        with patch.dict(
            os.environ,
            {
                "NEO4J_URI": "bolt://localhost:7687",
                "NEO4J_USERNAME": "neo4j",
                "NEO4J_PASSWORD": "password",
                "CGC_DB_SELECTION_SOURCE": "environment",
            },
            clear=False,
        ):
            DatabaseManager._instance = None
            db_manager = DatabaseManager()

            with pytest.raises(Neo4jConnectionError) as exc:
                db_manager.get_driver()

            assert "Neo4j connection failed (source: environment)" in str(exc.value)
            assert "service not reachable on port 7687" in str(exc.value)
