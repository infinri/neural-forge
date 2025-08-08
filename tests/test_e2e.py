import os
import sqlite3
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

# Ensure env before importing app
os.environ.setdefault("MCP_TOKEN", "dev")

def init_db(db_path: str):
    schema_path = Path(__file__).resolve().parents[1] / "server" / "db" / "schema.sql"
    sql = Path(schema_path).read_text()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(sql)
        conn.commit()


def make_client(tmpdb: str):
    os.environ["MCP_DB_PATH"] = tmpdb
    from server.main import app  # import after env set
    return TestClient(app)


def test_capabilities_and_auth():
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "mcp.db")
        init_db(db)
        client = make_client(db)

        # Missing auth
        r = client.get("/get_capabilities")
        assert r.status_code == 401

        # With auth
        r = client.get("/get_capabilities", headers={"Authorization": "Bearer dev"})
        assert r.status_code == 200
        data = r.json()
        assert data["serverVersion"].startswith("1.")
        assert "add_memory" in data["tools"]


def test_memory_lifecycle():
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "mcp.db")
        init_db(db)
        client = make_client(db)
        H = {"Authorization": "Bearer dev"}

        # add_memory
        add = client.post(
            "/tool/add_memory",
            headers=H,
            json={"projectId": "nf", "content": "hello alpha", "metadata": {"tags": ["alpha"]}},
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
        assert item["projectId"] == "nf"
        assert item["quarantined"] is False

        # search_memory
        srch = client.post(
            "/tool/search_memory", headers=H, json={"projectId": "nf", "query": "alpha", "limit": 5}
        )
        if srch.status_code != 200:
            print("search_memory failed:", srch.text)
        assert srch.status_code == 200
        items = srch.json()["items"]
        assert any(it["id"] == mid for it in items)


def test_task_and_diff_and_logging():
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "mcp.db")
        init_db(db)
        client = make_client(db)
        H = {"Authorization": "Bearer dev"}

        # enqueue_task
        enq = client.post(
            "/tool/enqueue_task",
            headers=H,
            json={"projectId": "nf", "payload": {"kind": "plan", "note": "unit"}},
        )
        if enq.status_code != 200:
            print("enqueue_task failed:", enq.text)
        assert enq.status_code == 200

        # get_next_task
        nxt = client.post("/tool/get_next_task", headers=H, json={"projectId": "nf"})
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
                "projectId": "nf",
                "filePath": "server/main.py",
                "diff": "--- a\n+++ b\n@@\n+unit\n",
                "author": "test",
            },
        )
        assert sd.status_code == 200

        # list_recent
        lr = client.post(
            "/tool/list_recent", headers=H, json={"projectId": "nf", "limit": 5}
        )
        assert lr.status_code == 200
        assert lr.json()["count"] >= 1

        # log_error
        le = client.post(
            "/tool/log_error",
            headers=H,
            json={"level": "info", "message": "unit done", "projectId": "nf"},
        )
        assert le.status_code == 200
        assert le.json()["level"] == "info"
