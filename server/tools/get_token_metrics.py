import uuid
from typing import Any, Dict

from server.db.engine import get_async_engine
from server.db.repo import fetch_governance_token_metrics_pg
from server.utils.time import utc_now_iso_z

SERVER_VERSION = "1.3.0"


def _normalize_token_ids(raw: Any) -> list[str] | None:
    if raw is None:
        return None
    if isinstance(raw, (list, tuple, set)):
        tokens = [str(item).strip() for item in raw if isinstance(item, str) and item.strip()]
        return tokens or None
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return None


async def handler(req: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch governance token usage metrics."""

    request_id = str(uuid.uuid4())
    ts = utc_now_iso_z()

    project_id = req.get("projectId")
    token_filters = _normalize_token_ids(req.get("tokenIds"))

    limit = req.get("limit", 50)
    min_activations = req.get("minActivations", 0)

    try:
        limit_val = int(limit)
    except Exception:
        limit_val = 50
    limit_val = max(1, min(limit_val, 500))

    try:
        min_act = max(0, int(min_activations))
    except Exception:
        min_act = 0

    engine = get_async_engine()
    if engine is None:
        return {
            "error": {"code": "ERR.DB_UNAVAILABLE", "message": "DATABASE_URL not configured"},
            "requestId": request_id,
            "serverVersion": SERVER_VERSION,
            "timestamp": ts,
        }

    metrics = await fetch_governance_token_metrics_pg(
        engine,
        token_ids=token_filters,
        project_id=project_id,
        min_activation_count=min_act,
        limit=limit_val,
    )

    return {
        "requestId": request_id,
        "serverVersion": SERVER_VERSION,
        "timestamp": ts,
        "projectId": project_id or "global",
        "minActivations": min_act,
        "limit": limit_val,
        "count": len(metrics),
        "items": metrics,
        "tokenIds": token_filters,
    }
