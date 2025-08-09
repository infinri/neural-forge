import uuid
from typing import Any, Dict

from server.db.engine import get_async_engine
from server.db.repo import list_recent_diffs_pg
from server.utils.db import sqlite_fetch_all
from server.utils.time import utc_now_iso_z

SERVER_VERSION = "1.3.0"

async def handler(req: Dict[str, Any]):
    """List recent diffs.

    Request:
      {
        "projectId": "string" | null,  # optional filter
        "limit": number                 # optional, default 20
      }
    """
    request_id = str(uuid.uuid4())
    ts = utc_now_iso_z()

    project_id = req.get("projectId")
    limit = req.get("limit", 20)
    try:
        limit = int(limit)
    except Exception:
        return {
            "error": {"code": "ERR.BAD_REQUEST", "message": "limit must be an integer"},
            "requestId": request_id,
            "serverVersion": SERVER_VERSION,
            "timestamp": ts,
        }
    if limit <= 0 or limit > 200:
        limit = 20

    engine = get_async_engine()
    if engine is not None:
        rows = await list_recent_diffs_pg(
            engine,
            project_id=project_id if isinstance(project_id, str) else None,
            limit=limit,
        )
    else:
        rows = []
        if isinstance(project_id, str) and project_id.strip():
            raw = await sqlite_fetch_all(
                "SELECT id, project_id, file_path, author, created_at FROM diffs WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
                (project_id, limit),
            )
        else:
            raw = await sqlite_fetch_all(
                "SELECT id, project_id, file_path, author, created_at FROM diffs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        for r in raw:
            rows.append({
                "id": r[0],
                "projectId": r[1],
                "filePath": r[2],
                "author": r[3],
                "createdAt": r[4],
            })

    return {
        "requestId": request_id,
        "serverVersion": SERVER_VERSION,
        "items": rows,
        "count": len(rows),
        "timestamp": ts,
    }
