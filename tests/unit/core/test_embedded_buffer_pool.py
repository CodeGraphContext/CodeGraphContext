"""
Tests for the embedded LadybugDB/Kuzu buffer-pool size resolution and wiring.

Mocks the backend driver so the suite does not require a real kuzu/ladybug install.
"""
from unittest.mock import MagicMock, patch

import pytest

from codegraphcontext.core.database_kuzu import KuzuDBManager


DEFAULT_POOL = 4 * 1024**3


def _reset_kuzu_singleton():
    if KuzuDBManager._instance is not None:
        try:
            KuzuDBManager._instance.close_driver()
        except Exception:
            pass
    KuzuDBManager._instance = None
    KuzuDBManager._db = None
    KuzuDBManager._pool = None


@pytest.fixture(autouse=True)
def _clean_singleton():
    _reset_kuzu_singleton()
    yield
    _reset_kuzu_singleton()


class TestResolveEmbeddedBufferPoolSize:
    def test_default_is_4_gib_when_memory_is_plentiful(self, monkeypatch):
        from codegraphcontext.core import database_embedded_kuzu as dek

        monkeypatch.delenv("CGC_EMBEDDED_BUFFER_POOL_MB", raising=False)
        # The default is 4 GiB capped at half of available memory — a fixed
        # 4 GiB pool made LadybugDB fault natively on constrained CI runners.
        monkeypatch.setattr(dek, "_available_memory_bytes", lambda: 64 * 1024**3)
        assert dek.resolve_embedded_buffer_pool_size() == DEFAULT_POOL

    def test_env_override_mib(self, monkeypatch):
        from codegraphcontext.core.database_embedded_kuzu import (
            resolve_embedded_buffer_pool_size,
        )

        monkeypatch.setenv("CGC_EMBEDDED_BUFFER_POOL_MB", "512")
        assert resolve_embedded_buffer_pool_size() == 512 * 1024**2

    def test_zero_means_library_default(self, monkeypatch):
        from codegraphcontext.core.database_embedded_kuzu import (
            resolve_embedded_buffer_pool_size,
        )

        monkeypatch.setenv("CGC_EMBEDDED_BUFFER_POOL_MB", "0")
        assert resolve_embedded_buffer_pool_size() == 0

    def test_invalid_abc_falls_back(self, monkeypatch):
        from codegraphcontext.core.database_embedded_kuzu import (
            resolve_embedded_buffer_pool_size,
        )

        monkeypatch.setenv("CGC_EMBEDDED_BUFFER_POOL_MB", "abc")
        assert resolve_embedded_buffer_pool_size() == DEFAULT_POOL

    def test_invalid_negative_falls_back(self, monkeypatch):
        from codegraphcontext.core.database_embedded_kuzu import (
            resolve_embedded_buffer_pool_size,
        )

        monkeypatch.setenv("CGC_EMBEDDED_BUFFER_POOL_MB", "-1")
        assert resolve_embedded_buffer_pool_size() == DEFAULT_POOL


class TestDatabaseReceivesBufferPoolSize:
    def _open_with_mocked_backend(self, tmp_path):
        mock_db = MagicMock()
        mock_db.is_closed.return_value = False
        backend = MagicMock()
        backend.Database.return_value = mock_db
        backend.Connection.return_value = MagicMock()

        with patch(
            "codegraphcontext.core.database_embedded_kuzu.importlib.import_module",
            return_value=backend,
        ), patch.object(KuzuDBManager, "_initialize_schema", return_value=None):
            manager = KuzuDBManager(db_path=str(tmp_path / "graph.kuzu"))
            manager.get_driver()
        return backend

    def test_default_passes_4_gib(self, tmp_path, monkeypatch):
        from codegraphcontext.core import database_embedded_kuzu as dek
        monkeypatch.delenv("CGC_EMBEDDED_BUFFER_POOL_MB", raising=False)
        monkeypatch.setattr(dek, "_available_memory_bytes", lambda: 64 * 1024**3)
        backend = self._open_with_mocked_backend(tmp_path)
        backend.Database.assert_called_once()
        _, kwargs = backend.Database.call_args
        assert kwargs.get("buffer_pool_size") == DEFAULT_POOL

    def test_env_override_passes_bytes(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CGC_EMBEDDED_BUFFER_POOL_MB", "512")
        backend = self._open_with_mocked_backend(tmp_path)
        _, kwargs = backend.Database.call_args
        assert kwargs.get("buffer_pool_size") == 512 * 1024**2

    def test_zero_omits_the_kwarg_entirely(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CGC_EMBEDDED_BUFFER_POOL_MB", "0")
        backend = self._open_with_mocked_backend(tmp_path)
        _, kwargs = backend.Database.call_args
        # 0 means "library default": the kwarg is omitted rather than trusting
        # every backend to treat a literal 0 that way.
        assert "buffer_pool_size" not in kwargs

    def test_invalid_falls_back_without_raise(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CGC_EMBEDDED_BUFFER_POOL_MB", "abc")
        backend = self._open_with_mocked_backend(tmp_path)
        _, kwargs = backend.Database.call_args
        assert kwargs.get("buffer_pool_size") == DEFAULT_POOL


def test_default_adapts_to_available_memory(monkeypatch):
    """On a constrained host the unset default must shrink below 4 GiB —
    a fixed 4 GiB pool made LadybugDB fault natively on CI runners."""
    from codegraphcontext.core import database_embedded_kuzu as dek
    monkeypatch.delenv("CGC_EMBEDDED_BUFFER_POOL_MB", raising=False)
    monkeypatch.setattr(dek, "_available_memory_bytes", lambda: 2 * 1024**3)
    assert dek.resolve_embedded_buffer_pool_size() == 1 * 1024**3  # half of avail

    monkeypatch.setattr(dek, "_available_memory_bytes", lambda: 64 * 1024**3)
    assert dek.resolve_embedded_buffer_pool_size() == 4 * 1024**3  # capped at 4 GiB

    monkeypatch.setattr(dek, "_available_memory_bytes", lambda: 100 * 1024**2)
    assert dek.resolve_embedded_buffer_pool_size() == 256 * 1024**2  # floor

    monkeypatch.setattr(dek, "_available_memory_bytes", lambda: None)
    assert dek.resolve_embedded_buffer_pool_size() == 4 * 1024**3  # unknown → 4 GiB


def test_explicit_value_is_honored_verbatim(monkeypatch):
    from codegraphcontext.core import database_embedded_kuzu as dek
    monkeypatch.setenv("CGC_EMBEDDED_BUFFER_POOL_MB", "8192")
    monkeypatch.setattr(dek, "_available_memory_bytes", lambda: 1 * 1024**3)
    # explicit values are never second-guessed by the availability heuristic
    assert dek.resolve_embedded_buffer_pool_size() == 8192 * 1024**2
