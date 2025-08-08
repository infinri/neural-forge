import uuid
from typing import Any, Dict

from server.utils.time import utc_now_iso_z

from ..nf_client import governance

SERVER_VERSION = "1.3.0"

async def handler(req: Dict[str, Any]):
    """Get governance policies resolved for a project and scopes.

    Request:
      {
        "projectId": "string",           # required
        "scopes": ["memory", ...]        # optional list[str]
      }
    """
    request_id = str(uuid.uuid4())
    ts = utc_now_iso_z()

    project_id = req.get("projectId")
    scopes = req.get("scopes", [])

    if not isinstance(project_id, str) or not project_id.strip():
        return {
            "error": {
                "code": "ERR.BAD_REQUEST",
                "message": "projectId (string) is required",
            },
            "requestId": request_id,
            "serverVersion": SERVER_VERSION,
            "timestamp": ts,
        }

    if not isinstance(scopes, list) or not all(isinstance(s, str) for s in scopes):
        return {
            "error": {
                "code": "ERR.BAD_REQUEST",
                "message": "scopes must be a list of strings",
            },
            "requestId": request_id,
            "serverVersion": SERVER_VERSION,
            "timestamp": ts,
        }

    result = governance.fetch_policies(project_id=project_id, scopes=list(scopes))

    return {
        "requestId": request_id,
        "serverVersion": SERVER_VERSION,
        "policies": result.get("policies", []),
        "resolutionGraph": result.get("resolutionGraph", {}),
        "timestamp": ts,
    }
