import json
from datetime import datetime, timezone
from typing import Any, Dict, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from server.utils.logger import log_json


def _to_pgvector_literal(vec: list[float]) -> str:
    """Format a Python list[float] as a pgvector literal string: '[v1, v2, ...]'

    The caller is responsible for casting with ::vector in SQL when binding.
    """
    # Use a compact but precise repr to avoid huge payloads; 6 decimal places is plenty
    return "[" + ", ".join(f"{float(v):.6f}" for v in vec) + "]"


def _normalize_project_id(project_id: str | None) -> str:
    if project_id and project_id.strip():
        return project_id.strip()
    return "global"


def _dt_to_iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return str(value)


def _row_to_metric(row: Any) -> Dict[str, Any]:
    mapping = getattr(row, "_mapping", None)
    if mapping is not None:
        token_id = mapping.get("token_id") or mapping.get("tokenId")
        project_id = mapping.get("project_id") or mapping.get("projectId")
        activation = mapping.get("activation_count")
        effectiveness = mapping.get("effectiveness_score")
        last_applied = mapping.get("last_applied_at")
        created = mapping.get("created_at")
        updated = mapping.get("updated_at")
    else:
        token_id = row[0] if len(row) > 0 else None
        project_id = row[1] if len(row) > 1 else None
        activation = row[2] if len(row) > 2 else None
        effectiveness = row[3] if len(row) > 3 else None
        last_applied = row[4] if len(row) > 4 else None
        created = row[5] if len(row) > 5 else None
        updated = row[6] if len(row) > 6 else None

    return {
        "tokenId": token_id,
        "projectId": project_id,
        "activationCount": int(activation) if activation is not None else 0,
        "effectivenessScore": float(effectiveness) if effectiveness is not None else 0.0,
        "lastAppliedAt": _dt_to_iso(last_applied),
        "createdAt": _dt_to_iso(created),
        "updatedAt": _dt_to_iso(updated),
    }


async def add_memory_pg(
    engine: AsyncEngine,
    *,
    mem_id: str,
    project_id: str,
    content: str,
    metadata: Dict[str, Any] | None,
    quarantined: bool,
    embedding: list[float] | None = None,
    group_id: str | None = None,
) -> None:
    """Insert a memory row into Postgres using the provided async engine.

    Optional: embedding (pgvector) and group_id for chunk grouping.
    """
    meta_json = json.dumps(metadata or {})

    # Build column/value lists conditionally to avoid requiring pgvector in all paths
    columns = [
        "id",
        "project_id",
        "content",
        "metadata",
        "quarantined",
    ]
    values = [
        ":id",
        ":project_id",
        ":content",
        "CAST(:metadata AS JSONB)",
        ":quarantined",
    ]
    params: Dict[str, Any] = {
        "id": mem_id,
        "project_id": project_id,
        "content": content,
        "metadata": meta_json,
        "quarantined": quarantined,
    }

    if group_id is not None:
        columns.append("group_id")
        values.append(":group_id")
        params["group_id"] = group_id

    if embedding is not None:
        columns.append("embedding")
        # Bind as text and cast to vector on the server side
        values.append(":embedding::vector")
        params["embedding"] = _to_pgvector_literal(embedding)

    cols = ", ".join(columns)
    vals = ", ".join(values)
    q = text(f"INSERT INTO memory_entries ({cols}) VALUES ({vals})")

    async with engine.begin() as conn:
        await conn.execute(q, params)


async def update_task_status_pg(
    engine: AsyncEngine,
    *,
    task_id: str,
    status: str,
    result: Dict[str, Any] | None,
) -> bool:
    q = text(
        """
        UPDATE tasks
        SET status = :status,
            result = CAST(:result AS JSONB),
            updated_at = NOW()
        WHERE id = :task_id
        """
    )
    async with engine.begin() as conn:
        res = await conn.execute(q, {
            "status": status,
            "result": json.dumps(result or {}),
            "task_id": task_id,
        })
        return bool(res.rowcount and res.rowcount > 0)


async def save_diff_pg(
    engine: AsyncEngine,
    *,
    row_id: str,
    project_id: str,
    file_path: str,
    diff_text: str,
    author: str | None,
) -> None:
    q = text(
        """
        INSERT INTO diffs (id, project_id, file_path, diff, author)
        VALUES (:id, :project_id, :file_path, :diff, :author)
        """
    )
    async with engine.begin() as conn:
        await conn.execute(q, {
            "id": row_id,
            "project_id": project_id,
            "file_path": file_path,
            "diff": diff_text,
            "author": author,
        })


