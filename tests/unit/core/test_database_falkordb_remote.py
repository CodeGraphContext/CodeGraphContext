
import os
import pytest
from unittest.mock import MagicMock, patch, PropertyMock


class TestFalkorDBRemoteManager:
    """
    Unit tests for the FalkorDBRemoteManager class.
    Mocks the FalkorDB client to test logic without a real remote DB.
    """

    def _reset_singleton(self):
        """Reset the singleton so each test starts fresh."""
        from codegraphcontext.core.database_falkordb_remote import FalkorDBRemoteManager
        FalkorDBRemoteManager._instance = None
        FalkorDBRemoteManager._driver = None
        FalkorDBRemoteManager._graph = None
        # Remove _initialized from any lingering instance
        if FalkorDBRemoteManager._instance and hasattr(FalkorDBRemoteManager._instance, '_initialized'):
            del FalkorDBRemoteManager._instance._initialized

    def setup_method(self):
        self._reset_singleton()

    def teardown_method(self):
        self._reset_singleton()

    def test_initialization_defaults(self):
        """Test default config values when no env vars are set."""
        env = {
            'FALKORDB_HOST': 'myhost.example.com',
        }
        # Clear all FALKORDB_ env vars first
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith('FALKORDB_')}
        clean_env.update(env)

        with patch.dict(os.environ, clean_env, clear=True):
            from codegraphcontext.core.database_falkordb_remote import FalkorDBRemoteManager
            self._reset_singleton()
            manager = FalkorDBRemoteManager()

            assert manager.host == 'myhost.example.com'
            assert manager.port == 6379
            assert manager.password is None
            assert manager.username is None
            assert manager.ssl is False
            assert manager.graph_name == 'codegraph'

    def test_initialization_custom_values(self):
        """Test that all env vars are correctly read."""
        env = {
            'FALKORDB_HOST': 'remote.falkordb.io',
            'FALKORDB_PORT': '16379',
            'FALKORDB_PASSWORD': 'secret123',
            'FALKORDB_USERNAME': 'admin',
            'FALKORDB_SSL': 'true',
            'FALKORDB_GRAPH_NAME': 'mygraph',
        }
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith('FALKORDB_')}
        clean_env.update(env)

        with patch.dict(os.environ, clean_env, clear=True):
            from codegraphcontext.core.database_falkordb_remote import FalkorDBRemoteManager
            self._reset_singleton()
            manager = FalkorDBRemoteManager()

            assert manager.host == 'remote.falkordb.io'
            assert manager.port == 16379
            assert manager.password == 'secret123'
            assert manager.username == 'admin'
            assert manager.ssl is True
            assert manager.graph_name == 'mygraph'

    def test_ssl_variations(self):
        """Test various truthy values for FALKORDB_SSL."""
        for val in ('true', 'True', 'TRUE', '1', 'yes', 'YES'):
            clean_env = {k: v for k, v in os.environ.items() if not k.startswith('FALKORDB_')}
            clean_env.update({'FALKORDB_HOST': 'h', 'FALKORDB_SSL': val})
            with patch.dict(os.environ, clean_env, clear=True):
                from codegraphcontext.core.database_falkordb_remote import FalkorDBRemoteManager
                self._reset_singleton()
                manager = FalkorDBRemoteManager()
                assert manager.ssl is True, f"Expected ssl=True for FALKORDB_SSL={val}"

        for val in ('false', '0', 'no', ''):
            clean_env = {k: v for k, v in os.environ.items() if not k.startswith('FALKORDB_')}
            clean_env.update({'FALKORDB_HOST': 'h', 'FALKORDB_SSL': val})
            with patch.dict(os.environ, clean_env, clear=True):
                from codegraphcontext.core.database_falkordb_remote import FalkorDBRemoteManager
                self._reset_singleton()
                manager = FalkorDBRemoteManager()
                assert manager.ssl is False, f"Expected ssl=False for FALKORDB_SSL={val}"

    def test_get_driver_connects_with_correct_params(self):
        """Test that get_driver() calls FalkorDB with the right kwargs."""
        env = {
            'FALKORDB_HOST': 'remote.host',
            'FALKORDB_PORT': '6380',
            'FALKORDB_PASSWORD': 'pass',
            'FALKORDB_USERNAME': 'user',
            'FALKORDB_SSL': 'true',
            'FALKORDB_GRAPH_NAME': 'testgraph',
        }
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith('FALKORDB_')}
        clean_env.update(env)

        with patch.dict(os.environ, clean_env, clear=True):
            from codegraphcontext.core.database_falkordb_remote import FalkorDBRemoteManager

            self._reset_singleton()
            manager = FalkorDBRemoteManager()

            mock_falkordb_cls = MagicMock()
            mock_db_instance = MagicMock()
            mock_graph = MagicMock()
            mock_falkordb_cls.return_value = mock_db_instance
            mock_db_instance.select_graph.return_value = mock_graph

            with patch('falkordb.FalkorDB', mock_falkordb_cls):
                driver_wrapper = manager.get_driver()

            mock_falkordb_cls.assert_called_once_with(
                host='remote.host',
                port=6380,
                password='pass',
                username='user',
                ssl=True,
            )
            mock_db_instance.select_graph.assert_called_once_with('testgraph')
            mock_graph.query.assert_called_once_with("RETURN 1")

            # Returns a FalkorDBDriverWrapper
            from codegraphcontext.core.database_falkordb import FalkorDBDriverWrapper
            assert isinstance(driver_wrapper, FalkorDBDriverWrapper)

    def test_get_driver_minimal_params(self):
        """Test get_driver with only host set (no password/username/ssl)."""
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith('FALKORDB_')}
        clean_env.update({'FALKORDB_HOST': 'simple.host'})

        with patch.dict(os.environ, clean_env, clear=True):
            from codegraphcontext.core.database_falkordb_remote import FalkorDBRemoteManager

            self._reset_singleton()
            manager = FalkorDBRemoteManager()

            mock_falkordb_cls = MagicMock()
            mock_db = MagicMock()
            mock_graph = MagicMock()
            mock_falkordb_cls.return_value = mock_db
            mock_db.select_graph.return_value = mock_graph

            with patch('falkordb.FalkorDB', mock_falkordb_cls):
                manager.get_driver()

            # Should NOT include password, username, or ssl
            mock_falkordb_cls.assert_called_once_with(
                host='simple.host',
                port=6379,
            )

    def test_get_driver_singleton_reuses_connection(self):
        """Test that calling get_driver() twice doesn't create a second connection."""
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith('FALKORDB_')}
        clean_env.update({'FALKORDB_HOST': 'h'})

        with patch.dict(os.environ, clean_env, clear=True):
            from codegraphcontext.core.database_falkordb_remote import FalkorDBRemoteManager

            self._reset_singleton()
            manager = FalkorDBRemoteManager()

            mock_falkordb_cls = MagicMock()
            mock_db = MagicMock()
            mock_graph = MagicMock()
            mock_falkordb_cls.return_value = mock_db
            mock_db.select_graph.return_value = mock_graph

            with patch('falkordb.FalkorDB', mock_falkordb_cls):
                d1 = manager.get_driver()
                d2 = manager.get_driver()

            # FalkorDB constructor called only once
            assert mock_falkordb_cls.call_count == 1

    def test_is_connected_true(self):
        """Test is_connected returns True when graph query succeeds."""
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith('FALKORDB_')}
        clean_env.update({'FALKORDB_HOST': 'h'})

        with patch.dict(os.environ, clean_env, clear=True):
            from codegraphcontext.core.database_falkordb_remote import FalkorDBRemoteManager

            self._reset_singleton()
            manager = FalkorDBRemoteManager()
            mock_graph = MagicMock()
            manager._graph = mock_graph

            assert manager.is_connected() is True
            mock_graph.query.assert_called_with("RETURN 1")

    def test_is_connected_false_no_graph(self):
        """Test is_connected returns False when graph is None."""
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith('FALKORDB_')}
        clean_env.update({'FALKORDB_HOST': 'h'})

        with patch.dict(os.environ, clean_env, clear=True):
            from codegraphcontext.core.database_falkordb_remote import FalkorDBRemoteManager

            self._reset_singleton()
            manager = FalkorDBRemoteManager()
            assert manager.is_connected() is False

    def test_is_connected_false_on_exception(self):
        """Test is_connected returns False when query raises."""
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith('FALKORDB_')}
        clean_env.update({'FALKORDB_HOST': 'h'})

        with patch.dict(os.environ, clean_env, clear=True):
            from codegraphcontext.core.database_falkordb_remote import FalkorDBRemoteManager

            self._reset_singleton()
            manager = FalkorDBRemoteManager()
            mock_graph = MagicMock()
            mock_graph.query.side_effect = ConnectionError("disconnected")
            manager._graph = mock_graph

            assert manager.is_connected() is False

    def test_get_backend_type(self):
        """Test backend type string."""
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith('FALKORDB_')}
        clean_env.update({'FALKORDB_HOST': 'h'})

        with patch.dict(os.environ, clean_env, clear=True):
            from codegraphcontext.core.database_falkordb_remote import FalkorDBRemoteManager

            self._reset_singleton()
            manager = FalkorDBRemoteManager()
            assert manager.get_backend_type() == 'falkordb-remote'

    def test_close_driver(self):
        """Test close_driver clears internal state."""
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith('FALKORDB_')}
        clean_env.update({'FALKORDB_HOST': 'h'})

        with patch.dict(os.environ, clean_env, clear=True):
            from codegraphcontext.core.database_falkordb_remote import FalkorDBRemoteManager

            self._reset_singleton()
            manager = FalkorDBRemoteManager()
            manager._driver = MagicMock()
            manager._graph = MagicMock()

            manager.close_driver()
            assert manager._driver is None
            assert manager._graph is None

    def test_validate_config_no_host(self):
        """Test validate_config fails when FALKORDB_HOST not set."""
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith('FALKORDB_')}

        with patch.dict(os.environ, clean_env, clear=True):
            from codegraphcontext.core.database_falkordb_remote import FalkorDBRemoteManager
            valid, error = FalkorDBRemoteManager.validate_config()
            assert valid is False
            assert 'FALKORDB_HOST' in error

    def test_validate_config_valid(self):
        """Test validate_config succeeds with host set."""
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith('FALKORDB_')}
        clean_env.update({'FALKORDB_HOST': 'myhost'})

        with patch.dict(os.environ, clean_env, clear=True):
            from codegraphcontext.core.database_falkordb_remote import FalkorDBRemoteManager
            valid, error = FalkorDBRemoteManager.validate_config()
            assert valid is True
            assert error is None

    def test_validate_config_bad_port(self):
        """Test validate_config fails with non-numeric port."""
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith('FALKORDB_')}
        clean_env.update({'FALKORDB_HOST': 'h', 'FALKORDB_PORT': 'abc'})

        with patch.dict(os.environ, clean_env, clear=True):
            from codegraphcontext.core.database_falkordb_remote import FalkorDBRemoteManager
            valid, error = FalkorDBRemoteManager.validate_config()
            assert valid is False
            assert 'number' in error

    def test_get_driver_import_error(self):
        """Test that missing falkordb package raises ValueError."""
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith('FALKORDB_')}
        clean_env.update({'FALKORDB_HOST': 'h'})

        with patch.dict(os.environ, clean_env, clear=True):
            from codegraphcontext.core.database_falkordb_remote import FalkorDBRemoteManager

            self._reset_singleton()
            manager = FalkorDBRemoteManager()

            with patch.dict('sys.modules', {'falkordb': None}):
                with patch('builtins.__import__', side_effect=ImportError("no falkordb")):
                    with pytest.raises(ValueError, match="FalkorDB client missing"):
                        manager.get_driver()


