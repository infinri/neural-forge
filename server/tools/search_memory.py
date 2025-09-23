import uuid
from typing import Any, Dict, Optional

from server.db.engine import get_async_engine
from server.db.repo import search_memory_pg, semantic_search_memory_pg
from server.memory.semantic import compute_embedding, is_semantic_enabled
from server.utils.time import utc_now_iso_z

SERVER_VERSION = "1.3.0"
async def handler(req: Dict[str, Any]):
    """Search memory entries.

    Request:
      {
        "query": "string",                 # required (used for keyword or to embed)
        "projectId": "string" | null,      # optional filter
        "limit": number | null,             # optional (default 20, max 200) for keyword mode
        "includeQuarantined": bool | null,  # optional (default false)
        "mode": "keyword"|"semantic"|"hybrid" | null,  # optional (default keyword)
        "k": number | null,                 # optional top-k for semantic/hybrid (default = limit)
        "threshold": number | null          # optional max cosine distance for semantic/hybrid
      }
    """
    request_id = str(uuid.uuid4())
    ts = utc_now_iso_z()

    query = req.get("query")
    project_id = req.get("projectId")
    limit = req.get("limit", 20)
    include_quarantined = bool(req.get("includeQuarantined", False))
    mode = (req.get("mode") or "keyword").strip().lower() if isinstance(req.get("mode"), str) else "keyword"
    k = req.get("k")
    threshold = req.get("threshold")

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
    if k is None:
        k = limit
    else:
        try:
            k = int(k)
        except Exception:
            return bad("k must be an integer if provided")
        if k <= 0 or k > 200:
            k = limit

    engine = get_async_engine()
    if engine is None:
        return {
            "error": {"code": "ERR.DB_UNAVAILABLE", "message": "DATABASE_URL not configured"},
            "requestId": request_id,
            "serverVersion": SERVER_VERSION,
            "timestamp": ts,
        }
    rows: list[Dict[str, Any]] = []

    # Helper: keyword search via PostgreSQL
    async def keyword_search() -> list[Dict[str, Any]]:
        return await search_memory_pg(
            engine,
            query=query.strip(),
            project_id=project_id if isinstance(project_id, str) else None,
            limit=limit,
            include_quarantined=include_quarantined,
        )

    def dedupe_merge(primary: list[Dict[str, Any]], secondary: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        seen = set()
        merged: list[Dict[str, Any]] = []
        for lst in (primary, secondary):
            for it in lst:
                mid = it.get("id")
                if mid in seen:
                    continue
                seen.add(mid)
                merged.append(it)
        return merged[: max(limit, k)]

    async def compute_query_embedding_safe() -> Optional[list[float]]:
        if not isinstance(query, str):
            return None
        try:
            return await compute_embedding(query)
        except Exception:
            return None

    # Execute according to mode
    if mode == "semantic" and is_semantic_enabled():
        # Semantic only; fallback to keyword if embedding unavailable
        qemb = await compute_query_embedding_safe()
        if qemb is not None:
            rows = await semantic_search_memory_pg(
                engine,
                query_embedding=qemb,
                project_id=project_id if isinstance(project_id, str) else None,
                k=k,
                include_quarantined=include_quarantined,
                threshold=float(threshold) if isinstance(threshold, (int, float)) else None,
            )
        else:
            rows = await keyword_search()
    elif mode == "hybrid" and is_semantic_enabled():
        kw = await keyword_search()
        qemb = await compute_query_embedding_safe()
        if qemb is not None:
            sem = await semantic_search_memory_pg(
                engine,
                query_embedding=qemb,
                project_id=project_id if isinstance(project_id, str) else None,
                k=k,
                include_quarantined=include_quarantined,
                threshold=float(threshold) if isinstance(threshold, (int, float)) else None,
            )
            rows = dedupe_merge(sem, kw)
        else:
            rows = kw
    else:
        # default keyword
        rows = await keyword_search()

    return {
        "requestId": request_id,
        "serverVersion": SERVER_VERSION,
        "items": rows,
        "count": len(rows),
        "timestamp": ts,
    }