async def list_recent_diffs_pg(
    engine: AsyncEngine,
    *,
    project_id: str | None,
    limit: int,
) -> list[Dict[str, Any]]:
    if project_id and project_id.strip():
        q = text(
            """
            SELECT id, project_id, file_path, author, created_at
            FROM diffs
            WHERE project_id = :project_id
            ORDER BY created_at DESC
            LIMIT :limit
            """
        )
        params = {"project_id": project_id, "limit": limit}
    else:
        q = text(
            """
            SELECT id, project_id, file_path, author, created_at
            FROM diffs
            ORDER BY created_at DESC
            LIMIT :limit
            """
        )
        params = {"limit": limit}
    async with engine.connect() as conn:
        res = await conn.execute(q, params)
        rows = res.fetchall()
    items: list[Dict[str, Any]] = []
    for r in rows:
        created = r[4]
        items.append({
            "id": r[0],
            "projectId": r[1],
            "filePath": r[2],
            "author": r[3],
            "createdAt": created.isoformat() if hasattr(created, "isoformat") else str(created),
        })
    return items


async def watchdog_count_stale_inprogress_pg(
    engine: AsyncEngine,
    *,
    ttl_seconds: int,
    project_id: str | None = None,
) -> int:
    """Count stale in-progress tasks older than ttl_seconds.

    Mirrors the update conditions used by watchdog requeue/fail to aid debugging.
    """
    cond = [
        "status = 'in_progress'",
        "(updated_at IS NULL OR updated_at < NOW() - make_interval(secs => :ttl_seconds))",
    ]
    params: Dict[str, Any] = {"ttl_seconds": int(ttl_seconds)}
    if project_id and project_id.strip():
        cond.append("project_id = :project_id")
        params["project_id"] = project_id

    q = text(
        f"""
        SELECT COUNT(*)
        FROM tasks
        WHERE {' AND '.join(cond)}
        """
    )
    async with engine.connect() as conn:
        res = await conn.execute(q, params)
        row = res.first()
        cnt = int(row[0]) if row and row[0] is not None else 0
    try:
        log_json(
            "info",
            "watchdog.repo.count",
            ttlSeconds=int(ttl_seconds),
            projectId=project_id,
            count=cnt,
        )
    except Exception:
        pass
    return cnt


async def watchdog_list_stale_inprogress_pg(
    engine: AsyncEngine,
    *,
    ttl_seconds: int,
    limit: int,
    project_id: str | None = None,
) -> list[Dict[str, Any]]:
    """List up to limit stale in-progress tasks for preview/debug.

    Returns: [{id, projectId, updatedAt, createdAt, ageSeconds}]
    """
    cond = [
        "status = 'in_progress'",
        "(updated_at IS NULL OR updated_at < NOW() - make_interval(secs => :ttl_seconds))",
    ]
    params: Dict[str, Any] = {"ttl_seconds": int(ttl_seconds), "limit": int(limit)}
    if project_id and project_id.strip():
        cond.append("project_id = :project_id")
        params["project_id"] = project_id

    q = text(
        f"""
        SELECT id,
               project_id,
               updated_at,
               created_at,
               EXTRACT(EPOCH FROM (NOW() - COALESCE(updated_at, created_at))) AS age_seconds
        FROM tasks
        WHERE {' AND '.join(cond)}
        ORDER BY updated_at NULLS FIRST
        LIMIT :limit
        """
    )
    items: list[Dict[str, Any]] = []
    async with engine.connect() as conn:
        res = await conn.execute(q, params)
        for row in res.fetchall():
            up = row[2]
            cr = row[3]
            items.append(
                {
                    "id": row[0],
                    "projectId": row[1],
                    "updatedAt": up.isoformat() if hasattr(up, "isoformat") else (str(up) if up is not None else None),
                    "createdAt": cr.isoformat() if hasattr(cr, "isoformat") else str(cr),
                    "ageSeconds": float(row[4]) if row[4] is not None else None,
                }
            )
    try:
        log_json(
            "info",
            "watchdog.repo.list",
            ttlSeconds=int(ttl_seconds),
            projectId=project_id,
            limit=int(limit),
            count=len(items),
        )
    except Exception:
        pass
    return items


