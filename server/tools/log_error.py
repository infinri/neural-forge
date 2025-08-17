import uuid
from typing import Any, Dict

from server.db.engine import get_async_engine
from server.db.repo import log_error_pg
from server.utils.time import utc_now_iso_z

SERVER_VERSION = "1.3.0"

LEVELS = {"info", "warn", "error"}

async def handler(req: Dict[str, Any]):
    """Log an error/warning/info event.

    Request:
      {
        "level": "info|warn|error",    # required
        "message": "string",           # required
        "projectId": "string" | null,  # optional
        "context": { ... } | null       # optional
      }
    """
    request_id = str(uuid.uuid4())
    ts = utc_now_iso_z()

    level = req.get("level")
    message = req.get("message")
    project_id = req.get("projectId")
    context = req.get("context")

    def bad(msg: str):
        return {
            "error": {"code": "ERR.BAD_REQUEST", "message": msg},
            "requestId": request_id,
            "serverVersion": SERVER_VERSION,
            "timestamp": ts,
        }

    if not isinstance(level, str) or level not in LEVELS:
        return bad("level must be one of info|warn|error")
    if not isinstance(message, str) or not message.strip():
        return bad("message (string) is required")
    if project_id is not None and not isinstance(project_id, str):
        return bad("projectId must be a string if provided")
    if context is not None and not isinstance(context, dict):
        return bad("context must be an object if provided")

    row_id = str(uuid.uuid4())
    engine = get_async_engine()
    if engine is None:
        return {
            "error": {"code": "ERR.DB_UNAVAILABLE", "message": "DATABASE_URL not configured"},
            "requestId": request_id,
            "serverVersion": SERVER_VERSION,
            "timestamp": ts,
        }
    await log_error_pg(
        engine,
        row_id=row_id,
        level=level,
        message=message,
        project_id=project_id if isinstance(project_id, str) else None,
        context=context if isinstance(context, dict) else None,
    )

    return {
        "requestId": request_id,
        "serverVersion": SERVER_VERSION,
        "id": row_id,
        "level": level,
        "timestamp": ts,
    }
