"""Unit tests for wire.grpc_extractor (MULTI_REPO_LINKS PR #6)."""
from __future__ import annotations

from pathlib import Path

from codegraphcontext.wire import extract_grpc_from_source, looks_like_grpc_source


P = Path("Svc.java")


def _extract(src: str):
    return extract_grpc_from_source(src, P)


def test_looks_like_triggers_on_implbase():
    assert looks_like_grpc_source("class X extends OrdersServiceGrpc.OrdersServiceImplBase {}")
    assert looks_like_grpc_source("var s = OrdersServiceGrpc.newBlockingStub(chan);")
    assert not looks_like_grpc_source("class Plain {}")


def test_impl_base_class_emits_server_records_for_public_rpcs():
    src = """
        package com.acme;
        import io.grpc.stub.StreamObserver;
        public class OrdersServiceImpl extends OrdersServiceGrpc.OrdersServiceImplBase {
            @Override
            public void createOrder(CreateReq req, StreamObserver<CreateResp> resp) { resp.onCompleted(); }
            @Override
            public void getOrder(GetReq req, StreamObserver<GetResp> resp) { resp.onCompleted(); }
        }
    """
    r = _extract(src)
    rpcs = {s.rpc for s in r.servers}
    assert rpcs == {"createOrder", "getOrder"}
    assert all(s.service == "OrdersService" for s in r.servers)
    assert all(s.path.startswith("OrdersService/") for s in r.servers)
    assert r.servers[0].confidence == "EXTRACTED"
    assert r.servers[0].fqn == "com.acme.OrdersServiceImpl.createOrder"


def test_inline_stub_call_emits_client():
    src = """
        package com.acme;
        class C {
            void call() { OrdersServiceGrpc.newBlockingStub(chan).createOrder(req); }
        }
    """
    r = _extract(src)
    assert len(r.clients) == 1
    c = r.clients[0]
    assert c.service == "OrdersService"
    assert c.rpc == "createOrder"
    assert c.path == "OrdersService/createOrder"
    assert c.stub_kind == "blockingStub"
    assert c.fqn == "com.acme.C.call"


def test_variable_stub_binding_emits_client_for_each_rpc_call():
    src = """
        package com.acme;
        class C {
            OrdersServiceGrpc.OrdersServiceBlockingStub stub = OrdersServiceGrpc.newBlockingStub(chan);
            void a() { stub.createOrder(req); }
            void b() { stub.getOrder(req); }
        }
    """
    r = _extract(src)
    rpcs = {(c.rpc, c.fqn) for c in r.clients}
    assert ("createOrder", "com.acme.C.a") in rpcs
    assert ("getOrder", "com.acme.C.b") in rpcs
    assert all(c.stub_kind == "blockingStub" for c in r.clients)


def test_var_style_stub_binding_is_recognized():
    src = """
        package com.acme;
        class C {
            void call() {
                var stub = OrdersServiceGrpc.newBlockingStub(chan);
                stub.createOrder(req);
            }
        }
    """
    r = _extract(src)
    # var-style bindings are lexically scoped inside call() so the match should still resolve.
    assert any(c.rpc == "createOrder" and c.service == "OrdersService" for c in r.clients)


def test_non_grpc_source_yields_empty_result():
    r = _extract("package p; class X {}")
    assert r.is_empty()


def test_newStub_and_newFutureStub_stub_kinds_are_reported():
    src = """
        package com.acme;
        class C {
            void a() { OrdersServiceGrpc.newStub(chan).createOrder(req, obs); }
            void b() { OrdersServiceGrpc.newFutureStub(chan).createOrder(req); }
        }
    """
    r = _extract(src)
    kinds = {c.stub_kind for c in r.clients}
    assert "Stub" in kinds  # newStub -> Stub
    assert "futureStub" in kinds


def test_multiple_impl_classes_in_same_file():
    src = """
        package com.acme;
        import io.grpc.stub.StreamObserver;
        public class A extends OrdersServiceGrpc.OrdersServiceImplBase {
            public void createOrder(Req r, StreamObserver<Resp> o) {}
        }
        public class B extends PaymentServiceGrpc.PaymentServiceImplBase {
            public void charge(Req r, StreamObserver<Resp> o) {}
        }
    """
    r = _extract(src)
    svcs = {(s.service, s.rpc) for s in r.servers}
    assert ("OrdersService", "createOrder") in svcs
    assert ("PaymentService", "charge") in svcs
