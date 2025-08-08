import json
import uuid
from typing import Any, Dict

import aiosqlite

from server.db.engine import get_async_engine
from server.db.repo import enqueue_task_pg
from server.utils.db import get_db_path
from server.utils.time import utc_now_iso_z

SERVER_VERSION = "1.3.0"

async def handler(req: Dict[str, Any]):
    """Enqueue a task with status=queued.

    Request:
      {
        "projectId": "string",     # required
        "payload": { ... } | null    # optional JSON object
      }
    """
    request_id = str(uuid.uuid4())
    ts = utc_now_iso_z()

    project_id = req.get("projectId")
    payload = req.get("payload")

    def bad(msg: str):
        return {
            "error": {"code": "ERR.BAD_REQUEST", "message": msg},
            "requestId": request_id,
            "serverVersion": SERVER_VERSION,
            "timestamp": ts,
        }

    if not isinstance(project_id, str) or not project_id.strip():
        return bad("projectId (string) is required")
    if payload is not None and not isinstance(payload, dict):
        return bad("payload must be an object if provided")

    task_id = str(uuid.uuid4())
    engine = get_async_engine()
    if engine is not None:
        await enqueue_task_pg(engine, task_id=task_id, project_id=project_id.strip(), payload=payload)
    else:
        async with aiosqlite.connect(get_db_path()) as db:
            await db.execute(
                """
                INSERT INTO tasks (id, project_id, status, payload)
                VALUES (?, ?, 'queued', ?)
                """,
                (task_id, project_id, json.dumps(payload or {})),
            )
            await db.commit()

    return {
        "requestId": request_id,
        "serverVersion": SERVER_VERSION,
        "id": task_id,
        "status": "queued",
        "timestamp": ts,
    }
