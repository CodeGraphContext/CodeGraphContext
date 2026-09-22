"""Unit tests for wire.writer (MULTI_REPO_LINKS PR #9)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codegraphcontext.wire import (
    GrpcClientRecord,
    GrpcServerRecord,
    HttpClientRecord,
    HttpServerRecord,
    KafkaConsumerRecord,
    KafkaProducerRecord,
    WireWriteStats,
    write_wire_edges,
)
from codegraphcontext.wire.grpc_scanner import GrpcScanResult
from codegraphcontext.wire.http_scanner import HttpScanResult
from codegraphcontext.wire.kafka_scanner import KafkaScanResult


# ── Test doubles ────────────────────────────────────────────────────────────


class _FakeSession:
    def __init__(self, capture: list):
        self._capture = capture

    def __enter__(self): return self
    def __exit__(self, *args): return False

    def run(self, cypher, **params):
        self._capture.append({"cypher": cypher, "params": params})
        return MagicMock()


class _FakeDriver:
    """Minimal driver stub — GraphWriter uses .session()."""
    def __init__(self):
        self.calls: list = []

    def session(self, *args, **kwargs):
        return _FakeSession(self.calls)


class _FakeWriter:
    """Duck-types GraphWriter enough for write_wire_edges (driver + _db_manager)."""
    def __init__(self):
        self.driver = _FakeDriver()
        self._db_manager = None  # forces backend detection to 'neo4j' default


# ── Helpers ─────────────────────────────────────────────────────────────────


def _mk_kafka_producer(fqn: str, topic: str, confidence: str = "EXTRACTED", line: int = 10) -> KafkaProducerRecord:
    return KafkaProducerRecord(
        fqn=fqn, topic_raw=topic, topic_resolved=topic,
        confidence=confidence, provenance="literal",
        source_file="/x/A.java", line=line, call_shape="template.send",
    )


def _mk_kafka_consumer(fqn: str, topic: str, confidence: str = "EXTRACTED", line: int = 20) -> KafkaConsumerRecord:
    return KafkaConsumerRecord(
        fqn=fqn, topic_raw=topic, topic_resolved=topic,
        confidence=confidence, provenance="literal",
        source_file="/x/B.java", line=line, is_pattern=False,
    )


def _mk_http_server(fqn: str, method: str, path: str, confidence: str = "EXTRACTED") -> HttpServerRecord:
    return HttpServerRecord(
        fqn=fqn, method=method, path=path, path_raw=path,
        confidence=confidence, provenance="literal",
        source_file="/x/S.java", line=1, framework="spring",
    )


def _mk_http_client(fqn: str, method: str, path: str, confidence: str = "EXTRACTED") -> HttpClientRecord:
    return HttpClientRecord(
        fqn=fqn, method=method, path=path, path_raw=path,
        confidence=confidence, provenance="literal",
        source_file="/x/C.java", line=1, framework="restTemplate",
    )


def _mk_grpc_server(fqn: str, service: str, rpc: str) -> GrpcServerRecord:
    return GrpcServerRecord(
        fqn=fqn, service=service, rpc=rpc, path=f"{service}/{rpc}",
        confidence="EXTRACTED", provenance="grpc:impl",
        source_file="/x/GrpcS.java", line=1,
    )


def _mk_grpc_client(fqn: str, service: str, rpc: str) -> GrpcClientRecord:
    return GrpcClientRecord(
        fqn=fqn, service=service, rpc=rpc, path=f"{service}/{rpc}",
        confidence="EXTRACTED", provenance="grpc:stub",
        source_file="/x/GrpcC.java", line=1, stub_kind="blockingStub",
    )


# ── Tests ───────────────────────────────────────────────────────────────────


def test_empty_scans_write_nothing():
    writer = _FakeWriter()
    stats = write_wire_edges(writer)  # all None
    assert isinstance(stats, WireWriteStats)
    assert stats.topics_merged == 0
    assert stats.produces_edges == 0
    assert writer.driver.calls == []


def test_kafka_producer_writes_topic_and_edge():
    writer = _FakeWriter()
    scan = KafkaScanResult(producers=[_mk_kafka_producer("com.a.Svc.publish", "orders")])
    stats = write_wire_edges(writer, kafka_scan=scan)
    assert stats.topics_merged == 1
    assert stats.produces_edges == 1
    assert stats.consumes_edges == 0

    cypher_texts = [c["cypher"] for c in writer.driver.calls]
    assert any("MERGE (t:Topic" in c for c in cypher_texts)
    assert any(":PRODUCES_TO" in c for c in cypher_texts)

    edge_call = next(c for c in writer.driver.calls if ":PRODUCES_TO" in c["cypher"])
    rows = edge_call["params"]["rows"]
    assert rows[0]["method_name"] == "publish"
    assert rows[0]["topic_name"] == "orders"
    assert rows[0]["match_confidence"] == "EXTRACTED"


def test_kafka_consumer_writes_topic_and_edge():
    writer = _FakeWriter()
    scan = KafkaScanResult(consumers=[_mk_kafka_consumer("com.a.Cons.on", "orders")])
    stats = write_wire_edges(writer, kafka_scan=scan)
    assert stats.consumes_edges == 1

    consumes_calls = [c for c in writer.driver.calls if ":CONSUMES_FROM" in c["cypher"]]
    assert len(consumes_calls) == 1
    assert consumes_calls[0]["params"]["rows"][0]["topic_name"] == "orders"


def test_ambiguous_records_skipped_by_default():
    writer = _FakeWriter()
    scan = KafkaScanResult(producers=[
        _mk_kafka_producer("com.a.Svc.publish", "topicVar", confidence="AMBIGUOUS"),
        _mk_kafka_producer("com.a.Svc.publish2", "orders"),  # EXTRACTED
    ])
    stats = write_wire_edges(writer, kafka_scan=scan)
    assert stats.produces_edges == 1
    assert stats.skipped_ambiguous == 1


def test_ambiguous_records_written_when_include_flag_set():
    writer = _FakeWriter()
    scan = KafkaScanResult(producers=[
        _mk_kafka_producer("com.a.Svc.publish", "topicVar", confidence="AMBIGUOUS"),
    ])
    stats = write_wire_edges(writer, kafka_scan=scan, include_ambiguous=True)
    assert stats.produces_edges == 1
    assert stats.skipped_ambiguous == 0


def test_bad_fqn_dropped():
    writer = _FakeWriter()
    scan = KafkaScanResult(producers=[
        # fqn without a trailing identifier — cannot pick method name
        _mk_kafka_producer("com.a.$$$", "orders"),
    ])
    stats = write_wire_edges(writer, kafka_scan=scan)
    assert stats.produces_edges == 0
    assert stats.dropped_bad_fqn == 1


def test_http_server_and_client_write_serves_and_invokes():
    writer = _FakeWriter()
    scan = HttpScanResult(
        servers=[_mk_http_server("com.a.Ctrl.getOne", "GET", "/v1/players/{id}")],
        clients=[_mk_http_client("com.b.Sync.fetch", "GET", "/v1/players/{id}")],
    )
    stats = write_wire_edges(writer, http_scan=scan)
    assert stats.serves_edges == 1
    assert stats.invokes_edges == 1
    assert stats.endpoints_merged == 1  # dedup'd

    cypher_texts = [c["cypher"] for c in writer.driver.calls]
    assert any(":SERVES" in c for c in cypher_texts)
    assert any(":INVOKES" in c for c in cypher_texts)


def test_grpc_server_and_client_write_serves_and_invokes():
    writer = _FakeWriter()
    scan = GrpcScanResult(
        servers=[_mk_grpc_server("com.a.OrdersImpl.createOrder", "OrdersService", "CreateOrder")],
        clients=[_mk_grpc_client("com.b.Caller.doIt", "OrdersService", "CreateOrder")],
    )
    stats = write_wire_edges(writer, grpc_scan=scan)
    assert stats.serves_edges == 1
    assert stats.invokes_edges == 1
    assert stats.endpoints_merged == 1

    edge_calls = [c for c in writer.driver.calls if ":SERVES" in c["cypher"]]
    row = edge_calls[0]["params"]["rows"][0]
    assert row["protocol"] == "grpc"
    assert row["endpoint_method"] == "CreateOrder"
    assert row["endpoint_path"] == "OrdersService/CreateOrder"


def test_producer_and_consumer_dedup_topic_merge():
    writer = _FakeWriter()
    scan = KafkaScanResult(
        producers=[_mk_kafka_producer("com.a.Svc.publish", "orders")],
        consumers=[_mk_kafka_consumer("com.a.Cons.on", "orders")],
    )
    stats = write_wire_edges(writer, kafka_scan=scan)
    # Both edges reference same topic — merged as ONE Topic node row batch
    topic_calls = [c for c in writer.driver.calls if "MERGE (t:Topic" in c["cypher"] and "MATCH" not in c["cypher"]]
    assert len(topic_calls) == 1
    assert len(topic_calls[0]["params"]["rows"]) == 1
    assert stats.topics_merged == 1