async def semantic_search_memory_pg(
    engine: AsyncEngine,
    *,
    query_embedding: list[float],
    project_id: str | None,
    k: int,
    include_quarantined: bool,
    threshold: float | None = None,
) -> list[Dict[str, Any]]:
    """Vector similarity search using pgvector.

    - Orders by cosine distance (`embedding <=> :qvec`). Lower is better.
    - Filters to rows with non-null embeddings.
    - Optional `threshold` filters by max distance.
    """
    clauses = ["embedding IS NOT NULL"]
    params: Dict[str, Any] = {
        "qvec": _to_pgvector_literal(query_embedding),
        "k": int(k),
    }
    if project_id and project_id.strip():
        clauses.append("project_id = :project_id")
        params["project_id"] = project_id
    if not include_quarantined:
        clauses.append("quarantined = FALSE")
    if threshold is not None:
        clauses.append("(embedding <=> :qvec) <= :threshold")
        params["threshold"] = float(threshold)

    where = " AND ".join(clauses)
    q = text(
        f"""
        SELECT id, project_id, content, metadata::text, quarantined, created_at
        FROM memory_entries
        WHERE {where}
        ORDER BY embedding <=> :qvec
        LIMIT :k
        """
    )
    items: list[Dict[str, Any]] = []
    async with engine.connect() as conn:
        res = await conn.execute(q, params)
        for row in res:
            items.append(
                {
                    "id": row[0],
                    "projectId": row[1],
                    "content": row[2],
                    "metadata": json.loads(row[3]) if row[3] else {},
                    "quarantined": bool(row[4]),
                    "createdAt": row[5].isoformat() if hasattr(row[5], "isoformat") else str(row[5]),
                }
            )
    return items


async def log_error_pg(
    engine: AsyncEngine,
    *,
    row_id: str,
    level: str,
    message: str,
    project_id: str | None,
    context: Dict[str, Any] | None,
) -> None:
    q = text(
        """
        INSERT INTO errors (id, project_id, level, message, context)
        VALUES (:id, :project_id, :level, :message, CAST(:context AS JSONB))
        """
    )
    async with engine.begin() as conn:
        await conn.execute(q, {
            "id": row_id,
            "project_id": project_id,
            "level": level,
            "message": message,
            "context": json.dumps(context or {}),
        })


async def claim_next_task_pg(
    engine: AsyncEngine,
    *,
    project_id: str | None,
) -> Dict[str, Any] | None:
    # Atomically select oldest queued task (optionally by project) and mark it in_progress
    # Using SKIP LOCKED to avoid worker contention
    cond = ["status = 'queued'"]
    params: Dict[str, Any] = {}
    if project_id and project_id.strip():
        cond.append("project_id = :project_id")
        params["project_id"] = project_id
    q = text(
        f"""
        WITH next_task AS (
          SELECT id
          FROM tasks
          WHERE {" AND ".join(cond)}
          ORDER BY created_at ASC
          FOR UPDATE SKIP LOCKED
          LIMIT 1
        )
        UPDATE tasks t
        SET status = 'in_progress', updated_at = NOW()
        FROM next_task nt
        WHERE t.id = nt.id
        RETURNING t.id, t.project_id, t.payload::text, t.created_at
        """
    )
    async with engine.begin() as conn:
        res = await conn.execute(q, params)
        row = res.first()
        if not row:
            return None
        return {
            "id": row[0],
            "projectId": row[1],
            "payload": json.loads(row[2]) if row[2] else {},
            "createdAt": row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3]),
        }


async def get_memory_pg(engine: AsyncEngine, *, mem_id: str) -> Dict[str, Any] | None:
    q = text(
        """
        SELECT id, project_id, content, metadata::text, quarantined, created_at
        FROM memory_entries
        WHERE id = :id
        """
    )
    async with engine.connect() as conn:
        res = await conn.execute(q, {"id": mem_id})
        row = res.first()
        if not row:
            return None
        return {
            "id": row[0],
            "projectId": row[1],
            "content": row[2],
            "metadata": json.loads(row[3]) if row[3] else {},
            "quarantined": bool(row[4]),
            "createdAt": row[5].isoformat() if hasattr(row[5], "isoformat") else str(row[5]),
        }


