from typing import Any, Optional, Sequence, Tuple


def get_db_path() -> str:
    """Deprecated: SQLite support removed. Postgres-only."""
    raise RuntimeError("SQLite support removed; use PostgreSQL via DATABASE_URL")


async def sqlite_fetch_all(
    sql: str,
    params: Sequence[Any] | Tuple[Any, ...] = (),
    *,
    db_path: Optional[str] = None,
    retries: int = 3,
    base_delay: float = 0.05,
    max_delay: float = 0.5,
    jitter: float = 0.02,
    retry_exceptions: Tuple[type[BaseException], ...] = (Exception,),
) -> list[tuple[Any, ...]]:
    """Deprecated: SQLite support removed. Postgres-only."""
    raise RuntimeError("SQLite support removed; use PostgreSQL via DATABASE_URL")