class TestFactoryFalkorDBRemote:
    """Test that get_database_manager() correctly routes to FalkorDBRemoteManager."""

    def setup_method(self):
        from codegraphcontext.core.database_falkordb_remote import FalkorDBRemoteManager
        FalkorDBRemoteManager._instance = None
        FalkorDBRemoteManager._driver = None
        FalkorDBRemoteManager._graph = None

    def teardown_method(self):
        from codegraphcontext.core.database_falkordb_remote import FalkorDBRemoteManager
        FalkorDBRemoteManager._instance = None
        FalkorDBRemoteManager._driver = None
        FalkorDBRemoteManager._graph = None

    def test_explicit_falkordb_remote(self):
        """Test DATABASE_TYPE=falkordb-remote returns FalkorDBRemoteManager."""
        env = {
            'DATABASE_TYPE': 'falkordb-remote',
            'FALKORDB_HOST': 'myhost',
        }
        # Clear conflicting vars
        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ('DATABASE_TYPE', 'DEFAULT_DATABASE', 'CGC_RUNTIME_DB_TYPE')
                     and not k.startswith('FALKORDB_')}
        clean_env.update(env)

        with patch.dict(os.environ, clean_env, clear=True):
            from codegraphcontext.core import get_database_manager
            from codegraphcontext.core.database_falkordb_remote import FalkorDBRemoteManager
            manager = get_database_manager()
            assert isinstance(manager, FalkorDBRemoteManager)

    def test_explicit_falkordb_remote_missing_host(self):
        """Test DATABASE_TYPE=falkordb-remote without FALKORDB_HOST raises."""
        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ('DATABASE_TYPE', 'DEFAULT_DATABASE', 'CGC_RUNTIME_DB_TYPE')
                     and not k.startswith('FALKORDB_')}
        clean_env.update({'DATABASE_TYPE': 'falkordb-remote'})

        with patch.dict(os.environ, clean_env, clear=True):
            from codegraphcontext.core import get_database_manager
            with pytest.raises(ValueError, match="FALKORDB_HOST is not set"):
                get_database_manager()

    def test_auto_detect_remote_via_host(self):
        """Test that setting FALKORDB_HOST (without DATABASE_TYPE) auto-detects remote."""
        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ('DATABASE_TYPE', 'DEFAULT_DATABASE', 'CGC_RUNTIME_DB_TYPE')
                     and not k.startswith('FALKORDB_')
                     and not k.startswith('NEO4J_')}
        clean_env.update({'FALKORDB_HOST': 'auto-detected.host'})

        with patch.dict(os.environ, clean_env, clear=True):
            from codegraphcontext.core import get_database_manager
            from codegraphcontext.core.database_falkordb_remote import FalkorDBRemoteManager
            manager = get_database_manager()
            assert isinstance(manager, FalkorDBRemoteManager)
            assert manager.host == 'auto-detected.host'

    def test_unknown_db_type_includes_falkordb_remote(self):
        """Test that unknown DATABASE_TYPE error message mentions falkordb-remote."""
        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ('DATABASE_TYPE', 'DEFAULT_DATABASE', 'CGC_RUNTIME_DB_TYPE')}
        clean_env.update({'DATABASE_TYPE': 'badvalue'})

        with patch.dict(os.environ, clean_env, clear=True):
            from codegraphcontext.core import get_database_manager
            with pytest.raises(ValueError, match="falkordb-remote"):
                get_database_manager()
