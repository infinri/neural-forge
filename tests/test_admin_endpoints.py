import os

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Json

# Ensure token for app auth
os.environ.setdefault("MCP_TOKEN", "test-token")
TOKEN = os.environ["MCP_TOKEN"]


def _sync_dsn() -> str:
    url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://forge:forge@127.0.0.1:5432/neural_forge")
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if url.startswith("postgresql+psycopg://"):
        url = url.replace("postgresql+psycopg://", "postgresql://", 1)
    return url


try:
    with psycopg.connect(_sync_dsn()):
        pass
except psycopg.OperationalError:
    pytest.skip("Postgres is required for admin endpoint tests", allow_module_level=True)


def make_client_pg():
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://forge:forge@127.0.0.1:5432/neural_forge")
    from server.main import app  # import after env set
    return TestClient(app)


def seed_data_pg():
    """Seed isolated test data using unique project ids to avoid cross-test interference."""
    P_MAIN = "nf_admin"
    P_OTHER = "other_admin"
    with psycopg.connect(_sync_dsn()) as conn:
        with conn.cursor() as cur:
            # memory_entries
            cur.execute(
                "INSERT INTO memory_entries (id, project_id, content, metadata, quarantined) VALUES (%s,%s,%s,%s,%s) "
                "ON CONFLICT (id) DO UPDATE SET project_id = EXCLUDED.project_id, content = EXCLUDED.content, metadata = EXCLUDED.metadata, quarantined = EXCLUDED.quarantined",
                ("m1_admin", P_MAIN, "alpha text", Json({}), False),
            )
            cur.execute(
                "INSERT INTO memory_entries (id, project_id, content, metadata, quarantined) VALUES (%s,%s,%s,%s,%s) "
                "ON CONFLICT (id) DO UPDATE SET project_id = EXCLUDED.project_id, content = EXCLUDED.content, metadata = EXCLUDED.metadata, quarantined = EXCLUDED.quarantined",
                ("m2_admin", P_MAIN, "beta text", Json({}), True),
            )
            cur.execute(
                "INSERT INTO memory_entries (id, project_id, content, metadata, quarantined) VALUES (%s,%s,%s,%s,%s) "
                "ON CONFLICT (id) DO UPDATE SET project_id = EXCLUDED.project_id, content = EXCLUDED.content, metadata = EXCLUDED.metadata, quarantined = EXCLUDED.quarantined",
                ("m3_admin", P_OTHER, "gamma text", Json({}), False),
            )

            # tasks for P_MAIN: queued=1, in_progress=2, done=1, failed=1 (total=5)
            cur.execute(
                "INSERT INTO tasks (id, project_id, status, payload) VALUES (%s,%s,%s,%s) "
                "ON CONFLICT (id) DO UPDATE SET project_id = EXCLUDED.project_id, status = EXCLUDED.status, payload = EXCLUDED.payload, updated_at = NOW()",
                ("tq_admin", P_MAIN, "queued", Json({})),
            )
            cur.execute(
                "INSERT INTO tasks (id, project_id, status, payload) VALUES (%s,%s,%s,%s) "
                "ON CONFLICT (id) DO UPDATE SET project_id = EXCLUDED.project_id, status = EXCLUDED.status, payload = EXCLUDED.payload, updated_at = NOW()",
                ("ti1_admin", P_MAIN, "in_progress", Json({})),
            )
            cur.execute(
                "INSERT INTO tasks (id, project_id, status, payload) VALUES (%s,%s,%s,%s) "
                "ON CONFLICT (id) DO UPDATE SET project_id = EXCLUDED.project_id, status = EXCLUDED.status, payload = EXCLUDED.payload, updated_at = NOW()",
                ("ti2_admin", P_MAIN, "in_progress", Json({})),
            )
            cur.execute(
                "INSERT INTO tasks (id, project_id, status, payload) VALUES (%s,%s,%s,%s) "
                "ON CONFLICT (id) DO UPDATE SET project_id = EXCLUDED.project_id, status = EXCLUDED.status, payload = EXCLUDED.payload, updated_at = NOW()",
                ("td_admin", P_MAIN, "done", Json({})),
            )
            cur.execute(
                "INSERT INTO tasks (id, project_id, status, payload) VALUES (%s,%s,%s,%s) "
                "ON CONFLICT (id) DO UPDATE SET project_id = EXCLUDED.project_id, status = EXCLUDED.status, payload = EXCLUDED.payload, updated_at = NOW()",
                ("tf_admin", P_MAIN, "failed", Json({})),
            )
            # tasks other project
            cur.execute(
                "INSERT INTO tasks (id, project_id, status, payload) VALUES (%s,%s,%s,%s) "
                "ON CONFLICT (id) DO UPDATE SET project_id = EXCLUDED.project_id, status = EXCLUDED.status, payload = EXCLUDED.payload, updated_at = NOW()",
                ("tq_o_admin", P_OTHER, "queued", Json({})),
            )

            # diffs: P_MAIN=2, other=1
            cur.execute(
                "INSERT INTO diffs (id, project_id, file_path, diff, author) VALUES (%s,%s,%s,%s,%s) "
                "ON CONFLICT (id) DO UPDATE SET project_id = EXCLUDED.project_id, file_path = EXCLUDED.file_path, diff = EXCLUDED.diff, author = EXCLUDED.author",
                ("d1_admin", P_MAIN, "a.py", "+a", "u"),
            )
            cur.execute(
                "INSERT INTO diffs (id, project_id, file_path, diff, author) VALUES (%s,%s,%s,%s,%s) "
                "ON CONFLICT (id) DO UPDATE SET project_id = EXCLUDED.project_id, file_path = EXCLUDED.file_path, diff = EXCLUDED.diff, author = EXCLUDED.author",
                ("d2_admin", P_MAIN, "b.py", "+b", "u"),
            )
            cur.execute(
                "INSERT INTO diffs (id, project_id, file_path, diff, author) VALUES (%s,%s,%s,%s,%s) "
                "ON CONFLICT (id) DO UPDATE SET project_id = EXCLUDED.project_id, file_path = EXCLUDED.file_path, diff = EXCLUDED.diff, author = EXCLUDED.author",
                ("d3_admin", P_OTHER, "c.py", "+c", "u"),
            )

            # errors: P_MAIN=1, other=1
            cur.execute(
                "INSERT INTO errors (id, project_id, level, message) VALUES (%s,%s,%s,%s) "
                "ON CONFLICT (id) DO UPDATE SET project_id = EXCLUDED.project_id, level = EXCLUDED.level, message = EXCLUDED.message",
                ("e1_admin", P_MAIN, "error", "bad"),
            )
            cur.execute(
                "INSERT INTO errors (id, project_id, level, message) VALUES (%s,%s,%s,%s) "
                "ON CONFLICT (id) DO UPDATE SET project_id = EXCLUDED.project_id, level = EXCLUDED.level, message = EXCLUDED.message",
                ("e2_admin", P_OTHER, "error", "worse"),
            )
        conn.commit()


def test_admin_endpoints_require_auth():
    client = make_client_pg()

    r = client.get("/admin/stats")
    assert r.status_code == 401

    r = client.get("/admin/memory_meta")
    assert r.status_code == 401


def test_admin_stats_and_memory_meta_pg():
    seed_data_pg()
    client = make_client_pg()
    H = {"Authorization": f"Bearer {TOKEN}"}

    # Stats filtered by project nf_admin
    rs = client.get("/admin/stats", headers=H, params={"projectId": "nf_admin"})
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
        params={"projectId": "nf_admin", "quarantinedOnly": True},
    )
    assert rm.status_code == 200, rm.text
    jm = rm.json()
    assert jm["count"] == 1
    assert jm["items"][0]["id"] == "m2_admin"
    assert jm["items"][0]["projectId"] == "nf_admin"
    assert jm["items"][0]["quarantined"] is True
    assert jm["items"][0]["size"] > 0

    # Pagination
    rp = client.get(
        "/admin/memory_meta",
        headers=H,
        params={"projectId": "nf_admin", "limit": 1},
    )
    assert rp.status_code == 200
    jp = rp.json()
    assert jp["count"] == 1
