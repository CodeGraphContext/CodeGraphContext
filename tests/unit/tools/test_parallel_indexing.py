# tests/unit/tools/test_parallel_indexing.py
"""Unit tests for the parallelized-indexing improvements (issue #710).

Covers:
- discovery.py: MAX_FILE_SIZE_MB, IGNORE_TEST_FILES, MAX_DEPTH enforcement
- pipeline.py:  PARALLEL_WORKERS wired to asyncio semaphore
- incremental.py: compute_file_hash correctness
- writer.py:   set_file_content_hashes UNWIND query shape
- incremental.py: fetch_cached_hashes bulk query
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_repo(tmp_path: Path) -> Path:
    """Return a temporary directory tree used as a fake repo root."""
    return tmp_path


def _write(root: Path, rel: str, content: str = "x") -> Path:
    """Create a file at *root/rel* with *content*."""
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# 1. discovery.py – PARALLEL_WORKERS not relevant here
# ---------------------------------------------------------------------------

class TestDiscoveryMaxDepth:
    """safe_walk / discover_files_to_index respects MAX_DEPTH."""

    def _collect(self, root: Path, max_depth_val: str) -> List[Path]:
        from codegraphcontext.tools.indexing.discovery import discover_files_to_index

        with patch(
            "codegraphcontext.tools.indexing.discovery.get_config_value",
            side_effect=lambda k: {
                "IGNORE_DIRS": "",
                "IGNORE_TEST_FILES": "false",
                "MAX_DEPTH": max_depth_val,
                "MAX_FILE_SIZE_MB": "100",
            }.get(k, ""),
        ):
            files, _ = discover_files_to_index(root)
        return files

    def test_unlimited_returns_all_depths(self, tmp_repo: Path):
        _write(tmp_repo, "a.py")
        _write(tmp_repo, "sub/b.py")
        _write(tmp_repo, "sub/deep/c.py")

        files = self._collect(tmp_repo, "unlimited")
        names = {f.name for f in files}
        assert {"a.py", "b.py", "c.py"}.issubset(names)

    def test_depth_1_includes_first_level_only(self, tmp_repo: Path):
        _write(tmp_repo, "a.py")
        _write(tmp_repo, "sub/b.py")
        _write(tmp_repo, "sub/deep/c.py")

        files = self._collect(tmp_repo, "1")
        names = {f.name for f in files}
        assert "a.py" in names
        assert "b.py" in names
        assert "c.py" not in names

    def test_depth_2_includes_two_levels(self, tmp_repo: Path):
        _write(tmp_repo, "a.py")
        _write(tmp_repo, "sub/b.py")
        _write(tmp_repo, "sub/deep/c.py")

        files = self._collect(tmp_repo, "2")
        names = {f.name for f in files}
        assert "a.py" in names
        assert "b.py" in names
        assert "c.py" in names

    def test_invalid_depth_falls_back_to_unlimited(self, tmp_repo: Path):
        _write(tmp_repo, "a.py")
        _write(tmp_repo, "sub/b.py")
        # Bad value → warning logged, unlimited used
        files = self._collect(tmp_repo, "notanumber")
        names = {f.name for f in files}
        assert "a.py" in names
        assert "b.py" in names


class TestDiscoveryMaxFileSizeMB:
    """discover_files_to_index skips files that exceed MAX_FILE_SIZE_MB."""

    def _collect(self, root: Path, max_mb: str) -> List[Path]:
        from codegraphcontext.tools.indexing.discovery import discover_files_to_index

        with patch(
            "codegraphcontext.tools.indexing.discovery.get_config_value",
            side_effect=lambda k: {
                "IGNORE_DIRS": "",
                "IGNORE_TEST_FILES": "false",
                "MAX_DEPTH": "unlimited",
                "MAX_FILE_SIZE_MB": max_mb,
            }.get(k, ""),
        ):
            files, _ = discover_files_to_index(root)
        return files

    def test_small_file_included(self, tmp_repo: Path):
        _write(tmp_repo, "small.py", "print('hi')")
        files = self._collect(tmp_repo, "10")
        assert any(f.name == "small.py" for f in files)

    def test_oversized_file_excluded(self, tmp_repo: Path):
        big = tmp_repo / "big.py"
        big.write_bytes(b"x" * (2 * 1024 * 1024))  # 2 MB
        files = self._collect(tmp_repo, "1")  # limit = 1 MB
        assert not any(f.name == "big.py" for f in files)

    def test_file_at_exact_limit_included(self, tmp_repo: Path):
        exact = tmp_repo / "exact.py"
        exact.write_bytes(b"x" * (1 * 1024 * 1024))  # exactly 1 MB
        files = self._collect(tmp_repo, "1")
        assert any(f.name == "exact.py" for f in files)

    def test_invalid_limit_uses_default_10mb(self, tmp_repo: Path):
        # An invalid config should not raise; tiny files are always included.
        _write(tmp_repo, "tiny.py", "x")
        files = self._collect(tmp_repo, "badvalue")
        assert any(f.name == "tiny.py" for f in files)


class TestDiscoveryIgnoreTestFiles:
    """discover_files_to_index applies IGNORE_TEST_FILES."""

    def _collect(self, root: Path, ignore: str = "true") -> List[Path]:
        from codegraphcontext.tools.indexing.discovery import discover_files_to_index

        with patch(
            "codegraphcontext.tools.indexing.discovery.get_config_value",
            side_effect=lambda k: {
                "IGNORE_DIRS": "",
                "IGNORE_TEST_FILES": ignore,
                "MAX_DEPTH": "unlimited",
                "MAX_FILE_SIZE_MB": "100",
            }.get(k, ""),
        ):
            files, _ = discover_files_to_index(root)
        return files

    def test_test_prefixed_py_excluded(self, tmp_repo: Path):
        _write(tmp_repo, "test_foo.py")
        _write(tmp_repo, "foo.py")
        files = self._collect(tmp_repo)
        names = {f.name for f in files}
        assert "foo.py" in names
        assert "test_foo.py" not in names

    def test_test_suffixed_py_excluded(self, tmp_repo: Path):
        _write(tmp_repo, "foo_test.py")
        _write(tmp_repo, "foo.py")
        files = self._collect(tmp_repo)
        names = {f.name for f in files}
        assert "foo.py" in names
        assert "foo_test.py" not in names

    def test_dottest_js_excluded(self, tmp_repo: Path):
        _write(tmp_repo, "widget.test.js")
        _write(tmp_repo, "widget.js")
        files = self._collect(tmp_repo)
        names = {f.name for f in files}
        assert "widget.js" in names
        assert "widget.test.js" not in names

    def test_spec_ts_excluded(self, tmp_repo: Path):
        _write(tmp_repo, "service.spec.ts")
        _write(tmp_repo, "service.ts")
        files = self._collect(tmp_repo)
        names = {f.name for f in files}
        assert "service.ts" in names
        assert "service.spec.ts" not in names

    def test_conftest_excluded(self, tmp_repo: Path):
        _write(tmp_repo, "conftest.py")
        _write(tmp_repo, "app.py")
        files = self._collect(tmp_repo)
        names = {f.name for f in files}
        assert "app.py" in names
        assert "conftest.py" not in names

    def test_tests_directory_pruned(self, tmp_repo: Path):
        _write(tmp_repo, "tests/unit/test_something.py")
        _write(tmp_repo, "src/app.py")
        files = self._collect(tmp_repo)
        names = {f.name for f in files}
        assert "app.py" in names
        assert "test_something.py" not in names

    def test_disabled_includes_test_files(self, tmp_repo: Path):
        _write(tmp_repo, "test_foo.py")
        files = self._collect(tmp_repo, ignore="false")
        assert any(f.name == "test_foo.py" for f in files)


# ---------------------------------------------------------------------------
# 2. pipeline.py – PARALLEL_WORKERS read from config
# ---------------------------------------------------------------------------

class TestParallelWorkers:
    """The pipeline reads PARALLEL_WORKERS from config to size the semaphore."""

    def _semaphore_value_used(self, config_value: str) -> int:
        """
        Patch get_config_value to return *config_value* for PARALLEL_WORKERS
        and capture the value passed to asyncio.Semaphore during a minimal
        pipeline run (we intercept before file-processing starts).
        """
        captured: List[int] = []

        original_semaphore = asyncio.Semaphore

        class _CapturingSemaphore:
            def __init__(self, n: int):
                captured.append(n)
                self._s = original_semaphore(n)

            async def __aenter__(self):
                return await self._s.__aenter__()

            async def __aexit__(self, *a):
                return await self._s.__aexit__(*a)

        import codegraphcontext.tools.indexing.pipeline as _pipeline_mod

        with (
            patch.object(_pipeline_mod.asyncio, "Semaphore", _CapturingSemaphore),
            patch(
                "codegraphcontext.tools.indexing.pipeline._gcv_pipeline",
                side_effect=lambda k: {
                    "PARALLEL_WORKERS": config_value,
                    "CACHE_ENABLED": "false",
                }.get(k, ""),
            ),
        ):
            # Run a minimal pipeline with zero files so it exits immediately.
            writer = MagicMock()
            writer.driver = MagicMock()
            writer.add_repository_to_graph = MagicMock()
            job_mgr = MagicMock()

            async def _run():
                await _pipeline_mod.run_tree_sitter_index_async(
                    path=Path(tempfile.mkdtemp()),
                    is_dependency=False,
                    job_id=None,
                    cgcignore_path=None,
                    writer=writer,
                    job_manager=job_mgr,
                    parsers={},
                    get_parser=lambda _: None,
                    parse_file=lambda *_: {},
                    add_minimal_file_node=lambda *_: None,
                )

            with patch(
                "codegraphcontext.tools.indexing.pipeline.discover_files_to_index",
                return_value=([], Path(".")),
            ), patch(
                "codegraphcontext.tools.indexing.pipeline.pre_scan_for_imports",
                return_value={},
            ):
                asyncio.run(_run())

        return captured[0] if captured else -1

    def test_reads_config_value_4(self):
        val = self._semaphore_value_used("4")
        assert val == 4

    def test_reads_config_value_8(self):
        val = self._semaphore_value_used("8")
        assert val == 8

    def test_clamps_to_max_32(self):
        val = self._semaphore_value_used("99")
        assert val == 32

    def test_clamps_to_min_1(self):
        val = self._semaphore_value_used("0")
        assert val == 1

    def test_falls_back_to_4_on_invalid(self):
        val = self._semaphore_value_used("bad")
        assert val == 4


# ---------------------------------------------------------------------------
# 3. incremental.py – compute_file_hash
# ---------------------------------------------------------------------------

class TestComputeFileHash:
    """compute_file_hash returns correct SHA-256 digests."""

    def test_matches_hashlib(self, tmp_path: Path):
        from codegraphcontext.tools.indexing.incremental import compute_file_hash

        content = b"hello world\n"
        f = tmp_path / "sample.py"
        f.write_bytes(content)

        expected = hashlib.sha256(content).hexdigest()
        assert compute_file_hash(f) == expected

    def test_different_files_different_hashes(self, tmp_path: Path):
        from codegraphcontext.tools.indexing.incremental import compute_file_hash

        a = tmp_path / "a.py"
        b = tmp_path / "b.py"
        a.write_text("content A", encoding="utf-8")
        b.write_text("content B", encoding="utf-8")

        assert compute_file_hash(a) != compute_file_hash(b)

    def test_same_content_same_hash(self, tmp_path: Path):
        from codegraphcontext.tools.indexing.incremental import compute_file_hash

        a = tmp_path / "a.py"
        b = tmp_path / "b.py"
        a.write_text("identical", encoding="utf-8")
        b.write_text("identical", encoding="utf-8")

        assert compute_file_hash(a) == compute_file_hash(b)

    def test_nonexistent_file_returns_none(self, tmp_path: Path):
        from codegraphcontext.tools.indexing.incremental import compute_file_hash

        assert compute_file_hash(tmp_path / "does_not_exist.py") is None


# ---------------------------------------------------------------------------
# 4. incremental.py – fetch_cached_hashes
# ---------------------------------------------------------------------------

class TestFetchCachedHashes:
    """fetch_cached_hashes issues a single bulk query and returns a path→hash dict."""

    def test_returns_dict_from_db(self):
        from codegraphcontext.tools.indexing.incremental import fetch_cached_hashes

        mock_records = [
            {"path": "/repo/a.py", "hash": "aabbcc"},
            {"path": "/repo/b.py", "hash": "ddeeff"},
        ]

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.run.return_value = mock_records

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session

        result = fetch_cached_hashes(mock_driver, "/repo")
        assert result == {"/repo/a.py": "aabbcc", "/repo/b.py": "ddeeff"}

    def test_empty_result_returns_empty_dict(self):
        from codegraphcontext.tools.indexing.incremental import fetch_cached_hashes

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.run.return_value = []

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session

        result = fetch_cached_hashes(mock_driver, "/repo")
        assert result == {}

    def test_db_exception_returns_empty_dict(self):
        """A DB error must not propagate — cache is best-effort."""
        from codegraphcontext.tools.indexing.incremental import fetch_cached_hashes

        mock_driver = MagicMock()
        mock_driver.session.side_effect = RuntimeError("connection refused")

        result = fetch_cached_hashes(mock_driver, "/repo")
        assert result == {}

    def test_single_bulk_query_issued(self):
        from codegraphcontext.tools.indexing.incremental import fetch_cached_hashes

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.run.return_value = []

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session

        fetch_cached_hashes(mock_driver, "/repo")
        assert mock_session.run.call_count == 1, "Expected exactly one bulk DB read"


# ---------------------------------------------------------------------------
# 5. writer.py – set_file_content_hashes
# ---------------------------------------------------------------------------

class _FakeResult:
    def single(self):
        return None
    def __iter__(self):
        return iter([])


class _RecordingSession:
    def __init__(self):
        self.calls: List[Dict] = []

    def run(self, query: str, **kwargs):
        self.calls.append({"query": query, "kwargs": kwargs})
        return _FakeResult()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class _FakeDriver:
    def __init__(self, session: _RecordingSession):
        self._session = session

    def session(self):
        return self._session


class TestSetFileContentHashes:
    """GraphWriter.set_file_content_hashes issues an UNWIND bulk SET."""

    def _make_writer(self) -> tuple:
        from codegraphcontext.tools.indexing.persistence.writer import GraphWriter

        session = _RecordingSession()
        driver = _FakeDriver(session)
        writer = GraphWriter(driver)
        return writer, session

    def test_single_unwind_query_for_multiple_files(self):
        writer, session = self._make_writer()
        updates = [
            {"path": "/repo/a.py", "hash": "aa"},
            {"path": "/repo/b.py", "hash": "bb"},
            {"path": "/repo/c.py", "hash": "cc"},
        ]
        writer.set_file_content_hashes(updates)
        assert len(session.calls) == 1, "Expected exactly one UNWIND query"
        query = session.calls[0]["query"]
        assert "UNWIND" in query
        assert "content_hash" in query
        assert session.calls[0]["kwargs"]["batch"] == updates

    def test_no_op_on_empty_list(self):
        writer, session = self._make_writer()
        writer.set_file_content_hashes([])
        assert session.calls == [], "No DB call should be made for empty updates"

    def test_db_error_does_not_raise(self):
        """Failures must be swallowed — cache is best-effort."""
        from codegraphcontext.tools.indexing.persistence.writer import GraphWriter

        bad_session = MagicMock()
        bad_session.__enter__ = MagicMock(return_value=bad_session)
        bad_session.__exit__ = MagicMock(return_value=False)
        bad_session.run.side_effect = RuntimeError("db error")

        bad_driver = MagicMock()
        bad_driver.session.return_value = bad_session

        writer = GraphWriter(bad_driver)
        # Must not raise
        writer.set_file_content_hashes([{"path": "/a.py", "hash": "xx"}])


# ---------------------------------------------------------------------------
# 6. pipeline.py – incremental cache skips unchanged files
# ---------------------------------------------------------------------------

class TestPipelineIncrementalSkip:
    """Files with unchanged content hashes are skipped by the pipeline."""

    def test_unchanged_file_is_skipped(self, tmp_path: Path):
        """When a file's hash matches the cached hash it should not be parsed."""
        from codegraphcontext.tools.indexing import pipeline as _pipeline_mod

        source = tmp_path / "app.py"
        source.write_text("print('hello')", encoding="utf-8")

        # Compute the real hash so the cache appears warm
        from codegraphcontext.tools.indexing.incremental import compute_file_hash
        real_hash = compute_file_hash(source)

        parse_calls: List[Path] = []

        def fake_parse(repo_path, file, is_dep):
            parse_calls.append(file)
            return {"path": str(file), "functions": [], "classes": [], "imports": []}

        writer = MagicMock()
        writer.driver = MagicMock()
        writer.add_repository_to_graph = MagicMock()
        writer.add_file_to_graph = MagicMock()
        writer.set_file_content_hashes = MagicMock()

        job_mgr = MagicMock()

        async def _run():
            with (
                patch(
                    "codegraphcontext.tools.indexing.pipeline.discover_files_to_index",
                    return_value=([source], tmp_path),
                ),
                patch(
                    "codegraphcontext.tools.indexing.pipeline.pre_scan_for_imports",
                    return_value={},
                ),
                patch(
                    "codegraphcontext.tools.indexing.pipeline.fetch_cached_hashes",
                    return_value={str(source.resolve()): real_hash},
                ),
                patch(
                    "codegraphcontext.tools.indexing.pipeline._gcv_pipeline",
                    side_effect=lambda k: {
                        "PARALLEL_WORKERS": "1",
                        "CACHE_ENABLED": "true",
                    }.get(k, ""),
                ),
            ):
                await _pipeline_mod.run_tree_sitter_index_async(
                    path=tmp_path,
                    is_dependency=False,
                    job_id=None,
                    cgcignore_path=None,
                    writer=writer,
                    job_manager=job_mgr,
                    parsers={".py": "python"},
                    get_parser=lambda _: None,
                    parse_file=fake_parse,
                    add_minimal_file_node=lambda *_: None,
                )

        asyncio.run(_run())

        assert parse_calls == [], (
            "parse_file should NOT have been called for the unchanged file"
        )
        writer.add_file_to_graph.assert_not_called()

    def test_changed_file_is_reparsed(self, tmp_path: Path):
        """A file whose hash differs from the cache must be fully reprocessed."""
        from codegraphcontext.tools.indexing import pipeline as _pipeline_mod

        source = tmp_path / "app.py"
        source.write_text("print('hello')", encoding="utf-8")

        parse_calls: List[Path] = []

        def fake_parse(repo_path, file, is_dep):
            parse_calls.append(file)
            return {
                "path": str(file),
                "functions": [],
                "classes": [],
                "imports": [],
                "lang": "python",
            }

        writer = MagicMock()
        writer.driver = MagicMock()
        writer.add_repository_to_graph = MagicMock()
        writer.add_file_to_graph = MagicMock()
        writer.set_file_content_hashes = MagicMock()

        job_mgr = MagicMock()

        async def _run():
            with (
                patch(
                    "codegraphcontext.tools.indexing.pipeline.discover_files_to_index",
                    return_value=([source], tmp_path),
                ),
                patch(
                    "codegraphcontext.tools.indexing.pipeline.pre_scan_for_imports",
                    return_value={},
                ),
                patch(
                    "codegraphcontext.tools.indexing.pipeline.fetch_cached_hashes",
                    # Stale hash → triggers reparse
                    return_value={str(source.resolve()): "000000stale"},
                ),
                patch(
                    "codegraphcontext.tools.indexing.pipeline._gcv_pipeline",
                    side_effect=lambda k: {
                        "PARALLEL_WORKERS": "1",
                        "CACHE_ENABLED": "true",
                    }.get(k, ""),
                ),
            ):
                await _pipeline_mod.run_tree_sitter_index_async(
                    path=tmp_path,
                    is_dependency=False,
                    job_id=None,
                    cgcignore_path=None,
                    writer=writer,
                    job_manager=job_mgr,
                    parsers={".py": "python"},
                    get_parser=lambda _: None,
                    parse_file=fake_parse,
                    add_minimal_file_node=lambda *_: None,
                )

        asyncio.run(_run())

        assert len(parse_calls) == 1, "parse_file should be called for the changed file"
