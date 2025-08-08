import uuid
from typing import Any, Dict

from server.utils.time import utc_now_iso_z

from ..nf_client import tokens

SERVER_VERSION = "1.3.0"

async def handler(req: Dict[str, Any]):
    """Get active tokens for a project by kinds.

    Request:
      {
        "projectId": "string",        # required
        "kinds": ["governance", ...]  # optional list[str]
      }
    """
    request_id = str(uuid.uuid4())
    ts = utc_now_iso_z()

    project_id = req.get("projectId")
    kinds = req.get("kinds", [])

    if not isinstance(project_id, str) or not project_id.strip():
        return {
            "error": {"code": "ERR.BAD_REQUEST", "message": "projectId (string) is required"},
            "requestId": request_id,
            "serverVersion": SERVER_VERSION,
            "timestamp": ts,
        }

    if not isinstance(kinds, list) or not all(isinstance(k, str) for k in kinds):
        return {
            "error": {"code": "ERR.BAD_REQUEST", "message": "kinds must be a list of strings"},
            "requestId": request_id,
            "serverVersion": SERVER_VERSION,
            "timestamp": ts,
        }

    result = tokens.fetch_tokens(project_id=project_id, kinds=list(kinds))

    return {
        "requestId": request_id,
        "serverVersion": SERVER_VERSION,
        "tokens": result.get("tokens", []),
        "timestamp": ts,
    }
