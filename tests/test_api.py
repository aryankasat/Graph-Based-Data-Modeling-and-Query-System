from unittest.mock import patch, MagicMock
import json
import pytest

def test_read_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

@patch("backend.graph_builder.get_graph_json")
def test_get_graph_success(mock_get_graph, client):
    mock_data = {"nodes": [], "links": []}
    mock_get_graph.return_value = mock_data
    
    response = client.get("/api/graph")
    assert response.status_code == 200
    assert response.json() == mock_data

@patch("backend.graph_builder.get_graph_json")
def test_get_graph_failure(mock_get_graph, client):
    mock_get_graph.side_effect = Exception("DB Error")
    
    response = client.get("/api/graph")
    assert response.status_code == 500
    assert response.json()["detail"] == "DB Error"

def test_chat_no_llm(client):
    with patch("main.groq_client", None):
        response = client.post("/api/chat", json={"query": "test"})
        assert response.status_code == 500
        assert "LLM not configured" in response.json()["detail"]

def test_chat_no_db(client):
    with patch("main.groq_client", MagicMock()), patch("main.kuzu_db", None):
        response = client.post("/api/chat", json={"query": "test"})
        assert response.status_code == 500
        assert "Kùzu Database not initialized" in response.json()["detail"]
