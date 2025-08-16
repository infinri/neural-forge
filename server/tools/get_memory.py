import json
import uuid
from typing import Any, Dict

from server.db.engine import get_async_engine
from server.db.repo import get_memory_pg
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
    if engine is None:
        return {
            "error": {"code": "ERR.DB_UNAVAILABLE", "message": "DATABASE_URL not configured"},
            "requestId": request_id,
            "serverVersion": SERVER_VERSION,
            "timestamp": ts,
        }

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
