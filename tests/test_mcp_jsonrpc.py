import os

from fastapi.testclient import TestClient


TOKEN = os.environ["MCP_TOKEN"]


def _client():
    os.environ["ENV"] = "dev"
    os.environ["MCP_TOKEN"] = TOKEN
    from server.main import app
    return TestClient(app)


def test_initialize_envelope():
    with _client() as c:
        r = c.post("/sse", headers={"Authorization": f"Bearer {TOKEN}"}, json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {}
        })
        assert r.status_code == 200
        data = r.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert "result" in data
        assert "serverInfo" in data["result"]


def test_tools_list_envelope_contains_known_tools():
    with _client() as c:
        r = c.post("/sse", headers={"Authorization": f"Bearer {TOKEN}"}, json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        })
        assert r.status_code == 200
        data = r.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 2
        assert "result" in data
        tools = data["result"]["tools"]
        # Expect at least one known tool present in the list
        assert any(t["name"] == "add_memory" for t in tools)