async def search_memory_pg(
    engine: AsyncEngine,
    *,
    query: str,
    project_id: str | None,
    limit: int,
    include_quarantined: bool,
) -> list[Dict[str, Any]]:
    like = f"%{query}%"
    clauses = ["content ILIKE :like"]
    params: Dict[str, Any] = {"like": like, "limit": int(limit)}
    if project_id and project_id.strip():
        clauses.append("project_id = :project_id")
        params["project_id"] = project_id
    if not include_quarantined:
        clauses.append("quarantined = FALSE")
    where = " AND ".join(clauses)
    q = text(
        f"""
        SELECT id, project_id, content, metadata::text, quarantined, created_at
        FROM memory_entries
        WHERE {where}
        ORDER BY created_at DESC
        LIMIT :limit
        """
    )
    items: list[Dict[str, Any]] = []
    async with engine.connect() as conn:
        res = await conn.execute(q, params)
        for row in res:
            items.append(
                {
                    "id": row[0],
                    "projectId": row[1],
                    "content": row[2],
                    "metadata": json.loads(row[3]) if row[3] else {},
                    "quarantined": bool(row[4]),
                    "createdAt": row[5].isoformat() if hasattr(row[5], "isoformat") else str(row[5]),
                }
            )
    return items


async def watchdog_requeue_stale_inprogress_pg(
    engine: AsyncEngine,
    *,
    ttl_seconds: int,
    limit: int,
    project_id: str | None = None,
) -> int:
    """Requeue stale in-progress tasks older than ttl_seconds.

    Returns number of tasks affected.
    """
    cond = [
        "status = 'in_progress'",
        "(updated_at IS NULL OR updated_at < NOW() - make_interval(secs => :ttl_seconds))",
    ]
    params: Dict[str, Any] = {"ttl_seconds": int(ttl_seconds), "limit": int(limit)}
    if project_id and project_id.strip():
        cond.append("project_id = :project_id")
        params["project_id"] = project_id

    q = text(
        f"""
        WITH stale AS (
            SELECT id
            FROM tasks
            WHERE {' AND '.join(cond)}
            ORDER BY updated_at NULLS FIRST
            LIMIT :limit
        )
        UPDATE tasks t
        SET status = 'queued',
            updated_at = NOW()
        FROM stale s
        WHERE t.id = s.id
        RETURNING t.id
        """
    )
    async with engine.begin() as conn:
        res = await conn.execute(q, params)
        rows = res.fetchall()
        affected = len(rows)
        affected_ids = [r[0] for r in rows]
    try:
        log_json(
            "info",
            "watchdog.repo.requeue",
            ttlSeconds=int(ttl_seconds),
            limit=int(limit),
            projectId=project_id,
            affected=affected,
            ids=affected_ids,
        )
    except Exception:
        pass
    return affected


async def watchdog_fail_stale_inprogress_pg(
    engine: AsyncEngine,
    *,
    ttl_seconds: int,
    limit: int,
    project_id: str | None = None,
    reason: str = "stale_ttl",
) -> int:
    """Fail stale in-progress tasks older than ttl_seconds.

    Returns number of tasks affected.
    """
    cond = [
        "status = 'in_progress'",
        "(updated_at IS NULL OR updated_at < NOW() - make_interval(secs => :ttl_seconds))",
    ]
    params: Dict[str, Any] = {"ttl_seconds": int(ttl_seconds), "limit": int(limit)}
    if project_id and project_id.strip():
        cond.append("project_id = :project_id")
        params["project_id"] = project_id

    payload = {
        "error": "ERR.STALE_TASK",
        "watchdog": {"action": "fail", "reason": reason, "ttlSeconds": int(ttl_seconds)},
    }
    q = text(
        f"""
        WITH stale AS (
            SELECT id
            FROM tasks
            WHERE {' AND '.join(cond)}
            ORDER BY updated_at NULLS FIRST
            LIMIT :limit
        )
        UPDATE tasks t
        SET status = 'failed',
            result = CAST(:result AS JSONB),
            updated_at = NOW()
        FROM stale s
        WHERE t.id = s.id
        RETURNING t.id
        """
    )
    params_with_res = {**params, "result": json.dumps(payload)}
    async with engine.begin() as conn:
        res = await conn.execute(q, params_with_res)
        rows = res.fetchall()
        affected = len(rows)
        affected_ids = [r[0] for r in rows]
    try:
        log_json(
            "info",
            "watchdog.repo.fail",
            ttlSeconds=int(ttl_seconds),
            limit=int(limit),
            projectId=project_id,
            reason=reason,
            affected=affected,
            ids=affected_ids,
        )
    except Exception:
        pass
    return affected


