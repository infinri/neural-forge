import json
import uuid
from typing import Any, Dict

import aiosqlite

from server.db.engine import get_async_engine
from server.db.repo import get_memory_pg
from server.utils.db import get_db_path
from server.utils.time import utc_now_iso_z

SERVER_VERSION = "1.3.0"

async def handler(req: Dict[str, Any]):
    """Get a memory by id.

    Request: { "id": "string" }
    """
    request_id = str(uuid.uuid4())
    ts = utc_now_iso_z()

    mem_id = req.get("id")
    if isinstance(mem_id, str):
        mem_id = mem_id.strip()
    if not isinstance(mem_id, str) or not mem_id:
        return {
            "error": {"code": "ERR.BAD_REQUEST", "message": "id (string) is required"},
            "requestId": request_id,
            "serverVersion": SERVER_VERSION,
            "timestamp": ts,
        }

    engine = get_async_engine()
    row_obj = None
    if engine is not None:
        row_obj = await get_memory_pg(engine, mem_id=mem_id)
        if row_obj is None:
            return {
                "error": {"code": "ERR.NOT_FOUND", "message": "memory not found"},
                "requestId": request_id,
                "serverVersion": SERVER_VERSION,
                "timestamp": ts,
            }
        item = row_obj
        return {
            "requestId": request_id,
            "serverVersion": SERVER_VERSION,
            "item": item,
            "timestamp": ts,
        }
    else:
        async with aiosqlite.connect(get_db_path()) as db:
            cur = await db.execute(
                "SELECT id, project_id, content, metadata, quarantined, created_at FROM memory_entries WHERE id=?",
                (mem_id,),
            )
            row = await cur.fetchone()
            await cur.close()

    if not row:
        return {
            "error": {"code": "ERR.NOT_FOUND", "message": "memory not found"},
            "requestId": request_id,
            "serverVersion": SERVER_VERSION,
            "timestamp": ts,
        }

    item = {
        "id": row[0],
        "projectId": row[1],
        "content": row[2],
        "metadata": json.loads(row[3]) if row[3] else {},
        "quarantined": bool(row[4]),
        "createdAt": row[5],
    }

    return {
        "requestId": request_id,
        "serverVersion": SERVER_VERSION,
        "item": item,
        "timestamp": ts,
    }
