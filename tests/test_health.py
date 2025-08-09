import os

from fastapi.testclient import TestClient


def test_health_reports_running_when_enabled():
    os.environ["ENV"] = "dev"
    os.environ["MCP_TOKEN"] = "dev"
    os.environ["ORCHESTRATOR_ENABLED"] = "true"
    from server.core import orchestrator
    from server.main import app

    with TestClient(app) as c:
        r = c.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["serverVersion"]
        assert data["orchestratorRunning"] is True
    assert orchestrator.is_running is False


def test_health_reports_not_running_when_disabled():
    os.environ["ENV"] = "dev"
    os.environ["MCP_TOKEN"] = "dev"
    os.environ["ORCHESTRATOR_ENABLED"] = "false"
    from server.core import orchestrator
    from server.main import app

    with TestClient(app) as c:
        r = c.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["serverVersion"]
        assert data["orchestratorRunning"] is False
    assert orchestrator.is_running is False
