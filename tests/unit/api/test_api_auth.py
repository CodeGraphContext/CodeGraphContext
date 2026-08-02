"""Tests for optional API-key authentication on the HTTP API (issue #1008).

Covers the opt-in, backward-compatible design:

* When ``CGC_API_KEY`` is configured, protected router endpoints require the
  key via ``Authorization: Bearer <key>`` or ``X-API-Key`` and return 401
  otherwise.
* When no key is configured, endpoints stay open (backward compatible) and a
  prominent security warning is logged at startup.
* ``/health`` and ``/`` stay unauthenticated regardless of configuration.
"""

import logging

import pytest
from fastapi.testclient import TestClient

from codegraphcontext.api.app import create_app
from codegraphcontext.api.router import get_server

API_KEY = "s3cret-key-123"
PROTECTED_PATH = "/api/v1/repositories"


class FakeServer:
    """Minimal stand-in for MCPServer so protected endpoints can run."""

    async def handle_tool_call(self, name, arguments):
        return {"repositories": [], "tool": name}


@pytest.fixture
def client_factory(monkeypatch):
    """Build a TestClient whose get_server dependency is stubbed out.

    Callers pass the desired CGC_API_KEY (or None to leave it unset) so each
    test controls whether auth is active.
    """

    def _make(api_key):
        if api_key is None:
            monkeypatch.delenv("CGC_API_KEY", raising=False)
        else:
            monkeypatch.setenv("CGC_API_KEY", api_key)
        app = create_app()
        app.dependency_overrides[get_server] = lambda: FakeServer()
        return TestClient(app)

    return _make


# --- Key configured: auth is enforced ---------------------------------------

def test_missing_header_returns_401(client_factory):
    client = client_factory(API_KEY)
    response = client.get(PROTECTED_PATH)
    assert response.status_code == 401


def test_correct_bearer_header_returns_200(client_factory):
    client = client_factory(API_KEY)
    response = client.get(
        PROTECTED_PATH, headers={"Authorization": f"Bearer {API_KEY}"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_correct_x_api_key_header_returns_200(client_factory):
    client = client_factory(API_KEY)
    response = client.get(PROTECTED_PATH, headers={"X-API-Key": API_KEY})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_wrong_bearer_header_returns_401(client_factory):
    client = client_factory(API_KEY)
    response = client.get(
        PROTECTED_PATH, headers={"Authorization": "Bearer wrong-key"}
    )
    assert response.status_code == 401


def test_wrong_x_api_key_header_returns_401(client_factory):
    client = client_factory(API_KEY)
    response = client.get(PROTECTED_PATH, headers={"X-API-Key": "nope"})
    assert response.status_code == 401


def test_health_stays_open_when_key_configured(client_factory):
    client = client_factory(API_KEY)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_stays_open_when_key_configured(client_factory):
    client = client_factory(API_KEY)
    response = client.get("/")
    assert response.status_code == 200


# --- MCP-over-SSE transport is behind the same key --------------------------

# These routes dispatch to the same tools as the REST router (execute_cypher_query,
# add_code_to_graph, delete_repository), so leaving them off the authenticated
# router made CGC_API_KEY trivially bypassable.

def test_mcp_messages_requires_key(client_factory):
    client = client_factory(API_KEY)
    response = client.post("/api/v1/mcp/messages", json={"jsonrpc": "2.0", "id": 1})
    assert response.status_code == 401


def test_mcp_sse_requires_key(client_factory):
    client = client_factory(API_KEY)
    response = client.get("/api/v1/mcp/sse")
    assert response.status_code == 401


def test_mcp_messages_rejects_wrong_key(client_factory):
    client = client_factory(API_KEY)
    response = client.post(
        "/api/v1/mcp/messages",
        json={"jsonrpc": "2.0", "id": 1},
        headers={"X-API-Key": "nope"},
    )
    assert response.status_code == 401


def test_mcp_messages_open_when_no_key_configured(client_factory):
    # Backward compatible: without a configured key the transport stays open.
    client = client_factory(None)
    response = client.post("/api/v1/mcp/messages", json={"jsonrpc": "2.0", "id": 1})
    assert response.status_code != 401


# --- No key configured: backward compatible + warning -----------------------

def test_no_key_endpoint_works_without_header(client_factory):
    client = client_factory(None)
    response = client.get(PROTECTED_PATH)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_no_key_emits_startup_warning(monkeypatch, caplog):
    monkeypatch.delenv("CGC_API_KEY", raising=False)
    with caplog.at_level(logging.WARNING, logger="codegraphcontext.api.auth"):
        create_app()
    assert any(
        "without authentication" in record.getMessage().lower()
        for record in caplog.records
    ), "Expected a startup security warning when no API key is configured"


def test_key_configured_does_not_emit_warning(monkeypatch, caplog):
    monkeypatch.setenv("CGC_API_KEY", API_KEY)
    with caplog.at_level(logging.WARNING, logger="codegraphcontext.api.auth"):
        create_app()
    assert not any(
        "without authentication" in record.getMessage().lower()
        for record in caplog.records
    )
