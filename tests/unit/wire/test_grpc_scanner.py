"""Unit tests for wire.grpc_scanner (MULTI_REPO_LINKS PR #6)."""
from __future__ import annotations

from pathlib import Path

from codegraphcontext.wire import scan_repo_grpc


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_scan_empty_repo(tmp_path: Path):
    r = scan_repo_grpc(tmp_path)
    assert r.servers == [] and r.clients == []


def test_scan_finds_impl_base_server(tmp_path: Path):
    _write(tmp_path / "src/main/java/com/acme/Impl.java", """
        package com.acme;
        import io.grpc.stub.StreamObserver;
        public class OrdersServiceImpl extends OrdersServiceGrpc.OrdersServiceImplBase {
            public void createOrder(Req r, StreamObserver<Resp> o) {}
        }
    """)
    r = scan_repo_grpc(tmp_path)
    assert len(r.servers) == 1
    assert r.servers[0].service == "OrdersService"


def test_scan_skips_non_grpc_files(tmp_path: Path):
    _write(tmp_path / "src/main/java/com/acme/Plain.java", "package com.acme; class Plain {}")
    r = scan_repo_grpc(tmp_path)
    assert r.servers == []
    assert r.files_scanned == 1
