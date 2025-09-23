import os

from fastapi.testclient import TestClient


TOKEN = os.environ["MCP_TOKEN"]


def test_orchestrator_starts_and_stops():
    # Ensure env before importing app
    os.environ["ENV"] = "dev"
    os.environ["MCP_TOKEN"] = TOKEN
    os.environ["ORCHESTRATOR_ENABLED"] = "true"

    from server.core import orchestrator  # singleton
    from server.main import app

    assert orchestrator.is_running is False
    with TestClient(app) as client:
        # Startup hook should have started orchestrator
        assert orchestrator.is_running is True
        # Make a simple authed call to ensure app works
        r = client.get("/get_capabilities", headers={"Authorization": f"Bearer {TOKEN}"})
        assert r.status_code == 200
    # Shutdown hook should have stopped orchestrator
    assert orchestrator.is_running is False


def test_orchestrator_respects_disabled_flag():
    os.environ["ENV"] = "dev"
    os.environ["MCP_TOKEN"] = TOKEN
    os.environ["ORCHESTRATOR_ENABLED"] = "false"

    from server.core import orchestrator
    from server.main import app

    assert orchestrator.is_running is False
    with TestClient(app) as client:
        assert orchestrator.is_running is False
        r = client.get("/get_capabilities", headers={"Authorization": f"Bearer {TOKEN}"})
        assert r.status_code == 200
    assert orchestrator.is_running is False
