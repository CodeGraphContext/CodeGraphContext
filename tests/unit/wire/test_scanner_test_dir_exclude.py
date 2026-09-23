"""MULTI_REPO_LINKS PR #9: verify Java scanners skip src/test/** by default.

Test files were the dominant source of noisy topic literals (e.g. Mockito's
``anyString()``) during a pre-flight smoke run on a large multi-service
codebase. The default exclude now filters them out; passing
``exclude_path_parts=()`` restores full scan.
"""
from __future__ import annotations

from pathlib import Path

from codegraphcontext.wire import (
    scan_repo_grpc,
    scan_repo_http,
    scan_repo_kafka,
)


def _w(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


PROD = """
    package com.a;
    import org.springframework.kafka.core.KafkaTemplate;
    class P { void x() { kafkaTemplate.send("prodTopic", p); } }
"""

TEST = """
    package com.a;
    import org.springframework.kafka.core.KafkaTemplate;
    class Ptest { void x() { kafkaTemplate.send("testTopic", p); } }
"""


def test_kafka_scanner_skips_src_test_by_default(tmp_path: Path):
    _w(tmp_path / "src/main/java/com/a/P.java", PROD)
    _w(tmp_path / "src/test/java/com/a/Ptest.java", TEST)

    r = scan_repo_kafka(tmp_path)
    topics = {p.topic_raw for p in r.producers}
    assert topics == {"prodTopic"}
    # Test file was seen (once, via the "." include dir), then skipped.
    assert r.files_skipped >= 1


def test_kafka_scanner_test_dir_included_when_exclude_empty(tmp_path: Path):
    _w(tmp_path / "src/main/java/com/a/P.java", PROD)
    _w(tmp_path / "src/test/java/com/a/Ptest.java", TEST)

    r = scan_repo_kafka(tmp_path, exclude_path_parts=())
    topics = {p.topic_raw for p in r.producers}
    assert topics == {"prodTopic", "testTopic"}


HTTP_SERVER_PROD = """
    package com.a;
    import org.springframework.web.bind.annotation.GetMapping;
    import org.springframework.web.bind.annotation.RestController;
    @RestController
    class C {
        @GetMapping("/prod") String getProd() { return "hi"; }
    }
"""

HTTP_SERVER_TEST = """
    package com.a;
    import org.springframework.web.bind.annotation.GetMapping;
    import org.springframework.web.bind.annotation.RestController;
    @RestController
    class Ctest {
        @GetMapping("/test") String getTest() { return "hi"; }
    }
"""


def test_http_scanner_skips_src_test_by_default(tmp_path: Path):
    _w(tmp_path / "src/main/java/com/a/C.java", HTTP_SERVER_PROD)
    _w(tmp_path / "src/test/java/com/a/Ctest.java", HTTP_SERVER_TEST)

    r = scan_repo_http(tmp_path)
    paths = {s.path for s in r.servers}
    assert paths == {"/prod"}


GRPC_SERVER_PROD = """
    package com.a;
    class OrdersImpl extends OrdersServiceGrpc.OrdersServiceImplBase {
        @Override
        public void createOrder(CreateOrderRequest req,
                                StreamObserver<CreateOrderResponse> resp) {}
    }
"""

GRPC_SERVER_TEST = """
    package com.a;
    class OrdersTestImpl extends OrdersServiceGrpc.OrdersServiceImplBase {
        @Override
        public void createOrderTest(CreateOrderRequest req,
                                    StreamObserver<CreateOrderResponse> resp) {}
    }
"""


def test_grpc_scanner_skips_src_test_by_default(tmp_path: Path):
    _w(tmp_path / "src/main/java/com/a/OrdersImpl.java", GRPC_SERVER_PROD)
    _w(tmp_path / "src/test/java/com/a/OrdersTestImpl.java", GRPC_SERVER_TEST)

    r = scan_repo_grpc(tmp_path)
    rpcs = {s.rpc for s in r.servers}
    # createOrder from prod source only; test override method excluded.
    assert "createOrder" in rpcs
    assert "createOrderTest" not in rpcs
