import os
import uuid
import pytest
from sqlalchemy import text

from server.db.engine import get_async_engine
from server.db.repo import (
    enqueue_task_pg,
    watchdog_requeue_stale_inprogress_pg,
    watchdog_fail_stale_inprogress_pg,
)


@pytest.mark.asyncio
async def test_watchdog_requeue_and_fail_pg():
    # Ensure Postgres URL is set; align with existing tests' default
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://forge:forge@127.0.0.1:5432/neural_forge",
    )
    engine = get_async_engine()
    assert engine is not None, "Async engine not initialized; set DATABASE_URL to Postgres"

    tid = f"tw_{uuid.uuid4()}"
    project = "watchdog-test"

    # Seed a queued task
    await enqueue_task_pg(engine, task_id=tid, project_id=project, payload={"n": 1})

    # Make it stale in_progress: 2 minutes old
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                UPDATE tasks
                SET status='in_progress', updated_at = NOW() - INTERVAL '2 minutes'
                WHERE id = :id
                """
            ),
            {"id": tid},
        )

    # Requeue stale in_progress older than 60s
    affected = await watchdog_requeue_stale_inprogress_pg(
        engine,
        ttl_seconds=60,
        limit=10,
        project_id=project,
    )
    assert affected >= 1

    async with engine.connect() as conn:
        st = (
            await conn.execute(
                text("SELECT status FROM tasks WHERE id = :id"), {"id": tid}
            )
        ).scalar_one()
    assert st == "queued"

    # Mark stale again and fail via watchdog
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                UPDATE tasks
                SET status='in_progress', updated_at = NOW() - INTERVAL '2 minutes'
                WHERE id = :id
                """
            ),
            {"id": tid},
        )

    affected2 = await watchdog_fail_stale_inprogress_pg(
        engine,
        ttl_seconds=60,
        limit=10,
        project_id=project,
        reason="test",
    )
    assert affected2 >= 1

    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT status, result::text FROM tasks WHERE id = :id"), {"id": tid}
            )
        ).first()
    assert row is not None
    assert row[0] == "failed"
    assert row[1] is None or ("ERR.STALE_TASK" in row[1])
