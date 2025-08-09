import os
import sqlite3
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

# Ensure token for app auth
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


def seed_data(db_path: str):
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        # memory_entries
        cur.execute(
            "INSERT INTO memory_entries (id, project_id, content, metadata, quarantined) VALUES (?,?,?,?,?)",
            ("m1", "nf", "alpha text", "{}", 0),
        )
        cur.execute(
            "INSERT INTO memory_entries (id, project_id, content, metadata, quarantined) VALUES (?,?,?,?,?)",
            ("m2", "nf", "beta text", "{}", 1),
        )
        cur.execute(
            "INSERT INTO memory_entries (id, project_id, content, metadata, quarantined) VALUES (?,?,?,?,?)",
            ("m3", "other", "gamma text", "{}", 0),
        )

        # tasks for nf: queued=1, in_progress=2, done=1, failed=1 (total=5)
        cur.execute(
            "INSERT INTO tasks (id, project_id, status, payload) VALUES (?,?,?,?)",
            ("tq", "nf", "queued", "{}"),
        )
        cur.execute(
            "INSERT INTO tasks (id, project_id, status, payload) VALUES (?,?,?,?)",
            ("ti1", "nf", "in_progress", "{}"),
        )
        cur.execute(
            "INSERT INTO tasks (id, project_id, status, payload) VALUES (?,?,?,?)",
            ("ti2", "nf", "in_progress", "{}"),
        )
        cur.execute(
            "INSERT INTO tasks (id, project_id, status, payload) VALUES (?,?,?,?)",
            ("td", "nf", "done", "{}"),
        )
        cur.execute(
            "INSERT INTO tasks (id, project_id, status, payload) VALUES (?,?,?,?)",
            ("tf", "nf", "failed", "{}"),
        )
        # tasks other project
        cur.execute(
            "INSERT INTO tasks (id, project_id, status, payload) VALUES (?,?,?,?)",
            ("tq_o", "other", "queued", "{}"),
        )

        # diffs: nf=2, other=1
        cur.execute(
            "INSERT INTO diffs (id, project_id, file_path, diff, author) VALUES (?,?,?,?,?)",
            ("d1", "nf", "a.py", "+a", "u"),
        )
        cur.execute(
            "INSERT INTO diffs (id, project_id, file_path, diff, author) VALUES (?,?,?,?,?)",
            ("d2", "nf", "b.py", "+b", "u"),
        )
        cur.execute(
            "INSERT INTO diffs (id, project_id, file_path, diff, author) VALUES (?,?,?,?,?)",
            ("d3", "other", "c.py", "+c", "u"),
        )

        # errors: nf=1, other=1
        cur.execute(
            "INSERT INTO errors (id, project_id, level, message) VALUES (?,?,?,?)",
            ("e1", "nf", "error", "bad"),
        )
        cur.execute(
            "INSERT INTO errors (id, project_id, level, message) VALUES (?,?,?,?)",
            ("e2", "other", "error", "worse"),
        )
        conn.commit()


def test_admin_endpoints_require_auth():
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "mcp.db")
        init_db(db)
        client = make_client(db)

        r = client.get("/admin/stats")
        assert r.status_code == 401

        r = client.get("/admin/memory_meta")
        assert r.status_code == 401


def test_admin_stats_and_memory_meta_sqlite():
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "mcp.db")
        init_db(db)
        seed_data(db)
        client = make_client(db)
        H = {"Authorization": "Bearer dev"}

        # Stats filtered by project nf
        rs = client.get("/admin/stats", headers=H, params={"projectId": "nf"})
        assert rs.status_code == 200, rs.text
        js = rs.json()
        assert js["counts"]["memoryEntries"] == 2
        assert js["counts"]["diffs"] == 2
        assert js["counts"]["errors"] == 1
        tasks = js["counts"]["tasks"]
        assert tasks["queued"] == 1
        assert tasks["inProgress"] == 2
        assert tasks["done"] == 1
        assert tasks["failed"] == 1
        assert tasks["total"] == 5

        # Memory meta filtering
        rm = client.get(
            "/admin/memory_meta",
            headers=H,
            params={"projectId": "nf", "quarantinedOnly": True},
        )
        assert rm.status_code == 200, rm.text
        jm = rm.json()
        assert jm["count"] == 1
        assert jm["items"][0]["id"] == "m2"
        assert jm["items"][0]["projectId"] == "nf"
        assert jm["items"][0]["quarantined"] is True
        assert jm["items"][0]["size"] > 0

        # Pagination
        rp = client.get(
            "/admin/memory_meta",
            headers=H,
            params={"projectId": "nf", "limit": 1},
        )
        assert rp.status_code == 200
        jp = rp.json()
        assert jp["count"] == 1
