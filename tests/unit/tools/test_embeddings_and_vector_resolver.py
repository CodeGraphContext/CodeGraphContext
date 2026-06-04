"""
Unit tests for Phase 4 — EmbeddingPipeline and VectorResolver.

Uses only mocked Neo4j driver and embedder to stay unit-test fast (no network,
no real DB, no GPU).  Tests verify the fetch/embed/write pipeline logic and the
ANN resolver's candidate selection behaviour.
"""

import pytest
from unittest.mock import MagicMock, call, patch


# ---------------------------------------------------------------------------
# Minimal Neo4j stubs (consistent pattern with test_graph_builder_perf_fixes.py)
# ---------------------------------------------------------------------------

class _FakeRow(dict):
    """dict that also supports attribute access like a Record."""
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item)


class _FakeResult:
    def __init__(self, rows=None):
        self._rows = rows or []

    def single(self):
        return _FakeRow(self._rows[0]) if self._rows else None

    def __iter__(self):
        return iter(_FakeRow(r) for r in self._rows)


class _RecordingSession:
    def __init__(self, responses=None):
        self.calls = []
        self._responses = list(responses or [])
        self._idx = 0

    def run(self, query, **kwargs):
        self.calls.append({"query": query, "kwargs": kwargs})
        result = self._responses[self._idx] if self._idx < len(self._responses) else _FakeResult()
        self._idx += 1
        return result

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class _FakeDriver:
    def __init__(self, session):
        self._session = session

    def session(self):
        return self._session


# ---------------------------------------------------------------------------
# Tests: EmbeddingPipeline
# ---------------------------------------------------------------------------

