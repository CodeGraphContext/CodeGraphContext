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


class TestCgroupAwareness:
    """Inside a container /proc/meminfo shows the HOST's memory; the pool
    must respect the tighter cgroup limit or the process is OOM-killed
    natively when the reservation is first touched."""

    def _patch_files(self, monkeypatch, contents):
        import builtins
        real_open = builtins.open

        def fake_open(path, *a, **k):
            if path in contents:
                raw = contents[path]
                if isinstance(raw, OSError):
                    raise raw
                import io
                return io.StringIO(raw)
            return real_open(path, *a, **k)

        monkeypatch.setattr(builtins, "open", fake_open)

    def test_cgroup_v2_limit_caps_host_available(self, monkeypatch):
        from codegraphcontext.core import database_embedded_kuzu as dek
        self._patch_files(monkeypatch, {
            "/proc/meminfo": "MemTotal: 67108864 kB\nMemAvailable: 33554432 kB\n",  # 32 GiB avail
            "/sys/fs/cgroup/memory.max": str(1 * 1024**3),   # 1 GiB pod limit
            "/sys/fs/cgroup/memory.current": str(256 * 1024**2),
        })
        # headroom = 1 GiB - 256 MiB = 768 MiB, far below host's 32 GiB
        assert dek._available_memory_bytes() == 768 * 1024**2

    def test_cgroup_v2_unlimited_uses_host_value(self, monkeypatch):
        from codegraphcontext.core import database_embedded_kuzu as dek
        self._patch_files(monkeypatch, {
            "/proc/meminfo": "MemAvailable: 8388608 kB\n",  # 8 GiB
            "/sys/fs/cgroup/memory.max": "max",
            "/sys/fs/cgroup/memory/memory.limit_in_bytes": OSError("no v1"),
        })
        assert dek._available_memory_bytes() == 8 * 1024**3

    def test_cgroup_v1_limit_caps_host_available(self, monkeypatch):
        from codegraphcontext.core import database_embedded_kuzu as dek
        self._patch_files(monkeypatch, {
            "/proc/meminfo": "MemAvailable: 33554432 kB\n",
            "/sys/fs/cgroup/memory.max": OSError("no v2"),
            "/sys/fs/cgroup/memory/memory.limit_in_bytes": str(2 * 1024**3),
            "/sys/fs/cgroup/memory/memory.usage_in_bytes": str(1 * 1024**3),
        })
        assert dek._available_memory_bytes() == 1 * 1024**3

    def test_cgroup_v1_unlimited_sentinel_ignored(self, monkeypatch):
        from codegraphcontext.core import database_embedded_kuzu as dek
        self._patch_files(monkeypatch, {
            "/proc/meminfo": "MemAvailable: 4194304 kB\n",  # 4 GiB
            "/sys/fs/cgroup/memory.max": OSError("no v2"),
            "/sys/fs/cgroup/memory/memory.limit_in_bytes": str(1 << 62),  # "unlimited"
        })
        assert dek._available_memory_bytes() == 4 * 1024**3

    def test_no_meminfo_falls_back_to_cgroup_alone(self, monkeypatch):
        from codegraphcontext.core import database_embedded_kuzu as dek
        self._patch_files(monkeypatch, {
            "/proc/meminfo": OSError("macOS-in-container"),
            "/sys/fs/cgroup/memory.max": str(1 * 1024**3),
            "/sys/fs/cgroup/memory.current": OSError("unreadable"),
        })
        assert dek._available_memory_bytes() == 1 * 1024**3

    def test_pod_limit_shrinks_the_default_pool(self, monkeypatch):
        """End-to-end: a 1 GiB pod on a 64 GiB host gets a ~384 MiB pool
        (half of headroom), not the 4 GiB that would OOM-kill it."""
        from codegraphcontext.core import database_embedded_kuzu as dek
        monkeypatch.delenv("CGC_EMBEDDED_BUFFER_POOL_MB", raising=False)
        self._patch_files(monkeypatch, {
            "/proc/meminfo": "MemAvailable: 67108864 kB\n",  # 64 GiB host
            "/sys/fs/cgroup/memory.max": str(1 * 1024**3),
            "/sys/fs/cgroup/memory.current": str(256 * 1024**2),
        })
        assert dek.resolve_embedded_buffer_pool_size() == 384 * 1024**2
