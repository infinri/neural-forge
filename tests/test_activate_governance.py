import os

from fastapi.testclient import TestClient


def make_client():
    os.environ.setdefault("MCP_TOKEN", "dev")
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://forge:forge@127.0.0.1:5432/neural_forge",
    )
    from server.main import app  # Import after env configuration

    return TestClient(app)


def test_activate_governance_includes_request_id(monkeypatch):
    client = make_client()

    async def fake_activate_pre_action_governance(*, user_message, conversation_history=None, project_id=None):
        return "governance guidance"

    monkeypatch.setattr(
        "server.tools.activate_governance.activate_pre_action_governance",
        fake_activate_pre_action_governance,
    )

    response = client.post(
        "/tool/activate_governance",
        headers={"Authorization": "Bearer dev"},
        json={"user_message": "Let's plan a new feature"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["governance_activated"] is True
    assert "requestId" in payload
    assert isinstance(payload["requestId"], str)
    assert payload["requestId"]
