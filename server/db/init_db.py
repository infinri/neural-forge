#!/usr/bin/env python3
import sqlite3
from pathlib import Path


def apply_schema(conn: sqlite3.Connection, schema_path: Path) -> None:
    sql = schema_path.read_text(encoding="utf-8")
    # executescript allows multiple statements incl. PRAGMA & CREATE
    conn.executescript(sql)
    conn.commit()


def main() -> None:
    raise SystemExit(
        "Deprecated: SQLite initialization has been removed. "
        "Neural Forge is PostgreSQL-only. Run migrations via Docker Compose (recommended):\n"
        "  make db-upgrade-docker\n\n"
        "Or run on host with sync driver (psycopg):\n"
        "  ALEMBIC_DATABASE_URL=postgresql+psycopg://user:pass@127.0.0.1:55432/db alembic upgrade head\n\n"
        "Note: When using Docker Compose Postgres, the host port is 55432.\n"
        "See docs/MCP_SERVER_GUIDE.md for details."
    )


if __name__ == "__main__":
    main()