class TestEmbeddingPipeline:

    def _make_pipeline(self, session):
        from codegraphcontext.tools.indexing.embeddings import EmbeddingPipeline
        driver = _FakeDriver(session)
        return EmbeddingPipeline(driver, batch_size=2)

    def test_run_does_nothing_when_no_unembedded_nodes(self):
        """If the fetch query returns no rows, no embed or write calls should occur."""
        session = _RecordingSession(responses=[
            _FakeResult([]),  # ensure_vector_index
            _FakeResult([]),  # fetch_unembedded → empty
        ])
        pipeline = self._make_pipeline(session)

        mock_embedder = MagicMock()
        mock_embedder.dim = 384

        with patch("codegraphcontext.tools.indexing.embeddings._get_embedder", return_value=mock_embedder):
            pipeline.run("/opt/repos/myapp")

        mock_embedder.embed_batch.assert_not_called()

    def test_run_calls_embed_batch_for_each_batch(self):
        """With 3 nodes and batch_size=2, embed_batch must be called twice."""
        nodes = [
            {"path": "/a.java", "name": "execute", "line_number": 1,
             "qualified_name": "com.example.billing.BillingService.execute",
             "docstring": None, "parameters": []},
            {"path": "/b.java", "name": "process", "line_number": 5,
             "qualified_name": None, "docstring": "processes order", "parameters": ["orderId"]},
            {"path": "/c.java", "name": "validate", "line_number": 10,
             "qualified_name": "com.example.auth.Authenticator.validate",
             "docstring": None, "parameters": ["token"]},
        ]
        session = _RecordingSession(responses=[
            _FakeResult([]),  # ensure_vector_index
            _FakeResult(nodes),  # fetch_unembedded
            _FakeResult([]),  # write batch 1
            _FakeResult([]),  # write batch 2
        ])
        pipeline = self._make_pipeline(session)  # batch_size=2

        mock_embedder = MagicMock()
        mock_embedder.dim = 384
        mock_embedder.embed_batch.return_value = [[0.1] * 384, [0.2] * 384]

        with patch("codegraphcontext.tools.indexing.embeddings._get_embedder", return_value=mock_embedder):
            pipeline.run("/opt/repos/myapp")

        assert mock_embedder.embed_batch.call_count == 2

    def test_run_writes_embeddings_back_to_neo4j(self):
        """Each Write call must include an UNWIND query that sets f.embedding."""
        nodes = [
            {"path": "/a.java", "name": "execute", "line_number": 1,
             "qualified_name": None, "docstring": None, "parameters": []},
        ]
        session = _RecordingSession(responses=[
            _FakeResult([]),   # ensure_vector_index
            _FakeResult(nodes),
            _FakeResult([]),   # write
        ])
        pipeline = self._make_pipeline(session)

        mock_embedder = MagicMock()
        mock_embedder.dim = 384
        mock_embedder.embed_batch.return_value = [[0.5] * 384]

        with patch("codegraphcontext.tools.indexing.embeddings._get_embedder", return_value=mock_embedder):
            pipeline.run("/opt/repos/myapp")

        write_queries = [c["query"] for c in session.calls if "embedding" in c["query"].lower()]
        assert write_queries, "Expected at least one query that sets f.embedding"
        assert any("UNWIND" in q for q in write_queries), "Write must use UNWIND for batching"

    def test_vector_index_creation_is_first_call(self):
        """Vector index DDL must be issued before any embed or write calls."""
        nodes = [
            {"path": "/a.java", "name": "fn", "line_number": 1,
             "qualified_name": None, "docstring": None, "parameters": []},
        ]
        session = _RecordingSession(responses=[
            _FakeResult([]),   # ensure_vector_index
            _FakeResult(nodes),
            _FakeResult([]),
        ])
        pipeline = self._make_pipeline(session)

        mock_embedder = MagicMock()
        mock_embedder.dim = 384
        mock_embedder.embed_batch.return_value = [[0.1] * 384]

        with patch("codegraphcontext.tools.indexing.embeddings._get_embedder", return_value=mock_embedder):
            pipeline.run("/opt/repos/myapp")

        first_query = session.calls[0]["query"]
        assert "INDEX" in first_query.upper() or "VECTOR" in first_query.upper(), (
            "First DB call must create the vector index; got: " + first_query[:80]
        )

    def test_embed_batch_failure_skips_batch_but_continues(self):
        """An embedder failure on one batch must not crash the pipeline."""
        nodes = [
            {"path": "/a.java", "name": "fn1", "line_number": 1,
             "qualified_name": None, "docstring": None, "parameters": []},
            {"path": "/b.java", "name": "fn2", "line_number": 2,
             "qualified_name": None, "docstring": None, "parameters": []},
            {"path": "/c.java", "name": "fn3", "line_number": 3,
             "qualified_name": None, "docstring": None, "parameters": []},
        ]
        session = _RecordingSession(responses=[
            _FakeResult([]),    # ensure_vector_index
            _FakeResult(nodes),
            _FakeResult([]),    # write for successful batch
        ])
        pipeline = self._make_pipeline(session)  # batch_size=2

        mock_embedder = MagicMock()
        mock_embedder.dim = 384
        # First batch fails, second succeeds
        mock_embedder.embed_batch.side_effect = [RuntimeError("API error"), [[0.1] * 384]]

        with patch("codegraphcontext.tools.indexing.embeddings._get_embedder", return_value=mock_embedder):
            # Must not raise
            pipeline.run("/opt/repos/myapp")


# ---------------------------------------------------------------------------
# Tests: _build_text
# ---------------------------------------------------------------------------

class TestBuildText:

    def test_includes_qualified_name_when_present(self):
        from codegraphcontext.tools.indexing.embeddings import _build_text
        fn = {"name": "execute", "qualified_name": "com.example.acme.BillingService.execute"}
        text = _build_text(fn)
        assert "com.example.acme.BillingService.execute" in text

    def test_falls_back_to_name_without_qualified_name(self):
        from codegraphcontext.tools.indexing.embeddings import _build_text
        fn = {"name": "doWork"}
        text = _build_text(fn)
        assert "doWork" in text

    def test_includes_docstring_when_present(self):
        from codegraphcontext.tools.indexing.embeddings import _build_text
        fn = {"name": "process", "docstring": "Processes the incoming payment request."}
        text = _build_text(fn)
        assert "Processes the incoming payment request." in text

    def test_includes_parameters(self):
        from codegraphcontext.tools.indexing.embeddings import _build_text
        fn = {"name": "find", "parameters": ["orderId", "userId"]}
        text = _build_text(fn)
        assert "orderId" in text
        assert "userId" in text

    def test_empty_function_node_does_not_crash(self):
        from codegraphcontext.tools.indexing.embeddings import _build_text
        text = _build_text({})
        assert isinstance(text, str)


