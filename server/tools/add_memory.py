import json
import uuid
from typing import Any, Dict

import aiosqlite

from server.db.engine import get_async_engine
from server.db.repo import add_memory_pg
from server.utils.db import get_db_path
from server.utils.time import utc_now_iso_z

SERVER_VERSION = "1.3.0"

async def handler(req: Dict[str, Any]):
    """Add a memory entry.

    Request:
      {
        "projectId": "string",            # required
        "content": "string",              # required
        "metadata": { ... } | null,        # optional
        "quarantined": bool | null         # optional
      }
    """
    request_id = str(uuid.uuid4())
    ts = utc_now_iso_z()

    project_id = req.get("projectId")
    content = req.get("content")
    metadata = req.get("metadata")
    quarantined = req.get("quarantined", False)

    def bad(msg: str):
        return {
            "error": {"code": "ERR.BAD_REQUEST", "message": msg},
            "requestId": request_id,
            "serverVersion": SERVER_VERSION,
            "timestamp": ts,
        }

    if not isinstance(project_id, str) or not project_id.strip():
        return bad("projectId (string) is required")
    if not isinstance(content, str) or not content.strip():
        return bad("content (string) is required")
    if metadata is not None and not isinstance(metadata, dict):
        return bad("metadata must be an object if provided")
    if not isinstance(quarantined, (bool,)):
        return bad("quarantined must be a boolean if provided")

    mem_id = str(uuid.uuid4())
    engine = get_async_engine()
    if engine is not None:
        # Use PostgreSQL via SQLAlchemy
        await add_memory_pg(
            engine,
            mem_id=mem_id,
            project_id=project_id,
            content=content,
            metadata=metadata,
            quarantined=bool(quarantined),
        )
    else:
        # Fallback to SQLite for local tests
        async with aiosqlite.connect(get_db_path()) as db:
            await db.execute(
                """
                INSERT INTO memory_entries (id, project_id, content, metadata, quarantined)
                VALUES (?, ?, ?, ?, ?)
                """,
                (mem_id, project_id, content, json.dumps(metadata or {}), 1 if quarantined else 0),
            )
            await db.commit()

    return {
        "requestId": request_id,
        "serverVersion": SERVER_VERSION,
        "id": mem_id,
        "projectId": project_id,
        "quarantined": bool(quarantined),
        "timestamp": ts,
    }
