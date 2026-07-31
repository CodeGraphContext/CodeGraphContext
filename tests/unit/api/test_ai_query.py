import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from codegraphcontext.viz.server import app, set_db_manager

client = TestClient(app)

def test_ai_query_no_api_keys(monkeypatch):
    # Ensure no supported provider key is in env
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ATLASCLOUD_API_KEY", raising=False)
    monkeypatch.delenv("ATLAS_CLOUD_API_KEY", raising=False)
    
    # Mock db_manager
    mock_db = MagicMock()
    set_db_manager(mock_db)
    
    response = client.post("/api/ai_query", json={"query": "test query"})
    
    assert response.status_code == 400
    assert "AI querying requires" in response.json()["detail"]


@patch("codegraphcontext.viz.server.requests.post")
def test_call_llm_with_atlascloud(mock_post, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ATLASCLOUD_API_KEY", "fake-atlas-key")
    monkeypatch.setenv("ATLASCLOUD_API_BASE", "https://api.atlascloud.ai/v1/")
    monkeypatch.setenv("ATLASCLOUD_MODEL", "qwen/qwen3.5-flash")

    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "choices": [{"message": {"content": "MATCH (n) RETURN n"}}]
    }

    from codegraphcontext.viz.server import call_llm

    result = call_llm("system prompt", "user prompt")

    assert result == "MATCH (n) RETURN n"
    mock_post.assert_called_once_with(
        "https://api.atlascloud.ai/v1/chat/completions",
        json={
            "model": "qwen/qwen3.5-flash",
            "messages": [
                {"role": "system", "content": "system prompt"},
                {"role": "user", "content": "user prompt"},
            ],
        },
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer fake-atlas-key",
        },
        timeout=30,
    )


@patch("codegraphcontext.viz.server.requests.post")
def test_call_llm_with_atlas_cloud_alias_defaults(mock_post, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ATLASCLOUD_API_KEY", raising=False)
    monkeypatch.delenv("ATLASCLOUD_API_BASE", raising=False)
    monkeypatch.delenv("ATLASCLOUD_MODEL", raising=False)
    monkeypatch.setenv("ATLAS_CLOUD_API_KEY", "fake-atlas-key")

    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "choices": [{"message": {"content": "default response"}}]
    }

    from codegraphcontext.viz.server import call_llm

    assert call_llm("system", "user") == "default response"
    _, kwargs = mock_post.call_args
    assert mock_post.call_args.args[0] == "https://api.atlascloud.ai/v1/chat/completions"
    assert kwargs["json"]["model"] == "deepseek-ai/deepseek-v4-pro"


@patch("codegraphcontext.viz.server.call_llm")
def test_ai_query_success(mock_call_llm, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    
    mock_call_llm.side_effect = [
        '{"cypher_query": "MATCH (n) RETURN n", "explanation": "translating test"}',
        "This is the explanation of the results."
    ]
    
    mock_db = MagicMock()
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_result = MagicMock()
    
    mock_record = MagicMock()
    mock_node_dict = {"_label": "Class", "name": "TestClass", "path": "/path/to/test"}
    mock_record.values.return_value = [mock_node_dict]
    mock_record.items.return_value = [("n", mock_node_dict)]
    mock_record.get.return_value = mock_node_dict
    
    mock_result.__iter__.return_value = [mock_record]
    
    mock_session.run.return_value = mock_result
    mock_driver.session.return_value.__enter__.return_value = mock_session
    mock_db.get_driver.return_value = mock_driver
    set_db_manager(mock_db)
    
    response = client.post("/api/ai_query", json={"query": "test query"})
    
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["success"] is True
    assert res_data["cypher_query"] == "MATCH (n) RETURN n"
    assert res_data["explanation"] == "This is the explanation of the results."
    assert len(res_data["nodes"]) > 0
    assert res_data["nodes"][0]["name"] == "TestClass"
