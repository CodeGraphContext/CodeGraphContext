"""Tests for API /health endpoint (BUG-008)."""

from fastapi.testclient import TestClient

from codegraphcontext.api.app import create_app


def test_health_endpoint_returns_ok():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
