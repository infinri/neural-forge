import json
from typing import Any, Dict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def add_memory_pg(engine: AsyncEngine, *, mem_id: str, project_id: str, content: str, metadata: Dict[str, Any] | None, quarantined: bool) -> None:
    """Insert a memory row into Postgres using the provided async engine."""
    meta_json = json.dumps(metadata or {})
    q = text(
        """
        INSERT INTO memory_entries (id, project_id, content, metadata, quarantined)
        VALUES (:id, :project_id, :content, CAST(:metadata AS JSONB), :quarantined)
        """
    )
    async with engine.begin() as conn:
        await conn.execute(
            q,
            {
                "id": mem_id,
                "project_id": project_id,
                "content": content,
                "metadata": meta_json,
                "quarantined": quarantined,
            },
        )


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