# ---------------------------------------------------------------------------
# Tests: VectorResolver
# ---------------------------------------------------------------------------

class TestVectorResolver:

    def _make_resolver(self, session, threshold=0.75):
        from codegraphcontext.tools.indexing.vector_resolver import VectorResolver
        driver = _FakeDriver(session)
        resolver = VectorResolver(driver, threshold=threshold)
        return resolver

    def _patch_embedder(self, resolver, vec=None):
        """Inject a mock embedder that returns a fixed vector."""
        mock_embedder = MagicMock()
        mock_embedder.embed_batch.return_value = [vec or ([0.1] * 384)]
        resolver._embedder = mock_embedder

    def test_returns_none_when_no_candidates(self):
        session = _RecordingSession()
        resolver = self._make_resolver(session)
        self._patch_embedder(resolver)

        result = resolver.resolve("execute", None, [], "/opt/repos/myapp")
        assert result is None

    def test_returns_path_above_threshold(self):
        session = _RecordingSession(responses=[
            _FakeResult([{"path": "/repo/BillingService.java", "score": 0.92}])
        ])
        resolver = self._make_resolver(session, threshold=0.75)
        self._patch_embedder(resolver)

        result = resolver.resolve(
            "execute",
            "com.example.acme.billing.BillingService.handle",
            ["/repo/BillingService.java"],
            "/opt/repos/myapp",
        )
        assert result == "/repo/BillingService.java"

    def test_returns_none_below_threshold(self):
        session = _RecordingSession(responses=[
            _FakeResult([{"path": "/repo/GenericAction.java", "score": 0.50}])
        ])
        resolver = self._make_resolver(session, threshold=0.75)
        self._patch_embedder(resolver)

        result = resolver.resolve("execute", None, ["/repo/GenericAction.java"], "/opt/repos/myapp")
        assert result is None

    def test_returns_none_on_embedder_failure(self):
        session = _RecordingSession()
        resolver = self._make_resolver(session)
        mock_embedder = MagicMock()
        mock_embedder.embed_batch.side_effect = RuntimeError("network error")
        resolver._embedder = mock_embedder

        result = resolver.resolve("execute", None, ["/repo/A.java"], "/opt/repos/myapp")
        assert result is None

    def test_returns_none_on_db_failure(self):
        session = _RecordingSession(responses=[_FakeResult([])])
        session.run = MagicMock(side_effect=RuntimeError("connection refused"))
        resolver = self._make_resolver(session)
        self._patch_embedder(resolver)

        result = resolver.resolve("execute", None, ["/repo/A.java"], "/opt/repos/myapp")
        assert result is None

    def test_resolve_bulk_maps_indices_to_paths(self):
        """resolve_bulk must return a dict mapping call index → resolved path."""
        session = _RecordingSession(responses=[
            _FakeResult([{"path": "/repo/A.java", "score": 0.95}]),
            _FakeResult([]),  # second call finds no match above threshold
        ])
        resolver = self._make_resolver(session, threshold=0.75)
        self._patch_embedder(resolver)

        calls = [
            {"called_name": "execute", "candidate_paths": ["/repo/A.java"], "caller_qualified_name": None},
            {"called_name": "validate", "candidate_paths": ["/repo/B.java"], "caller_qualified_name": None},
        ]
        result = resolver.resolve_bulk(calls, "/opt/repos/myapp")

        assert 0 in result
        assert result[0] == "/repo/A.java"
        assert 1 not in result  # below threshold

    def test_resolve_bulk_empty_input(self):
        session = _RecordingSession()
        resolver = self._make_resolver(session)
        self._patch_embedder(resolver)

        result = resolver.resolve_bulk([], "/opt/repos/myapp")
        assert result == {}
