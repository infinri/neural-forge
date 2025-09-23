import os
import time

import pytest
from fastapi.testclient import TestClient

from server.governance.pre_action_engine import PreActionGovernanceEngine


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
    security_policy = next(p for p in body2["policies"] if p["tagSet"] == "SecurityPrinciples")
    assert "Security-first" in security_policy["description"]
    assert "security/ThreatModel" in security_policy["includes"]
    assert isinstance(security_policy.get("principles"), list)
    assert security_policy["principles"]


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
    rate_limit = next(t for t in toks if t["name"] == "RateLimitGuard")
    assert "safe API limits" in rate_limit["description"]
    assert isinstance(rate_limit["rules"], list)
    assert rate_limit["rules"]
    assert rate_limit["rules"] == rate_limit["bestPractices"]
    assert isinstance(rate_limit["linkedTags"], dict)
    assert "direct_links" in rate_limit["linkedTags"]
    assert isinstance(rate_limit["usage_metadata"], dict)
    assert "common_combinations" in rate_limit["usage_metadata"]


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
    security_rules = next(r for r in rules if r["tagSet"] == "SecurityPrinciples")
    assert "Security-first" in security_rules["description"]
    assert "security/ThreatModel" in security_rules["includes"]
    assert isinstance(security_rules.get("principles"), list)
    assert security_rules["principles"]
    assert security_rules.get("tokenBudget")


@pytest.mark.asyncio
async def test_pre_action_engine_loads_security_rules_from_tokens():
    engine = PreActionGovernanceEngine()
    security_rules = await engine._load_domain_rules("security")
    assert isinstance(security_rules, list)
    assert len(security_rules) > 1
    rate_limit_rule = next(r for r in security_rules if r["name"] == "RateLimitGuard")
    assert "safe API limits" in rate_limit_rule["description"]
    assert isinstance(rate_limit_rule["rules"], list)
    assert rate_limit_rule["rules"]
    assert rate_limit_rule.get("category") == "security"


@pytest.mark.asyncio
async def test_pre_action_engine_rule_cache_invalidation(tmp_path):
    tags_dir = tmp_path / "tags"
    security_dir = tags_dir / "security"
    security_dir.mkdir(parents=True)
    token_file = security_dir / "rate_limit.yaml"
    token_file.write_text("initial description", encoding="utf-8")

    loader_calls = 0

    def loader(project_id, kinds):
        nonlocal loader_calls
        loader_calls += 1
        tokens = []
        for kind in kinds:
            kind_dir = tags_dir / kind
            if not kind_dir.is_dir():
                continue
            for path in sorted(kind_dir.glob("*.yaml")):
                tokens.append(
                    {
                        "kind": kind,
                        "name": path.stem,
                        "description": path.read_text(encoding="utf-8"),
                        "rules": [f"rule::{path.stem}"],
                        "source": str(path),
                    }
                )
        return {"tokens": tokens}

    engine = PreActionGovernanceEngine(
        token_loader=loader,
        tags_dir=tags_dir,
        cache_ttl=3600,
    )

    first_rules = await engine._load_domain_rules("security")
    assert loader_calls == 1
    second_rules = await engine._load_domain_rules("security")
    assert loader_calls == 1
    assert second_rules == first_rules

    token_file.write_text("updated description", encoding="utf-8")
    ts = time.time() + 5
    os.utime(token_file, (ts, ts))

    refreshed_rules = await engine._load_domain_rules("security")
    assert loader_calls == 2
    assert any(rule["description"] == "updated description" for rule in refreshed_rules)
