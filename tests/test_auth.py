import os

import pytest
from fastapi.testclient import TestClient

# Ensure predictable token for auth
os.environ.setdefault("MCP_TOKEN", "dev")

from server.main import app  # noqa: E402  # import after env is set


@pytest.fixture()
def client():
    return TestClient(app)


def test_authorization_header_required(client, monkeypatch):
    monkeypatch.delenv("MCP_ALLOW_QUERY_TOKEN", raising=False)

    # Missing header should be unauthorized
    r_missing = client.get("/get_capabilities")
    assert r_missing.status_code == 401

    # Query parameter must not work by default
    r_query = client.get("/get_capabilities", params={"token": "dev"})
    assert r_query.status_code == 401

    # Proper Authorization header unlocks access
    r_header = client.get("/get_capabilities", headers={"Authorization": "Bearer dev"})
    assert r_header.status_code == 200
    data = r_header.json()
    assert data["serverVersion"].startswith("1.")


def test_query_token_opt_in(client, monkeypatch):
    monkeypatch.setenv("MCP_ALLOW_QUERY_TOKEN", "true")

    r = client.get("/get_capabilities", params={"token": "dev"})
    assert r.status_code == 200
    assert r.json()["serverVersion"].startswith("1.")
