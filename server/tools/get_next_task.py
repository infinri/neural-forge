import json
import uuid
from typing import Any, Dict

import aiosqlite

from server.db.engine import get_async_engine
from server.db.repo import claim_next_task_pg
from server.utils.db import get_db_path
from server.utils.time import utc_now_iso_z

SERVER_VERSION = "1.3.0"

async def handler(req: Dict[str, Any]):
    """Claim the next queued task and mark it in_progress.

    Request:
      {
        "projectId": "string" | null  # optional filter
      }
    """
    request_id = str(uuid.uuid4())
    ts = utc_now_iso_z()

    project_id = req.get("projectId")

    engine = get_async_engine()
    if engine is not None:
        claimed = await claim_next_task_pg(engine, project_id=project_id if isinstance(project_id, str) else None)
        if not claimed:
            return {
                "requestId": request_id,
                "serverVersion": SERVER_VERSION,
                "task": None,
                "timestamp": ts,
            }
        task = {
            "id": claimed["id"],
            "projectId": claimed["projectId"],
            "status": "in_progress",
            "payload": claimed["payload"],
            "createdAt": claimed["createdAt"],
        }
    else:
        async with aiosqlite.connect(get_db_path()) as db:
            # Ensure immediate transaction to avoid race
            await db.execute("BEGIN IMMEDIATE")

            if isinstance(project_id, str) and project_id.strip():
                cur = await db.execute(
                    "SELECT id, project_id, status, payload, created_at FROM tasks WHERE status='queued' AND project_id=? ORDER BY created_at ASC LIMIT 1",
                    (project_id,),
                )
            else:
                cur = await db.execute(
                    "SELECT id, project_id, status, payload, created_at FROM tasks WHERE status='queued' ORDER BY created_at ASC LIMIT 1"
                )

            row = await cur.fetchone()
            await cur.close()

            if not row:
                await db.execute("COMMIT")
                return {
                    "requestId": request_id,
                    "serverVersion": SERVER_VERSION,
                    "task": None,
                    "timestamp": ts,
                }

            task_id, proj, status, payload_json, created_at = row

            # Attempt to claim the task
            await db.execute(
                "UPDATE tasks SET status='in_progress', updated_at=? WHERE id=? AND status='queued'",
                (ts, task_id),
            )
            changes_cur = await db.execute("SELECT changes()")
            _changes_row = await changes_cur.fetchone()
            changes = _changes_row[0] if _changes_row else 0
            await changes_cur.close()
            await db.execute("COMMIT")

            if changes == 0:
                # Another worker claimed it; return no task to caller
                return {
                    "requestId": request_id,
                    "serverVersion": SERVER_VERSION,
                    "task": None,
                    "timestamp": ts,
                }

            task = {
                "id": task_id,
                "projectId": proj,
                "status": "in_progress",
                "payload": json.loads(payload_json) if payload_json else {},
                "createdAt": created_at,
            }

        return {
            "requestId": request_id,
            "serverVersion": SERVER_VERSION,
            "task": task,
            "timestamp": ts,
        }
