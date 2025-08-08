import json
import os
import uuid
from typing import Any, Dict

import aiosqlite

from server.db.engine import get_async_engine
from server.db.repo import update_task_status_pg
from server.utils.time import utc_now_iso_z

SERVER_VERSION = "1.3.0"

VALID_STATUSES = {"queued", "in_progress", "done", "failed"}

async def handler(req: Dict[str, Any]):
    """Update a task's status (typically to done/failed) with optional result.

    Request:
      {
        "id": "uuid",                # required
        "status": "done|failed|in_progress|queued",  # required
        "result": { ... } | null      # optional JSON object
      }
    """
    request_id = str(uuid.uuid4())
    ts = utc_now_iso_z()

    task_id = req.get("id")
    status = req.get("status")
    result = req.get("result")

    def bad(msg: str):
        return {
            "error": {"code": "ERR.BAD_REQUEST", "message": msg},
            "requestId": request_id,
            "serverVersion": SERVER_VERSION,
            "timestamp": ts,
        }

    if not isinstance(task_id, str) or not task_id.strip():
        return bad("id (string) is required")
    if not isinstance(status, str) or status not in VALID_STATUSES:
        return bad("status must be one of queued|in_progress|done|failed")
    if result is not None and not isinstance(result, dict):
        return bad("result must be an object if provided")

    engine = get_async_engine()
    if engine is not None:
        ok = await update_task_status_pg(
            engine,
            task_id=task_id.strip(),
            status=status,
            result=result,
        )
        if not ok:
            return {
                "error": {"code": "ERR.NOT_FOUND", "message": "task not found"},
                "requestId": request_id,
                "serverVersion": SERVER_VERSION,
                "timestamp": ts,
            }
    else:
        db_path = os.getenv("MCP_DB_PATH", "data/mcp.db")
        async with aiosqlite.connect(db_path) as db:
            cur = await db.execute(
                "SELECT status FROM tasks WHERE id=?",
                (task_id,),
            )
            row = await cur.fetchone()
            await cur.close()
            if not row:
                return {
                    "error": {"code": "ERR.NOT_FOUND", "message": "task not found"},
                    "requestId": request_id,
                    "serverVersion": SERVER_VERSION,
                    "timestamp": ts,
                }

            await db.execute(
                "UPDATE tasks SET status=?, result=?, updated_at=? WHERE id=?",
                (status, json.dumps(result or {}), ts, task_id),
            )
            await db.commit()

    return {
        "requestId": request_id,
        "serverVersion": SERVER_VERSION,
        "id": task_id,
        "status": status,
        "timestamp": ts,
    }
