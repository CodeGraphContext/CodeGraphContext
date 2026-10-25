from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from codegraphcontext.viz import server


@pytest.fixture(autouse=True)
def isolated_provider_keys(monkeypatch):
    for key in (
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "ATLASCLOUD_API_KEY",
        "ATLAS_CLOUD_API_KEY",
        "CHEAPER_INFERENCE_API_KEY",
        "API_ROUTE_API_KEY",
        "API_ROUTE_API_BASE",
        "API_ROUTE_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("API_ROUTE_API_KEY", "test-api-route-key")


@pytest.mark.parametrize(
    "base_url,model,expected_url,expected_model",
    [
        (None, None, "https://global.api-route.com/v1/chat/completions", "gpt-6.1-sol"),
        (
            "https://gateway.example/v1/",
            "account-model",
            "https://gateway.example/v1/chat/completions",
            "account-model",
        ),
    ],
)
def test_api_route_returns_completion_with_configured_connection(
    monkeypatch, base_url, model, expected_url, expected_model
):
    if base_url:
        monkeypatch.setenv("API_ROUTE_API_BASE", base_url)
    if model:
        monkeypatch.setenv("API_ROUTE_MODEL", model)
    post = MagicMock()
    post.return_value.status_code = 200
    post.return_value.json.return_value = {"choices": [{"message": {"content": "MATCH (n) RETURN n"}}]}
    monkeypatch.setattr(server.requests, "post", post)

    assert server.call_llm("system prompt", "user prompt") == "MATCH (n) RETURN n"
    assert post.call_args.args == (expected_url,)
    assert post.call_args.kwargs == {
        "json": {
            "model": expected_model,
            "messages": [
                {"role": "system", "content": "system prompt"},
                {"role": "user", "content": "user prompt"},
            ],
        },
        "headers": {"Content-Type": "application/json", "Authorization": "Bearer test-api-route-key"},
        "timeout": 30,
    }


@pytest.mark.parametrize(
    "key,expected_host",
    [
        ("GEMINI_API_KEY", "generativelanguage.googleapis.com"),
        ("OPENAI_API_KEY", "api.openai.com"),
        ("ATLASCLOUD_API_KEY", "api.atlascloud.ai"),
        ("ATLAS_CLOUD_API_KEY", "api.atlascloud.ai"),
        ("CHEAPER_INFERENCE_API_KEY", "api.cheaperinference.com"),
    ],
)
def test_existing_providers_keep_priority_over_api_route(monkeypatch, key, expected_host):
    monkeypatch.setenv(key, "existing-provider-key")
    post = MagicMock()
    post.return_value.status_code = 200
    post.return_value.json.return_value = {
        "choices": [{"message": {"content": "existing provider"}}],
        "candidates": [{"content": {"parts": [{"text": "existing provider"}]}}],
    }
    monkeypatch.setattr(server.requests, "post", post)

    assert server.call_llm("system", "user") == "existing provider"
    assert expected_host in post.call_args.args[0]


def test_api_route_http_error_identifies_the_provider(monkeypatch):
    post = MagicMock()
    post.return_value.status_code = 401
    post.return_value.text = "Unauthorized"
    monkeypatch.setattr(server.requests, "post", post)

    with pytest.raises(RuntimeError, match="API Route API returned error 401"):
        server.call_llm("system", "user")


def test_missing_key_error_mentions_api_route(monkeypatch):
    monkeypatch.delenv("API_ROUTE_API_KEY")
    with pytest.raises(ValueError, match="API_ROUTE_API_KEY"):
        server.call_llm("system", "user")


def test_ai_query_accepts_api_route_and_returns_graph_results(monkeypatch):
    post = MagicMock()
    post.return_value.status_code = 200
    post.return_value.json.side_effect = [
        {"choices": [{"message": {"content": '{"cypher_query":"MATCH (n) RETURN n","explanation":"Find nodes"}'}}]},
        {"choices": [{"message": {"content": "Found TestClass."}}]},
    ]
    monkeypatch.setattr(server.requests, "post", post)
    node = {"_label": "Class", "name": "TestClass", "path": "/project/test.py"}
    record = MagicMock()
    record.items.return_value = [("n", node)]
    record.values.return_value = [node]
    database = MagicMock()
    database.get_driver.return_value.session.return_value.__enter__.return_value.run.return_value = [record]
    monkeypatch.setattr(server, "db_manager", database)

    response = TestClient(server.app).post("/api/ai_query", json={"query": "Show classes"})

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    assert result["nodes"][0]["name"] == "TestClass"
    assert result["explanation"] == "Found TestClass."
    assert post.call_count == 2
    assert all(call.args[0] == "https://global.api-route.com/v1/chat/completions" for call in post.call_args_list)