async def enqueue_task_pg(
    engine: AsyncEngine,
    *,
    task_id: str,
    project_id: str,
    payload: Dict[str, Any] | None,
) -> None:
    q = text(
        """
        INSERT INTO tasks (id, project_id, status, payload)
        VALUES (:id, :project_id, 'queued', CAST(:payload AS JSONB))
        """
    )
    async with engine.begin() as conn:
        await conn.execute(
            q,
            {
                "id": task_id,
                "project_id": project_id,
                "payload": json.dumps(payload or {}),
            },
        )


async def record_governance_token_metric_pg(
    engine: AsyncEngine,
    *,
    token_id: str,
    project_id: str | None,
    sample_effectiveness: float | None,
    applied_at: datetime | None = None,
) -> Dict[str, Any] | None:
    token = (token_id or "").strip()
    if not token:
        return None
    project = _normalize_project_id(project_id)
    effectiveness = float(sample_effectiveness) if sample_effectiveness is not None else 0.0
    applied = applied_at or datetime.now(timezone.utc)
    params = {
        "token_id": token,
        "project_id": project,
        "effectiveness_score": effectiveness,
        "last_applied_at": applied,
        "updated_at": applied,
    }
    q = text(
        """
        INSERT INTO governance_token_metrics (
            token_id, project_id, activation_count, effectiveness_score, last_applied_at, updated_at
        )
        VALUES (:token_id, :project_id, 1, :effectiveness_score, :last_applied_at, :updated_at)
        ON CONFLICT (token_id, project_id) DO UPDATE SET
            activation_count = governance_token_metrics.activation_count + 1,
            effectiveness_score = (
                (COALESCE(governance_token_metrics.effectiveness_score, 0) * governance_token_metrics.activation_count)
                + :effectiveness_score
            ) / (governance_token_metrics.activation_count + 1.0),
            last_applied_at = CASE
                WHEN governance_token_metrics.last_applied_at IS NULL THEN :last_applied_at
                WHEN :last_applied_at IS NULL THEN governance_token_metrics.last_applied_at
                WHEN governance_token_metrics.last_applied_at < :last_applied_at THEN :last_applied_at
                ELSE governance_token_metrics.last_applied_at
            END,
            updated_at = :updated_at
        RETURNING token_id, project_id, activation_count, effectiveness_score, last_applied_at, created_at, updated_at
        """
    )
    async with engine.begin() as conn:
        res = await conn.execute(q, params)
        row = res.first()
        if not row:
            return None
        return _row_to_metric(row)


async def fetch_governance_token_metrics_pg(
    engine: AsyncEngine,
    *,
    token_ids: Sequence[str] | None = None,
    project_id: str | None = None,
    min_activation_count: int = 0,
    limit: int | None = None,
) -> list[Dict[str, Any]]:
    clauses: list[str] = []
    params: Dict[str, Any] = {}

    if token_ids:
        filtered = [tid.strip() for tid in token_ids if tid and tid.strip()]
        if filtered:
            placeholders = []
            for idx, tid in enumerate(filtered):
                key = f"token_id_{idx}"
                placeholders.append(f":{key}")
                params[key] = tid
            clauses.append(f"token_id IN ({', '.join(placeholders)})")

    if project_id is not None:
        params["project_id"] = _normalize_project_id(project_id)
        clauses.append("project_id = :project_id")

    if min_activation_count and min_activation_count > 0:
        params["min_activation"] = int(min_activation_count)
        clauses.append("activation_count >= :min_activation")

    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""

    limit_clause = ""
    if limit is not None:
        try:
            limit_val = int(limit)
        except Exception:
            limit_val = None
        if limit_val is not None and limit_val > 0:
            params["limit"] = limit_val
            limit_clause = " LIMIT :limit"

    q = text(
        f"""
        SELECT token_id,
               project_id,
               activation_count,
               effectiveness_score,
               last_applied_at,
               created_at,
               updated_at
        FROM governance_token_metrics{where}
        ORDER BY activation_count DESC, updated_at DESC{limit_clause}
        """
    )

    async with engine.connect() as conn:
        res = await conn.execute(q, params)
        rows = res.fetchall()

    return [_row_to_metric(row) for row in rows]
