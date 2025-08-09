import asyncio
import os
import random
from typing import Any, Optional, Sequence, Tuple

import aiosqlite


def get_db_path() -> str:
    """Return the SQLite DB path from MCP_DB_PATH or default."""
    return os.getenv("MCP_DB_PATH", "data/mcp.db")


async def sqlite_fetch_all(
    sql: str,
    params: Sequence[Any] | Tuple[Any, ...] = (),
    *,
    db_path: Optional[str] = None,
    retries: int = 3,
    base_delay: float = 0.05,
    max_delay: float = 0.5,
    jitter: float = 0.02,
    retry_exceptions: Tuple[type, ...] = (aiosqlite.OperationalError, aiosqlite.Error),
) -> list[tuple]:
    """Execute a read-only query with retries and return all rows.

    - Uses exponential backoff with optional jitter.
    - Intended for simple SELECT queries.
    """
    path = db_path or get_db_path()
    delay = max(0.0, base_delay)
    attempt = 0
    while True:
        try:
            async with aiosqlite.connect(path) as db:
                async with db.execute(sql, tuple(params)) as cur:
                    rows = await cur.fetchall()
                    return rows
        except retry_exceptions:
            if attempt >= retries:
                raise
            # Backoff and retry
            sleep_for = delay + (random.random() * jitter if jitter > 0 else 0)
            await asyncio.sleep(sleep_for)
            delay = min(delay * 2, max_delay)
            attempt += 1
