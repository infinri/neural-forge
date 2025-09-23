import os

import psycopg
import pytest
from fastapi.testclient import TestClient

# Ensure env before importing app
os.environ.setdefault("MCP_TOKEN", "test-token")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://forge:forge@127.0.0.1:5432/neural_forge")

TOKEN = os.environ["MCP_TOKEN"]


def _sync_dsn() -> str:
    url = os.environ["DATABASE_URL"]
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if url.startswith("postgresql+psycopg://"):
        url = url.replace("postgresql+psycopg://", "postgresql://", 1)
    return url


try:
    with psycopg.connect(_sync_dsn()):
        pass
except psycopg.OperationalError:
    pytest.skip("Postgres is required for E2E API tests", allow_module_level=True)


def make_client_pg():
    from server.main import app  # import after env set
    return TestClient(app)


def test_capabilities_and_auth():
    client = make_client_pg()

    # Missing auth
    r = client.get("/get_capabilities")
    assert r.status_code == 401

    # With auth
    r = client.get("/get_capabilities", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200
    data = r.json()
    assert data["serverVersion"].startswith("1.")
    assert "add_memory" in data["tools"]


def test_memory_lifecycle():
    client = make_client_pg()
    H = {"Authorization": f"Bearer {TOKEN}"}

    project = "nf_e2e"
    # add_memory
    add = client.post(
        "/tool/add_memory",
        headers=H,
        json={"projectId": project, "content": "hello alpha", "metadata": {"tags": ["alpha"]}},
    )
    if add.status_code != 200:
        print("add_memory failed:", add.text)
    assert add.status_code == 200
    mid = add.json()["id"]

    # get_memory
    got = client.post("/tool/get_memory", headers=H, json={"id": mid})
    assert got.status_code == 200
    j = got.json()
    item = j["item"]
    assert item["id"] == mid
    assert item["projectId"] == project
    assert item["quarantined"] is False

    # search_memory
    srch = client.post(
        "/tool/search_memory", headers=H, json={"projectId": project, "query": "alpha", "limit": 5}
    )
    if srch.status_code != 200:
        print("search_memory failed:", srch.text)
    assert srch.status_code == 200
    items = srch.json()["items"]
    assert any(it["id"] == mid for it in items)


def test_task_and_diff_and_logging():
    client = make_client_pg()
    H = {"Authorization": f"Bearer {TOKEN}"}

    project = "nf_e2e"
    # enqueue_task
    enq = client.post(
        "/tool/enqueue_task",
        headers=H,
        json={"projectId": project, "payload": {"kind": "plan", "note": "unit"}},
    )
    if enq.status_code != 200:
        print("enqueue_task failed:", enq.text)
    assert enq.status_code == 200

    # get_next_task
    nxt = client.post("/tool/get_next_task", headers=H, json={"projectId": project})
    if nxt.status_code != 200:
        print("get_next_task failed:", nxt.text)
    assert nxt.status_code == 200
    task = nxt.json().get("task")
    assert task and task["status"] == "in_progress"
    tid = task["id"]

    # update_task_status
    upd = client.post(
        "/tool/update_task_status",
        headers=H,
        json={"id": tid, "status": "done", "result": {"ok": True}},
    )
    assert upd.status_code == 200
    assert upd.json()["status"] == "done"

    # save_diff
    sd = client.post(
        "/tool/save_diff",
        headers=H,
        json={
            "projectId": project,
            "filePath": "server/main.py",
            "diff": "--- a\n+++ b\n@@\n+unit\n",
            "author": "test",
        },
    )
    assert sd.status_code == 200

    # list_recent
    lr = client.post(
        "/tool/list_recent", headers=H, json={"projectId": project, "limit": 5}
    )
    assert lr.status_code == 200
    assert lr.json()["count"] >= 1

    # log_error
    le = client.post(
        "/tool/log_error",
        headers=H,
        json={"level": "info", "message": "unit done", "projectId": project},
    )
    assert le.status_code == 200
    assert le.json()["level"] == "info"
