import uuid
from typing import Any, Dict

from server.db.engine import get_async_engine
from server.db.repo import add_memory_pg
from server.memory.semantic import compute_embedding, is_semantic_enabled
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
        emb = None
        if is_semantic_enabled():
            try:
                emb = await compute_embedding(content)
            except Exception:
                emb = None
        await add_memory_pg(
            engine,
            mem_id=mem_id,
            project_id=project_id,
            content=content,
            metadata=metadata,
            quarantined=bool(quarantined),
            embedding=emb,
            group_id=None,
        )
    else:
        return {
            "error": {"code": "ERR.DB_UNAVAILABLE", "message": "DATABASE_URL not configured"},
            "requestId": request_id,
            "serverVersion": SERVER_VERSION,
            "timestamp": ts,
        }

    return {
        "requestId": request_id,
        "serverVersion": SERVER_VERSION,
        "id": mem_id,
        "projectId": project_id,
        "quarantined": bool(quarantined),
        "timestamp": ts,
    }
