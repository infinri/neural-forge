import os

from fastapi.testclient import TestClient


def make_client_pg():
    os.environ.setdefault("MCP_TOKEN", "dev")
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://forge:forge@127.0.0.1:5432/neural_forge")
    from server.main import app  # import after env set
    return TestClient(app)


def test_get_governance_policies_validation_and_success():
    client = make_client_pg()
    H = {"Authorization": "Bearer dev"}

    # Missing projectId -> returns error envelope (200 with error)
    r = client.post("/tool/get_governance_policies", headers=H, json={"scopes": ["memory"]})
    assert r.status_code == 200
    body = r.json()
    assert "error" in body and body["error"]["code"] == "ERR.BAD_REQUEST"

    # Happy path
    r2 = client.post(
        "/tool/get_governance_policies",
        headers=H,
        json={"projectId": "nf_gov", "scopes": ["memory"]},
    )
    assert r2.status_code == 200
    body2 = r2.json()
    assert isinstance(body2["policies"], list)
    assert len(body2["policies"]) >= 1
    assert isinstance(body2["resolutionGraph"], dict)


def test_get_active_tokens_validation_and_success():
    client = make_client_pg()
    H = {"Authorization": "Bearer dev"}

    r = client.post("/tool/get_active_tokens", headers=H, json={"kinds": ["governance"]})
    assert r.status_code == 200
    assert r.json()["error"]["code"] == "ERR.BAD_REQUEST"

    r2 = client.post(
        "/tool/get_active_tokens",
        headers=H,
        json={"projectId": "nf_gov", "kinds": ["security"]},
    )
    assert r2.status_code == 200
    toks = r2.json()["tokens"]
    assert isinstance(toks, list)
    assert len(toks) >= 1


def test_get_rules_validation_and_success():
    client = make_client_pg()
    H = {"Authorization": "Bearer dev"}

    r = client.post("/tool/get_rules", headers=H, json={"scopes": ["memory"]})
    assert r.status_code == 200
    assert r.json()["error"]["code"] == "ERR.BAD_REQUEST"

    r2 = client.post(
        "/tool/get_rules",
        headers=H,
        json={"projectId": "nf_gov", "scopes": ["memory"]},
    )
    assert r2.status_code == 200
    rules = r2.json()["rules"]
    assert isinstance(rules, list)
    assert len(rules) >= 1
