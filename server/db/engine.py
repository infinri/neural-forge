import os

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

_engine: AsyncEngine | None = None


def get_database_url() -> str | None:
    return os.getenv("DATABASE_URL") or None


def get_async_engine() -> AsyncEngine | None:
    global _engine
    url = get_database_url()
    if not url:
        return None
    if _engine is None:
        # pool_pre_ping ensures stale connections are detected
        _engine = create_async_engine(
            url,
            pool_pre_ping=True,
            poolclass=NullPool,  # Avoid cross-event-loop reuse in tests/TestClient
            future=True,
        )
    return _engine
