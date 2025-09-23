import json
import os

from fastapi.testclient import TestClient
TOKEN = os.environ["MCP_TOKEN"]


def setup_env():
    os.environ["ENV"] = "dev"
    os.environ["MCP_TOKEN"] = TOKEN
    os.environ["ORCHESTRATOR_ENABLED"] = "true"


def test_rest_tool_ingest_event_publishes_and_returns_ok():
    setup_env()
    from server.core import bus
    from server.main import app

    with TestClient(app) as c:
        before = dict(bus.events_published_total)
        payload = {
            "type": "conversation.message",
            "projectId": "p1",
            "role": "User",
            "content": "hello via REST",
        }
        r = c.post(
            "/tool/ingest_event",
            headers={"Authorization": f"Bearer {TOKEN}"},
            json=payload,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["type"] == "conversation.message"
        assert data["projectId"] == "p1"
        assert data["serverVersion"]
        # requestId present
        assert isinstance(data.get("requestId"), str) and len(data["requestId"]) > 0
        # metrics increment
        after = dict(bus.events_published_total)
        assert after.get("conversation.message", 0) == before.get("conversation.message", 0) + 1


def test_mcp_tools_call_ingest_event_success():
    setup_env()
    from server.main import app
    with TestClient(app) as c:
        message = {
            "jsonrpc": "2.0",
            "id": 42,
            "method": "tools/call",
            "params": {
                "name": "ingest_event",
                "arguments": {
                    "type": "conversation.message",
                    "projectId": "p1",
                    "role": "assistant",
                    "content": "hello via MCP",
                },
            },
        }
        r = c.post("/sse", headers={"Authorization": f"Bearer {TOKEN}"}, json=message)
        assert r.status_code == 200
        data = r.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 42
        assert "result" in data and "content" in data["result"]
        content_blocks = data["result"]["content"]
        assert isinstance(content_blocks, list) and len(content_blocks) >= 1
        # parse the text JSON returned by handler
        text = content_blocks[0]["text"]
        parsed = json.loads(text)
        assert parsed["status"] == "ok"
        assert parsed["type"] == "conversation.message"
        assert parsed["projectId"] == "p1"
        assert isinstance(parsed.get("requestId"), str)
