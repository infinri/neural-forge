import uuid
from typing import Any, Dict

from server.db.engine import get_async_engine
from server.db.repo import save_diff_pg
from server.utils.time import utc_now_iso_z

SERVER_VERSION = "1.3.0"

async def handler(req: Dict[str, Any]):
    """Persist a code diff.

    Expected request shape (v1.3):
      {
        "projectId": "string",   # required
        "filePath": "string",    # required
        "diff": "string",        # required (unified diff text)
        "author": "string"       # optional
      }
    """
    request_id = str(uuid.uuid4())
    ts = utc_now_iso_z()

    project_id = req.get("projectId")
    file_path = req.get("filePath")
    diff_text = req.get("diff")
    author = req.get("author")

    def bad_request(msg: str):
        return {
            "error": {"code": "ERR.BAD_REQUEST", "message": msg},
            "requestId": request_id,
            "serverVersion": SERVER_VERSION,
            "timestamp": ts,
        }

    if not isinstance(project_id, str) or not project_id.strip():
        return bad_request("projectId (string) is required")
    if not isinstance(file_path, str) or not file_path.strip():
        return bad_request("filePath (string) is required")
    if not isinstance(diff_text, str) or not diff_text:
        return bad_request("diff (string) is required")
    if author is not None and not isinstance(author, str):
        return bad_request("author must be a string if provided")

    row_id = str(uuid.uuid4())
    engine = get_async_engine()
    if engine is None:
        return {
            "error": {"code": "ERR.DB_UNAVAILABLE", "message": "DATABASE_URL not configured"},
            "requestId": request_id,
            "serverVersion": SERVER_VERSION,
            "timestamp": ts,
        }
    await save_diff_pg(
        engine,
        row_id=row_id,
        project_id=project_id,
        file_path=file_path,
        diff_text=diff_text,
        author=author,
    )

    return {
        "requestId": request_id,
        "serverVersion": SERVER_VERSION,
        "id": row_id,
        "projectId": project_id,
        "filePath": file_path,
        "author": author,
        "timestamp": ts,
    }
