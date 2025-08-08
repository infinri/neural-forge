import json
import uuid
from typing import Any, Dict

import aiosqlite

from server.db.engine import get_async_engine
from server.db.repo import search_memory_pg
from server.utils.db import get_db_path
from server.utils.time import utc_now_iso_z

SERVER_VERSION = "1.3.0"
async def handler(req: Dict[str, Any]):
    """Search memory entries by content substring.

    Request:
      {
        "query": "string",                 # required
        "projectId": "string" | null,      # optional filter
        "limit": number | null,             # optional (default 20, max 200)
        "includeQuarantined": bool | null   # optional (default false)
      }
    """
    request_id = str(uuid.uuid4())
    ts = utc_now_iso_z()

    query = req.get("query")
    project_id = req.get("projectId")
    limit = req.get("limit", 20)
    include_quarantined = bool(req.get("includeQuarantined", False))

    def bad(msg: str):
        return {
            "error": {"code": "ERR.BAD_REQUEST", "message": msg},
            "requestId": request_id,
            "serverVersion": SERVER_VERSION,
            "timestamp": ts,
        }

    if not isinstance(query, str) or not query.strip():
        return bad("query (string) is required")
    try:
        limit = int(limit)
    except Exception:
        return bad("limit must be an integer")
    if limit <= 0 or limit > 200:
        limit = 20

    engine = get_async_engine()
    rows = []
    if engine is not None:
        rows = await search_memory_pg(
            engine,
            query=query.strip(),
            project_id=project_id if isinstance(project_id, str) else None,
            limit=limit,
            include_quarantined=include_quarantined,
        )
    else:
        like = f"%{query}%"
        async with aiosqlite.connect(get_db_path()) as db:
            params: tuple[Any, ...]
            if isinstance(project_id, str) and project_id.strip():
                if include_quarantined:
                    sql = (
                        "SELECT id, project_id, content, metadata, quarantined, created_at "
                        "FROM memory_entries WHERE project_id = ? AND content LIKE ? "
                        "ORDER BY created_at DESC LIMIT ?"
                    )
                    params = (project_id, like, limit)
                else:
                    sql = (
                        "SELECT id, project_id, content, metadata, quarantined, created_at "
                        "FROM memory_entries WHERE project_id = ? AND quarantined=0 AND content LIKE ? "
                        "ORDER BY created_at DESC LIMIT ?"
                    )
                    params = (project_id, like, limit)
            else:
                if include_quarantined:
                    sql = (
                        "SELECT id, project_id, content, metadata, quarantined, created_at "
                        "FROM memory_entries WHERE content LIKE ? ORDER BY created_at DESC LIMIT ?"
                    )
                    params = (like, limit)
                else:
                    sql = (
                        "SELECT id, project_id, content, metadata, quarantined, created_at "
                        "FROM memory_entries WHERE quarantined=0 AND content LIKE ? ORDER BY created_at DESC LIMIT ?"
                    )
                    params = (like, limit)

            async with db.execute(sql, params) as cur:
                async for r in cur:
                    rows.append({
                        "id": r[0],
                        "projectId": r[1],
                        "content": r[2],
                        "metadata": json.loads(r[3]) if r[3] else {},
                        "quarantined": bool(r[4]),
                        "createdAt": r[5],
                    })

    return {
        "requestId": request_id,
        "serverVersion": SERVER_VERSION,
        "items": rows,
        "count": len(rows),
        "timestamp": ts,
    }
