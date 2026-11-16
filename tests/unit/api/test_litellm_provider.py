import os
import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from codegraphcontext.viz import server

PROVIDER_ENV = (
    "LITELLM_MODEL",
    "LITELLM_API_BASE",
    "GEMINI_API_KEY",
    "OPENAI_API_KEY",
    "ATLASCLOUD_API_KEY",
    "ATLAS_CLOUD_API_KEY",
    "CHEAPER_INFERENCE_API_KEY",
    "API_ROUTE_API_KEY",
)


def _completion(content):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


@pytest.fixture(autouse=True)
def isolated_provider_keys(monkeypatch):
    for key in PROVIDER_ENV:
        monkeypatch.delenv(key, raising=False)
    # Register LITELLM_MODE with monkeypatch so the setdefault in the provider
    # is rolled back after each test.
    monkeypatch.setenv("LITELLM_MODE", "PRODUCTION")


@pytest.fixture
def fake_litellm(monkeypatch):
    module = types.ModuleType("litellm")
    module.completion = MagicMock(return_value=_completion("MATCH (n) RETURN n"))
    monkeypatch.setitem(sys.modules, "litellm", module)
    return module


def test_litellm_model_routes_through_litellm_completion(monkeypatch, fake_litellm):
    monkeypatch.setenv("LITELLM_MODEL", "anthropic/claude-sonnet-4-6")

    assert server.call_llm("system prompt", "user prompt") == "MATCH (n) RETURN n"

    fake_litellm.completion.assert_called_once_with(
        model="anthropic/claude-sonnet-4-6",
        messages=[
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "user prompt"},
        ],
        timeout=30,
        drop_params=True,
    )


def test_litellm_model_wins_over_exported_provider_keys(monkeypatch, fake_litellm):
    monkeypatch.setenv("LITELLM_MODEL", "bedrock/anthropic.claude-sonnet-4-6")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-not-be-used")
    monkeypatch.setenv("GEMINI_API_KEY", "should-not-be-used")
    post = MagicMock()
    monkeypatch.setattr(server.requests, "post", post)

    server.call_llm("system", "user")

    post.assert_not_called()
    assert fake_litellm.completion.call_args.kwargs["model"] == "bedrock/anthropic.claude-sonnet-4-6"


def test_litellm_api_base_is_forwarded_when_set(monkeypatch, fake_litellm):
    monkeypatch.setenv("LITELLM_MODEL", "ollama/llama3")
    monkeypatch.setenv("LITELLM_API_BASE", "http://localhost:11434/")

    server.call_llm("system", "user")

    kwargs = fake_litellm.completion.call_args.kwargs
    assert kwargs["api_base"] == "http://localhost:11434"
    assert "api_key" not in kwargs


def test_litellm_does_not_load_dotenv_on_import(monkeypatch, fake_litellm):
    monkeypatch.delenv("LITELLM_MODE")
    monkeypatch.setenv("LITELLM_MODEL", "anthropic/claude-sonnet-4-6")

    server.call_llm("system", "user")

    assert os.environ["LITELLM_MODE"] == "PRODUCTION"


def test_blank_litellm_model_keeps_existing_provider_chain(monkeypatch, fake_litellm):
    monkeypatch.setenv("LITELLM_MODEL", "   ")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    post = MagicMock()
    post.return_value.status_code = 200
    post.return_value.json.return_value = {"choices": [{"message": {"content": "from openai"}}]}
    monkeypatch.setattr(server.requests, "post", post)

    assert server.call_llm("system", "user") == "from openai"
    assert post.call_args.args[0] == "https://api.openai.com/v1/chat/completions"
    fake_litellm.completion.assert_not_called()


def test_missing_litellm_package_names_the_extra(monkeypatch):
    monkeypatch.setenv("LITELLM_MODEL", "anthropic/claude-sonnet-4-6")
    monkeypatch.setitem(sys.modules, "litellm", None)

    with pytest.raises(RuntimeError, match=r"codegraphcontext\[litellm\]"):
        server.call_llm("system", "user")


def test_provider_error_is_wrapped_with_model_name(monkeypatch, fake_litellm):
    monkeypatch.setenv("LITELLM_MODEL", "anthropic/claude-sonnet-4-6")
    upstream = ValueError("AuthenticationError: invalid x-api-key")
    fake_litellm.completion.side_effect = upstream

    with pytest.raises(RuntimeError, match=r"LiteLLM \(anthropic/claude-sonnet-4-6\) API returned error") as exc:
        server.call_llm("system", "user")
    assert exc.value.__cause__ is upstream


def test_empty_completion_is_an_error(monkeypatch, fake_litellm):
    monkeypatch.setenv("LITELLM_MODEL", "ollama/llama3")
    fake_litellm.completion.return_value = _completion(None)

    with pytest.raises(RuntimeError, match="empty response"):
        server.call_llm("system", "user")


def test_ai_query_accepts_litellm_model_as_its_only_provider(monkeypatch):
    monkeypatch.setenv("LITELLM_MODEL", "anthropic/claude-sonnet-4-6")
    monkeypatch.setattr(server, "call_llm", MagicMock(side_effect=RuntimeError("reached the LLM")))
    server.set_db_manager(MagicMock())

    response = TestClient(server.app).post("/api/ai_query", json={"query": "who calls main?"})

    # Past the "requires an API key" 400: the request reached call_llm.
    assert response.status_code == 500
    assert response.json()["detail"] == "reached the LLM"


def test_ai_query_error_lists_litellm_model_when_nothing_is_configured():
    server.set_db_manager(MagicMock())

    response = TestClient(server.app).post("/api/ai_query", json={"query": "who calls main?"})

    assert response.status_code == 400
    assert "LITELLM_MODEL" in response.json()["detail"]
