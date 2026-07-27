import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from codegraphcontext.viz.server import app, set_db_manager

client = TestClient(app)

def test_ai_query_no_api_keys(monkeypatch):
    # Ensure neither key is in env
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    
    # Mock db_manager
    mock_db = MagicMock()
    set_db_manager(mock_db)
    
    response = client.post("/api/ai_query", json={"query": "test query"})
    
    assert response.status_code == 400
    assert "AI querying requires" in response.json()["detail"]


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
