from __future__ import annotations

from types import SimpleNamespace

from codegraphcontext.tools.indexing.persistence.writer import GraphWriter
from codegraphcontext.tools.indexing.schema import create_graph_schema
from codegraphcontext.tools.indexing import worker_config


class _RecordingSession:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def run(self, query: str, **_kwargs):
        self.queries.append(query)
        return SimpleNamespace()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class _FakeDriver:
    def __init__(self, session: _RecordingSession) -> None:
        self._session = session

    def session(self):
        return self._session


def test_schema_creates_parameter_constraint():
    session = _RecordingSession()
    create_graph_schema(_FakeDriver(session), SimpleNamespace(get_backend_type=lambda: "neo4j"))
    assert any("parameter_unique" in q for q in session.queries)


def test_resolve_file_write_workers_uses_parallel_write_workers(monkeypatch):
    monkeypatch.setattr(worker_config, "get_config_value", lambda key: {"PARALLEL_WRITE_WORKERS": "6"}.get(key, ""))
    assert worker_config.resolve_file_write_workers() == 6


def test_resolve_file_write_workers_falls_back_to_parallel_workers(monkeypatch):
    monkeypatch.setattr(worker_config, "get_config_value", lambda key: {"PARALLEL_WORKERS": "5"}.get(key, ""))
    assert worker_config.resolve_file_write_workers() == 5


def test_resolve_file_write_workers_clamps_high_values(monkeypatch):
    monkeypatch.setattr(worker_config, "get_config_value", lambda key: {"PARALLEL_WRITE_WORKERS": "99"}.get(key, ""))
    assert worker_config.resolve_file_write_workers() == 8


def test_rel_write_workers_respects_configurable_cap(monkeypatch):
    writer = GraphWriter(driver=None)
    monkeypatch.setenv("CGC_RUNTIME_DB_TYPE", "neo4j")
    monkeypatch.setenv("CGC_NEO4J_REL_WRITE_WORKERS", "10")
    monkeypatch.setenv("CGC_NEO4J_REL_WRITE_WORKERS_MAX", "14")
    assert writer._neo4j_rel_write_workers() == 10


def test_rel_write_workers_clamps_to_max_cap(monkeypatch):
    writer = GraphWriter(driver=None)
    monkeypatch.setenv("CGC_RUNTIME_DB_TYPE", "neo4j")
    monkeypatch.setenv("CGC_NEO4J_REL_WRITE_WORKERS", "25")
    monkeypatch.setenv("CGC_NEO4J_REL_WRITE_WORKERS_MAX", "12")
    assert writer._neo4j_rel_write_workers() == 12


def test_rel_write_workers_allows_single_worker_when_explicitly_set(monkeypatch):
    writer = GraphWriter(driver=None)
    monkeypatch.setenv("CGC_RUNTIME_DB_TYPE", "neo4j")
    monkeypatch.setenv("CGC_NEO4J_REL_WRITE_WORKERS", "1")
    monkeypatch.setenv("CGC_NEO4J_REL_WRITE_WORKERS_MAX", "12")
    assert writer._neo4j_rel_write_workers() == 1

